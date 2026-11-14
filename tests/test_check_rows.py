"""The rows of the build at Stop (spec 15.10, rulings 18, 19 and 24 and the
details of step 6c: The record, Undo, A mark). Made-up lines; no model."""

import pytest

from openconsult.consult.consultations import Consultations
from openconsult.db import open_database


@pytest.fixture
def rows(tmp_path, clock):
    db = open_database(tmp_path / "openconsult.db")
    db.execute("INSERT INTO patient (name, date_of_birth, sex, created_at) VALUES ('Made-up Patient', '1990-01-01', 'F', 't')")
    found = Consultations(db, clock)
    cid = found.start(1, 15, "nemotron", "vllm", "0", "tag", None, 2)
    found.add_transcript_lines(cid, [
        {"n": n, "start_s": float(n), "end_s": n + 0.5, "text": f"made up {n}", "raw_speaker": speaker, "label": label}
        for n, speaker, label in ((1, "S1", "doctor"), (2, "S2", "patient"), (3, None, "unsure"), (4, "S1", "doctor"))])
    yield found, cid
    db.close()


def labels_of(found, cid):
    return [(r["n"], r["label"], r["changed_by_check"], r["unsure"], r["set_by_doctor"]) for r in found.transcript_lines(cid)]


def test_6c_a_run_ends_all_at_once_with_its_changes_its_counts_and_the_edit_of_kind_check_only_when_a_line_was_marked(rows):
    found, cid = rows
    run = found.add_check_run(cid, parts=2, joined_lines=3)
    assert [(r["outcome"], r["parts"], r["joined_lines"], r["ended_at"]) for r in found.check_runs(cid)] == [("running", 2, 3, None)]
    assert [r["id"] for r in found.running_checks()] == [run]
    # A run that marks nothing writes no edit of kind check (the plan review of 6c, point 2); its row keeps the counts.
    found.end_check_run(run, "answered", call_ids=[7, 8], labels={3: {"label": "patient", "changed_by_check": False, "unsure": True}},
                        changes=[], no_first_reading=1, named_twice=2, dropped=1)
    first = found.check_runs(cid)[0]
    assert (first["outcome"], first["call_ids"], first["changed"], first["no_first_reading"], first["named_twice"], first["dropped"]) == (
        "answered", [7, 8], 0, 1, 2, 1)                                             # ruling 24: the two counts kept with the run
    assert first["ended_at"] is not None and found.transcript_edits(cid) == [] and found.running_checks() == []
    assert labels_of(found, cid)[2] == (3, "patient", 0, 1, 0)
    # A run that marks lines: the labels, one change row a line, one edit row of kind check, the run's end (ruling 18).
    second = found.add_check_run(cid, 1, 4)
    found.end_check_run(second, "answered", call_ids=[9], named_twice=0, dropped=0, changes=[(1, "doctor", "patient"), (2, "patient", "doctor")],
                        labels={1: {"label": "patient", "changed_by_check": True, "unsure": False},
                                2: {"label": "doctor", "changed_by_check": True, "unsure": False}})
    assert labels_of(found, cid)[:2] == [(1, "patient", 1, 0, 0), (2, "doctor", 1, 0, 0)]
    assert [(e["kind"], e["line_n"], e["after"]) for e in found.transcript_edits(cid)] == [("check", None, "2")]
    assert [(c["line_n"], c["label_before"], c["label_after"], c["undone_at"]) for c in found.check_changes(second)] == [
        (1, "doctor", "patient", None), (2, "patient", "doctor", None)]
    assert found.check_runs(cid)[1]["changed"] == 2 and sorted(found.standing_changes(cid)) == [1, 2]
    # A failed or refused run ends with its reason and changes nothing; an end that is not one is refused.
    third = found.add_check_run(cid, 1, 4)
    found.end_check_run(third, "refused", reason="missing 4", call_ids=[10], named_twice=0, dropped=0)
    assert (found.check_runs(cid)[2]["outcome"], found.check_runs(cid)[2]["reason"]) == ("refused", "missing 4")
    assert len(found.transcript_edits(cid)) == 1 and labels_of(found, cid)[:2] == [(1, "patient", 1, 0, 0), (2, "doctor", 1, 0, 0)]
    with pytest.raises(ValueError):
        found.end_check_run(third, "running")


def test_6c_undo_puts_back_the_label_before_also_after_a_swap_and_a_swap_is_not_a_setting_of_one_line(rows):
    found, cid = rows
    run = found.add_check_run(cid, 1, 4)
    found.end_check_run(run, "answered", changes=[(1, "doctor", "patient"), (4, "doctor", "patient")], named_twice=0, dropped=0,
                        labels={1: {"label": "patient", "changed_by_check": True, "unsure": False},
                                4: {"label": "patient", "changed_by_check": True, "unsure": False}})
    assert found.undo_change(cid, 2) is None                                        # no change of a check stands on line 2
    assert found.undo_change(cid, 1) == "doctor" and labels_of(found, cid)[0] == (1, "doctor", 0, 0, 1)
    assert sorted(found.standing_changes(cid)) == [4] and found.check_changes(run)[0]["undone_at"] is not None
    assert found.undo_change(cid, 1) is None                                        # once
    # A Swap exchanges the labels as they stand, and the stored label before with them: Undo after it is still right.
    found.swap_labels(cid)
    assert labels_of(found, cid)[3][:2] == (4, "doctor") and found.standing_changes(cid)[4]["label_before"] == "patient"
    assert found.undo_change(cid, 4) == "patient" and labels_of(found, cid)[3][:3] == (4, "patient", 0)
    assert [e["kind"] for e in found.transcript_edits(cid)] == ["check", "undo", "swap", "undo"]
    # The lines set one by one are those of the edits of kind label: not a Swap, not an Undo (ruling 19, detail one).
    assert found.lines_set_one_by_one(cid) == set()
    found.set_line_label(cid, 2, "doctor")
    assert found.lines_set_one_by_one(cid) == {2}


def test_6c_a_mark_is_stored_with_its_places_found_in_the_order_of_the_page_and_a_cleared_mark_stays_in_the_record(rows):
    found, cid = rows
    assert found.drug_call(cid) is None and found.drug_marks(cid) == []
    call = found.add_drug_call(cid, None, "answered", None, kept=2, dropped=1)
    assert (found.drug_call(cid)["outcome"], found.drug_call(cid)["kept"], found.drug_call(cid)["dropped"]) == ("answered", 2, 1)
    late = found.add_drug_mark(cid, call, 2, "made up 4", "a made-up drug", [3, 4], [{"line": 4, "first": 0, "last": 9}])
    early = found.add_drug_mark(cid, call, 1, "up 1 made", "", [1, 2], [{"line": 1, "first": 5, "last": 9}, {"line": 2, "first": 0, "last": 4}])
    marks = found.drug_marks(cid)
    assert [(m["id"], m["first_line"], m["page_lines"], m["heard"], m["meant"]) for m in marks] == [
        (early, 1, [1, 2], "up 1 made", ""), (late, 4, [3, 4], "made up 4", "a made-up drug")]
    found.set_mark_places(late, [{"line": 3, "first": 2, "last": 6}])
    assert found.drug_marks(cid)[1]["first_line"] == 3 and found.drug_marks(cid)[1]["places"] == [{"line": 3, "first": 2, "last": 6}]
    found.clear_mark(early)
    assert [m["id"] for m in found.drug_marks(cid)] == [late]
    kept = found.drug_marks(cid, every=True)
    assert [m["id"] for m in kept] == [early, late] and kept[0]["cleared_at"] is not None and kept[0]["meant"] == ""
