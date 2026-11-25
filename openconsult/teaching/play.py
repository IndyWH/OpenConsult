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
from typing import Callable

from openconsult.patients.audit import Audit
from openconsult.teaching.bank import Bank
from openconsult.teaching.cases import Cases


class Teaching:
    def __init__(self, bank: Bank, cases: Cases, audit: Audit, door_of: Callable):
        """door_of gives the door of a language model by its name in a
        case's row: this computer's, or the door to Claude."""
        self.bank = bank
        self.cases = cases
        self.door_of = door_of
        self._audit = audit
        self._starting = threading.Lock()

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
