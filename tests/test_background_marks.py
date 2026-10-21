"""The marks of the background bench on made results (spec 8.6; 15.11
ruling 6; 5.2: the scoring is a plain function over stored results, and
what a model says is never asserted). Every chain here is made up."""

import json

import pytest

from openconsult.bench import background as marks
from openconsult.bench.writer import ResultWriter


def a_pass(actions=(), differentials=(), alarm_failure=None, assessment_failure=None, wall_ms=3000):
    return {"point": 4, "wall_ms": wall_ms,
            "alarm": {"actions": list(actions), "failure": alarm_failure},
            "assessment": {"differentials": [{"condition": d} for d in differentials], "failure": assessment_failure}}


def chain(name, passes, failed=None):
    return {"case": "made", "chain": name, "passes": passes, "failed": failed}


ACT = ({"action": "made-up step", "reason": "made up"},)


def made_results(case, fired, hypo, sah=0, n=13):
    """n made chains of one case: the first `fired` fire, the first `hypo`
    name hypoglycaemia third, the first `sah` name subarachnoid."""
    found = {}
    for i in range(n):
        names = ["Made-up A", "Made-up B", "Hypoglycaemia" if i < hypo else "Made-up C", "Made-up D"]
        if i < sah:
            names[0] = "Subarachnoid hemorrhage"
        found[(case, f"C{i}")] = chain(f"C{i}", [a_pass(ACT if i < fired else (), ["Made-up A"]), a_pass((), names)])
    return found


def test_ruling_6_the_scoring_counts_fired_named_and_both_on_made_results():
    # Fired: the actions after bookkeeping, at any pass.
    assert marks.fired(chain("x", [a_pass(), a_pass(ACT), a_pass()]))
    assert not marks.fired(chain("x", [a_pass(), a_pass()])) and not marks.fired(chain("x", []))
    # The top three at the last pass only.
    late = chain("x", [a_pass((), ["Hypoglycaemia"]), a_pass((), ["Made-up A", "Made-up B", "Made-up C", "Hypoglycaemia"])])
    assert marks.top_three(late) == ["Made-up A", "Made-up B", "Made-up C"] and not marks.names(late, marks.HYPOGLYCAEMIA)
    for name in ("Hypoglycaemia", "hypoglycemia", "Hypoglycaemic episode", "Low blood sugar (hypo)", "low blood glucose"):
        assert marks.names_match(name, marks.HYPOGLYCAEMIA), name
    for name in ("Hypo", "Hyperglycaemia", "Diabetic ketoacidosis", "", "hypoglycaemias"):
        assert not marks.names_match(name, marks.HYPOGLYCAEMIA), name
    assert marks.names_match("Subarachnoid hemorrhage", marks.SUBARACHNOID) and marks.names_match("SAH (subarachnoid haemorrhage)", marks.SUBARACHNOID)
    assert not marks.names_match("Migraine", marks.SUBARACHNOID)
    # A chain with a failed call is counted on what was stored and listed by name.
    failed = chain("B3", [a_pass(ACT, ["Hypoglycaemia"], assessment_failure="too_slow")])
    assert marks.had_a_failed_call(failed) and marks.fired(failed) and marks.names(failed, marks.HYPOGLYCAEMIA)
    assert marks.had_a_failed_call(chain("B4", [a_pass()], failed="the engine was unreachable"))
    table = marks.arm_table({("made", "B3"): failed, ("made", "A1"): chain("A1", [a_pass(wall_ms=1000), a_pass(ACT, ["Low blood sugar"], wall_ms=5000)])}, "made")
    assert table == {"chains": 2, "failed_call": ["B3"], "fired": 2, "named_hypoglycaemia": 2, "both": 2,
                     "named_subarachnoid": 0, "pass_s": 3.0}
    assert marks.arm_table({}, "made") == {"chains": 0, "failed_call": [], "fired": 0, "named_hypoglycaemia": 0, "both": 0,
                                           "named_subarachnoid": 0, "pass_s": None}


def test_ruling_6_the_four_marks_are_held_and_missed_on_made_tables(tmp_path):
    held = marks.score({**made_results("A_hypo", 13, 12), **made_results("B_headache", 13, 0, sah=11)},
                       {**made_results("A_hypo", 13, 5), **made_results("B_headache", 13, 0, sah=9)})
    assert held["held"] and [m["held"] for m in held["marks"]] == [True, True, True, True]
    assert held["cases"]["A_hypo"]["with"]["both"] == 12 and held["cases"]["A_hypo"]["without"]["both"] == 5
    assert held["cases"]["B_headache"]["with"]["named_subarachnoid"] == 11
    assert [m["mark"] for m in held["marks"]] == ["A1", "A2", "B1", "B2"]
    # A1 missed at 11; A2 missed when without is not fewer; B1 and B2 missed at 12; a 12-chain arm meets no mark.
    missed = marks.score({**made_results("A_hypo", 13, 11), **made_results("B_headache", 12, 0)},
                         {**made_results("A_hypo", 13, 11), **made_results("B_headache", 13, 0, n=12)})
    assert not missed["held"] and [m["held"] for m in missed["marks"]] == [False, False, False, False]
    text = marks.as_markdown(held)
    assert "| A_hypo | with | 13 | none | 13 | 12 | 12 | 0 |" in text and "Mark A1" in text and "held" in text
    assert "MISSED" in marks.as_markdown(missed) and "Every mark did not hold" in marks.as_markdown(missed)
    with pytest.raises(marks.MarksRefused):
        marks.score(made_results("A_hypo", 13, 12), made_results("A_hypo", 13, 5))       # case B missing
    # Written once, never over.
    marks.write(tmp_path / "marks", held)
    assert json.loads((tmp_path / "marks" / "marks.json").read_text(encoding="utf-8"))["held"] is True
    assert (tmp_path / "marks" / "marks.md").read_text(encoding="utf-8") == text
    with pytest.raises(marks.MarksRefused):
        marks.write(tmp_path / "marks", held)


def test_ruling_6_background_score_writes_the_tables_once_and_exits_by_the_marks(tmp_path):
    from openconsult.bench.cli import main
    folders = {}
    for arm, hypo in (("with", 12), ("without", 4)):
        writer = ResultWriter(tmp_path / arm)
        for (case, name), result in {**made_results("A_hypo", 13, hypo), **made_results("B_headache", 13, 0)}.items():
            writer.write(case, name, result)
        folders[arm] = str(tmp_path / arm)
    assert main(["background-score", "--with", folders["with"], "--without", folders["without"], "--write", str(tmp_path / "out")]) == 0
    assert (tmp_path / "out" / "marks.md").exists()
    assert main(["background-score", "--with", folders["with"], "--without", folders["without"], "--write", str(tmp_path / "out")]) == 6
    # A2 missed: the arm without names as many as the arm with.
    assert main(["background-score", "--with", folders["with"], "--without", folders["with"], "--write", str(tmp_path / "out2")]) == 1
