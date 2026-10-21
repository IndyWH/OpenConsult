"""The red mark and the alarm lines at review (spec 15.11 ruling 9; R9;
R29; R15; V1_LESSONS 3.14). Code alone: no word a model reads changes
and no new call is made. The alarm's own call names no differential
outright, so the condition named in its reasoning and actions is
matched against the differential names with matching.normalise on both
sides and a whole-word run; the match is marked red with the alarm one
press away. The warnings pane lists each alarm of the consultation's
history once, at the pass it first fired, with its state then,
acknowledged where the audit log says so, and a press that plays from
the last line the pass had read."""

from __future__ import annotations

from datetime import datetime

from openconsult.consult.passes import FIRED, NO_ACTION, alarm_key
from openconsult.speech.matching import normalise

MARKED_STATES = (FIRED, NO_ACTION)


def alarm_text(reasoning: str | None, actions: list) -> str:
    parts = [str(reasoning or "")]
    for action in actions or []:
        if isinstance(action, dict):
            parts += [str(action.get("action", "")), str(action.get("reason", ""))]
    return " ".join(parts)


def matched_names(reasoning: str | None, actions: list, names: list) -> list[str]:
    """The differential names whose words stand in the alarm's text as a
    contiguous whole-word run, in the list's order."""
    words = normalise(alarm_text(reasoning, actions))
    found = []
    for name in names:
        wanted = normalise(str(name))
        if wanted and any(words[i:i + len(wanted)] == wanted for i in range(len(words) - len(wanted) + 1)):
            found.append(name)
    return found


def _stored_alarms(pass_rows: list[dict]) -> list[dict]:
    """Each alarm of the history once, at the pass it first fired (R9),
    from the stored results: key, state, reasoning, actions, the pass."""
    seen, found = set(), []
    for row in pass_rows:
        alarm = (row.get("result") or {}).get("alarm") or {}
        state = alarm.get("state")
        if state not in MARKED_STATES:
            continue
        key = alarm_key(state, alarm.get("actions") or [])
        if key in seen:
            continue
        seen.add(key)
        # The stored Alarm keeps its reasoning under reason (cds_pass.Alarm).
        found.append({"key": key, "state": state, "reasoning": alarm.get("reason"), "actions": list(alarm.get("actions") or []),
                      "n": row["n"], "at": row["at"], "transcript": row.get("transcript") or ""})
    return found


def acknowledged_keys(audit_lines, consultation_id: int) -> set[str]:
    """R29: the acknowledgements stage 6 wrote to the audit log."""
    prefix = f"consultation {consultation_id}: "
    return {line.detail[len(prefix):] for line in audit_lines
            if line.event == "alarm.acknowledged" and line.detail and line.detail.startswith(prefix)}


def last_line_read(transcript: str, live_lines: list[dict]) -> dict | None:
    """The live line the pass had last read: its transcript is the heard
    lines joined by line breaks, so the count names the line."""
    if not transcript:
        return None
    heard = [row for row in live_lines if not row.get("refused")]
    count = transcript.count("\n") + 1
    return heard[count - 1] if 0 < count <= len(heard) else None


def alarm_lines(pass_rows: list[dict], live_lines: list[dict], started_at: datetime, acknowledged: set[str],
                sentences) -> list[dict]:
    """One line per alarm: the time it first fired against the start, its
    state then, acknowledged or not, and where a press plays from."""
    found = []
    for alarm in _stored_alarms(pass_rows):
        fired = datetime.fromisoformat(alarm["at"])
        seconds = max(0, int((fired - started_at).total_seconds()))
        state = sentences.ALARM_STATE_FIRED if alarm["state"] == FIRED else sentences.ALARM_STATE_NO_ACTION
        if alarm["key"] in acknowledged:
            state += sentences.ALARM_STATE_ACKNOWLEDGED
        line = last_line_read(alarm["transcript"], live_lines)
        found.append({**alarm, "time": f"{seconds // 60}:{seconds % 60:02d}", "acknowledged": alarm["key"] in acknowledged,
                      "text": sentences.ALARM_LINE.format(time=f"{seconds // 60}:{seconds % 60:02d}", state=state),
                      "start_s": line["start_s"] if line else None, "line_n": line["n"] if line else None})
    return found


def review_marks(pass_rows: list[dict], names: list) -> dict:
    """At review: each differential name matched by any alarm of the
    history, with the latest matching alarm's reasoning and actions."""
    marks = {}
    for alarm in _stored_alarms(pass_rows):
        for name in matched_names(alarm["reasoning"], alarm["actions"], names):
            marks[name] = {"reasoning": alarm["reasoning"], "actions": alarm["actions"]}
    return marks
