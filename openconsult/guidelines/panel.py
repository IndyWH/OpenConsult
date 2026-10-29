"""The guideline panel of the live page (spec 15.12, ruling 6; the detail
The passages and the search; R3, R4, R5, R30; 10.4): after a pass whose
top two differentials differ from the last search, one search and, when
passages pass the floor, one summary call, on a thread of their own, one
at a time, never during Stop; a failed or slow call touches nothing of
the pass or the alarm; a result that lands after Stop is recorded and not
shown. With no document loaded the panel says so and nothing is asked of
a model. The panel is drawn from the row it writes."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from openconsult import words
from openconsult.consult.messages import Patient, names_of
from openconsult.guidelines import summary as summary_module
from openconsult.guidelines.search import GUIDELINE_FLOOR, INDEX_MODEL_DIFFERS, Index, query_of, search
from openconsult.guidelines.sources import AnswerRow, Sources
from openconsult.llm.door import Door

NO_CORPUS, NOT_INSTALLED, WORKER_FAILED, READY = "no_corpus", "not_installed", "worker_failed", "ready"
WAITING, COVERED, NOT_COVERED, FAILED, INDEX_MODEL = "waiting", "covered", "not_covered", "failed", "index_model"
TOP = 2                      # the top two differentials (ruling 6)
LIVE = "live"


@dataclass(frozen=True)
class Answered:
    """One search's result, before the row knows whether it was shown."""
    row: AnswerRow
    panel: dict


class Guidelines:
    """The app's one guideline service: the corpus's rows and index, the
    embedding worker, the door and the floor. The reranker is not wired
    (15.12, ruling 25): the search is asked without it and the row says 0."""

    def __init__(self, sources: Sources, index: Index, embedder, door: Door, audit,
                 floor: float = GUIDELINE_FLOOR, timer: Callable = time.perf_counter):
        self.sources, self.index, self.embedder, self.door, self.audit = sources, index, embedder, door, audit
        self.floor, self.timer = floor, timer

    def availability(self) -> tuple[str, str | None]:
        """Whether a search can run, and why not: no document loaded (R3,
        nothing asked), the worker not installed, or the worker dead."""
        if not self.index.rows:
            return NO_CORPUS, None
        if not self.embedder.installed:
            return NOT_INSTALLED, self.embedder.ready()
        if self.embedder.state == "failed":
            return WORKER_FAILED, self.embedder.reason
        return READY, None

    def provenance(self) -> dict:
        counts = self.sources.counts()
        latest = counts["latest"]
        return {"sources": counts["sources"], "passages": counts["passages"],
                "date": words.plain_date(datetime.fromisoformat(latest)) if latest else ""}

    def answer(self, names: list[str], patient: Patient, consultation_id: int, pass_n: int) -> Answered:
        """The search, the call when the floor lets passages through, and the outcome by code."""
        started = self.timer()
        query = query_of(names)
        not_ready = self.embedder.ready()
        if not_ready:
            return self._answered(names, query, None, pass_n, consultation_id, FAILED, failure=not_ready, started=started)
        found = search(self.index, self.embedder, names, floor=self.floor)
        if found.failure:
            return self._answered(names, found.query, found, pass_n, consultation_id, FAILED, failure=found.failure, started=started)
        if found.below_floor:
            return self._answered(names, found.query, found, pass_n, consultation_id, "below_floor", started=started)
        outcome = summary_module.summarise(self.door, found.query, found.sent, patient, consultation_id=consultation_id)
        for sent in found.sent:
            sent["cited"] = sent["n"] in outcome.cited
        return self._answered(names, found.query, found, pass_n, consultation_id, outcome.outcome, outcome=outcome, started=started)

    def _answered(self, names, query, found, pass_n, consultation_id, outcome_name, failure=None, outcome=None, started=0.0) -> Answered:
        wall_ms = round(1000 * (self.timer() - started))
        row = AnswerRow(
            consultation_id, pass_n, list(names), query, [dict(s) for s in found.sent] if found else [],
            len(found.candidates) if found else 0, found.top_similarity if found else None, self.floor,
            False, outcome_name,                                   # reranker_ran: never, in the app (ruling 25)
            outcome.call_id if outcome else None, outcome.covered if outcome else None,
            outcome.summary if outcome else None, outcome.cited if outcome else None, outcome.invalid if outcome else 0,
            outcome.failure if outcome and outcome.failure else failure, found.search_ms if found else 0, wall_ms, True)
        return Answered(row, panel_of(row))

    def record(self, answered: Answered, shown: bool) -> int:
        """The row with whether it was shown, and the audit line of counts."""
        row = answered.row
        answer_id = self.sources.add_answer(AnswerRow(**{**row.__dict__, "shown": shown}))
        where = f"consultation {row.consultation_id}, pass {row.pass_n}, answer {answer_id}"
        if row.outcome == COVERED:
            self.audit.record("guideline.summary", f"{where}: {len(row.passages)} passages sent, {len(row.passages_cited or [])} cited, "
                                                   f"{row.invalid_cites} invalid marks, "
                                                   f"search {row.search_ms} ms, {row.wall_ms} ms")
        elif row.outcome == FAILED:
            self.audit.record("guideline.failed", f"{where}: {row.failure}")
        else:
            self.audit.record("guideline.not_covered", f"{where}: {row.outcome}, {len(row.passages)} passages sent, "
                                                       f"top similarity {row.top_similarity}, floor {row.floor}")
        return answer_id


def panel_of(row: AnswerRow) -> dict:
    """What the page draws from the row: the one state and its words' fill."""
    if row.outcome == COVERED:
        state = COVERED
    elif row.outcome == FAILED:
        state = INDEX_MODEL if row.failure == INDEX_MODEL_DIFFERS else FAILED
    else:
        state = NOT_COVERED
    return {"state": state, "names": list(row.names), "names_text": row.query, "pass_n": row.pass_n, "outcome": row.outcome,
            "summary": row.summary if row.outcome == COVERED else None,
            "model_sentence": row.summary if row.outcome == "not_covered" else None,
            "passages": [dict(p) for p in row.passages], "cited": list(row.passages_cited or []), "invalid": row.invalid_cites,
            "failure": row.failure}


class PanelState:
    """One consultation's panel: the pair last searched, the search in
    flight, the pair held for after it, and what is shown."""

    def __init__(self, service: Guidelines, consultation):
        self.service = service
        self.c = consultation
        self.last: frozenset | None = None
        self.pending: tuple | None = None
        self.searching: tuple | None = None
        self.shown: dict | None = None
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"consultation-{consultation.id}_guideline")
        self._future = None

    @property
    def running(self) -> bool:
        return self.searching is not None

    def after_pass(self, n: int, assessment) -> None:
        """Under the consultation's lock, once a pass has landed and is shown."""
        if self.c.state != LIVE or not assessment.ok or assessment.kept:
            return
        names = list(names_of(assessment.differentials)[:TOP])
        if not names or self.last == frozenset(names):
            return
        if self.service.availability()[0] != READY:
            return
        if self.running:
            self.pending = (n, names)
            return
        self._start(n, names)

    def _start(self, n: int, names: list[str]) -> None:
        self.searching = (n, names)
        self.last = frozenset(names)
        self.c._changed()
        self._future = self._pool.submit(self._run, n, names)

    def _run(self, n: int, names: list[str]) -> None:
        answered = self.service.answer(names, self.c.model_patient, self.c.id, n)
        with self.c.lock:
            shown = self.c.state == LIVE
            self.service.record(answered, shown)
            self.searching = None
            if shown:
                self.shown = answered.panel
            self.c._changed()
            pending, self.pending = self.pending, None
            if pending and self.c.state == LIVE and frozenset(pending[1]) != self.last:
                self._start(*pending)

    def wait(self, timeout_s: float = 30.0) -> None:
        """For tests: the search in flight, if any, lands."""
        if self._future is not None:
            self._future.result(timeout=timeout_s)

    def close(self) -> None:
        self._pool.shutdown(wait=True)

    def state(self) -> dict:
        availability, reason = self.service.availability()
        if availability != READY:
            state = availability
        elif self.shown is not None:
            state = "result"
        else:
            state = "searching" if self.running else WAITING
        found = {"state": state,
                 "reason": reason, "searching": list(self.searching[1]) if self.searching else None,
                 "searching_text": "; ".join(self.searching[1]) if self.searching else None,
                 "result": self.shown, "provenance": self.service.provenance()}
        return found
