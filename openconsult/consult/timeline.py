"""The timeline at the head of the what-the-model-saw view (spec 15.12,
ruling 28): every call drawn in time order from Start to final against
the clock, the passes marked, the seconds of each kind of call averaged,
a pass longer than twice the consultation's typical pass marked, and the
figures of the consultation.final audit line beside them. Figures only,
computed here and run by tests; the page draws them. Nothing here writes.

The two rules. Typical pass: the median of the stored passes' wall_ms,
the whole pass with both calls, over every pass of the consultation, the
same figure stop.figures gives the final line, so the two agree. Long: a
pass whose wall_ms is more than LONG_FACTOR times the typical pass; with
one pass nothing is long."""

from __future__ import annotations

import statistics
from datetime import datetime

LONG_FACTOR = 2
# The kinds drawn as rows of the band, in this order; a kind not here
# (the referral list, a letter) comes after final and is listed apart.
ROW_ORDER = ("alarm", "assessment", "guideline", "label_check", "note")
FINAL_EVENT = "consultation.final"


def seconds_between(earlier: str, later: str) -> float:
    return (datetime.fromisoformat(later) - datetime.fromisoformat(earlier)).total_seconds()


def pass_seconds(pass_row: dict) -> float:
    return (pass_row.get("result") or {}).get("wall_ms", 0) / 1000


def typical_pass_s(pass_rows: list[dict]) -> float | None:
    walls = [pass_seconds(p) for p in pass_rows]
    return round(statistics.median(walls), 2) if walls else None


def is_long(seconds: float, typical: float | None) -> bool:
    return typical is not None and seconds > LONG_FACTOR * typical


def _fraction(seconds: float, length_s: float) -> float:
    return round(min(1.0, max(0.0, seconds / length_s)), 4)


def pass_marks(pass_rows: list[dict], started_at: str, length_s: float) -> list[dict]:
    """Each pass as an interval from its stored at less its wall to its at,
    with the long mark by the rule above."""
    typical = typical_pass_s(pass_rows)
    found = []
    for pass_row in pass_rows:
        seconds = pass_seconds(pass_row)
        end_s = seconds_between(started_at, pass_row["at"])
        start_s = max(0.0, end_s - seconds)
        found.append({"n": pass_row["n"], "start_s": round(start_s, 2), "end_s": round(end_s, 2), "seconds": round(seconds, 2),
                      "long": is_long(seconds, typical), "left": _fraction(start_s, length_s),
                      "width": round(_fraction(end_s, length_s) - _fraction(start_s, length_s), 4)})
    return found


def bars(calls: list[dict], started_at: str, final_at: str, length_s: float) -> tuple[list[dict], list[dict]]:
    """Each call as a bar from (at less wall) to at, as fractions of Start to
    final; a call that ended after final is listed apart with its lead."""
    within, after = [], []
    for call in calls:
        seconds = call["wall_ms"] / 1000
        end_s = seconds_between(started_at, call["at"])
        start_s = max(0.0, end_s - seconds)
        bar = {"call_id": call["id"], "kind": call["job"], "start_s": round(start_s, 2), "end_s": round(end_s, 2),
               "seconds": round(seconds, 2), "outcome": call["outcome"], "at": call["at"]}
        if seconds_between(final_at, call["at"]) <= 0:
            within.append({**bar, "left": _fraction(start_s, length_s),
                           "width": round(_fraction(end_s, length_s) - _fraction(start_s, length_s), 4)})
        else:
            after.append({**bar, "lead": lead(seconds_between(final_at, call["at"]))})
    return within, after


def lead(seconds: float) -> tuple[int, str]:
    """A lead from final in plain units: seconds under a minute, then
    minutes, hours, days; rounded down."""
    whole = int(seconds)
    if whole < 60:
        return whole, "seconds"
    if whole < 3600:
        return whole // 60, "minutes"
    if whole < 86400:
        return whole // 3600, "hours"
    return whole // 86400, "days"


def averages(calls: list[dict]) -> list[dict]:
    """Per kind present, in the band's order then as first seen: the count,
    how many failed, the mean seconds and the slowest. Failed calls count
    in their kind: a too_slow call's wall is its limit."""
    kinds = list(ROW_ORDER) + [c["job"] for c in calls if c["job"] not in ROW_ORDER]
    found = []
    for kind in dict.fromkeys(kinds):
        walls = [c["wall_ms"] / 1000 for c in calls if c["job"] == kind]
        if not walls:
            continue
        failed = sum(1 for c in calls if c["job"] == kind and c["outcome"] != "ok")
        found.append({"kind": kind, "count": len(walls), "failed": failed,
                      "mean_s": round(sum(walls) / len(walls), 1), "slowest_s": round(max(walls), 1)})
    return found


def final_line(audit_lines, consultation_id: int) -> str | None:
    """The figures the consultation.final line already gives, as its
    sentence; None when no such line was written."""
    prefix = f"consultation {consultation_id}: "
    for line in audit_lines:
        if line.event == FINAL_EVENT and line.detail and line.detail.startswith(prefix):
            return line.detail[len(prefix):]
    return None


def band(row: dict, calls: list[dict], pass_rows: list[dict], audit_lines) -> dict:
    """Everything the page draws, for a final consultation."""
    started_at, final_at = row["started_at"], row["final_at"]
    length_s = max(seconds_between(started_at, final_at), 0.001)
    within, after = bars(calls, started_at, final_at, length_s)
    stop_s = seconds_between(started_at, row["stopped_at"]) if row.get("stopped_at") else None
    typical = typical_pass_s(pass_rows)
    passes = pass_marks(pass_rows, started_at, length_s)
    return {"length_s": round(length_s, 1), "stop_s": round(stop_s, 1) if stop_s is not None else None,
            "stop_left": _fraction(stop_s, length_s) if stop_s is not None else None,
            "rows": [kind for kind in ROW_ORDER if any(b["kind"] == kind for b in within)],
            "bars": within, "after_final": after, "passes": passes, "typical_pass_s": typical,
            "long_passes": [p["n"] for p in passes if p["long"]], "averages": averages(calls),
            "final_line": final_line(audit_lines, row["id"])}
