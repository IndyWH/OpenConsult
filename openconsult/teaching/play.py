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
from openconsult.teaching import checks, frames, room, words as t
from openconsult.teaching.bank import Bank
from openconsult.teaching.cases import EXAMINATION, FEEDBACK, HISTORY, QUESTIONS, WRITING, Cases

DONE, STALE, REFUSED = "done", "stale", "refused"
# How long a delete waits for a call of the case that is in flight before it says that the case is waiting.
DELETE_WAITS_S = 5.0


def _beside(work: Callable) -> None:
    threading.Thread(target=work, name="teaching", daemon=True).start()


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
        self._making: set[int] = set()      # the cases whose feedback is being made at this moment
        # How work that takes a model's time is run beside the page: a thread of its own. A test puts its own way here.
        self.run: Callable[[Callable], None] = _beside

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

    def start_fresh(self, topic: str, level: str, press: str, language_model: str) -> int:
        """A fresh case begins: its row, with no scenario yet and the label
        of a scenario a model writes, one audit line, and the writing
        beside the page. The same press a second time gives the case it
        started and asks for nothing."""
        with self._starting:
            before = self.cases.by_press(press)
            if before is not None:
                return before
            case_id = self.cases.start(press, "fresh", topic, level, "ai", language_model)
            self._audit.record("teaching.started", f"case {case_id}: a fresh scenario, level {level}, language model {language_model}")
        self._begin(case_id, self._write)
        return case_id

    def _begin(self, case_id: int, work: Callable) -> None:
        self._making.add(case_id)
        self.run(lambda: work(case_id))

    def _write(self, case_id: int) -> None:
        """The scenario of a fresh case, by the job of ruling 10, with its
        own sampling so that one topic and one level do not give every
        learner the same patient. A patient appears only when the door
        held the reply to the form and code finds no dose in the plan
        and nothing missing; whether it is clinically right code cannot
        check, and the label says so. Nothing is asked again by itself."""
        try:
            with self._lock(case_id):
                row = self.cases.get(case_id)
                if row is None or row["step"] != WRITING:
                    return
                result = self._ask(row, "teaching_case", frames.case_message(row["topic"], row["level"]), frames.case_sampling())
                if not result.ok:
                    self.cases.failed(case_id, WRITING, result.failure)
                elif checks.plan_doses(result.answer):
                    self.cases.failed(case_id, WRITING, t.DOSE)
                elif checks.incomplete(result.answer):
                    self.cases.failed(case_id, WRITING, t.INCOMPLETE)
                else:
                    self.cases.written(case_id, result.answer)
        finally:
            self._making.discard(case_id)

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

    # ------------------------------------ the three questions, the feedback

    def answer(self, case_id: int, question: int, text: str) -> Outcome:
        """The answer to question 1, 2 or 3, at that question alone. The
        questions go to no model. After the third the feedback is made,
        once, beside the page."""
        text = text.strip()
        with self._lock(case_id):
            row = self.cases.get(case_id)
            if row is None or question not in (1, 2, 3) or row["step"] != QUESTIONS[question - 1]:
                return Outcome(STALE)
            if not text:
                return Outcome(REFUSED, t.TYPE_AN_ANSWER)
            if len(text) > room.ANSWER_MOST:
                return Outcome(REFUSED, t.ANSWER_TOO_LONG.format(most=t.most(room.ANSWER_MOST)))
            if not self.cases.answer(case_id, question, text):
                return Outcome(STALE)
        if question == len(QUESTIONS):
            self._begin(case_id, self._make_feedback)      # outside the case's lock, which the making takes itself
        return Outcome(DONE)

    def making(self, case_id: int) -> bool:
        """Whether the scenario or the feedback of this case is being made at this moment."""
        return case_id in self._making

    def _make_feedback(self, case_id: int) -> None:
        """The feedback, once: the whole scenario, the numbered turns, what
        was asked at the examination and the three answers, by frames
        alone. What the model answers is stored as the door held it to
        its form; the page builds what a learner sees from it by the rule
        of openconsult/teaching/shown.py, every time. A failed call
        leaves its reason and everything the learner did; nothing is
        asked again by itself (R30)."""
        try:
            with self._lock(case_id):
                row = self.cases.get(case_id)
                if row is None or row["step"] != FEEDBACK:
                    return
                said, examined = self.cases.conversation(case_id), self.cases.examined(case_id)
                result = self._ask(row, "teaching_feedback", frames.feedback_message(
                    row["scenario"], said, [request["text"] for request in examined], self.cases.answers(row)))
                if not result.ok:
                    self.cases.failed(case_id, FEEDBACK, result.failure)
                elif self.cases.fed_back(case_id, result.answer):
                    self._audit.record("teaching.finished", f"case {case_id}: {len(said) // 2} lines, {len(examined)} examination "
                                                            "requests, feedback made")
        finally:
            self._making.discard(case_id)

    # -------------------------------------------------------------- the flag

    def flag(self, case_id: int, note: str) -> Outcome:
        """The learner's flag on a finished case (12.3, rule 7): once a
        case, with a note that may be empty, kept with a copy of the
        scenario. The audit line holds the note's length, never its words."""
        note = note.strip()
        with self._lock(case_id):
            if len(note) > room.LINE_MOST:
                return Outcome(REFUSED, t.NOTE_TOO_LONG.format(most=t.most(room.LINE_MOST)))
            if self.cases.flag(case_id, note) is None:
                return Outcome(STALE)
            self._audit.record("teaching.flagged", f"case {case_id}: " + (f"a note of {len(note)} characters" if note else "no note"))
            return Outcome(DONE)

    def remove_flag(self, flag_id: int) -> bool:
        """A flag taken out of the list in Settings, with its copy of the scenario and its note; audited by its number."""
        if not self.cases.remove_flag(flag_id):
            return False
        self._audit.record("teaching.flag_removed", f"flag {flag_id}")
        return True

    # ------------------------------------------------------------ the delete

    def delete(self, case_id: int) -> Outcome:
        """One case removed with every line, reply, finding shown, answer
        and feedback, and every stored model call of it, in one go
        (ruling 22), and one audit line of counts. A case whose answer
        from the model is still awaited is not deleted under it: the
        press says so, and nothing is removed. A flag stays."""
        lock = self._lock(case_id)
        if not lock.acquire(timeout=DELETE_WAITS_S):
            return Outcome(REFUSED, t.DELETE_WAITING)
        try:
            counts = self.cases.delete(case_id)
        finally:
            lock.release()
        if counts is None:
            return Outcome(STALE)
        kept = f", {counts['flags_kept']} flag kept" if counts["flags_kept"] else ""
        self._audit.record("teaching.deleted", f"case {case_id} of {counts['date']}: {counts['turns']} turns, "
                           f"{counts['examination_requests']} examination requests, {counts['answers']} answers, "
                           f"{counts['feedback']} feedback, {counts['model_calls']} model calls{kept}")
        return Outcome(DONE)

    def again(self, case_id: int) -> Outcome:
        """Write the scenario or make the feedback again, by a press
        alone, after one that did not come. A press while one is being
        made, or for a case that waits for neither, changes nothing."""
        with self._lock(case_id):
            row = self.cases.get(case_id)
            if row is None or row["step"] not in (WRITING, FEEDBACK) or self.making(case_id):
                return Outcome(STALE)
            self.cases.trying(case_id, row["step"])
            self._making.add(case_id)
        self._begin(case_id, self._write if row["step"] == WRITING else self._make_feedback)
        return Outcome(DONE)
