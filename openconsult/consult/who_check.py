"""The check of who spoke, asked for on the review page (spec 15.9
ruling 37; 15.10 rulings 7, 14, 18, 19 and 24, and the details of step
6c: The who-spoke check on the review page, Undo, A page in parts). It
no longer runs at Stop: it helped where the labels were poor and harmed
where they were good, and the doctor is the one who can tell. A press
starts one run on a thread of its own; the labels are written only at
the end and all at once, so a run cut short has changed nothing. A
label the doctor set on one line is never changed. The run is offered
once: again only after a run that failed or whose reply was refused."""

from __future__ import annotations

import threading
import time

from openconsult import words
from openconsult.consult import joined, labels, speakers
from openconsult.consult.consultations import Consultations
from openconsult.llm.door import Door
from openconsult.patients.audit import Audit

# A thread still running at the app's close is waited for this long and no longer:
# the call has its own limit of 120 s (llm/jobs.py), and close must never hang.
CLOSE_WAIT_S = 5.0


class WhoChecks:
    """The runs of the check, held for the app's run: one thread a run."""

    def __init__(self, door: Door, rows: Consultations, audit: Audit):
        self.door, self.rows, self.audit = door, rows, audit
        self._threads: dict[int, threading.Thread] = {}
        self._lock = threading.Lock()

    def sweep(self) -> int:
        """At the app's start: a run left running by the last run of the
        app is ended as failed with its reason. Its labels were to be
        written at its end, so none has changed (V1_LESSONS 1.12; R30)."""
        left = self.rows.running_checks()
        for run in left:
            self.rows.end_check_run(run["id"], "failed", reason=words.CHECK_RESTARTED)
            self.audit.record("speakers.check_ended", f"consultation {run['consultation_id']}: failed: {words.CHECK_RESTARTED}")
        return len(left)

    def start(self, consultation_id: int) -> bool:
        """The press: the run's row as running, the audit line, the thread.
        False when a run of this consultation is running: a second press
        does nothing."""
        with self._lock:
            runs = self.rows.check_runs(consultation_id)
            if runs and runs[-1]["outcome"] == "running":
                return False
            lines = joined.of_rows(self.rows.transcript_lines(consultation_id))
            parts = len(joined.cut(lines))
            run_id = self.rows.add_check_run(consultation_id, parts, len(lines))
            self.audit.record("speakers.check_asked", f"consultation {consultation_id}: {len(lines)} lines, "
                              + ("whole" if parts == 1 else f"in {parts} parts"))
            thread = threading.Thread(target=self._run, args=(consultation_id, run_id), name=f"who-check-{consultation_id}", daemon=True)
            self._threads[consultation_id] = thread
            thread.start()
        return True

    def _run(self, consultation_id: int, run_id: int) -> None:
        try:
            self._check(consultation_id, run_id)
        except Exception as error:      # a run never stays running: whatever broke is said plainly (R30)
            self.rows.end_check_run(run_id, "failed", reason=f"{type(error).__name__}: {error}.")
            self.audit.record("speakers.check_ended", f"consultation {consultation_id}: failed: {type(error).__name__}")

    def _check(self, consultation_id: int, run_id: int) -> None:
        rows = [r for r in self.rows.transcript_lines(consultation_id) if r["n"] is not None]
        found, outcome = labels.run(self.door, rows, consultation_id)
        counts = {"call_ids": outcome["call_ids"], "named_twice": outcome["named_twice"], "dropped": outcome["dropped"]}
        if found is None:
            reason = outcome.get("detail") or outcome.get("failure")
            self.rows.end_check_run(run_id, outcome["outcome"], reason=reason, **counts)
            self.audit.record("speakers.check_ended", f"consultation {consultation_id}: {outcome['outcome']}: {reason}")
            return
        fresh = [r for r in self.rows.transcript_lines(consultation_id) if r["n"] is not None]
        if labels.texts_hash(fresh) != labels.texts_hash(rows):
            raise RuntimeError("a word of the transcript changed during the check")
        # A label the doctor set with the control of one line is never changed and never marked (ruling 19).
        set_by_hand = self.rows.lines_set_one_by_one(consultation_id)
        said = {n: label for n, label in found.items() if n not in set_by_hand}
        new = speakers.apply_check(fresh, said)
        standing = {r["n"]: r for r in fresh}
        changes = [(n, standing[n]["label"], row["label"]) for n, row in new.items() if row["changed_by_check"]]
        # A line with no speaker from the choice takes the label and stays shown unsure: kept as a count, never a change (ruling 14).
        no_first_reading = sum(1 for n in new if standing[n].get("raw_speaker") is None and said[n] != "unsure")
        self.rows.end_check_run(run_id, "answered", labels=new, changes=changes, no_first_reading=no_first_reading, **counts)
        self.audit.record("speakers.check_ended", f"consultation {consultation_id}: answered, {len(changes)} lines changed")

    def undo_all(self, consultation_id: int) -> int:
        """One press: the label before is put back on every line still
        marked. The count of lines put back."""
        marked = sorted(self.rows.standing_changes(consultation_id))
        for n in marked:
            self.rows.undo_change(consultation_id, n)
        self.audit.record("speakers.check_undone_all", f"consultation {consultation_id}: {len(marked)} lines put back")
        return len(marked)

    def wait(self, consultation_id: int, timeout_s: float = CLOSE_WAIT_S) -> None:
        thread = self._threads.get(consultation_id)
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout_s)

    def close(self) -> None:
        """At the app's shutdown: every run in flight is waited for, within
        one limit for all of them."""
        end = time.monotonic() + CLOSE_WAIT_S
        for consultation_id in list(self._threads):
            self.wait(consultation_id, max(0.0, end - time.monotonic()))


def page_state(rows: Consultations, consultation_id: int, read_only: bool, has_lines: bool) -> dict:
    """What the review page shows of the check (ruling 19; R15): whether
    the control is offered, the reason when it is not, the outcome of the
    latest run only, and whether Undo all is shown (only while a line is
    marked)."""
    runs = rows.check_runs(consultation_id)
    latest = runs[-1] if runs else None
    outcome = latest["outcome"] if latest else None
    marked = len(rows.standing_changes(consultation_id))
    line, failed = None, False
    if outcome == "answered":
        if marked > 1:
            line = words.CHECK_CHANGED.format(count=marked)
        elif marked == 1:
            line = words.CHECK_CHANGED_ONE
        elif latest["changed"] == 0:
            line = words.CHECK_CHANGED_NONE
    elif outcome == "failed":
        line, failed = words.WARN_LABEL_CHECK_FAILED.format(reason=latest["reason"] or ""), True
    elif outcome == "refused":
        line, failed = words.WARN_LABEL_CHECK_REFUSED.format(reason=latest["reason"] or ""), True
    running, ran = outcome == "running", outcome == "answered"
    reason = (words.CHECK_RUNNING if running else words.NOTE_READ_ONLY if read_only else words.CHECK_ALREADY_RAN if ran else None)
    return {"running": running, "ran": ran, "offered": has_lines and reason is None, "reason": reason, "has_lines": has_lines,
            "line": line, "failed": failed, "marked": marked, "undo_all": marked > 0 and not read_only and not running}
