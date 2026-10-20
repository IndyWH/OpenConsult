"""The review page (spec 15.10, rulings 4, 8, 11 and 12; R2, R3, R4, R9,
R15, R20, R30; 11.5 rules 2 and 5; 6a's final page folded in). Made-up
doors; made sound; no model's words asserted."""

import json

from openconsult import words
from openconsult.app import build_app
from openconsult.consult import stop
from openconsult.consult.live import FINAL
from openconsult.settings import store
from openconsult.settings.machine import Card, describe
from openconsult.speech.choices import NEMOTRON, WHISPERX_PYANNOTE
from openconsult.speech.door import Door as SpeechDoor
from openconsult.web.review import SCRIPT_WORDS, script_words
from tests.conftest import PORT, browser, log_in, refusal_on, set_up, text_of
from tests.fakes import ALARM_FIRES, ASSESSMENT, FakeEngine, MadeUpWorker
from tests.test_loudness import sine
from tests.test_speech_door import seg
from tests.test_start import PATIENT, TICKS
from tests.test_stop import until

RATE = 16000
LOUD = sine(0.25, -20.0)
CAPTURE = {"type": "capture", "echo_cancellation": False, "noise_suppression": False, "auto_gain": False, "rate": RATE}
LONG = " ".join(["word"] * 70)
LINES = [[{"id": 1, "start": 0.0, "end": 0.5, "text": LONG, "speaker": "S1", "confidence": None}],
         [{"id": 2, "start": 0.6, "end": 1.0, "text": "Yes.", "speaker": None, "confidence": None}]]
CHECK = {"lines": [{"line": 1, "label": "doctor"}, {"line": 2, "label": "patient"}]}
NOTE = {"reasoning": "made up.", "subjective": [{"text": "made up history [1]", "turns": [1]}], "objective": [],
        "assessment": [{"text": "made up impression", "turns": [0]}], "plan": [{"text": "made up plan", "turns": [8]}]}


def engine_with(**script):
    return FakeEngine({"alarm": [ALARM_FIRES], "label_check": [CHECK], "note": [NOTE], **script})


def app_on(tmp_path, clock, machine, doors, engine):
    app = build_app(store.build(tmp_path, PORT), machine=machine, clock=clock,
                    engines={"vllm": FakeEngine(version=None), "ollama": engine}, doors=doors)
    return app, browser(app)


def run_through(tmp_path, clock, machine, doors, engine, answer="S1", pieces=8):
    app, client = app_on(tmp_path, clock, machine, doors, engine)
    set_up(client)
    log_in(client)
    client.post("/patients", data=PATIENT)
    client.post("/consultations/start/1", data=TICKS)
    c = app.state.parts.running[1]
    from openconsult.web.live import capture_from
    c.begin_sound(capture_from(CAPTURE))
    for _ in range(pieces):
        c.sound(LOUD)
        c.wait_for_pass()
    client.post("/consultations/1/stop")
    assert until(lambda: c.stop_stage == "who_spoke")
    client.post("/consultations/1/speakers", data={"speaker": answer})
    assert until(lambda: c.state == FINAL)
    return app, client, c


def nemotron_doors(worker):
    return {NEMOTRON.name: SpeechDoor(NEMOTRON, make_worker=lambda: worker, installed=lambda: True)}


def reviewed(tmp_path, clock, machine, engine=None):
    return run_through(tmp_path, clock, machine, nemotron_doors(MadeUpWorker(live=LINES)), engine or engine_with())


def test_ruling_8_the_review_page_shows_the_warnings_the_labels_and_the_last_pass(tmp_path, clock, machine):
    # 6a's final page test, now of the review page: the warnings, the labels and the last pass stay pinned.
    app, client, c = reviewed(tmp_path, clock, machine)
    page = text_of(client.get("/consultations/1"))
    assert words.REVIEW_TITLE in page and words.FINAL_TITLE not in page
    assert words.WARN_NO_SPEAKER.format(n=2) in page                                  # a line with no speaker: flagged
    assert words.WARN_CONFIDENCE_NOT_MEASURED.format(choice=words.ROW_NEMOTRON) in page   # Nemotron gives no score
    assert words.WARN_TOO_SHORT.split("{")[0] not in page                              # 71 words: not too short
    assert "[1] Doctor" in page and "[2] Patient" in page and words.LABEL_UNSURE in page
    assert "Made-up condition A" in page and words.MODELS_DIFFERENTIALS in page       # the last pass's differentials (ruling 4)
    assert words.MODEL_LINE.format(speech=words.ROW_NEMOTRON, model="gemma4:26b-a4b-it-qat", engine="made-up",
                                   version="0.0-made-up") in page
    assert not c.final.refused


def test_11_5_rule_2_missing_speech_is_shown_at_its_place_and_the_gate_refuses_so_no_note_is_drafted(tmp_path, clock):
    # A made-up card large enough for the WhisperX choice beside the language model.
    big = describe("Linux", "x86_64", [Card("Made-up card", 49140)])
    live_text = "go straight to the hospital now please"
    worker = MadeUpWorker(live=[[{"start": 0.0, "end": 1.0, "text": live_text}]] + [[]] * 11,
                          final={"last_live": [], "segments": [seg(0.0, 1.0, "now please", "S0", 0.9)], "seconds": {}})
    doors = {NEMOTRON.name: SpeechDoor(NEMOTRON, make_worker=MadeUpWorker, installed=lambda: False),
             WHISPERX_PYANNOTE.name: SpeechDoor(WHISPERX_PYANNOTE, make_worker=lambda: worker, installed=lambda: True)}
    engine = engine_with(label_check=[{"lines": [{"line": 1, "label": "patient"}]}])
    app, client, c = run_through(tmp_path, clock, big, doors, engine, answer="S0", pieces=12)
    page = text_of(client.get("/consultations/1"))
    assert words.WARN_MISSING_PASSAGE.format(start=0.0, end=1.0, words="go straight to the hospital") in page
    assert words.WARN_UNCOVERED.format(start=1.0, end=3.0) in page           # three seconds of sound, one covered
    assert words.WARN_TOO_SHORT.format(words=2, least=60) in page and c.final.refused
    assert words.WARN_CONFIDENCE_NOT_MEASURED.split(":")[0] not in page      # WhisperX gives a score
    assert c.final.figures["stop_s"] is not None and "Stop to final" in app.state.parts.audit.lines()[0].detail
    assert app.state.parts.consultations.get(1)["speech_choice"] == "whisperx_pyannote"
    # R3, ruling 8: the gate refused, so no note was drafted, no note call was made, and the page says why;
    # Draft the note is disabled with the reason on it (R15).
    assert app.state.parts.notes.drafts(1) == [] and engine.calls_for("note") == []
    assert words.NOTE_GATE_REFUSED.format(reason=words.WARN_TOO_SHORT.format(words=2, least=60)) in page
    assert 'id="draft" aria-describedby="draft-refusal" disabled' in client.get("/consultations/1").text
    answer = client.post("/consultations/1/note/draft")
    assert answer.status_code == 400 and words.NOTE_GATE_REFUSED.split(":")[0] in refusal_on(text_of(answer), "draft")


def slot_text(page: str, control: str) -> str:
    """The refusal in a control's slot when the control itself is absent by
    design (a read-only page, or an Undo that no longer applies): the slot
    stays, so a post anyway is never swallowed (R15)."""
    from tests.conftest import _RefusalFinder
    finder = _RefusalFinder(control)
    finder.feed(page)
    return finder.text.strip()


def positions(page: str, *marks: str) -> list[int]:
    found = [page.find(mark) for mark in marks]
    assert all(p >= 0 for p in found), [m for m, p in zip(marks, found) if p < 0]
    return found


def test_ruling_11_the_review_page_is_in_the_busy_gps_order(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine)
    raw = client.get("/consultations/1").text
    page = text_of(client.get("/consultations/1"))
    found = positions(raw, 'id="note"', 'id="controls"', 'id="warnings"', 'id="transcript"', 'id="model-line"')
    assert found == sorted(found)                                               # note, controls, warnings, transcript, model line
    # The entries by section; a line number is a press that shows the line; an uncited entry is marked.
    assert positions(raw, 'id="section-subjective"', 'id="section-objective"', 'id="section-assessment"', 'id="section-plan"') == \
        sorted(positions(raw, 'id="section-subjective"', 'id="section-objective"', 'id="section-assessment"', 'id="section-plan"'))
    assert 'class="cite no-print" data-line="2"' in raw and "made up history [1]" in page
    assert words.ENTRY_UNCITED in page and page.count(words.ENTRY_UNCITED) == 1                    # the plan's entry cites turn 8
    # The differentials beside the assessment, under the heading that they are the model's, inside that section.
    import html
    section = html.unescape(raw[raw.find('id="section-assessment"'):raw.find('id="section-plan"')])
    assert words.MODELS_DIFFERENTIALS in section and "Made-up condition A" in section and 'id="differentials"' in section
    # Approve carries the count of warnings, one press to them.
    assert '<a href="#warnings" id="warning-count"' in raw and words.WARNINGS_COUNT.format(count=2) in page
    assert words.NOTE_DRAFT_LINE in page and words.COPY_NOTE in page
    # The model line last, from the row (R20).
    assert raw.rfind('id="model-line"') > raw.rfind('id="transcript"')


def test_R2_approve_is_audited_writes_the_approved_note_and_makes_it_read_only(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine)
    p = app.state.parts
    text = client.get("/consultations/1/note.txt")
    assert text.status_code == 200 and text.text == "Subjective\nmade up history\n\nObjective\n\nAssessment\nmade up impression\n\nPlan\nmade up plan\n"
    assert client.post("/consultations/1/note/approve").status_code == 303
    approval = p.notes.approval(1)
    assert approval["draft_id"] == p.notes.current_draft(1)["id"] and approval["text"] == text.text
    assert p.audit.lines()[0].event == "note.approved" and "draft 1, 3 entries" in p.audit.lines()[0].detail
    page = text_of(client.get("/consultations/1"))
    assert words.APPROVED_LINE.split("{")[0] in page and words.NOTE_DRAFT_LINE not in page
    # Read-only after it: a second Approve, a Refuse and a draft again are each refused on the control pressed (R15).
    again = client.post("/consultations/1/note/approve")
    assert again.status_code == 400 and refusal_on(text_of(again), "approve") == words.ALREADY_APPROVED
    assert refusal_on(text_of(client.post("/consultations/1/note/refuse")), "refuse") == words.ALREADY_APPROVED
    assert refusal_on(text_of(client.post("/consultations/1/note/draft")), "draft") == words.NOTE_READ_ONLY
    assert len(p.notes.drafts(1)) == 1 and p.notes.refusals(1) == []
    assert client.get("/consultations/1/note.txt").text == approval["text"]
    # Ruling 4: the approved text and the copy text hold no trace of the differentials.
    assert "Made-up condition" not in approval["text"] and words.MODELS_DIFFERENTIALS not in approval["text"]
    assert p.consultations.waiting_for_review() == [] and words.HOME_REVIEW not in text_of(client.get("/"))


def test_refuse_is_recorded_and_nothing_enters_the_record(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine)
    p = app.state.parts
    assert client.post("/consultations/1/note/refuse").status_code == 303
    assert [r["draft_id"] for r in p.notes.refusals(1)] == [p.notes.current_draft(1)["id"]] and p.notes.approval(1) is None
    assert p.audit.lines()[0].event == "note.refused"
    page = text_of(client.get("/consultations/1"))
    assert words.REFUSED_LINE.split("{")[0] in page
    assert refusal_on(text_of(client.post("/consultations/1/note/approve")), "approve") == words.NOTHING_TO_APPROVE
    assert refusal_on(text_of(client.post("/consultations/1/note/refuse")), "refuse") == words.ALREADY_REFUSED
    # Draft again waits for an edit (ruling 11): nothing has been edited yet.
    assert refusal_on(text_of(client.post("/consultations/1/note/draft")), "draft") == words.DRAFT_AGAIN_NEEDS_EDIT
    assert words.HOME_REVIEW in text_of(client.get("/"))                              # still waiting for review


def test_R30_10_4_a_failed_note_call_is_said_plainly_and_draft_the_note_is_offered(tmp_path, clock, machine):
    from openconsult.llm.engine import EngineTimeout
    engine = engine_with(note=[EngineTimeout("no answer"), NOTE])
    app, client, c = reviewed(tmp_path, clock, machine, engine)
    p = app.state.parts
    page = text_of(client.get("/consultations/1"))
    assert words.NOTE_CALL_FAILED.format(reason="too_slow").split(":")[0] in page and "too_slow" in page
    assert refusal_on(text_of(client.post("/consultations/1/note/approve")), "approve") == words.NOTHING_TO_APPROVE
    assert client.get("/consultations/1/note.txt").status_code == 404
    # Draft the note again is offered after a failure without an edit: the failed draft stands as draft 1.
    assert client.post("/consultations/1/note/draft").status_code == 303
    assert [d["n"] for d in p.notes.drafts(1)] == [1, 2] and p.notes.current_draft(1)["failure"] is None
    assert words.EARLIER_DRAFTS.format(count=1) in text_of(client.get("/consultations/1"))


def test_a_final_consultation_from_6a_offers_draft_the_note_and_after_a_restart_the_page_reads_everything_from_the_tables(
        tmp_path, clock, machine, monkeypatch):
    # The first run stops as 6a stopped, with no note stage; then the app starts again on the folder.
    monkeypatch.setitem(stop.NEXT, "gate", None)
    engine = engine_with()
    app, client, c = reviewed(tmp_path, clock, machine, engine)
    monkeypatch.undo()
    assert app.state.parts.notes.drafts(1) == [] and engine.calls_for("note") == []
    c.close()
    engine2 = engine_with()
    app2, client2 = app_on(tmp_path, clock, machine, nemotron_doors(MadeUpWorker()), engine2)
    assert 1 not in app2.state.parts.running
    log_in(client2)
    home = text_of(client2.get("/"))
    assert words.HOME_REVIEW in home and words.REVIEW in home and words.HOME_WAITING not in home
    answer = client2.get("/consultations/1")
    assert answer.status_code == 200
    page = text_of(answer)
    assert words.NO_NOTE_YET in page
    assert words.DRAFT_THE_NOTE in page
    assert "Made-up condition A" in page                                            # from cds_pass
    assert "[1] Doctor" in page and words.WARN_NO_SPEAKER.format(n=2) in page
    assert client2.post("/consultations/1/note/draft").status_code == 303
    draft = app2.state.parts.notes.current_draft(1)
    assert draft["asked_by"] == "draft" and draft["entries_total"] == 3 and len(engine2.calls_for("note")) == 1
    page = text_of(client2.get("/consultations/1"))
    assert "made up history [1]" in page and words.NOTE_DRAFT_LINE in page and words.DRAFT_AGAIN in page
    assert client2.post("/consultations/1/note/approve").status_code == 303


def test_ruling_12_the_review_page_is_timed_by_its_own_script_and_every_keystroke_is_use(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine)
    raw = client.get("/consultations/1").text
    assert 'http-equiv="refresh"' not in raw and 'id="review" data-use data-seconds-left="' in raw
    assert '/static/use.js' in raw and client.get("/static/use.js").status_code == 200
    assert "querySelector('[data-use]')" in client.get("/static/use.js").text
    clock.advance(minutes=29)
    assert client.post("/use").json()["seconds_left"] == 1800              # a keystroke is use: the login is touched
    clock.advance(minutes=29)
    assert client.get("/consultations/1?quiet").status_code == 200       # a quiet check is not use
    clock.advance(minutes=2)
    assert client.get("/consultations/1?quiet").status_code == 303        # so the lock falls, and the login page says why


def test_15_6_every_sentence_the_review_scripts_render_comes_from_the_one_file(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine)
    handed = script_words()
    assert set(handed) == set(SCRIPT_WORDS)
    for name, sentence in handed.items():
        assert sentence == getattr(words, name) and isinstance(sentence, str) and sentence
    raw = client.get("/consultations/1").text
    assert '<script id="words" type="application/json">' in raw and json.loads(raw.split('<script id="words" type="application/json">')[1].split("</script>")[0]) == handed
    assert client.get("/static/review.js").status_code == 200


def test_R15_the_home_page_lists_each_consultation_waiting_for_review_once(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine)
    client.post("/consultations/1/note/refuse")
    home = text_of(client.get("/"))
    assert home.count(words.REVIEW + "</a>") == 1 and words.HOME_REVIEW in home


def test_ruling_11_draft_again_is_offered_only_after_an_edit_and_keeps_the_earlier_draft(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine, engine_with(note=[NOTE, {**NOTE, "plan": []}]))
    p = app.state.parts
    raw = client.get("/consultations/1").text
    assert 'id="draft" aria-describedby="draft-refusal" disabled' in raw and words.DRAFT_AGAIN_NEEDS_EDIT in text_of(client.get("/consultations/1"))
    assert refusal_on(text_of(client.post("/consultations/1/note/draft")), "draft") == words.DRAFT_AGAIN_NEEDS_EDIT
    # A word edit: recorded with the words before; then draft again acts, and the next draft reads the new words.
    assert client.post("/consultations/1/lines/2", data={"label": "patient", "text": "Yes, doctor."}).status_code == 303
    edits = p.consultations.transcript_edits(1)
    assert [(e["kind"], e["line_n"], e["before"], e["after"]) for e in edits] == [("words", 2, "Yes.", "Yes, doctor.")]
    assert p.audit.lines()[0].event == "transcript.edited"
    raw = client.get("/consultations/1").text
    assert 'id="draft" aria-describedby="draft-refusal" disabled' not in raw and words.DRAFT_AGAIN in text_of(client.get("/consultations/1"))
    first = p.notes.current_draft(1)
    assert client.post("/consultations/1/note/draft").status_code == 303
    second = p.notes.current_draft(1)
    assert (second["n"], second["asked_by"], second["last_edit_id"]) == (2, "again", edits[0]["id"]) and second["id"] != first["id"]
    assert p.notes.entries(first["id"])[2]["text"] == "made up plan" and len(p.notes.entries(second["id"])) == 2   # the earlier draft is kept
    sent = app.state.parts.door._engine.calls_for("note")[-1].user
    assert "Yes, doctor." in sent and "[1] Patient: Yes, doctor." in sent
    page = text_of(client.get("/consultations/1"))
    assert words.EARLIER_DRAFTS.format(count=1) in page and "made up plan" not in page.split('id="warnings"')[0]
    assert refusal_on(text_of(client.post("/consultations/1/note/draft")), "draft") == words.DRAFT_AGAIN_NEEDS_EDIT   # never by itself


def test_ruling_7_a_label_the_check_changed_is_undone_with_one_press_and_a_line_label_can_be_set(tmp_path, clock, machine):
    swapped = {"lines": [{"line": 1, "label": "patient"}, {"line": 2, "label": "doctor"}]}
    app, client, c = reviewed(tmp_path, clock, machine, engine_with(label_check=[swapped]))
    p = app.state.parts
    lines = p.consultations.transcript_lines(1)
    assert [(l["label"], l["changed_by_check"]) for l in lines] == [("patient", 1), ("doctor", 0)]   # line 2 had no first reading (ruling 14)
    page = text_of(client.get("/consultations/1"))
    assert words.WARN_LABEL_CHANGED.format(n=1, label="Patient") in page and words.UNDO_LABEL in page
    assert words.WARNINGS_COUNT.format(count=3) in page                                   # the changed label among the warnings
    assert client.post("/consultations/1/lines/1/undo").status_code == 303
    line = p.consultations.line(1, 1)
    assert (line["label"], line["changed_by_check"], line["set_by_doctor"], line["unsure"]) == ("doctor", 0, 1, 0)   # the answer's label
    assert p.audit.lines()[0].event == "label.undone" and p.consultations.transcript_edits(1)[-1]["kind"] == "undo"
    page = text_of(client.get("/consultations/1"))
    assert words.LABEL_SET_BY_YOU in page and words.WARN_LABEL_CHANGED.format(n=1, label="Patient") not in page
    assert slot_text(text_of(client.post("/consultations/1/lines/1/undo")), "undo-1") == words.NOT_CHANGED_BY_CHECK
    # The per-line label.
    assert client.post("/consultations/1/lines/2", data={"label": "unsure", "text": "Yes."}).status_code == 303
    line = p.consultations.line(1, 2)
    assert (line["label"], line["unsure"], line["set_by_doctor"]) == ("unsure", 1, 1) and p.audit.lines()[0].event == "label.set"
    assert refusal_on(text_of(client.post("/consultations/1/lines/2", data={"label": "nurse", "text": "Yes."})), "save-line-2") == words.PICK_LABEL
    assert client.post("/consultations/1/lines/9", data={"label": "doctor", "text": "x"}).status_code == 303   # no such line: no such control
    assert [l["text"] for l in p.consultations.transcript_lines(1)] == [l["text"] for l in lines]       # the words untouched


def test_swap_swaps_doctor_and_patient_on_every_line_and_leaves_unsure(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine)
    p = app.state.parts
    client.post("/consultations/1/lines/2", data={"label": "unsure", "text": "Yes."})
    assert client.post("/consultations/1/lines/swap").status_code == 303
    assert [l["label"] for l in p.consultations.transcript_lines(1)] == ["patient", "unsure"]
    assert p.consultations.transcript_edits(1)[-1]["kind"] == "swap" and p.audit.lines()[0].event == "labels.swapped"
    assert words.DRAFT_AGAIN in text_of(client.get("/consultations/1"))


def test_R2_an_entry_edit_is_kept_with_the_words_before_and_the_page_is_read_only_after_approve(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine)
    p = app.state.parts
    entry = p.notes.entries(p.notes.current_draft(1)["id"])[0]
    assert client.post(f"/consultations/1/entries/{entry['id']}", data={"text": "the doctor's words [1]"}).status_code == 303
    changed = p.notes.entry(entry["id"])
    assert (changed["text"], changed["model_text"]) == ("the doctor's words [1]", "made up history [1]")
    assert p.audit.lines()[0].event == "entry.edited"
    assert refusal_on(text_of(client.post(f"/consultations/1/entries/{entry['id']}", data={"text": " "})), f"entry-{entry['id']}") == words.ENTRY_EMPTY
    assert "the doctor's words [1]" in text_of(client.get("/consultations/1"))          # the page keeps the words as they stand
    assert client.get("/consultations/1/note.txt").text.startswith("Subjective\nthe doctor's words\n")   # the copy strips the citation
    client.post("/consultations/1/note/approve")
    assert p.notes.approval(1)["text"].startswith("Subjective\nthe doctor's words\n")
    # Read-only after Approve: the entries, the lines, Undo and Swap are each refused on the control pressed (R15).
    assert slot_text(text_of(client.post(f"/consultations/1/entries/{entry['id']}", data={"text": "x"})), f"entry-{entry['id']}") == words.NOTE_READ_ONLY
    assert slot_text(text_of(client.post("/consultations/1/lines/1", data={"label": "doctor", "text": "x"})), "save-line-1") == words.NOTE_READ_ONLY
    assert slot_text(text_of(client.post("/consultations/1/lines/swap")), "swap") == words.NOTE_READ_ONLY
    assert slot_text(text_of(client.post("/consultations/1/lines/1/undo")), "undo-1") == words.NOTE_READ_ONLY
    raw = client.get("/consultations/1").text
    assert "entry-form" not in raw and "line-form" not in raw and 'id="swap"' not in raw
    # After Refuse instead, the entries are read-only and the transcript is not.
    app2, client2, c2 = reviewed(tmp_path / "two", clock, machine)
    client2.post("/consultations/1/note/refuse")
    entry2 = app2.state.parts.notes.entries(app2.state.parts.notes.current_draft(1)["id"])[0]
    assert slot_text(text_of(client2.post(f"/consultations/1/entries/{entry2['id']}", data={"text": "x"})), f"entry-{entry2['id']}") == words.NOTE_NOT_EDITABLE
    assert client2.post("/consultations/1/lines/2", data={"label": "doctor", "text": "Yes."}).status_code == 303
