"""The check of who spoke on the review page (spec 15.9 rulings 4, 17 and
37; 15.10 rulings 7, 12, 14, 18, 19 and 24 and the details of step 6c:
The who-spoke check on the review page, Undo, A page in parts; R2, R15,
R30; V1_LESSONS 1.12). Made-up doors and made-up replies: only what code
does with a reply's numbers and labels is asserted, never what a model
would say."""

import threading

from openconsult import words
from openconsult.app import build_app
from openconsult.consult import labels, who_check
from openconsult.consult.who_check import WhoChecks
from openconsult.llm.engine import EngineTimeout
from openconsult.prompts import loader
from openconsult.settings import store
from tests.conftest import PORT, browser, log_in, refusal_on, text_of
from tests.fakes import FakeEngine, MadeUpWorker
from tests.test_live import Room, live_seg
from tests.test_review_page import engine_with, nemotron_doors, run_through, slot_text

# Four lines, 73 words: S1 is the doctor by the answer, S2 the patient, and one line has no speaker from the choice.
PAGE = [live_seg(1, 0.0, 0.5, "What brings you in today?", "S1"), live_seg(2, 0.6, 1.2, "A pain in my chest. " + "word " * 60, "S2"),
        live_seg(3, 1.3, 1.5, "Yes.", None), live_seg(4, 1.6, 2.0, "Tell me more.", "S1")]
AFTER_ANSWER = [("doctor", 0, 0), ("patient", 0, 0), ("unsure", 0, 1), ("doctor", 0, 0)]


def said(*labels_given):
    return {"lines": [{"line": n, "label": label} for n, label in enumerate(labels_given, start=1)]}


def reviewed(tmp_path, clock, machine, engine, page=PAGE):
    return run_through(tmp_path, clock, machine, nemotron_doors(MadeUpWorker(live=[page] + [[]] * 7)), engine)


def press(app, client, expect=303):
    answer = client.post("/consultations/1/who-check")
    assert answer.status_code == expect
    app.state.parts.who_checks.wait(1, 20)
    return answer


def lines_of(p):
    return [(x["label"], x["changed_by_check"], x["unsure"]) for x in p.consultations.transcript_lines(1)]


def test_ruling_19_the_control_is_offered_with_its_line_while_the_transcript_can_change_and_never_after_approve(tmp_path, clock, machine):
    engine = engine_with(label_check=[said("doctor", "patient", "patient", "doctor")])
    app, client, c = reviewed(tmp_path, clock, machine, engine)
    p = app.state.parts
    raw = client.get("/consultations/1").text
    page = text_of(client.get("/consultations/1"))
    assert 'id="check-who" aria-describedby="check-who-refusal">' + words.CHECK_WHO_SPOKE in raw           # offered, and it can act
    assert words.CHECK_WHO_SPOKE_LINE in page and raw.find('id="swap"') < raw.find('id="check-who"') < raw.find('id="final-transcript"')
    assert words.CHECK_ALREADY_RAN not in page and 'id="undo-all"' not in raw and 'id="check-who-outcome"' not in raw
    assert lines_of(p) == AFTER_ANSWER and engine.calls_for("label_check") == []                     # nothing ran by itself (15.9 ruling 37)
    # After Approve the transcript is read-only: the control is not there, and a press anyway changes nothing and says why.
    assert client.post("/consultations/1/note/approve").status_code == 303
    raw = client.get("/consultations/1").text
    assert 'id="check-who"' not in raw and words.CHECK_WHO_SPOKE_LINE not in text_of(client.get("/consultations/1"))
    refused = client.post("/consultations/1/who-check")
    assert refused.status_code == 400 and slot_text(text_of(refused), "check-who") == words.NOTE_READ_ONLY
    assert p.consultations.check_runs(1) == [] and engine.calls_for("label_check") == [] and lines_of(p) == AFTER_ANSWER
    # A transcript with no numbered line has no control to offer.
    assert not who_check.page_state(p.consultations, 1, False, False)["offered"]
    c.close()


class HeldEngine(FakeEngine):
    """Holds every call of the check until the test lets it go."""

    def __init__(self, script):
        super().__init__(script)
        self.entered, self.release, self.asked = threading.Event(), threading.Event(), 0

    def chat(self, call):
        if call.job == "label_check":
            self.asked += 1
            self.entered.set()
            assert self.release.wait(20)
        return super().chat(call)


def test_ruling_19_ruling_12_R15_while_a_run_lasts_the_page_says_so_has_no_edit_field_and_every_control_that_writes_changes_nothing(tmp_path, clock, machine):
    from tests.test_review_page import NOTE
    engine = HeldEngine({"note": [NOTE], "label_check": [said("patient", "doctor", "unsure", "patient")]})
    app, client, c = reviewed(tmp_path, clock, machine, engine)
    p = app.state.parts
    entry = p.notes.entries(p.notes.current_draft(1)["id"])[0]
    assert client.post("/consultations/1/who-check").status_code == 303 and engine.entered.wait(20)
    raw = client.get("/consultations/1").text
    page = text_of(client.get("/consultations/1"))
    assert 'id="check-who-running"' in raw and words.CHECK_RUNNING in page and 'class="spinner"' in raw
    assert 'http-equiv="refresh" content="1;' in raw                                           # the page waits, as the stopping page does
    for field in ('class="line-form"', 'class="entry-form', 'id="swap"', 'id="check-who"', 'id="undo-all"'):
        assert field not in raw                                                                # no edit field: no unsaved edit to lose (ruling 12)
    assert 'id="approve" aria-describedby="approve-refusal" disabled' in raw and 'id="draft" aria-describedby="draft-refusal" disabled' in raw
    # A second press, and every control that writes, changes nothing and answers with the running sentence beside it.
    for path, control, absent in (("who-check", "check-who", True), ("note/approve", "approve", False), ("note/refuse", "refuse", False),
                                  ("note/draft", "draft", False), ("lines/swap", "swap", True), ("lines/1", "save-line-1", True),
                                  ("lines/1/undo", "undo-1", True), (f"entries/{entry['id']}", f"entry-{entry['id']}", True),
                                  ("who-check/undo-all", "undo-all", True), ("delete", "delete", False)):
        answer = client.post(f"/consultations/1/{path}", data={"label": "patient", "text": "other words", "confirm": "yes"})
        found = slot_text(text_of(answer), control) if absent else refusal_on(text_of(answer), control)
        assert answer.status_code == 400 and found == words.CHECK_RUNNING, path
    assert [r["outcome"] for r in p.consultations.check_runs(1)] == ["running"] and engine.asked == 1
    assert lines_of(p) == AFTER_ANSWER and p.notes.approval(1) is None and len(p.notes.drafts(1)) == 1
    assert p.consultations.transcript_edits(1) == [] and p.consultations.get(1) is not None
    # Let go: the run ends, the page stops waiting, and the edit fields are back.
    engine.release.set()
    p.who_checks.wait(1, 20)
    raw = client.get("/consultations/1").text
    assert 'id="check-who-running"' not in raw and 'http-equiv="refresh"' not in raw and 'class="line-form"' in raw
    assert [r["outcome"] for r in p.consultations.check_runs(1)] == ["answered"] and lines_of(p)[0] == ("patient", 1, 0)
    c.close()


def test_rulings_7_14_19_a_changed_label_is_marked_an_unsure_line_is_shown_unsure_and_a_line_with_no_first_reading_stays_unsure(tmp_path, clock, machine):
    # Moved from Stop (15.9 ruling 37). The reply: line 1 the other speaker, line 2 as it stands, line 3 (no speaker) named, line 4 unsure.
    engine = engine_with(label_check=[said("patient", "patient", "patient", "unsure")])
    app, client, c = reviewed(tmp_path, clock, machine, engine)
    p = app.state.parts
    before = p.consultations.transcript_lines(1)
    warnings_before = client.get("/consultations/1").text.count('data-kind="no_speaker"')
    press(app, client)
    # The call: the numbered lines with no labels, in the words of the frame; the approved prompt; nothing of the choice's speakers.
    call = engine.calls_for("label_check")[0]
    assert call.user == labels.lines_text([{"n": x["n"], "text": x["text"].strip()} for x in before])
    assert call.system == loader.prompt("label_check") and "S1" not in call.user and "S2" not in call.user
    assert p.consultations.model_calls(1)[-1]["job"] == "label_check"
    assert lines_of(p) == [
        ("patient", 1, 0),      # the check differs from the answer: changed and marked (ruling 7)
        ("patient", 0, 0),      # the answer and the check agree: the label stands
        ("patient", 0, 1),      # no first reading: the check's label, still shown unsure, not marked (ruling 14)
        ("doctor", 0, 1)]       # the check said unsure: shown unsure, the label as it stood
    assert [x["text"] for x in p.consultations.transcript_lines(1)] == [x["text"] for x in before]       # not one word differs
    run = p.consultations.check_runs(1)[0]
    assert (run["outcome"], run["parts"], run["joined_lines"], run["changed"], run["no_first_reading"], run["at_stop"]) == ("answered", 1, 4, 1, 1, 0)
    assert (run["named_twice"], run["dropped"]) == (0, 0) and run["call_ids"] == [p.consultations.model_calls(1)[-1]["id"]]
    assert [(ch["line_n"], ch["label_before"], ch["label_after"]) for ch in p.consultations.check_changes(run["id"])] == [(1, "doctor", "patient")]
    assert [(e["kind"], e["after"]) for e in p.consultations.transcript_edits(1)] == [("check", "1")]
    raw = client.get("/consultations/1").text
    page = text_of(client.get("/consultations/1"))
    assert words.CHECK_CHANGED_ONE in page and words.WARN_LABEL_CHANGED.format(n=1, label="Patient") in page
    assert 'id="undo-1"' in raw and 'id="undo-3"' not in raw and 'id="undo-all"' in raw
    assert raw.count('data-kind="no_speaker"') == warnings_before == 1 and words.WARN_NO_SPEAKER.format(n=3) in page   # the gate's warnings are those of Stop
    events = {line.event: line.detail for line in p.audit.lines()}
    assert events["speakers.check_asked"] == "consultation 1: 4 lines, whole"
    assert events["speakers.check_ended"] == "consultation 1: answered, 1 lines changed"
    c.close()


JOINED_PAGE = [live_seg(1, 0.0, 0.4, "What brings you in", "S1"), live_seg(2, 0.5, 0.6, "today?", "S1"),
               live_seg(3, 0.7, 1.2, "A pain in my chest. " + "word " * 60, "S2"), live_seg(4, 1.3, 1.5, "Yes.", None),
               live_seg(5, 1.6, 2.0, "Tell me more.", "S1")]


def test_6c_15_10_ruling_24_a_joined_lines_label_goes_to_every_line_it_holds_and_a_line_named_twice_with_two_labels_is_shown_unsure(tmp_path, clock, machine):
    # The details, The lines a model reads: two neighbours of one speaker join; the model reads four lines, the page has five.
    engine = engine_with(label_check=[said("patient", "patient", "unsure", "doctor")])
    app, client, c = reviewed(tmp_path / "joined", clock, machine, engine, page=JOINED_PAGE)
    p = app.state.parts
    press(app, client)
    assert engine.calls_for("label_check")[0].user.split("\n")[1] == "[1] What brings you in today?"
    assert lines_of(p) == [("patient", 1, 0), ("patient", 1, 0), ("patient", 0, 0), ("unsure", 0, 1), ("doctor", 0, 0)]
    assert p.consultations.check_runs(1)[0]["joined_lines"] == 4 and words.CHECK_CHANGED.format(count=2) in text_of(client.get("/consultations/1"))
    c.close()
    # Ruling 24: line 1 named as patient and then as doctor holds both speakers, so it is unsure; 9 is not a line of the page.
    reply = {"lines": [{"line": 1, "label": "patient"}, {"line": 1, "label": "doctor"}, {"line": 2, "label": "patient"},
                       {"line": 3, "label": "unsure"}, {"line": 4, "label": "doctor"}, {"line": 9, "label": "doctor"}]}
    engine = engine_with(label_check=[reply])
    app, client, c = reviewed(tmp_path / "twice", clock, machine, engine)
    p = app.state.parts
    before = [x["text"] for x in p.consultations.transcript_lines(1)]
    press(app, client)
    assert lines_of(p) == [("doctor", 0, 1), ("patient", 0, 0), ("unsure", 0, 1), ("doctor", 0, 0)]     # line 1: its label as it stood, shown unsure, not marked
    run = p.consultations.check_runs(1)[0]
    assert (run["outcome"], run["changed"], run["named_twice"], run["dropped"]) == ("answered", 0, 1, 1)   # the two counts kept with the run
    assert p.consultations.check_changes(run["id"]) == [] and p.consultations.transcript_edits(1) == []  # no change row, no edit of kind check
    raw = client.get("/consultations/1").text
    assert words.CHECK_CHANGED_NONE in text_of(client.get("/consultations/1")) and 'id="undo-1"' not in raw and 'id="undo-all"' not in raw
    assert [x["text"] for x in p.consultations.transcript_lines(1)] == before                           # a reply taken by this rule changes no word
    c.close()


def test_ruling_19_a_label_set_on_one_line_is_never_changed_by_the_check_and_a_swap_is_not_such_a_setting(tmp_path, clock, machine):
    engine = engine_with(label_check=[said("doctor", "doctor", "unsure", "doctor")])
    app, client, c = reviewed(tmp_path, clock, machine, engine)
    p = app.state.parts
    words_two = p.consultations.line(1, 2)["text"]
    assert client.post("/consultations/1/lines/2", data={"label": "doctor", "text": words_two}).status_code == 303   # set on one line
    assert client.post("/consultations/1/lines/swap").status_code == 303                                        # every line set at once
    assert [x[0] for x in lines_of(p)] == ["patient", "patient", "unsure", "patient"]
    press(app, client)
    assert lines_of(p) == [("doctor", 1, 0),       # Swap is not a setting of one line: changed and marked
                           ("patient", 0, 0),      # set by the doctor on this line: never changed, never marked
                           ("unsure", 0, 1),
                           ("doctor", 1, 0)]
    assert [ch["line_n"] for ch in p.consultations.check_changes(p.consultations.check_runs(1)[0]["id"])] == [1, 4]
    # A label the doctor then sets by hand on a marked line is the doctor's: Undo all puts back the other line only.
    assert client.post("/consultations/1/lines/4", data={"label": "unsure", "text": p.consultations.line(1, 4)["text"]}).status_code == 303
    assert client.post("/consultations/1/who-check/undo-all").status_code == 303
    assert lines_of(p) == [("patient", 0, 0), ("patient", 0, 0), ("unsure", 0, 1), ("unsure", 0, 1)]
    assert p.audit.lines()[0].detail == "consultation 1: 1 lines put back"
    c.close()


def test_ruling_19_the_check_is_offered_once_and_again_only_after_a_run_that_failed_or_was_refused(tmp_path, clock, machine):
    # Moved from Stop: a refused or failed check changes nothing. Now it is said at the control, of the latest run only.
    missing = {"lines": said("patient", "doctor", "unsure", "patient")["lines"][:3]}
    engine = engine_with(label_check=[EngineTimeout("no answer"), missing, said("patient", "patient", "unsure", "doctor")])
    app, client, c = reviewed(tmp_path, clock, machine, engine)
    p = app.state.parts
    count_before = text_of(client.get("/consultations/1")).split('id="warning-count"')[1][:60]
    press(app, client)
    failed = p.consultations.check_runs(1)[0]
    assert failed["outcome"] == "failed" and failed["reason"] and lines_of(p) == AFTER_ANSWER
    raw, page = client.get("/consultations/1").text, text_of(client.get("/consultations/1"))
    assert words.WARN_LABEL_CHECK_FAILED.format(reason=failed["reason"]) in page and 'id="check-who-outcome"' in raw
    assert 'id="check-who" aria-describedby="check-who-refusal">' in raw and words.CHECK_ALREADY_RAN not in page       # offered again
    assert page.split('id="warning-count"')[1][:60] == count_before                    # said at the control, not counted on Approve
    press(app, client)
    refused = p.consultations.check_runs(1)[1]
    assert (refused["outcome"], refused["reason"]) == ("refused", "missing 4") and lines_of(p) == AFTER_ANSWER
    page = text_of(client.get("/consultations/1"))
    assert words.WARN_LABEL_CHECK_REFUSED.format(reason="missing 4") in page
    assert words.WARN_LABEL_CHECK_FAILED.split(":")[0] not in page                     # the latest run only
    assert p.consultations.transcript_edits(1) == [] and len(engine.calls_for("label_check")) == 2        # nothing asked again by itself (10.4)
    press(app, client)
    assert p.consultations.check_runs(1)[2]["outcome"] == "answered" and lines_of(p)[0] == ("patient", 1, 0)
    raw, page = client.get("/consultations/1").text, text_of(client.get("/consultations/1"))
    assert 'id="check-who" aria-describedby="check-who-refusal" disabled' in raw and words.CHECK_ALREADY_RAN in page
    assert words.WARN_LABEL_CHECK_REFUSED.split(":")[0] not in page and words.CHECK_WHO_SPOKE_LINE not in page
    again = press(app, client, expect=400)
    assert refusal_on(text_of(again), "check-who") == words.CHECK_ALREADY_RAN
    assert len(p.consultations.check_runs(1)) == 3 and len(engine.calls_for("label_check")) == 3
    c.close()


def test_6c_ruling_19_undo_puts_back_the_label_before_also_after_a_swap_and_undo_all_puts_back_every_line_still_marked(tmp_path, clock, machine):
    engine = engine_with(label_check=[said("patient", "doctor", "unsure", "patient")])
    app, client, c = reviewed(tmp_path, clock, machine, engine)
    p = app.state.parts
    press(app, client)
    assert lines_of(p) == [("patient", 1, 0), ("doctor", 1, 0), ("unsure", 0, 1), ("patient", 1, 0)]
    page = text_of(client.get("/consultations/1"))
    assert words.CHECK_CHANGED.format(count=3) in page and words.CHECK_UNDO_ALL in page             # the count for many lines
    # A Swap after the check: the labels as they stand are exchanged, and the stored labels before with them.
    assert client.post("/consultations/1/lines/swap").status_code == 303
    assert [x[0] for x in lines_of(p)] == ["doctor", "patient", "unsure", "doctor"]
    # Undo on line 1 puts back the label before, as swapped: patient. The answer's label was doctor.
    assert client.post("/consultations/1/lines/1/undo").status_code == 303
    line = p.consultations.line(1, 1)
    assert (line["label"], line["changed_by_check"], line["set_by_doctor"]) == ("patient", 0, 1)
    assert p.audit.lines()[0].event == "label.undone" and p.audit.lines()[0].detail == "consultation 1: line 1 back to patient"
    assert slot_text(text_of(client.post("/consultations/1/lines/1/undo")), "undo-1") == words.NOT_CHANGED_BY_CHECK       # once
    assert words.CHECK_CHANGED.format(count=2) in text_of(client.get("/consultations/1"))            # the lines that are marked
    assert client.post("/consultations/1/lines/2/undo").status_code == 303
    page = text_of(client.get("/consultations/1"))
    assert words.CHECK_CHANGED_ONE in page and words.CHECK_UNDO_ALL in page                          # the count for one line
    # Undo all: one press, every line still marked; the control then goes, and no sentence says a count.
    assert client.post("/consultations/1/who-check/undo-all").status_code == 303
    assert lines_of(p) == [("patient", 0, 0), ("doctor", 0, 0), ("unsure", 0, 1), ("patient", 0, 0)]
    assert p.audit.lines()[0].event == "speakers.check_undone_all" and p.audit.lines()[0].detail == "consultation 1: 1 lines put back"
    raw, page = client.get("/consultations/1").text, text_of(client.get("/consultations/1"))
    assert 'id="undo-all"' not in raw and words.CHECK_ALREADY_RAN in page
    for sentence in (words.CHECK_CHANGED_NONE, words.CHECK_CHANGED_ONE, words.CHECK_CHANGED.split("{")[0]):
        assert sentence not in page
    assert client.post("/consultations/1/who-check/undo-all").status_code == 303                     # no such control: nothing happens
    assert [e["kind"] for e in p.consultations.transcript_edits(1)] == ["check", "swap", "undo", "undo", "undo"]
    c.close()


def long_room(tmp_path, clock, script):
    """A consultation of 161 lines, none of which joins: one more than goes as one call."""
    r = Room(tmp_path, clock, engine=FakeEngine({"label_check": script}))
    r.rows.add_transcript_lines(r.consultation.id, [
        {"n": n, "start_s": n * 2.0, "end_s": n * 2.0 + 1, "text": f"Made up line {n}.", "raw_speaker": "S1" if n % 2 else "S2",
         "label": "doctor" if n % 2 else "patient"} for n in range(1, 162)])
    return r, WhoChecks(r.llm, r.rows, r.audit)


def test_6c_a_page_over_160_joined_lines_is_asked_in_parts_one_after_another_and_a_part_that_fails_or_is_refused_takes_no_label(tmp_path, clock):
    # The details, A page in parts: 161 lines go as 81 and 80 new lines, the second part beginning with the last 10 of the first.
    first, second = said(*["patient"] * 81), said(*["doctor"] * 90)
    r, checks = long_room(tmp_path / "taken", clock, [first, second])
    try:
        cid = r.consultation.id
        assert checks.start(cid)
        checks.wait(cid, 20)
        one, two = r.engine.calls_for("label_check")
        assert one.user.split("\n")[1] == "[1] Made up line 1." and one.user.split("\n")[-1] == "[81] Made up line 81."
        assert two.user.split("\n")[1] == "[1] Made up line 72." and two.user.split("\n")[-1] == "[90] Made up line 161."
        found = {x["n"]: (x["label"], x["changed_by_check"]) for x in r.rows.transcript_lines(cid)}
        assert all(found[n] == ("patient", n % 2) for n in range(1, 82))          # the carried lines 72 to 81 keep the first part's label
        assert all(found[n] == ("doctor", 1 - n % 2) for n in range(82, 162))
        run = r.rows.check_runs(cid)[0]
        assert (run["outcome"], run["parts"], run["joined_lines"], len(run["call_ids"]), run["changed"]) == ("answered", 2, 161, 2, 81)
        assert [line.detail for line in r.audit.lines() if line.event == "speakers.check_asked"] == [f"consultation {cid}: 161 lines, in 2 parts"]
    finally:
        r.close()
    # All or nothing: the first part gets no answer, so no later part is asked, no label is taken, and the control is offered again.
    r, checks = long_room(tmp_path / "failed", clock, [EngineTimeout("no answer"), second])
    try:
        cid = r.consultation.id
        before = [(x["label"], x["changed_by_check"]) for x in r.rows.transcript_lines(cid)]
        checks.start(cid)
        checks.wait(cid, 20)
        assert len(r.engine.calls_for("label_check")) == 1 and r.rows.check_runs(cid)[0]["outcome"] == "failed"
        assert [(x["label"], x["changed_by_check"]) for x in r.rows.transcript_lines(cid)] == before
        assert who_check.page_state(r.rows, cid, False, True)["offered"]
    finally:
        r.close()
    # The second part's reply misses its last line: refused, and no label is taken from the first part either.
    r, checks = long_room(tmp_path / "refused", clock, [first, {"lines": second["lines"][:-1]}])
    try:
        cid = r.consultation.id
        before = [(x["label"], x["changed_by_check"]) for x in r.rows.transcript_lines(cid)]
        checks.start(cid)
        checks.wait(cid, 20)
        run = r.rows.check_runs(cid)[0]
        assert (run["outcome"], run["reason"], len(run["call_ids"])) == ("refused", "part 2 of 2: missing 90", 2)
        assert [(x["label"], x["changed_by_check"]) for x in r.rows.transcript_lines(cid)] == before and r.rows.transcript_edits(cid) == []
        assert who_check.page_state(r.rows, cid, False, True)["offered"]
    finally:
        r.close()


def test_15_10_ruling_24_the_apps_run_gives_back_the_two_counts_with_a_reply_taken_and_with_a_reply_refused(tmp_path, clock):
    four = said("doctor", "patient", "patient", "unsure")["lines"]
    twice_and_off = {"lines": four + [{"line": 2, "label": "doctor"}, {"line": 9, "label": "doctor"}]}
    refused = {"lines": four[:3] + [{"line": 3, "label": "doctor"}, {"line": 0, "label": "doctor"}, {"line": 7, "label": "doctor"}]}
    r = Room(tmp_path, clock, engine=FakeEngine({"label_check": [twice_and_off, refused]}))
    try:
        rows = [{"n": n, "text": text, "start_s": n * 2.0, "end_s": n * 2.0 + 1, "raw_speaker": "S1"}
                for n, text in enumerate(["Made up one.", "Made up two.", "Made up three.", "Made up four."], start=1)]
        found, outcome = labels.run(r.consultation.llm, rows, r.consultation.id)
        assert found == {1: "doctor", 2: "unsure", 3: "patient", 4: "unsure"}
        assert (outcome["outcome"], outcome["named_twice"], outcome["dropped"], outcome["parts"], len(outcome["call_ids"])) == ("ok", 1, 1, 1, 1)
        found, outcome = labels.run(r.consultation.llm, rows, r.consultation.id)
        assert found is None and (outcome["outcome"], outcome["detail"], outcome["named_twice"], outcome["dropped"]) == ("refused", "missing 4", 1, 2)
        assert [row["text"] for row in rows] == ["Made up one.", "Made up two.", "Made up three.", "Made up four."]
    finally:
        r.close()


def test_1_12_R30_a_run_left_running_at_a_restart_is_ended_as_failed_with_no_label_changed_and_the_control_is_offered_again(tmp_path, clock, machine):
    engine = engine_with()
    app, client, c = reviewed(tmp_path, clock, machine, engine)
    rows = app.state.parts.consultations
    rows.add_check_run(1, 1, 4)                              # the app closes while the run is still running
    assert [r["outcome"] for r in rows.check_runs(1)] == ["running"]
    c.close()
    app2 = build_app(store.build(tmp_path, PORT), machine=machine, clock=clock,
                     engines={"vllm": FakeEngine(version=None), "ollama": FakeEngine()}, doors=nemotron_doors(MadeUpWorker()))
    client2 = browser(app2)
    p = app2.state.parts
    run = p.consultations.check_runs(1)[0]
    assert (run["outcome"], run["reason"]) == ("failed", words.CHECK_RESTARTED) and run["ended_at"] is not None
    assert lines_of(p) == AFTER_ANSWER and p.consultations.transcript_edits(1) == []
    assert any(line.event == "speakers.check_ended" and line.detail == f"consultation 1: failed: {words.CHECK_RESTARTED}"
               for line in p.audit.lines())
    log_in(client2)
    raw, page = client2.get("/consultations/1").text, text_of(client2.get("/consultations/1"))
    assert words.WARN_LABEL_CHECK_FAILED.format(reason=words.CHECK_RESTARTED) in page
    assert 'id="check-who" aria-describedby="check-who-refusal">' in raw and 'id="check-who-running"' not in raw


def test_R2_the_audit_lines_of_the_check_hold_numbers_and_no_word_of_the_transcript(tmp_path, clock, machine):
    engine = engine_with(label_check=[said("patient", "doctor", "unsure", "patient")])
    app, client, c = reviewed(tmp_path, clock, machine, engine)
    p = app.state.parts
    press(app, client)
    client.post("/consultations/1/who-check/undo-all")
    lines = [line for line in p.audit.lines() if line.event.startswith("speakers.check")]
    assert sorted(line.event for line in lines) == ["speakers.check_asked", "speakers.check_ended", "speakers.check_undone_all"]
    for line in lines:
        assert line.event in words.EVENTS                                          # each has its plain name on the Log page
        for word in ("pain", "chest", "brings", "word", "Tell"):
            assert word not in line.detail
    c.close()


def test_6c_a_check_that_answered_at_stop_before_6c_counts_as_already_run_and_undo_there_gives_the_answers_label(tmp_path, clock, machine):
    # As a folder of version 8 comes forward (test_db): the run of Stop, answered, its marked line with the answer's label before.
    engine = engine_with()
    app, client, c = reviewed(tmp_path, clock, machine, engine)
    p = app.state.parts
    run = p.consultations.add_check_run(1, 1, 4)
    p.consultations.end_check_run(run, "answered", call_ids=[], named_twice=0, dropped=0, changes=[(1, "doctor", "patient")],
                                  labels={1: {"label": "patient", "changed_by_check": True, "unsure": False}})
    p.db.execute("UPDATE speaker_check SET at_stop = 1 WHERE id = ?", (run,))
    raw, page = client.get("/consultations/1").text, text_of(client.get("/consultations/1"))
    assert 'id="check-who" aria-describedby="check-who-refusal" disabled' in raw and words.CHECK_ALREADY_RAN in page
    assert words.CHECK_CHANGED_ONE in page and words.WARN_LABEL_CHANGED.format(n=1, label="Patient") in page
    refused = client.post("/consultations/1/who-check")
    assert refused.status_code == 400 and refusal_on(text_of(refused), "check-who") == words.CHECK_ALREADY_RAN
    assert engine.calls_for("label_check") == []
    assert client.post("/consultations/1/lines/1/undo").status_code == 303
    assert p.consultations.line(1, 1)["label"] == "doctor"                                # the answer's label, as it was
    c.close()
