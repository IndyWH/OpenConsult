"""The Referral letters section of the review page and the letter's page
(spec 15.12, rulings 1, 2, 4 and 8; the detail The page; R2, R5, R15,
R20, R30; 10.4). Made-up doors, made-up replies; no model's words
asserted."""

import json

from openconsult import words
from openconsult.consult import letter as letter_module
from openconsult.llm.engine import EngineTimeout
from openconsult.web.letters import SCRIPT_WORDS, script_words
from tests.conftest import refusal_on, text_of
from tests.fakes import FakeEngine
from tests.test_review_page import MadeUpWorker, app_on, engine_with, log_in, nemotron_doors, reviewed, slot_text

NOTE = {"reasoning": "made up.",
        "subjective": [{"text": "made up history", "turns": [1]}, {"text": "Patient's expectations: a made-up wish", "turns": [1]}],
        "objective": [{"text": "BP 120/80", "turns": [1]}], "assessment": [{"text": "made up impression", "turns": [0]}],
        "plan": [{"text": "Routine referral to a made-up specialty.", "turns": [1]}]}
# The approved text numbers: 1 Subjective, 2 history, 3 expectations, 4 Objective, 5 BP, 6 Assessment, 7 impression, 8 Plan, 9 referral.
LIST = {"reasoning": "made", "referrals": [
    {"specialty": "A made-up specialty", "title": "Physician", "reason": "a made reason", "urgency": "urgent", "lines": [9], "suggestion": False},
    {"specialty": "Other specialty", "title": "Surgeon", "reason": "another reason", "urgency": "routine", "lines": [2], "suggestion": False}]}
LETTER = {"reasoning": "made", "paragraphs": [
    {"text": "Thank you for seeing this 35-year-old woman with a made-up history. She hoped for a made-up wish.", "note_lines": [2, 3]},
    {"text": "Her BP was 120/80.", "note_lines": [5]}]}
ALLERGY = {"reasoning": "made", "paragraphs": [
    {"text": "Thank you for seeing this 35-year-old woman with a made-up history. She has no known allergies.", "note_lines": [2]},
    {"text": "Her BP was 120/80.", "note_lines": [5]}]}
UNDER = {"reasoning": "made", "paragraphs": [{"text": "Made up. Made up twice. Her BP was 120/80.", "note_lines": [99]}]}


def approved(tmp_path, clock, machine, **script):
    engine = engine_with(**{"note": [NOTE], "referrals": [LIST], "letter": [LETTER], **script})
    app, client, c = reviewed(tmp_path, clock, machine, engine)
    client.post("/consultations/1/note/approve")
    return app, client, engine


def drafted(tmp_path, clock, machine, **script):
    app, client, engine = approved(tmp_path, clock, machine, **script)
    client.get("/consultations/1")
    item = [i for i in app.state.parts.letters.items(1) if i["kind"] == "stated"][0]
    answer = client.post(f"/consultations/1/referrals/{item['id']}/draft")
    assert answer.status_code == 303 and answer.headers["location"] == "/consultations/1/letters/1"
    return app, client, engine, item


def test_R5_ruling_2_the_section_appears_only_after_approve_and_the_list_call_runs_once_at_the_first_opening(tmp_path, clock, machine):
    engine = engine_with(note=[NOTE], referrals=[LIST], letter=[LETTER])
    app, client, c = reviewed(tmp_path, clock, machine, engine)
    p = app.state.parts
    raw = client.get("/consultations/1").text
    assert 'id="letters"' not in raw and engine.calls_for("referrals") == [] and p.letters.list_of(1) is None   # nothing before Approve
    assert client.post("/consultations/1/referrals/named", data={"specialty": "x", "title": "y"}).headers["location"] == "/consultations/1"
    client.post("/consultations/1/note/approve")
    assert engine.calls_for("referrals") == []                                            # Approve itself makes no call
    raw = client.get("/consultations/1").text
    page = text_of(client.get("/consultations/1"))
    assert len(engine.calls_for("referrals")) == 1 and p.letters.list_of(1)["failure"] is None   # once, at the first opening; not again
    assert raw.index('id="letters"') > raw.index('id="note"') and raw.index('id="letters"') < raw.index('id="controls"')
    assert words.LETTERS_HEADING in page
    # The stated item, then the suggestions line, then the demoted item under it, then name a specialty last.
    assert raw.index('id="stated-items"') < raw.index('id="suggestions-line"') < raw.index('id="suggested-items"') < raw.index('id="named-form"')
    assert words.SUGGESTIONS_LINE in page and 'data-kind="stated"' in raw and 'data-kind="suggested"' in raw
    items = p.letters.items(1)
    assert [(i["kind"], i["specialty"]) for i in items] == [("stated", "A made-up specialty"), ("suggested", "Other specialty")]
    assert 'value="Physician"' in raw and 'value="Surgeon"' in raw and "(urgent)" in page and "(routine)" in page
    assert "a made reason" in page and 'aria-label="Line 9 of the note"' in raw
    assert 'id="line-words-1-9" hidden>Routine referral to a made-up specialty.</span>' in raw     # the line's words on the page, hidden
    assert page.count(words.DRAFT_THE_LETTER) == 3 and words.NAME_A_SPECIALTY in page             # two items and name a specialty
    assert words.NO_REFERRALS not in page and words.LIST_FAILED.split(":")[0] not in page
    assert client.get("/static/letters.js").status_code == 200 and "/static/letters.js" in raw
    # Nothing of the section in the print or the copy text (ruling 4).
    assert "#letters" in client.get("/static/print.css").text and words.LETTERS_HEADING not in client.get("/consultations/1/note.txt").text
    # A restart shows the same list from the tables with no call.
    app2, client2 = app_on(tmp_path, clock, machine, nemotron_doors(MadeUpWorker()), engine_with(referrals=[LIST]))
    log_in(client2)
    assert "A made-up specialty" in text_of(client2.get("/consultations/1")) and app2.state.parts.door._engine.calls_for("referrals") == []


def test_R30_a_failed_list_call_is_said_plainly_and_make_the_list_again_is_offered(tmp_path, clock, machine):
    app, client, engine = approved(tmp_path, clock, machine, referrals=[EngineTimeout("no answer"), {"reasoning": "x", "referrals": []}])
    p = app.state.parts
    page = text_of(client.get("/consultations/1"))
    assert words.LIST_FAILED.format(reason="too_slow").split(":")[0] in page and "too_slow" in page and words.LIST_AGAIN in page
    assert p.letters.list_of(1)["failure"].startswith("too_slow") and p.letters.items(1) == []
    assert words.NAME_A_SPECIALTY in page and p.audit.lines()[0].event == "referrals.failed"
    assert len(engine.calls_for("referrals")) == 1 and text_of(client.get("/consultations/1")) and len(engine.calls_for("referrals")) == 1
    assert client.post("/consultations/1/referrals/list").status_code == 303 and len(engine.calls_for("referrals")) == 2
    listed = p.letters.list_of(1)
    assert listed["failure"] is None and len(p.db.query("SELECT * FROM referral_list")) == 1
    page = text_of(client.get("/consultations/1"))
    assert words.NO_REFERRALS in page and words.LIST_AGAIN not in page
    assert slot_text(text_of(client.post("/consultations/1/referrals/list")), "list-again") == words.LIST_STANDS   # a list that stands is never made again


def test_ruling_2_the_title_is_editable_on_the_item_and_the_salutation_follows_it(tmp_path, clock, machine):
    app, client, engine, item = drafted(tmp_path, clock, machine)
    p = app.state.parts
    assert "Dear Consultant Physician," in text_of(client.get("/consultations/1/letters/1"))
    assert refusal_on(text_of(client.post(f"/consultations/1/referrals/{item['id']}/title", data={"title": " "})), f"title-{item['id']}") == words.TITLE_EMPTY
    assert refusal_on(text_of(client.post(f"/consultations/1/referrals/{item['id']}/title", data={"title": "Physician"})), f"title-{item['id']}") == words.TITLE_UNCHANGED
    assert client.post(f"/consultations/1/referrals/{item['id']}/title", data={"title": "ENT Surgeon"}).status_code == 303
    assert p.letters.item(item["id"])["title"] == "ENT Surgeon" and 'value="ENT Surgeon"' in client.get("/consultations/1").text
    assert p.audit.lines()[0].event == "referral.title_changed" and "from Physician to ENT Surgeon" in p.audit.lines()[0].detail
    assert "Dear Consultant ENT Surgeon," in text_of(client.get("/consultations/1/letters/1"))
    assert client.post("/consultations/1/referrals/99/title", data={"title": "x"}).headers["location"] == "/consultations/1"   # no such item


def test_R2_R15_a_letter_is_drafted_edited_approved_audited_and_read_only_and_the_copy_is_the_letter_alone(tmp_path, clock, machine):
    app, client, engine, item = drafted(tmp_path, clock, machine)
    p = app.state.parts
    raw = client.get("/consultations/1/letters/1").text
    page = text_of(client.get("/consultations/1/letters/1"))
    assert words.LETTER_TITLE.format(specialty="A made-up specialty") in page and words.LETTER_DRAFT_LINE in page
    assert "Dear Consultant Physician," in page and "Re: Made-up Patient, born 21 Oct 1990, Female" in page and "Yours faithfully, Dr Example" in page
    assert raw.count('class="paragraph-form"') == 2 and "She hoped for a made-up wish." in page and "Her BP was 120/80." in page
    assert words.LETTER_COUNTS.format(total=3, grounded=3, placeholders=0, dropped=0, allergies=0) in page
    assert words.LETTER_MODEL_LINE.format(model="gemma4:26b-a4b-it-qat", engine="made-up", version="0.0-made-up") in page   # the engine's own name (R20)
    assert 'id="copy-letter"' not in raw and client.get("/consultations/1/letters/1/letter.txt").status_code == 404   # copy after Approve only
    assert words.ITEM_DRAFTED in text_of(client.get("/consultations/1")) and f'id="open-{item["id"]}"' in client.get("/consultations/1").text
    assert text_of(client.get("/consultations/1")).count(words.DRAFT_THE_LETTER) == 2              # the other item and name a specialty
    # A paragraph edit is kept with the words before; an empty one refused on the control.
    assert client.post("/consultations/1/letters/1/paragraphs/1", data={"text": "Her BP was 120/80, which is her usual."}).status_code == 303
    assert [(e["paragraph"], e["text_before"]) for e in p.letters.edits(1)] == [(1, "Her BP was 120/80.")]
    assert p.audit.lines()[0].event == "letter.edited" and refusal_on(text_of(client.post("/consultations/1/letters/1/paragraphs/0", data={"text": " "})), "paragraph-0") == words.PARAGRAPH_EMPTY
    assert client.post("/consultations/1/letters/1/paragraphs/7", data={"text": "x"}).headers["location"] == "/consultations/1/letters/1"
    # Approve: the assembled letter as it stands, audited; read-only after; the copy text is the letter alone (R2).
    assert client.post("/consultations/1/letters/1/approve").status_code == 303
    approval = p.letters.approval(1)
    assert approval["text"] == letter_module.assemble(p.letters.letter(1)["paragraphs"], "Physician", p.consultations.get(1), p.users.get())
    assert approval["text"].startswith("Dear Consultant Physician,\n\nRe: Made-up Patient, born 21 Oct 1990, Female\n\nThank you")
    assert approval["text"].endswith("which is her usual.\n\nYours faithfully,\nDr Example\n")
    assert p.audit.lines()[0].event == "letter.approved" and "letter 1, item" in p.audit.lines()[0].detail
    copy = client.get("/consultations/1/letters/1/letter.txt")
    assert copy.status_code == 200 and copy.text == approval["text"]
    for absent in ("grounded in the note", "Language model", words.SECTION_WORDS["subjective"], "Made-up condition", "sentences"):
        assert absent not in copy.text
    raw = client.get("/consultations/1/letters/1").text
    page = text_of(client.get("/consultations/1/letters/1"))
    assert words.LETTER_APPROVED_LINE.split("{")[0] in page and 'id="copy-letter"' in raw and "paragraph-form" not in raw
    assert slot_text(text_of(client.post("/consultations/1/letters/1/paragraphs/0", data={"text": "x"})), "paragraph-0") == words.LETTER_READ_ONLY
    assert refusal_on(text_of(client.post("/consultations/1/letters/1/approve")), "approve") == words.LETTER_ALREADY_APPROVED
    assert refusal_on(text_of(client.post("/consultations/1/letters/1/refuse")), "refuse") == words.LETTER_ALREADY_APPROVED
    assert refusal_on(text_of(client.post("/consultations/1/letters/1/again")), "again") == words.LETTER_READ_ONLY
    assert len(p.letters.letters(1)) == 1 and len(engine.calls_for("letter")) == 1
    review = text_of(client.get("/consultations/1"))
    assert words.ITEM_APPROVED in review and words.ITEM_DRAFTED not in review
    assert client.get("/consultations/1/note.txt").text.startswith("Subjective\n") and "Dear Consultant" not in client.get("/consultations/1/note.txt").text


def test_ruling_4_a_refused_letter_shows_the_reason_no_body_and_draft_again_and_the_earlier_is_kept(tmp_path, clock, machine):
    app, client, engine, item = drafted(tmp_path, clock, machine, letter=[UNDER, LETTER])
    p = app.state.parts
    raw = client.get("/consultations/1/letters/1").text
    page = text_of(client.get("/consultations/1/letters/1"))
    assert words.LETTER_REFUSED.format(grounded=0, total=3) in page and "paragraph-form" not in raw and "Dear Consultant" not in page
    assert words.LETTER_COUNTS.format(total=3, grounded=0, placeholders=3, dropped=0, allergies=0) in page
    assert refusal_on(text_of(client.post("/consultations/1/letters/1/approve")), "approve") == words.LETTER_NOTHING_TO_APPROVE
    assert client.post("/consultations/1/letters/1/paragraphs/0", data={"text": "x"}).status_code == 303   # no paragraph control on the page
    assert words.ITEM_REFUSED_BY_CHECK in text_of(client.get("/consultations/1")) and p.audit.lines()[0].event == "letter.refused_by_check"
    again = client.post("/consultations/1/letters/1/again")
    assert again.status_code == 303 and again.headers["location"] == "/consultations/1/letters/2"
    assert [(l["n"], l["refused"]) for l in p.letters.letters_of_item(item["id"])] == [(1, 1), (2, 0)]      # the earlier kept
    page = text_of(client.get("/consultations/1/letters/2"))
    assert words.EARLIER_LETTERS.format(count=1) in page and "Dear Consultant Physician," in page
    assert words.ITEM_DRAFTED in text_of(client.get("/consultations/1")) and len(engine.calls_for("letter")) == 2


def test_ruling_8_name_a_specialty_drafts_with_no_list_call(tmp_path, clock, machine):
    app, client, engine = approved(tmp_path, clock, machine, letter=[LETTER, LETTER])
    p = app.state.parts
    client.get("/consultations/1")
    assert len(engine.calls_for("referrals")) == 1
    assert refusal_on(text_of(client.post("/consultations/1/referrals/named", data={"specialty": " ", "title": "x"})), "draft-named") == words.SPECIALTY_EMPTY
    assert refusal_on(text_of(client.post("/consultations/1/referrals/named", data={"specialty": "Cardiology", "title": ""})), "draft-named") == words.TITLE_EMPTY
    answer = client.post("/consultations/1/referrals/named", data={"specialty": " Cardiology ", "title": " Cardiologist "})
    assert answer.status_code == 303 and answer.headers["location"] == "/consultations/1/letters/1"
    named = [i for i in p.letters.items(1) if i["kind"] == "named"]
    assert [(i["specialty"], i["title"], i["note_lines"], i["list_id"]) for i in named] == [("Cardiology", "Cardiologist", [], None)]
    assert len(engine.calls_for("referrals")) == 1 and len(engine.calls_for("letter")) == 1    # no second list call
    assert "SPECIALTY: Cardiology\n" in engine.calls_for("letter")[0].user
    page = text_of(client.get("/consultations/1/letters/1"))
    assert "Dear Consultant Cardiologist," in page and words.LETTER_TITLE.format(specialty="Cardiology") in page
    review = client.get("/consultations/1")
    assert 'id="named-items"' in review.text and words.ITEM_DRAFTED in text_of(review)
    assert [l.event for l in p.audit.lines()[:2]] == ["letter.drafted", "referral.named"]


def test_R30_a_failed_letter_call_is_said_plainly_and_draft_again_is_offered(tmp_path, clock, machine):
    app, client, engine, item = drafted(tmp_path, clock, machine, letter=[EngineTimeout("no answer"), LETTER])
    p = app.state.parts
    page = text_of(client.get("/consultations/1/letters/1"))
    assert words.LETTER_CALL_FAILED.format(reason="too_slow").split(":")[0] in page and "too_slow" in page and "Dear Consultant" not in page
    assert refusal_on(text_of(client.post("/consultations/1/letters/1/approve")), "approve") == words.LETTER_NOTHING_TO_APPROVE
    assert words.ITEM_FAILED in text_of(client.get("/consultations/1")) and p.audit.lines()[0].event == "letter.failed"
    assert len(engine.calls_for("letter")) == 1                                                 # nothing asked a second time by itself
    assert client.post("/consultations/1/letters/1/again").headers["location"] == "/consultations/1/letters/2"
    assert p.letters.letter(2)["failure"] is None and len(engine.calls_for("letter")) == 2


def test_refuse_marks_the_letter_and_draft_again_still_acts(tmp_path, clock, machine):
    app, client, engine, item = drafted(tmp_path, clock, machine, letter=[LETTER, LETTER])
    p = app.state.parts
    assert client.post("/consultations/1/letters/1/refuse").status_code == 303
    assert p.letters.letter(1)["doctor_refused_at"] and p.audit.lines()[0].event == "letter.refused"
    page = text_of(client.get("/consultations/1/letters/1"))
    assert words.LETTER_REFUSED_LINE.split("{")[0] in page and "paragraph-form" not in client.get("/consultations/1/letters/1").text
    assert refusal_on(text_of(client.post("/consultations/1/letters/1/refuse")), "refuse") == words.LETTER_ALREADY_REFUSED
    assert refusal_on(text_of(client.post("/consultations/1/letters/1/approve")), "approve") == words.LETTER_NOTHING_TO_APPROVE
    assert words.ITEM_REFUSED in text_of(client.get("/consultations/1"))
    assert client.post("/consultations/1/letters/1/again").headers["location"] == "/consultations/1/letters/2"
    assert p.letters.letter(2)["doctor_refused_at"] is None and p.letters.approval(1) is None


def test_15_6_every_sentence_the_letters_script_renders_comes_from_the_one_file(tmp_path, clock, machine):
    app, client, engine, item = drafted(tmp_path, clock, machine)
    handed = script_words()
    assert set(handed) == set(SCRIPT_WORDS) == {"COPIED", "COPY_FAILED"}
    for name, sentence in handed.items():
        assert sentence == getattr(words, name)
    raw = client.get("/consultations/1/letters/1").text
    assert json.loads(raw.split('<script id="words" type="application/json">')[1].split("</script>")[0]) == handed
    assert "/static/letters.js" in raw and "/static/use.js" in raw and 'id="letter-page" data-use' in raw


def test_R15_a_letter_of_another_consultation_is_not_found(tmp_path, clock, machine):
    app, client, engine, item = drafted(tmp_path, clock, machine)
    for address in ("/consultations/2/letters/1", "/consultations/1/letters/9"):
        assert client.get(address).status_code == 303
        for control in ("approve", "refuse", "again", "paragraphs/0"):
            assert client.post(f"{address}/{control}", data={"text": "x"}).status_code == 303
    assert client.get("/consultations/1/letters/9/letter.txt").headers["location"] == "/consultations/1"
    assert client.post("/consultations/1/referrals/9/draft").headers["location"] == "/consultations/1"


def test_ruling_16_the_counts_sentence_shows_the_allergy_sentences_dropped(tmp_path, clock, machine):
    """An allergy sentence with no cited allergy line is dropped by the check and never shown; the page's counts say so."""
    app, client, engine, item = drafted(tmp_path, clock, machine, letter=[ALLERGY])
    page = text_of(client.get("/consultations/1/letters/1"))
    assert "no known allergies" not in page and words.LETTER_PLACEHOLDER not in page         # dropped, never replaced
    assert words.LETTER_COUNTS.format(total=3, grounded=2, placeholders=0, dropped=0, allergies=1) in page
    assert app.state.parts.letters.letter(1)["check_detail"]["allergies_dropped"] == 1
