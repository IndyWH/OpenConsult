"""The timeline's figures (spec 15.12, ruling 28): the typical pass, the
long mark, the averages per kind, the bars against the clock, the calls
after final and the final line's figures. Made rows; no app, no model."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from openconsult.consult import stop, timeline
from openconsult.patients.audit import Line

START = datetime(2026, 10, 4, 9, 0, tzinfo=timezone.utc)


def at(seconds: float) -> str:
    return (START + timedelta(seconds=seconds)).isoformat(timespec="milliseconds")


def a_pass(n: int, end_s: float, seconds: float, shown=True) -> dict:
    return {"n": n, "at": at(end_s), "result": {"wall_ms": round(seconds * 1000)}, "shown": shown}


def a_call(call_id: int, job: str, end_s: float, seconds: float, outcome="ok") -> dict:
    return {"id": call_id, "job": job, "at": at(end_s), "wall_ms": round(seconds * 1000), "outcome": outcome}


def test_ruling_28_the_typical_pass_is_the_median_and_a_pass_over_twice_it_is_marked_long():
    passes = [a_pass(1, 10, 1.0), a_pass(2, 20, 1.0), a_pass(3, 30, 1.0), a_pass(4, 40, 1.0), a_pass(5, 50, 3.0)]
    assert timeline.typical_pass_s(passes) == 1.0
    marks = timeline.pass_marks(passes, at(0), 60.0)
    assert [(m["n"], m["long"], m["seconds"]) for m in marks] == [(1, False, 1.0), (2, False, 1.0), (3, False, 1.0), (4, False, 1.0), (5, True, 3.0)]
    assert marks[4] == {"n": 5, "start_s": 47.0, "end_s": 50.0, "seconds": 3.0, "long": True, "left": 0.7833, "width": 0.05}
    # Exactly twice is not long; one pass is never long; no pass gives no typical pass; a pass not shown still counts.
    assert not timeline.is_long(2.0, 1.0) and timeline.is_long(2.01, 1.0)
    assert timeline.typical_pass_s([a_pass(1, 10, 9.0)]) == 9.0 and not timeline.pass_marks([a_pass(1, 10, 9.0)], at(0), 60.0)[0]["long"]
    assert timeline.typical_pass_s([]) is None and timeline.pass_marks([], at(0), 60.0) == []
    assert timeline.typical_pass_s([a_pass(1, 10, 1.0), a_pass(2, 20, 4.0, shown=False)]) == 2.5
    # The same figure the final line gives: stop.figures takes the same median over the same rows.
    rows = SimpleNamespace(live_lines=lambda cid: [], passes=lambda cid: passes)
    stand_in = SimpleNamespace(rows=rows, id=1, clock=lambda: START + timedelta(seconds=70), stopped_at=START + timedelta(seconds=60))
    assert stop.figures(stand_in)["pass_s"] == timeline.typical_pass_s(passes) == 1.0


def test_ruling_28_the_averages_per_kind_the_bars_against_the_clock_and_the_calls_after_final():
    row = {"id": 7, "started_at": at(0), "stopped_at": at(60), "final_at": at(100)}
    calls = [a_call(1, "alarm", 10, 1.0), a_call(2, "assessment", 12, 3.0), a_call(3, "guideline", 14, 0.5),
             a_call(4, "alarm", 50, 1.0, "too_slow"), a_call(5, "assessment", 52, 5.0),
             a_call(6, "label_check", 70, 2.0), a_call(7, "note", 95, 4.0),
             a_call(8, "referrals", 100 + 45, 1.0), a_call(9, "letter", 100 + 3700, 2.0), a_call(10, "note", 100 + 2 * 86400 + 5, 4.0)]
    passes = [a_pass(1, 12, 3.0), a_pass(2, 52, 5.0)]
    audit = [Line(at(300), "consultation.final", "consultation 8: other"), Line(at(100), "consultation.final", "consultation 7: made figures"),
             Line(at(60), "consultation.stopped", "consultation 7")]
    found = timeline.band(row, calls, passes, audit)
    assert (found["length_s"], found["stop_s"], found["stop_left"]) == (100.0, 60.0, 0.6)
    assert found["rows"] == ["alarm", "assessment", "guideline", "label_check", "note"]
    assert [b["call_id"] for b in found["bars"]] == [1, 2, 3, 4, 5, 6, 7]
    assert found["bars"][1] == {"call_id": 2, "kind": "assessment", "start_s": 9.0, "end_s": 12.0, "seconds": 3.0, "outcome": "ok",
                                "at": at(12), "left": 0.09, "width": 0.03}
    assert found["bars"][3]["outcome"] == "too_slow"
    assert [(a["call_id"], a["lead"]) for a in found["after_final"]] == [(8, (45, "seconds")), (9, (1, "hours")), (10, (2, "days"))]
    assert timeline.lead(59.9) == (59, "seconds") and timeline.lead(60) == (1, "minutes") and timeline.lead(3599) == (59, "minutes")
    assert timeline.lead(86399) == (23, "hours") and timeline.lead(86400) == (1, "days")
    # The averages: the mean per kind with failed calls counted in, the slowest, in the band's order then as seen.
    assert found["averages"] == [
        {"kind": "alarm", "count": 2, "failed": 1, "mean_s": 1.0, "slowest_s": 1.0},
        {"kind": "assessment", "count": 2, "failed": 0, "mean_s": 4.0, "slowest_s": 5.0},
        {"kind": "guideline", "count": 1, "failed": 0, "mean_s": 0.5, "slowest_s": 0.5},
        {"kind": "label_check", "count": 1, "failed": 0, "mean_s": 2.0, "slowest_s": 2.0},
        {"kind": "note", "count": 2, "failed": 0, "mean_s": 4.0, "slowest_s": 4.0},
        {"kind": "referrals", "count": 1, "failed": 0, "mean_s": 1.0, "slowest_s": 1.0},
        {"kind": "letter", "count": 1, "failed": 0, "mean_s": 2.0, "slowest_s": 2.0}]
    assert (found["typical_pass_s"], found["long_passes"]) == (4.0, [])
    assert [(p["n"], p["left"], p["width"]) for p in found["passes"]] == [(1, 0.09, 0.03), (2, 0.47, 0.05)]
    # The final line's figures, this consultation's own; its absence said.
    assert found["final_line"] == "made figures"
    assert timeline.band(row, [], [], audit[:1])["final_line"] is None
    assert timeline.band(row, [], [], [])["averages"] == [] and timeline.band(row, [], [], [])["rows"] == []
