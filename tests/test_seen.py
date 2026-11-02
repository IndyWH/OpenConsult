"""The readers of what each call was given (spec 15.12, rulings 11 and 28;
15.8 ruling 1; R11, R20, R25; D3). Made calls through the door and the
app's own builders on a temporary database; the reader gives the parts the
builder put in. No model's words asserted."""

import json
from dataclasses import asdict
from datetime import date, datetime

import pytest

from openconsult.consult import labels, letter, note, referrals, seen
from openconsult.consult.background import build_block
from openconsult.consult.cds_pass import Carried, run_pass
from openconsult.consult.consultations import Consultations, line_as_row
from openconsult.consult.earlier import ApprovedNote
from openconsult.consult.letter_rows import Letters, ListRow
from openconsult.consult.messages import Patient, alarm_message, assessment_message, patient_line, with_background, with_patient
from openconsult.consult.note_rows import Notes
from openconsult.db import open_database
from openconsult.guidelines import summary
from openconsult.guidelines.sources import AnswerRow, Sources
from openconsult.llm import jobs
from openconsult.llm.door import Door
from openconsult.llm.record import CallRow, ModelCalls
from openconsult.patients.audit import Audit
from openconsult.patients.patients import Patients
from openconsult.prompts import loader
from openconsult.speech.lines import Line
from tests.fakes import ALARM_QUIET, ASSESSMENT, FakeEngine
from tests.test_guideline_summary import SENT
from tests.test_letters_page import LETTER, LIST, NOTE
from tests.test_review_page import CHECK

TRANSCRIPT = "S1: What brings you in today?\nS2: A pain in my chest."
ROWS = [{"n": 1, "text": "What brings you in today?"}, {"n": 2, "text": "A pain in my chest."}]
COVERED = {"covered": True, "summary": "made [1].", "passages_cited": [1]}


class Record:
    """A final consultation of a made patient, with every row class and a
    door on the made engine; the clock moves between calls so the order
    by at is a real order."""

    def __init__(self, tmp_path, clock, script=None):
        self.clock = clock
        self.db = open_database(tmp_path / "openconsult.db")
        self.audit = Audit(self.db, clock)
        self.patients = Patients(self.db, self.audit, clock)
        self.patient = self.patients.add("Made-up", date(1991, 3, 4), "F")      # 35 on the fake clock's day
        self.consultations = Consultations(self.db, clock)
        self.cid = self.consultations.start(self.patient.id, 15, "nemotron", "made-up", "0.0-made-up", "made-up/tag", "d", 2)
        self.notes, self.letters, self.sources = Notes(self.db, clock), Letters(self.db, clock), Sources(self.db, self.audit, clock)
        self.record = ModelCalls(self.db, clock)
        self.engine = FakeEngine(script or {"alarm": [ALARM_QUIET] * 4, "label_check": [CHECK], "note": [NOTE],
                                            "referrals": [LIST], "letter": [LETTER], "guideline": [COVERED]})
        self.door = Door(self.engine, self.record)
        self.model_patient = Patient(35, "F")
        self.consultations.set(self.cid, state="final", stopped_at=clock().isoformat(timespec="seconds"),
                               final_at=clock().isoformat(timespec="seconds"))

    def tick(self):
        self.clock.advance(seconds=1)

    def a_pass(self, n, carried=None, block=None):
        result = run_pass(self.door, TRANSCRIPT, self.model_patient, carried, consultation_id=self.cid, background=block)
        self.consultations.add_pass(self.cid, n, TRANSCRIPT, result.alarm.call_id, result.assessment.call_id,
                                    {"n": n, "shown": True, "wall_ms": 1000 * n}, True)
        self.tick()
        return result

    def lines(self):
        self.consultations.add_transcript_lines(self.cid, [
            line_as_row(Line("S1", 0.0, 0.5, ROWS[0]["text"], None), 1, "doctor"),
            line_as_row(Line("S2", 0.6, 1.0, ROWS[1]["text"], None), 2, "patient")])

    def seen(self):
        return seen.calls_of(self.consultations, self.notes, self.letters, self.sources, self.cid)

    def close(self):
        self.db.close()


@pytest.fixture
def room(tmp_path, clock):
    made = Record(tmp_path, clock)
    yield made
    made.close()


def settled(found: list) -> list:
    """The reader's order, with the two calls of one instant put alarm first:
    the made engine answers at once and the pass's two threads end in either
    order within the fake clock's one instant; a real engine's calls differ
    in their milliseconds."""
    out, k = [], 0
    while k < len(found):
        end = k
        while end < len(found) and found[end].call["at"] == found[k].call["at"]:
            end += 1
        out += sorted(found[k:end], key=lambda c: c.kind)
        k = end
    return out


def sources_of(found: seen.Seen) -> list[str]:
    return [part.source for part in found.parts]


def part(found: seen.Seen, source: str) -> seen.Part:
    return [p for p in found.parts if p.source == source][0]


def block_of():
    return build_block([ApprovedNote(9, datetime(2026, 3, 1), datetime(2026, 3, 1),
                                     {"subjective": ["made history"], "objective": [], "assessment": ["made"], "plan": ["made plan"]})])


def test_ruling_11_R11_R25_the_two_pass_calls_read_back_the_patient_line_the_block_the_stale_names_and_the_transcript(room):
    room.a_pass(1)
    block = block_of()
    room.a_pass(2, Carried(names=("Made-up condition A", "Made-up condition B")), block)
    calls = settled(room.seen())
    assert [(c.kind, c.name["pass_n"], c.taken_apart, c.reason) for c in calls] == [
        ("alarm", 1, True, None), ("assessment", 1, True, None), ("alarm", 2, True, None), ("assessment", 2, True, None)]
    first_alarm, first_assessment, alarm, assessment = calls
    # The first pass: no block, the first frame, no stale list (R12: the transcript alone).
    assert sources_of(first_alarm) == ["patient_line", "frame", "transcript"]
    assert sources_of(first_assessment) == ["patient_line", "frame", "transcript"]
    assert part(first_assessment, "frame").file == "assessment.first.frame.txt"
    # The second: the block in both (R25), the later frame with the names only (R12), the transcript as sent.
    assert sources_of(alarm) == ["patient_line", "background", "frame", "transcript"]
    assert sources_of(assessment) == ["patient_line", "background", "frame", "stale", "transcript"]
    for found in (alarm, assessment):
        assert part(found, "patient_line").text == patient_line(35, "F")                       # R11
        assert part(found, "background").text == block
        assert part(found, "transcript").text == TRANSCRIPT == found.row["transcript"]
    assert part(alarm, "frame").file == "alarm.frame.txt" and part(alarm, "frame").text == loader.frame("alarm")
    assert part(assessment, "stale").text == "Made-up condition A\nMade-up condition B"
    # The parts are the builder's own, and joined they are the request byte for byte.
    assert alarm.user_text == with_background(with_patient(alarm_message(TRANSCRIPT), room.model_patient), block)
    assert assessment.user_text == with_background(with_patient(assessment_message(
        TRANSCRIPT, ("Made-up condition A", "Made-up condition B")), room.model_patient), block)
    assert alarm.answer == json.dumps(ALARM_QUIET) and assessment.answer == json.dumps(ASSESSMENT)


def test_ruling_11_D3_the_note_and_the_label_check_read_back_from_their_frames_with_no_patient_line_and_no_block(room):
    room.lines()
    labels.run(room.door, ROWS, room.cid)
    room.tick()
    note.draft(room.door, room.consultations, room.notes, room.audit, room.cid, "stop")
    check, drafted = room.seen()
    assert (check.kind, check.name, check.taken_apart) == ("label_check", {"kind": "label_check", "referenced": False}, True)
    assert sources_of(check) == ["frame", "lines"] and part(check, "lines").text == "[1] What brings you in today?\n[2] A pain in my chest."
    assert check.user_text == labels.lines_text(ROWS) and part(check, "frame").file == "label_check.frame.txt"
    assert (drafted.kind, drafted.name, drafted.taken_apart) == ("note", {"kind": "note", "n": 1, "asked_by": "stop", "referenced": True}, True)
    assert sources_of(drafted) == ["frame", "turns"]
    assert part(drafted, "turns").text == "[0] Doctor: What brings you in today?\n[1] Patient: A pain in my chest."
    assert drafted.user_text == drafted.row["transcript"] and "patient_line" not in sources_of(drafted)   # D3; R25


def approved_room(room):
    room.lines()
    draft = note.draft(room.door, room.consultations, room.notes, room.audit, room.cid, "stop")
    room.notes.approve(room.cid, draft["id"], note.plain_text(room.notes.entries(draft["id"])))
    room.tick()
    return draft


def test_ruling_11_R11_the_list_and_the_letter_read_back_from_their_named_parts(room):
    approved_room(room)
    referrals.make_list(room.door, room.letters, room.notes, room.consultations, room.audit, room.cid)
    room.tick()
    item = room.letters.items(room.cid)[0]
    letter.draft(room.door, room.letters, room.notes, room.consultations, room.audit, room.cid, item)
    listed, lettered = room.seen()[1:]
    assert (listed.kind, listed.name, listed.taken_apart) == ("referrals", {"kind": "referrals", "referenced": True}, True)
    assert sources_of(listed) == ["patient_line", "frame", "note_lines"]
    assert part(listed, "note_lines").text == room.letters.list_of(room.cid)["note_lines"]        # the named part
    assert part(listed, "patient_line").text == patient_line(35, "F")                              # R11
    assert (lettered.kind, lettered.name["specialty"], lettered.name["n"], lettered.taken_apart) == ("letter", item["specialty"], 1, True)
    assert sources_of(lettered) == ["patient_line", "frame", "specialty", "note_lines"]
    assert part(lettered, "specialty").text == item["specialty"]
    assert part(lettered, "note_lines").text == room.letters.letters(room.cid)[0]["note_lines"]
    withheld = loader.file_text("letter.withheld")
    assert withheld in part(lettered, "note_lines").text and withheld not in part(listed, "note_lines").text
    assert part(lettered, "frame").file == "letter.frame.txt" and part(listed, "frame").file == "referrals.frame.txt"


def answered(room, query="Made-up condition A; Made-up condition B", stored_query=None):
    outcome = summary.summarise(room.door, query, SENT, room.model_patient, consultation_id=room.cid)
    room.sources.add_answer(AnswerRow(room.cid, 1, ["Made-up condition A", "Made-up condition B"], stored_query or query, SENT, 2, 0.7,
                                      0.45, False, outcome.outcome, outcome.call_id, outcome.covered, outcome.summary,
                                      outcome.cited, outcome.invalid, None, 42, outcome.wall_ms, True))
    return outcome


def test_ruling_11_the_guideline_call_reads_back_from_the_names_the_query_and_the_passages_with_their_sources(room):
    answered(room)
    found = room.seen()[0]
    assert (found.kind, found.taken_apart, found.reason) == ("guideline", True, None)
    assert found.name == {"kind": "guideline", "pass_n": 1, "search_ms": 42, "referenced": True}
    assert sources_of(found) == ["patient_line", "frame", "query", "passages"]
    assert part(found, "query").text == "Made-up condition A; Made-up condition B"
    assert part(found, "passages").items == SENT and part(found, "passages").text == summary.passages_text(SENT)
    assert found.user_text == summary.message(part(found, "query").text, SENT, room.model_patient)
    assert found.answer == json.dumps(COVERED)


def hand_made(room, job="alarm", request="", reply=None, prompt_sha256=None):
    row = CallRow(job, "made-up", "0.0-made-up", "made-up/tag", "d",
                  prompt_sha256 or loader.sha256(loader.prompt(job)) if job in jobs.JOBS else prompt_sha256 or "0" * 64,
                  request, reply, None, None, 5, None, None, None, None, "ok", None, room.cid)
    call_id = room.record.add(row)
    room.tick()
    return call_id


def test_rule_5_a_request_the_reader_cannot_take_apart_is_shown_whole_with_its_reason(room):
    line = patient_line(35, "F")
    hand_made(room, request="not json")
    hand_made(room, request=json.dumps({"messages": [{"role": "system", "content": "x"}]}))
    hand_made(room, request=json.dumps({"job": "alarm", "user": "The patient is a 99-year-old man.\n\n" + alarm_message(TRANSCRIPT)}))
    hand_made(room, request=json.dumps({"job": "alarm", "user": f"{line}\n\nLIVE TRANSCRIPT SO FAR\n{TRANSCRIPT}"}))
    hand_made(room, job="made", request=json.dumps({"job": "made", "user": "made text"}))
    answered(room, stored_query="another query")
    found = room.seen()
    assert [(c.taken_apart, c.reason, c.parts) for c in found] == [(False, reason, []) for reason in (
        seen.NOT_JSON, seen.NO_USER_TEXT, seen.NO_PATIENT_LINE, seen.FRAME_NOT_FOUND, seen.UNKNOWN_JOB, seen.REBUILD_DIFFERS)]
    assert found[0].user_text == "not json" and found[1].user_text == json.dumps({"messages": [{"role": "system", "content": "x"}]})
    assert found[2].user_text.startswith("The patient is a 99-year-old man.") and found[3].user_text.startswith(line)
    assert found[4].name == {"kind": "made", "referenced": False} and found[4].user_text == "made text"
    assert found[5].user_text == summary.message("Made-up condition A; Made-up condition B", SENT, room.model_patient)


def test_R20_15_8_ruling_1_every_call_gives_its_model_and_version_and_the_prompt_by_name_and_hash_never_its_text(room, monkeypatch):
    room.a_pass(1)
    hand_made(room, job="assessment", request=json.dumps({"job": "assessment", "user": "x"}), prompt_sha256="0" * 64)
    monkeypatch.setitem(jobs.JOBS, "renamed", jobs.Job("renamed", "made_up_renamed", "alarm", ("alarm",), 10, 1.0, ""))
    hand_made(room, job="renamed", request=json.dumps({"job": "renamed", "user": "x"}), prompt_sha256="1" * 64)
    hand_made(room, job="unknown", request=json.dumps({"job": "unknown", "user": "x"}), prompt_sha256="2" * 64)
    # A request that holds a prompt and no user text is shown with the prompt's words replaced (15.8 ruling 1).
    hand_made(room, request=json.dumps({"messages": [{"role": "system", "content": loader.prompt("alarm")}]}))
    alarm, assessment, differs, renamed, unknown, withheld = settled(room.seen())
    for found in (alarm, assessment):     # R20: the call's own row, not the consultation's
        assert (found.call["model_tag"], found.call["engine"], found.call["engine_version"]) == (room.door.profile.tag, "made-up", "0.0-made-up")
    assert alarm.prompt == {"name": "alarm.prompt.txt", "hash": loader.sha256(loader.prompt("alarm")), "today": seen.SAME}
    assert assessment.prompt == {"name": "assessment.prompt.txt", "hash": loader.sha256(loader.prompt("assessment")), "today": seen.SAME}
    assert differs.prompt == {"name": "assessment.prompt.txt", "hash": "0" * 64, "today": seen.DIFFERS}
    assert renamed.prompt == {"name": "made_up_renamed.prompt.txt", "hash": "1" * 64, "today": seen.NONE}
    assert unknown.prompt == {"name": None, "hash": "2" * 64, "today": seen.NONE}
    assert withheld.user_text == json.dumps({"messages": [{"role": "system", "content": seen.PROMPT_WITHHELD}]})
    for found in (alarm, assessment, differs, renamed, unknown, withheld):
        everything = json.dumps(asdict(found))
        for name in ("alarm", "assessment", "label_check", "note", "referrals", "letter", "guideline"):
            assert loader.prompt(name).split("\n")[0] not in everything


def test_ruling_28_every_call_of_a_consultation_is_found_by_its_row_in_time_order_and_an_unreferenced_call_is_shown_as_such(room):
    room.a_pass(1)
    room.a_pass(2, Carried(names=("Made-up condition A",)))
    answered(room)
    room.tick()
    room.lines()
    labels.run(room.door, ROWS, room.cid)
    room.tick()
    draft = note.draft(room.door, room.consultations, room.notes, room.audit, room.cid, "stop")
    room.notes.approve(room.cid, draft["id"], note.plain_text(room.notes.entries(draft["id"])))
    room.tick()
    # A list whose call failed is dropped when the list is made again (letter_rows): its call stands with no row.
    dropped = hand_made(room, job="referrals", request=json.dumps({"job": "referrals", "user": "x"}))
    list_id = room.letters.add_list(ListRow(room.cid, room.notes.approval(room.cid)["id"], dropped, "", None, "too_slow: made", 5))
    room.letters.drop_failed_list(list_id)
    referrals.make_list(room.door, room.letters, room.notes, room.consultations, room.audit, room.cid)
    room.tick()
    item = room.letters.items(room.cid)[0]
    letter.draft(room.door, room.letters, room.notes, room.consultations, room.audit, room.cid, item)
    raw = room.seen()
    assert [c.call["id"] for c in raw] == sorted(c.call["id"] for c in raw)      # by at, then id
    found = settled(raw)
    assert [(c.kind, c.name["referenced"]) for c in found] == [
        ("alarm", True), ("assessment", True), ("alarm", True), ("assessment", True), ("guideline", True),
        ("label_check", False), ("note", True), ("referrals", False), ("referrals", True), ("letter", True)]
    ats = [c.call["at"] for c in found]
    assert ats == sorted(ats)
    assert found[7].call["id"] == dropped and found[7].taken_apart is False and found[7].reason == seen.NO_PATIENT_LINE
    assert all(c.taken_apart for k, c in enumerate(found) if k != 7)
    # The order is by the moment: a stamp with the summer offset before one with the winter offset the same morning.
    winter = hand_made(room, request=json.dumps({"job": "alarm", "user": "x"}))
    room.record._db.execute("UPDATE model_call SET at = '2026-10-25T01:30:00.000+00:00' WHERE id = ?", (winter,))
    summer = hand_made(room, request=json.dumps({"job": "alarm", "user": "x"}))
    room.record._db.execute("UPDATE model_call SET at = '2026-10-25T01:45:00.000+01:00' WHERE id = ?", (summer,))
    assert [c.call["id"] for c in room.seen()][-2:] == [summer, winter]
    # A consultation that is not final yet has no view (ruling 28).
    room.consultations.set(room.cid, state="stopping")
    assert room.seen() == []
