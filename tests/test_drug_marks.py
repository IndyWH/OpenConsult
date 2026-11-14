"""The drug-name call at Stop and its marks (spec 15.9 rulings 18 and 39;
15.10 rulings 6, 20, 21 and 23 and the details of step 6c: The drug-name
call at Stop, A mark, When the doctor types over; 10.4; R2; R30). A
made-up page and made-up replies: what code does with a reply's lines
and words is asserted, never what a model would say."""

import hashlib

from openconsult import words
from openconsult.bench.speech import model_lines
from openconsult.consult import drug_marks, joined, stop
from openconsult.consult.live import FINAL, SPINNING
from openconsult.llm import jobs as app_jobs
from openconsult.llm.engine import EngineTimeout
from openconsult.prompts import loader
from openconsult.settings.machine import Card, describe
from openconsult.speech.choices import NEMOTRON, WHISPERX_PYANNOTE
from openconsult.speech.door import Door as SpeechDoor
from tests.conftest import text_of
from tests.fakes import FakeEngine, MadeUpWorker
from tests.test_live import live_seg
from tests.test_review_page import engine_with, run_through
from tests.test_speech_door import seg
from tests.test_stop import NOTE, room_stopped, until
from tests.test_who_check import reviewed

# Four lines; the first two are one speaker's and join, so the model reads three. Line 3 holds the doubted words twice.
PAGE = [live_seg(1, 0.0, 0.5, "What do you take", "S1"), live_seg(2, 0.6, 0.9, "for the sugar?", "S1"),
        live_seg(3, 1.0, 1.6, "I take met for min twice a day and met for min at night. " + "word " * 60, "S2"),
        live_seg(4, 1.7, 2.0, "Tell me more.", "S1")]
REPLY = {"doubtful": [{"line": 2, "heard": "met for min", "meant": "a made-up drug"},     # stands on its line, twice
                      {"line": 1, "heard": "take for", "meant": ""},                      # stands across two lines of the page
                      {"line": 2, "heard": "Met for min", "meant": "another made-up drug"},   # the case differs: not letter for letter
                      {"line": 9, "heard": "word", "meant": ""}]}                         # no such line


def stopped(tmp_path, clock, reply, page=PAGE):
    return room_stopped(tmp_path, clock, worker=MadeUpWorker(live=[page, [], [], []]),
                        engine=FakeEngine({"drug_name": [reply], "note": [NOTE]}))


def test_15_9_ruling_18_6c_the_drug_name_files_are_the_approved_bytes_and_the_job_has_3000_tokens_and_90_seconds():
    # Rule 3 of the stage prompt: no word a model reads is new. The two files moved byte for byte; the frame's bytes are the label check's.
    assert hashlib.sha256(loader.prompt_bytes("drug_name")).hexdigest() == loader.APPROVED_BYTES["drug_name"] == \
        "89fcdc35d7a6ea4ddf7cd9e1b7e96c3118fd7810013e857bd83f6bc7c3939963"
    assert hashlib.sha256(loader.form_bytes("drug_name")).hexdigest() == loader.APPROVED_BYTES["drug_name.form"] == \
        "4574f7e5c6da63a82e9a67299d4fa3b76fefe84ac7dac1dfc3f5faa575f505b8"
    assert hashlib.sha256(loader.file_bytes("drug_name.frame")).hexdigest() == loader.APPROVED_BYTES["drug_name.frame"] == \
        "44f10e089af2ab4b4df272002604d35b0a678df6472949b193ba183bac1e0637"
    assert loader.file_bytes("drug_name.frame") == loader.file_bytes("label_check.frame")
    assert hashlib.sha256(loader.file_bytes("label_check.frame")).hexdigest() == loader.APPROVED_BYTES["label_check.frame"]
    assert hashlib.sha256(loader.prompt_bytes("label_check")).hexdigest() == "262d1ef805d4b7a27a1823a71dd649b78d2cdb84da5ce570c8d7cd3d91de557a"
    job = app_jobs.job("drug_name")
    assert (job.prompt, job.form, job.frames, job.max_tokens, job.timeout_s) == ("drug_name", "drug_name", ("drug_name",), 3000, 90.0)


def test_6c_the_apps_drug_name_text_is_the_benchs_bytes_on_the_same_lines():
    # The details, What is reused: the words around the lines are those the bench sent.
    lines = joined.lines_of([{"start": 0.0, "end": 0.5, "text": "What do you take", "speaker": "S1"},
                             {"start": 0.6, "end": 0.9, "text": "for the sugar?", "speaker": "S1"},
                             {"start": 1.0, "end": 1.6, "text": "I take met for min.", "speaker": "S2"}])
    assert drug_marks.lines_text(lines) == model_lines.lines_text(lines)
    assert drug_marks.lines_text(lines) == "TRANSCRIPT:\n[1] What do you take for the sugar?\n[2] I take met for min."


def test_6c_a_marks_places_are_on_one_line_across_neighbours_and_everywhere_the_words_stand():
    text_of_line = {1: "What do you take", 2: "  for the sugar? ", 3: "I take met for min twice and met for min."}
    assert drug_marks.places_of("met for min", [3], text_of_line) == [{"line": 3, "first": 7, "last": 18}, {"line": 3, "first": 29, "last": 40}]
    # Across neighbours of one joined line: one piece on each line, by that line's own letters (its leading spaces counted).
    across = drug_marks.places_of("take for", [1, 2], text_of_line)
    assert across == [{"line": 1, "first": 12, "last": 16}, {"line": 2, "first": 2, "last": 5}]
    assert text_of_line[1][12:16] == "take" and text_of_line[2][2:5] == "for"
    assert drug_marks.places_of("Take for", [1, 2], text_of_line) == [] and drug_marks.places_of("", [1], text_of_line) == []


def test_rulings_20_21_the_drug_name_call_runs_once_at_stop_after_the_gate_on_the_whole_page_and_each_kept_entry_is_a_mark(tmp_path, clock):
    r, c = stopped(tmp_path, clock, REPLY)
    try:
        before = [x["text"] for x in r.rows.transcript_lines(c.id)]
        stop.answer(c, "S1")
        assert until(lambda: c.state == FINAL)
        # Stage six of Stop: after the gate, before the note; one call, the whole page as joined lines, no speaker shown.
        assert stop.STAGES.index("drug_name") == stop.STAGES.index("gate") + 1 == stop.STAGES.index("note") - 1 and "drug_name" in SPINNING
        assert [row["job"] for row in r.rows.model_calls(c.id)][-2:] == ["drug_name", "note"]
        (call,) = r.engine.calls_for("drug_name")
        lines = joined.of_rows(r.rows.transcript_lines(c.id))
        assert call.user == drug_marks.lines_text(lines) and call.user.split("\n")[1] == "[1] What do you take for the sugar?"
        assert len(lines) == 3 and call.system == loader.prompt("drug_name") and "S1" not in call.user
        assert (call.max_tokens, call.timeout_s) == (3000, 90.0)
        # An entry is kept only when its line exists and its words stand there letter for letter; the others are counted (ruling 18).
        stored = r.rows.drug_call(c.id)
        assert (stored["outcome"], stored["kept"], stored["dropped"], stored["reason"]) == ("answered", 2, 2, None)
        assert stored["call_id"] == r.rows.model_calls(c.id)[-2]["id"]
        marks = r.rows.drug_marks(c.id)
        assert [(m["first_line"], m["joined_line"], m["page_lines"], m["heard"], m["meant"]) for m in marks] == [
            (1, 1, [1, 2], "take for", ""), (3, 2, [3], "met for min", "a made-up drug")]
        assert marks[0]["places"] == [{"line": 1, "first": 12, "last": 16}, {"line": 2, "first": 0, "last": 3}]
        assert marks[1]["places"] == [{"line": 3, "first": 7, "last": 18}, {"line": 3, "first": 35, "last": 46}]       # every place the words stand
        assert [x["text"] for x in r.rows.transcript_lines(c.id)] == before                    # a mark never changes a word
        audit = [line.detail for line in r.audit.lines() if line.event == "drug_names.checked"]
        assert audit == [f"consultation {c.id}: 2 marked, 2 dropped"] and "drug_names.checked" in words.EVENTS       # counts, never a word
        # Once: the stage finds its row and makes no second call, as after a restart at this stage (10.4).
        stop.drug_names(c)
        assert len(r.engine.calls_for("drug_name")) == 1 and len(r.rows.drug_marks(c.id)) == 2
        # The note is drafted after it and knows nothing of it.
        assert "made-up drug" not in r.engine.calls_for("note")[0].user and r.notes.current_draft(c.id) is not None
    finally:
        r.close()


def test_R3_ruling_8_no_drug_name_call_is_made_when_the_gate_refused(tmp_path, clock):
    r, c = stopped(tmp_path, clock, REPLY, page=[live_seg(1, 0.0, 0.5, "Hello.", "S1")])
    try:
        stop.answer(c, "S1")
        assert until(lambda: c.state == FINAL)
        assert c.final.refused and r.engine.calls_for("drug_name") == [] and r.rows.drug_call(c.id) is None and r.rows.drug_marks(c.id) == []
    finally:
        r.close()


def test_ruling_21_the_drug_name_call_runs_whichever_speech_choice_made_the_lines(tmp_path, clock):
    # The WhisperX choice, whose lines come from its pass at Stop: the same call on its final transcript.
    big = describe("Linux", "x86_64", [Card("Made-up card", 49140)])
    said = "I take met for min twice a day. " + "word " * 60
    worker = MadeUpWorker(live=[[{"start": 0.0, "end": 1.0, "text": said}]] + [[]] * 11,
                          final={"last_live": [], "segments": [seg(0.0, 3.0, said, "S0", 0.9)], "seconds": {}})
    doors = {NEMOTRON.name: SpeechDoor(NEMOTRON, make_worker=MadeUpWorker, installed=lambda: False),
             WHISPERX_PYANNOTE.name: SpeechDoor(WHISPERX_PYANNOTE, make_worker=lambda: worker, installed=lambda: True)}
    engine = engine_with(drug_name=[{"doubtful": [{"line": 1, "heard": "met for min", "meant": "a made-up drug"}]}])
    app, client, c = run_through(tmp_path, clock, big, doors, engine, answer="S0", pieces=12)
    p = app.state.parts
    assert p.consultations.get(1)["speech_choice"] == "whisperx_pyannote" and not c.final.refused
    assert len(engine.calls_for("drug_name")) == 1 and [m["heard"] for m in p.consultations.drug_marks(1)] == ["met for min"]
    c.close()


def test_ruling_20_R30_10_4_a_drug_name_call_that_fails_is_kept_with_its_reason_and_nothing_is_asked_again(tmp_path, clock):
    r, c = stopped(tmp_path, clock, EngineTimeout("no answer"))
    try:
        stop.answer(c, "S1")
        assert until(lambda: c.state == FINAL)
        stored = r.rows.drug_call(c.id)
        assert (stored["outcome"], stored["kept"], stored["dropped"]) == ("failed", 0, 0)
        assert stored["reason"].startswith("too_slow") and stored["reason"].endswith(".")
        assert len(r.engine.calls_for("drug_name")) == 1 and r.rows.drug_marks(c.id) == []
        assert [line.detail for line in r.audit.lines() if line.event == "drug_names.checked"] == [f"consultation {c.id}: failed: too_slow"]
        assert r.notes.current_draft(c.id) is not None and len(r.engine.calls_for("note")) == 1        # Stop goes on: the note is drafted (R30)
        stop.drug_names(c)
        assert len(r.engine.calls_for("drug_name")) == 1                                        # never asked a second time by itself
    finally:
        r.close()


def test_6c_a_mark_typed_over_is_cleared_and_kept_in_the_record_and_one_whose_words_still_stand_is_found_again(tmp_path, clock):
    r, c = stopped(tmp_path, clock, REPLY)
    try:
        stop.answer(c, "S1")
        assert until(lambda: c.state == FINAL)
        across, twice = r.rows.drug_marks(c.id)
        # The doctor types the name over the first place on line 3: the words still stand once, so the mark is kept and found again.
        r.rows.set_line_words(c.id, 3, "I take a made-up name twice a day and met for min at night.")
        assert drug_marks.after_edit(r.rows, c.id, 3) == 0
        assert r.rows.drug_marks(c.id)[1]["places"] == [{"line": 3, "first": 38, "last": 49}]
        # Typed over everywhere: the mark is cleared, and stays in the record with its time and the drug the model named.
        r.rows.set_line_words(c.id, 3, "I take a made-up name twice a day and at night.")
        assert drug_marks.after_edit(r.rows, c.id, 3) == 1 and [m["id"] for m in r.rows.drug_marks(c.id)] == [across["id"]]
        kept = [m for m in r.rows.drug_marks(c.id, every=True) if m["id"] == twice["id"]][0]
        assert kept["cleared_at"] is not None and kept["meant"] == "a made-up drug" and kept["heard"] == "met for min"
        # A mark across two lines: an edit of either line that leaves its words standing keeps it; one that does not clears it.
        r.rows.set_line_words(c.id, 2, "for the sugar level?")
        assert drug_marks.after_edit(r.rows, c.id, 2) == 0 and len(r.rows.drug_marks(c.id)) == 1
        r.rows.set_line_words(c.id, 1, "What do you use")
        assert drug_marks.after_edit(r.rows, c.id, 1) == 1 and r.rows.drug_marks(c.id) == []
        assert len(r.rows.drug_marks(c.id, every=True)) == 2 and len(r.engine.calls_for("drug_name")) == 1     # the call is not made again
        assert drug_marks.after_edit(r.rows, c.id, 4) == 0                                                    # a line with no mark
    finally:
        r.close()


def test_ruling_23_ruling_6_the_page_of_the_calls_shows_the_line_and_the_words_heard_and_leaves_the_named_drug_out(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path / "read", clock, machine, engine_with(drug_name=[REPLY]), page=PAGE)
    p = app.state.parts
    answer = client.get("/consultations/1/calls")
    page, raw = text_of(answer), answer.text
    call = [row for row in p.consultations.model_calls(1) if row["job"] == "drug_name"][0]
    section = raw.split(f'id="call-{call["id"]}"')[1].split("</details>")[0]
    assert "the check of drug names" in page and words.CALL_NO_ROW not in text_of_section(section)        # named by its row
    assert words.DRUG_NAMED_NOT_SHOWN in text_of_section(section) and f'id="named-drug-{call["id"]}"' in raw
    assert '"heard": "met for min"' in text_of_section(section) and '"line": 2' in text_of_section(section)
    assert "made-up drug" not in page and "meant" not in text_of_section(section)                       # no guess is shown anywhere
    assert "a made-up drug" in call["reply"] and "another made-up drug" in call["reply"]                 # the stored reply is not changed
    assert 'data-source="lines"' in section and words.SOURCE_LABELS["frame"].format(file="drug_name.frame.txt") in text_of_section(section)
    assert "[1] What do you take for the sugar?" in text_of_section(section) and loader.prompt("drug_name").split("\n")[0] not in page
    c.close()
    # A reply that cannot be read as its form could hold a named drug in its raw text: it is not shown at all, and the page says so.
    app, client, c = reviewed(tmp_path / "unread", clock, machine, engine_with(drug_name=['{"doubtful": [{"line": 1, "meant": "a made-up drug"']), page=PAGE)
    p = app.state.parts
    page = text_of(client.get("/consultations/1/calls"))
    stored = [row for row in p.consultations.model_calls(1) if row["job"] == "drug_name"][0]
    assert stored["outcome"] != "ok" and "a made-up drug" in stored["reply"] and p.consultations.drug_call(1)["outcome"] == "failed"
    assert words.DRUG_REPLY_NOT_SHOWN in page and "made-up drug" not in page and words.DRUG_NAMED_NOT_SHOWN not in page
    c.close()


def text_of_section(section: str) -> str:
    import html
    return html.unescape(section)


def test_6c_the_stopping_page_says_checking_the_drug_names_during_the_stage(tmp_path, clock):
    # The details, The sentences: the stage line of Stop while the drug-name call runs; a named in-progress state (V1_LESSONS 5.3).
    r, c = stopped(tmp_path, clock, REPLY)
    try:
        c.set_stage("drug_name")
        assert c.page_state()["spinning"] == "drug_name" and words.STAGE_LINES["drug_name"] == "Checking the drug names."
        assert words.STAGE_LINES["answered"] == "Your answer is taken. Checking for missing speech." and "label_check" not in words.STAGE_LINES
        c.set_stage("who_spoke")
    finally:
        r.close()
