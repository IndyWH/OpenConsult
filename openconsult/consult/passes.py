"""When a pass runs, and what the screen keeps between passes (spec 15.10,
rulings 1 and 2, When a pass runs; R9, R29, R30; V1_LESSONS 3.14). A pass
runs when none is running, final lines have arrived since the last one
ended, and the transcript has grown by NEW_CHARS_FOR_PASS characters
since the last pass was sent; the first pass runs on the first line. The
alarm history is held here in code: an alarm that drops out stays as an
earlier alarm, and an acknowledgement covers one alarm, told from the
next by its actions' words. The assessment panel keeps the earlier lists
through an empty reply (kept, 15.8 ruling 5) and through a failed call
(ruling 2), each marked. A result that lands after Stop is recorded and
not shown."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from openconsult.consult.cds_pass import Alarm, Carried, PassResult
from openconsult.speech.matching import normalise

# v1 ran a pass once this much new confirmed text had accumulated
# (CDS_MIN_NEW_CHARS, v1 app/main.py), with the first pass on the first
# turn. It is characters of transcript, not seconds; no clock is added.
NEW_CHARS_FOR_PASS = 150

FIRED, NO_ACTION, NOT_JUDGED, QUIET = "fired", "no_action", "not_judged", "quiet"


def alarm_state(alarm: Alarm) -> str:
    if not alarm.judged:
        return NOT_JUDGED
    if alarm.flag_without_action:
        return NO_ACTION
    if alarm.actions:
        return FIRED
    return QUIET


def alarm_key(state: str, actions: list) -> str | None:
    """What makes an alarm the same alarm from pass to pass: its actions'
    words after the matching's normalise, so a changed comma or case does
    not make a new one; the no-action state is one alarm while it holds.
    Stage 12 looks at this again before it decides what pauses Alba."""
    if state == FIRED:
        texts = sorted(" ".join(normalise(str(a.get("action", "")))) for a in actions if isinstance(a, dict))
        return "actions:" + "|".join(texts)
    if state == NO_ACTION:
        return "no_action"
    return None


@dataclass
class AlarmShown:
    n: int                      # the pass it came from
    state: str
    actions: list
    reasoning: str | None
    reason: str | None          # why it was not judged
    arranged: bool
    key: str | None


@dataclass
class Panel:
    """The assessment panel: the lists shown, where they came from, and the
    failure line (rulings 2 and 5)."""
    n: int = 0
    differentials: list = field(default_factory=list)
    questions: list = field(default_factory=list)
    signs: list = field(default_factory=list)
    from_earlier: bool = False      # kept from an earlier pass: the mark of ruling 2
    failure: str | None = None      # this pass's assessment failed, and why
    reasoning: str | None = None


class Passes:
    def __init__(self):
        self.carried = Carried()
        self.running = False
        self.n = 0
        self.panel = Panel()
        self.history: list[AlarmShown] = []
        self.acknowledged: set[str] = set()
        self.results: list[dict] = []

    # ------------------------------------------------------------ when

    def due(self, transcript) -> bool:
        if self.running or not transcript.new_lines_since_pass():
            return False
        if self.n == 0:
            return bool(transcript.text())
        return transcript.new_chars() >= NEW_CHARS_FOR_PASS

    def begin(self) -> int:
        self.running = True
        self.n += 1
        return self.n

    # ---------------------------------------------------------- settle

    def settle(self, n: int, result: PassResult, shown: bool, wall_ms: int) -> dict:
        """The bookkeeping once a pass is back. shown is false when the
        consultation had stopped: the result is recorded and the screen is
        not changed. Returns the result as stored."""
        self.running = False
        self.carried = result.carried
        stored = self._as_stored(n, result, shown, wall_ms)
        self.results.append(stored)
        if not shown:
            return stored
        self._show_alarm(n, result.alarm)
        self._show_assessment(n, result)
        return stored

    def _show_alarm(self, n: int, alarm: Alarm) -> None:
        state = alarm_state(alarm)
        self.history.append(AlarmShown(n, state, list(alarm.actions), alarm.reason,
                                       alarm.detail if not alarm.judged else None, alarm.arranged,
                                       alarm_key(state, alarm.actions)))

    def _show_assessment(self, n: int, result: PassResult) -> None:
        assessment = result.assessment
        if assessment.ok:
            self.panel = Panel(n, list(assessment.differentials), list(assessment.questions), list(assessment.signs),
                               from_earlier=assessment.kept, failure=None, reasoning=assessment.reasoning)
            return
        # Ruling 2: the earlier lists stay, marked, with the failure line; at
        # the first pass there is no earlier list, so the line stands alone.
        earlier = self.panel
        self.panel = Panel(n, list(earlier.differentials), list(earlier.questions), list(earlier.signs),
                           from_earlier=bool(earlier.differentials or earlier.questions or earlier.signs),
                           failure=f"{assessment.failure}: {assessment.detail}", reasoning=earlier.reasoning)

    def _as_stored(self, n: int, result: PassResult, shown: bool, wall_ms: int) -> dict:
        alarm, assessment = result.alarm, result.assessment
        return {"n": n, "shown": shown, "wall_ms": wall_ms,
                "alarm": {**asdict(alarm), "state": alarm_state(alarm)},
                "assessment": asdict(assessment),
                "carried": {"names": list(result.carried.names), "arranged": result.carried.arranged}}

    # ------------------------------------------------------------ alarms

    def acknowledge(self, key: str) -> bool:
        """One press covers one alarm (R29). True when the key names an
        alarm in the history."""
        if not any(shown.key == key for shown in self.history):
            return False
        self.acknowledged.add(key)
        return True

    def current_alarm(self) -> AlarmShown | None:
        return self.history[-1] if self.history else None

    def earlier_alarms(self) -> list[AlarmShown]:
        """Alarms that fired at an earlier pass and are not the current one,
        each once, the latest pass it fired on (R9)."""
        current = self.current_alarm()
        seen, found = set(), []
        for shown in reversed(self.history[:-1]):
            if shown.key is None or shown.key in seen or (current and shown.key == current.key):
                continue
            seen.add(shown.key)
            found.append(shown)
        return found

    def is_acknowledged(self, shown: AlarmShown) -> bool:
        return shown.key is not None and shown.key in self.acknowledged

    # ------------------------------------------------------------- state

    def marked(self) -> list[str]:
        """The differentials the current alarm names (15.11 ruling 9)."""
        from openconsult.consult.alarms import MARKED_STATES, matched_names
        current = self.current_alarm()
        if current is None or current.state not in MARKED_STATES:
            return []
        names = [d.get("condition") for d in self.panel.differentials if isinstance(d, dict) and d.get("condition")]
        return matched_names(current.reasoning, current.actions, names)

    def state(self) -> dict:
        current = self.current_alarm()
        return {
            "n": self.n,
            "running": self.running,
            "assessment": {**asdict(self.panel), "marked": self.marked()},
            "alarm": self._alarm_dict(current) if current else None,
            "earlier_alarms": [self._alarm_dict(a) for a in self.earlier_alarms()],
        }

    def _alarm_dict(self, shown: AlarmShown) -> dict:
        return {**asdict(shown), "acknowledged": self.is_acknowledged(shown)}
