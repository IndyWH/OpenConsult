"""Teaching mode as the pages reach it (spec 12; 15.14 and the details of
run 10b; R24): one object that holds the bank as it was read at start
and the rows of the cases. The pages of teaching reach nothing else of
teaching, and nothing here reaches a table, a page or a job of the
clinic: teaching can never make a note, a letter or a record."""

from __future__ import annotations

from openconsult.teaching.bank import Bank
from openconsult.teaching.cases import Cases


class Teaching:
    def __init__(self, bank: Bank, cases: Cases):
        self.bank = bank
        self.cases = cases
