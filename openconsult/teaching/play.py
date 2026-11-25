"""Teaching mode as the pages reach it (spec 12; 15.14 and the details of
run 10b; R24): one object that holds the bank as it was read at start,
the rows of the cases, and the way to the language model. The pages of
teaching reach nothing else of teaching, and nothing here reaches a
table, a page or a job of the clinic: teaching can never make a note, a
letter or a record.

The language model of a case is the one Settings held at the press that
started it, written into the case's own row; every later call of the
case goes by the door of that model, and nothing is ever tried on the
other (10.4)."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable

from openconsult.patients.audit import Audit
from openconsult.teaching import frames, room, words as t
from openconsult.teaching.bank import Bank
from openconsult.teaching.cases import EXAMINATION, HISTORY, Cases

DONE, STALE, REFUSED = "done", "stale", "refused"


@dataclass(frozen=True)
class Outcome:
    """What came of a press on a case. done: stored, the case moved on.
    stale: the press came from a page that was no longer up to date, and
    nothing was stored. refused: nothing was stored, and problem is the
    sentence for the control that was pressed (R15)."""
    state: str
    problem: str | None = None


class Teaching:
    def __init__(self, bank: Bank, cases: Cases, audit: Audit, door_of: Callable):
        """door_of gives the door of a language model by its name in a
        case's row: this computer's, or the door to Claude."""
        self.bank = bank
        self.cases = cases
        self.door_of = door_of
        self._audit = audit
        self._starting = threading.Lock()
        self._locks: dict[int, threading.Lock] = {}

    def _lock(self, case_id: int) -> threading.Lock:
        """One lock a case: two presses on one case are taken one after the other."""
        with self._starting:
            return self._locks.setdefault(case_id, threading.Lock())

    def _ask(self, row: dict, job: str, user: str, sampling=None):
        """One call of a case, by the door of the case's own language model
        (10.4), tied to the case at once so that it goes when the case goes."""
        result = self.door_of(row["language_model"]).ask(job, user, sampling)
        self.cases.tie(row["id"], result.call_id)
        return result

    def start_bank(self, number: int, press: str, language_model: str) -> int | None:
        """A case of the bank begins: its row, with the scenario as it
        stands now, and one audit line. The same press a second time
        gives the case it started and writes nothing. None when the bank
        holds no such case."""
        case = self.bank.case(number)
        if case is None:
            return None
        with self._starting:
            before = self.cases.by_press(press)
            if before is not None:
                return before
            case_id = self.cases.start(press, "bank", case.topic, case.level, case.label, language_model, case.scenario, case.number)
            self._audit.record("teaching.started", f"case {case_id}: bank case {case.number}, level {case.level}, "
                                                   f"language model {language_model}")
        return case_id

    # ---------------------------------------------------------- the history

    def say(self, case_id: int, line: int, text: str) -> Outcome:
        """One line of the learner, by the number it will get. The actor is
        asked with the words frames builds, and with nothing else; the line
        and the reply are stored together only when the reply came back to
        its form. A failed call stores nothing and is not asked again by
        itself (R30): the page keeps the line in its box."""
        text = text.strip()
        with self._lock(case_id):
            row = self.cases.get(case_id)
            said = self.cases.conversation(case_id) if row else []
            if row is None or row["step"] != HISTORY or line != len(said) // 2 + 1:
                return Outcome(STALE)
            if not text:
                return Outcome(REFUSED, t.TYPE_A_LINE)
            if len(text) > room.LINE_MOST:
                return Outcome(REFUSED, t.LINE_TOO_LONG.format(most=t.most(room.LINE_MOST)))
            if not room.line_fits(row["scenario"], said, text):
                return Outcome(REFUSED, t.HISTORY_FULL)
            result = self._ask(row, "teaching_patient", frames.patient_message(row["scenario"], said, text))
            if not result.ok:
                return Outcome(REFUSED, t.REPLY_FAILED.format(reason=t.reason(result.failure)))
            stored = self.cases.add_exchange(case_id, line, text, result.answer["reply"], result.answer["facts_used"])
            return Outcome(DONE if stored else STALE)

    def end_history(self, case_id: int, typed: str) -> Outcome:
        """The one press that ends the history: no way back. A line typed
        and not sent travels with the press and refuses it, so no typed
        word is lost by it."""
        with self._lock(case_id):
            row = self.cases.get(case_id)
            if row is None or row["step"] != HISTORY:
                return Outcome(STALE)
            if typed.strip():
                return Outcome(REFUSED, t.END_WITH_WORDS)
            return Outcome(DONE if self.cases.end_history(case_id) else STALE)

    # ------------------------------------------------------ the examination

    def examine(self, case_id: int, n: int, text: str) -> Outcome:
        """What the learner would examine, by the number the request will
        get. The model writes no finding: it says which findings of the
        scenario were asked for (ruling 12), and what came back is stored
        as it came. A failed call stores nothing, so no finding and no
        sentence about a finding is shown for it."""
        text = text.strip()
        with self._lock(case_id):
            row = self.cases.get(case_id)
            before = self.cases.examined(case_id) if row else []
            if row is None or row["step"] != EXAMINATION or n != len(before) + 1:
                return Outcome(STALE)
            if not text:
                return Outcome(REFUSED, t.TYPE_A_REQUEST)
            if len(text) > room.LINE_MOST:
                return Outcome(REFUSED, t.REQUEST_TOO_LONG.format(most=t.most(room.LINE_MOST)))
            if not room.examination_fits([request["text"] for request in before], text):
                return Outcome(REFUSED, t.EXAMINATION_FULL)
            result = self._ask(row, "teaching_examination", frames.examination_message(row["scenario"], text))
            if not result.ok:
                return Outcome(REFUSED, t.EXAMINATION_FAILED.format(reason=t.reason(result.failure)))
            stored = self.cases.add_examined(case_id, n, text, result.answer["asked"], result.answer["not_in_case"])
            return Outcome(DONE if stored else STALE)

    def finish_examination(self, case_id: int, typed: str) -> Outcome:
        """The one press that ends the examination: the rest of the
        scenario's findings may then be shown, and the first question
        comes. A request typed and not sent refuses it."""
        with self._lock(case_id):
            row = self.cases.get(case_id)
            if row is None or row["step"] != EXAMINATION:
                return Outcome(STALE)
            if typed.strip():
                return Outcome(REFUSED, t.FINISH_WITH_WORDS)
            return Outcome(DONE if self.cases.finish_examination(case_id) else STALE)
