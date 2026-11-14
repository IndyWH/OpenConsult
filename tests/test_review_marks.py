"""The drug-name marks on the review page (spec 15.10 rulings 4, 6, 11, 20
and 21 and the details of step 6c: The marks on the review page, When the
doctor types over; 15.9 ruling 39; R15). A made-up page and made-up
replies; a made-up name stands for the drug the model named, which no
page the doctor works on may show."""

import html
import re

from openconsult import words
from openconsult.llm.engine import EngineTimeout
from tests.conftest import refusal_on, text_of
from tests.test_drug_marks import PAGE, REPLY
from tests.test_review_page import NOTE, engine_with
from tests.test_who_check import reviewed

NAMED = "made-up drug"       # in both drugs the made-up reply names


def page_of(client):
    answer = client.get("/consultations/1")
    return answer.text, text_of(answer)


def part(raw: str, start: str, end: str) -> str:
    return html.unescape(raw.split(start, 1)[1].split(end, 1)[0])


def test_ruling_20_a_mark_shows_in_its_three_places_and_the_line_that_a_name_with_no_mark_is_not_proven_right(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine, engine_with(drug_name=[REPLY]), page=PAGE)
    raw, page = page_of(client)
    # One: in the transcript, the doubted words on their line with the words Check this name; the line plays at a press.
    line_three = part(raw, 'id="line-3"', 'id="line-4"')
    assert line_three.count('<mark class="doubted">met for min</mark>') == 2 and words.CHECK_THIS_NAME in line_three
    assert 'class="play-line cite" data-line="3"' in raw
    assert '<mark class="doubted">take</mark>' in part(raw, 'id="line-1"', 'id="line-2"')              # a mark across two lines: a piece on each
    assert '<mark class="doubted">for</mark>' in part(raw, 'id="line-2"', 'id="line-3"') and "doubted" not in part(raw, 'id="line-4"', 'id="model-line"')
    assert 'name="text" value="I take met for min twice a day and met for min at night.' in raw       # the words stand as they were heard
    # Two: the warnings. The sentence that counts the marks and the line that is always shown head them; one row for each mark.
    warnings = part(raw, 'id="warnings"', 'id="alarms"')
    assert warnings.index(words.DRUG_MARKED.format(count=2)) < warnings.index(words.DRUG_NOT_PROVEN) < warnings.index('<ul class="panel-list">')
    first, second = words.WARN_DRUG_MARK.format(n=1, heard="take for"), words.WARN_DRUG_MARK.format(n=3, heard="met for min")
    assert warnings.index(first) < warnings.index(second) < warnings.index(words.WARN_CONFIDENCE_NOT_MEASURED.split(":")[0])
    assert warnings.count('data-kind="drug_mark"') == 2 and 'class="play-line cite" data-line="3">' + words.PLAY_FROM_LINE in warnings
    # Three: in the note, every entry that draws on a marked line carries the sign, set by the line and not by the word.
    subjective = part(raw, 'id="section-subjective"', 'id="section-objective"')
    assert words.DRUG_SIGN.format(n=3) in subjective and 'class="cite drug-sign no-print" data-line="3"' in subjective
    assert "met for min" not in subjective and "made up history [1]" in subjective                    # the note wrote another word: the sign still shows
    assessment = part(raw, 'id="section-assessment"', 'id="differentials"')
    assert assessment.count(words.DRUG_SIGN.format(n=1)) == 1 and words.DRUG_SIGN.format(n=2) not in page   # one sign, the mark's first line
    assert words.DRUG_SIGN.split("{")[0] not in part(raw, 'id="section-plan"', 'id="controls"')         # an entry that cites no marked line
    # No guess is shown anywhere (ruling 6): not on the page, and so not in its print; not in the copy text.
    assert NAMED not in page and NAMED not in client.get("/consultations/1/note.txt").text
    assert NAMED in [m["meant"] for m in app.state.parts.consultations.drug_marks(1)][1]             # kept in the record
    c.close()


def test_ruling_20_ruling_4_the_sign_is_on_the_page_only_never_in_the_copy_text_or_the_approved_text(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine, engine_with(drug_name=[REPLY]), page=PAGE)
    p = app.state.parts
    sign = words.DRUG_SIGN.split("{")[0]
    copy = client.get("/consultations/1/note.txt").text
    assert sign not in copy and words.CHECK_THIS_NAME not in copy and "made up history" in copy
    raw, _ = page_of(client)
    assert raw.count('class="cite drug-sign no-print"') == 2                                            # the print's style sheet leaves them out
    assert 'id="warnings"' in raw and 'class="pane no-print" id="warnings"' in raw
    # Approve is never blocked by a mark; the approved text holds the note alone; the page then shows the marks that stood at Approve.
    assert client.post("/consultations/1/note/approve").status_code == 303
    approved = p.notes.approval(1)["text"]
    assert sign not in approved and words.CHECK_THIS_NAME not in approved and NAMED not in approved
    raw, page = page_of(client)
    assert '<span class="line-text">I take <mark class="doubted">met for min</mark> twice a day and <mark class="doubted">met for min</mark> at night.' in raw
    assert words.WARN_DRUG_MARK.format(n=3, heard="met for min") in page and words.DRUG_SIGN.format(n=3) in page
    assert words.DRUG_NOT_PROVEN in page and NAMED not in page and NAMED not in client.get("/consultations/1/note.txt").text
    c.close()


def test_ruling_20_the_head_of_the_warnings_for_many_marks_for_one_and_for_none_and_nothing_when_the_call_has_not_run(tmp_path, clock, machine):
    one = {"doubtful": [REPLY["doubtful"][0]]}
    for name, reply, head, rows in (("many", REPLY, words.DRUG_MARKED.format(count=2), 2), ("one", one, words.DRUG_MARKED_ONE, 1),
                                    ("none", {"doubtful": []}, words.DRUG_MARKED_NONE, 0)):
        app, client, c = reviewed(tmp_path / name, clock, machine, engine_with(drug_name=[reply]), page=PAGE)
        raw, page = page_of(client)
        assert page.count(head) == 1 and page.count(words.DRUG_NOT_PROVEN) == 1, name          # the line is shown also when nothing is marked
        others = [s for s in (words.DRUG_MARKED.format(count=2), words.DRUG_MARKED_ONE, words.DRUG_MARKED_NONE) if s != head]
        assert all(s not in page for s in others) and words.DRUG_CHECK_FAILED.split(":")[0] not in page
        assert raw.count('data-kind="drug_mark"') == rows, name
        c.close()
    # A consultation from before 6c has no drug-name call: none of this is shown.
    app, client, c = reviewed(tmp_path / "before", clock, machine, engine_with(drug_name=[REPLY]), page=PAGE)
    p = app.state.parts
    p.db.execute("DELETE FROM drug_mark WHERE consultation_id = 1")
    p.db.execute("DELETE FROM drug_name_call WHERE consultation_id = 1")
    raw, page = page_of(client)
    for sentence in (words.DRUG_NOT_PROVEN, words.DRUG_MARKED_NONE, words.CHECK_THIS_NAME, words.DRUG_SIGN.split("{")[0]):
        assert sentence not in page
    assert 'class="doubted"' not in raw and 'data-kind="drug_mark"' not in raw
    c.close()


def count_on_approve(page: str) -> str:
    return page.split('id="warning-count"')[1].split("</a>")[0].split(">")[-1].strip()


def test_rulings_11_20_R15_approve_is_never_blocked_and_its_count_holds_each_standing_mark_and_not_the_sentences_at_the_head(tmp_path, clock, machine):
    # The count with no mark is the page's own warnings; the sentences at the head add nothing to it.
    app, client, c = reviewed(tmp_path / "none", clock, machine, engine_with(drug_name=[{"doubtful": []}]), page=PAGE)
    raw, _ = page_of(client)
    base = raw.count('<li class="warning"')
    assert count_on_approve(raw) == (words.WARNING_ONE if base == 1 else words.WARNINGS_COUNT.format(count=base))     # the head is not counted
    c.close()
    app, client, c = reviewed(tmp_path / "marks", clock, machine, engine_with(drug_name=[REPLY]), page=PAGE)
    raw, _ = page_of(client)
    assert raw.count('<li class="warning"') == base + 2 and count_on_approve(raw) == words.WARNINGS_COUNT.format(count=base + 2)
    assert 'id="approve" aria-describedby="approve-refusal" disabled' not in raw                      # a mark never blocks Approve
    assert client.post("/consultations/1/note/approve").status_code == 303 and app.state.parts.notes.approval(1) is not None
    c.close()


def test_ruling_20_R30_a_failed_drug_name_call_is_said_plainly_counts_as_one_warning_and_no_control_asks_again(tmp_path, clock, machine):
    engine = engine_with(drug_name=[EngineTimeout("no answer")])
    app, client, c = reviewed(tmp_path, clock, machine, engine, page=PAGE)
    p = app.state.parts
    raw, page = page_of(client)
    sentence = words.DRUG_CHECK_FAILED.format(reason=p.consultations.drug_call(1)["reason"])
    assert page.count(sentence) == 1 and sentence.endswith(". No drug name is marked.") and raw.count('data-kind="drug_names_failed"') == 1
    assert count_on_approve(raw) == words.WARNINGS_COUNT.format(count=raw.count('<li class="warning"'))
    for shown in (words.DRUG_NOT_PROVEN, words.DRUG_MARKED_NONE, words.CHECK_THIS_NAME):
        assert shown not in page                                                             # the call did not run: nothing says it found none
    assert not [action for action in re.findall(r'action="([^"]+)"', raw) if "drug" in action]      # no control asks again
    assert len(engine.calls_for("drug_name")) == 1
    client.get("/consultations/1")
    assert len(engine.calls_for("drug_name")) == 1 and client.post("/consultations/1/note/approve").status_code == 303     # nothing is asked again; Approve acts
    c.close()


def test_rulings_11_20_a_mark_typed_over_goes_from_its_three_places_stays_in_the_record_and_draft_again_does_not_ask_the_model_again(tmp_path, clock, machine):
    engine = engine_with(drug_name=[REPLY], note=[NOTE, NOTE])
    app, client, c = reviewed(tmp_path, clock, machine, engine, page=PAGE)
    p = app.state.parts
    # The doctor hears the word and types the name over both places on line 3.
    typed = "I take a made-up name twice a day and a made-up name at night."
    assert client.post("/consultations/1/lines/3", data={"label": "patient", "text": typed}).status_code == 303
    raw, page = page_of(client)
    assert "met for min" not in part(raw, 'id="line-3"', 'id="line-4"') and words.WARN_DRUG_MARK.format(n=3, heard="met for min") not in page
    assert words.DRUG_SIGN.format(n=3) not in page and words.DRUG_MARKED_ONE in page                 # one mark stands: the one across lines 1 and 2
    assert words.WARN_DRUG_MARK.format(n=1, heard="take for") in page and words.DRUG_SIGN.format(n=1) in page
    record = p.consultations.drug_marks(1, every=True)
    assert [(m["heard"], m["cleared_at"] is not None) for m in record] == [("take for", False), ("met for min", True)]
    assert record[1]["meant"] == "a made-up drug"
    # The edit offers Draft the note again, as any edit does; the draft is made from the corrected words, and the call is not made again.
    assert 'id="draft" aria-describedby="draft-refusal" disabled' not in raw and words.DRAFT_AGAIN in page
    assert client.post("/consultations/1/note/draft").status_code == 303
    assert len(engine.calls_for("drug_name")) == 1 and len(engine.calls_for("note")) == 2 and "a made-up name" in engine.calls_for("note")[1].user
    raw, page = page_of(client)
    assert words.DRUG_MARKED_ONE in page and words.DRUG_SIGN.format(n=1) in page                    # the marks belong to the transcript
    # An edit that leaves the doubted words standing keeps the mark where the words now are.
    assert client.post("/consultations/1/lines/1", data={"label": "doctor", "text": "So what do you take"}).status_code == 303
    assert p.consultations.drug_marks(1)[0]["places"][0] == {"line": 1, "first": 15, "last": 19}
    assert refusal_on(text_of(client.post("/consultations/1/lines/1", data={"label": "doctor", "text": ""})), "save-line-1") == words.ENTRY_EMPTY
    c.close()
