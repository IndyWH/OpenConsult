"""The tables of teaching, version 14, and their rows (spec 15.14, ruling
22 and the details of run 10b: Where teaching lives, Kept cases; 6.5;
R15; R24). Every scenario and every line here is made up; no model is
asked."""

import sqlite3

import pytest

from openconsult import schema
from openconsult.db import open_database
from openconsult.llm.record import CallRow, ModelCalls
from openconsult.teaching import cases as cases_module
from openconsult.teaching.cases import Cases
from tests.made_teaching import FEEDBACK_OK, SCENARIO

TABLES = {"teaching_case", "teaching_turn", "teaching_examined", "teaching_call", "teaching_flag"}


def made_call(record: ModelCalls, job: str, consultation_id=None) -> int:
    return record.add(CallRow(job=job, engine="made-up", engine_version="0", model_tag="made", model_digest="d", prompt_sha256="p",
                              request="{}", reply="{}", prompt_tokens=1, output_tokens=1, wall_ms=1, total_ms=1, load_ms=0,
                              read_ms=0, write_ms=1, outcome="ok", detail=None, consultation_id=consultation_id))


def rows_of(db, tables) -> dict:
    return {table: [tuple(row) for row in db.query(f"SELECT * FROM {table} ORDER BY 1")] for table in sorted(tables)}


@pytest.fixture
def db(tmp_path):
    made = open_database(tmp_path / "openconsult.db")
    yield made
    made.close()


def played(cases: Cases, record: ModelCalls, press: str = "press-1") -> int:
    """One made case from its start to its feedback, every call tied."""
    case_id = cases.start(press, "bank", "A made-up topic", "straightforward", "script", "this_computer", SCENARIO, bank_number=1)
    for line, (doctor, reply) in enumerate([("first line", "first reply"), ("second line", "second reply")], 1):
        cases.tie(case_id, made_call(record, "teaching_patient"))
        assert cases.add_exchange(case_id, line, doctor, reply, [1])
    assert cases.end_history(case_id)
    cases.tie(case_id, made_call(record, "teaching_examination"))
    assert cases.add_examined(case_id, 1, "examine one", [1], ["a made-up elbow"])
    assert cases.finish_examination(case_id)
    for question, text in enumerate(["answer one", "answer two", "answer three"], 1):
        assert cases.answer(case_id, question, text)
    cases.tie(case_id, made_call(record, "teaching_feedback"))
    assert cases.fed_back(case_id, FEEDBACK_OK)
    return case_id


def test_6_5_a_folder_of_version_13_comes_forward_to_14_and_no_older_row_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(schema, "VERSION", 13)
    old = open_database(tmp_path / "openconsult.db")
    assert old.version() == 13 and not TABLES & set(old.tables())
    made_call(ModelCalls(old), "alarm")
    old.execute("INSERT INTO audit_log (at, event, detail) VALUES ('2026-11-24T10:00:00+00:00', 'made.event', 'made detail')")
    old.execute("INSERT INTO setting (name, value, changed_at) VALUES ('made_setting', 'made', '2026-11-24T10:00:00+00:00')")
    older = set(old.tables())
    before = rows_of(old, older - {"schema_version"})
    old.close()
    monkeypatch.setattr(schema, "VERSION", 14)
    new = open_database(tmp_path / "openconsult.db")
    assert new.version() == 14 and set(new.tables()) == older | TABLES
    assert rows_of(new, older - {"schema_version"}) == before                       # version 14 only creates
    assert all(new.query(f"SELECT COUNT(*) AS n FROM {table}")[0]["n"] == 0 for table in TABLES)
    new.close()


def test_15_14_ruling_22_a_case_is_saved_as_it_happens_and_read_back_as_it_was(db, clock):
    cases, record = Cases(db, clock), ModelCalls(db, clock)
    case_id = played(cases, record)
    row = cases.get(case_id)
    assert (row["source"], row["bank_number"], row["topic"], row["level"], row["label"], row["language_model"], row["step"]) == (
        "bank", 1, "A made-up topic", "straightforward", "script", "this_computer", "done")
    assert row["scenario"] == SCENARIO and row["feedback"] == FEEDBACK_OK and row["finished_at"] and row["failure"] is None
    assert cases.answers(row) == {"differential": "answer one", "investigations": "answer two", "plan": "answer three"}
    # The turns as the bench numbered them: the learner's first line is turn 1, and its reply turn 2.
    assert [(t["n"], t["speaker"], t["text"]) for t in cases.turns(case_id)] == [
        (1, "doctor", "first line"), (2, "patient", "first reply"), (3, "doctor", "second line"), (4, "patient", "second reply")]
    assert cases.conversation(case_id)[0] == ("doctor", "first line") and cases.turns(case_id)[1]["facts_used"] == "[1]"
    assert [(e["n"], e["text"], e["asked"], e["not_in_case"]) for e in cases.examined(case_id)] == [(1, "examine one", [1], ["a made-up elbow"])]
    assert len(cases.calls(case_id)) == 4
    assert [(c["id"], c["step"]) for c in cases.listed()] == [(case_id, "done")] and "scenario" not in cases.listed()[0]
    # A fresh case has no scenario until it is written; a reason is kept while it stands at its step.
    fresh = cases.start("press-2", "fresh", "Another made-up topic", "hidden", "ai", "claude")
    assert cases.get(fresh)["step"] == "writing" and cases.get(fresh)["scenario"] is None
    cases.failed(fresh, "writing", "too_slow")
    assert cases.get(fresh)["failure"] == "too_slow"
    cases.trying(fresh, "writing")
    assert cases.get(fresh)["failure"] is None and cases.written(fresh, SCENARIO)
    assert cases.get(fresh)["step"] == "history" and cases.get(fresh)["scenario"] == SCENARIO
    assert [c["id"] for c in cases.listed()] == [fresh, case_id]                     # newest first


def test_R15_the_same_press_twice_is_one_case_and_a_stale_press_changes_nothing(db, clock):
    cases = Cases(db, clock)
    first = cases.start("press-1", "bank", "A made-up topic", "straightforward", "script", "this_computer", SCENARIO, 1)
    assert cases.start("press-1", "bank", "A made-up topic", "straightforward", "script", "this_computer", SCENARIO, 1) == first
    assert len(cases.listed()) == 1
    # A line is stored only as the next line: the same line a second time, or one from an older page, is not.
    assert cases.add_exchange(first, 1, "first line", "first reply", [])
    assert not cases.add_exchange(first, 1, "first line", "first reply", []) and not cases.add_exchange(first, 3, "late", "late", [])
    assert len(cases.turns(first)) == 2
    # One way: each move only from its own step, each once.
    assert not cases.finish_examination(first) and not cases.answer(first, 1, "early") and not cases.fed_back(first, FEEDBACK_OK)
    assert cases.end_history(first) and not cases.end_history(first)
    assert not cases.add_exchange(first, 2, "after the end", "never", []) and len(cases.turns(first)) == 2
    assert cases.add_examined(first, 1, "examine one", [1], []) and not cases.add_examined(first, 1, "examine one", [1], [])
    assert cases.finish_examination(first) and not cases.add_examined(first, 2, "late", [], [])
    assert not cases.answer(first, 2, "out of turn") and cases.answer(first, 1, "one") and not cases.answer(first, 1, "one again")
    assert cases.answer(first, 2, "two") and cases.answer(first, 3, "three") and cases.get(first)["step"] == "feedback"
    assert cases.flag(first, "too early") is None                                    # a case is flagged once it is finished
    assert cases.fed_back(first, FEEDBACK_OK) and not cases.fed_back(first, {"another": "answer"})
    assert cases.get(first)["feedback"] == FEEDBACK_OK and cases.get(first)["answer_differential"] == "one"
    assert cases.flag(first, "") is not None and cases.flag(first, "a second flag") is None and len(cases.flags()) == 1


def test_15_14_ruling_22_a_delete_takes_every_row_and_model_call_of_the_case_in_one_go_and_nothing_else(db, clock):
    cases, record = Cases(db, clock), ModelCalls(db, clock)
    clinic_call = made_call(record, "alarm")                                         # a call of the clinic: never touched
    gone, kept = played(cases, record, "press-1"), played(cases, record, "press-2")
    flag = cases.flag(gone, "a made-up note")
    kept_rows = (cases.get(kept), cases.turns(kept), cases.examined(kept), cases.calls(kept))
    counts = cases.delete(gone)
    assert counts == {"turns": 4, "examination_requests": 1, "answers": 3, "feedback": 1, "model_calls": 4, "flags_kept": 1,
                      "date": "2026-10-04"}
    assert cases.get(gone) is None and cases.turns(gone) == [] and cases.examined(gone) == [] and cases.calls(gone) == []
    assert (cases.get(kept), cases.turns(kept), cases.examined(kept), cases.calls(kept)) == kept_rows
    assert sorted(row["id"] for row in record.rows()) == sorted([clinic_call, *cases.calls(kept)])
    # The flag stays with its scenario and the learner's note, and points to no case (12.3, rule 7).
    held = cases.flag_row(flag)
    assert (held["case_id"], held["note"], held["scenario"], held["topic"], held["level"], held["label"]) == (
        None, "a made-up note", SCENARIO, "A made-up topic", "straightforward", "script")
    assert cases.delete(gone) is None                                                # a second delete removes nothing
    assert cases.remove_flag(flag) and not cases.remove_flag(flag) and cases.flags() == []


def test_15_14_ruling_22_a_delete_that_fails_in_the_middle_leaves_everything(db, clock):
    cases, record = Cases(db, clock), ModelCalls(db, clock)
    case_id = played(cases, record)
    before = rows_of(db, TABLES | {"model_call"})
    db.execute("CREATE TRIGGER made_failure BEFORE DELETE ON teaching_case BEGIN SELECT RAISE(ABORT, 'made-up failure'); END;")
    with pytest.raises(sqlite3.DatabaseError):
        cases.delete(case_id)
    assert rows_of(db, TABLES | {"model_call"}) == before and cases.get(case_id)["step"] == "done"


def test_15_14_the_steps_and_the_three_answers_are_the_ones_the_tables_hold(db):
    # The words of a step, a level, a label and a source are checked by the tables themselves.
    made = "INSERT INTO teaching_case (press, started_at, source, topic, level, label, language_model, step) VALUES (?, 'now', ?, 't', ?, ?, ?, ?)"
    for n, values in enumerate([("another", "hidden", "ai", "claude", "history"), ("bank", "easy", "ai", "claude", "history"),
                                ("bank", "hidden", "reviewed", "claude", "history"), ("bank", "hidden", "ai", "ollama", "history"),
                                ("bank", "hidden", "ai", "claude", "paused")]):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(made, (f"press-{n}", *values))
    assert cases_module.STEPS == ("writing", "history", "examination", "question_1", "question_2", "question_3", "feedback", "done")
    assert cases_module.ANSWERS == ("differential", "investigations", "plan")
