"""The rows of the build at Stop (spec 15.10, rulings 18 to 24 and the
details of step 6c: The record, Undo, A mark): each run of the
who-spoke check with how it ended, each line a run changed with its
label before and after, the drug-name call of Stop and its marks. A
part of the consultation's rows (consultations.py), kept apart for its
size. A run's labels, its change rows, its edit row and its end are
written in one transaction, so a run cut short has changed nothing."""

from __future__ import annotations

import json

OUTCOMES = ("running", "answered", "failed", "refused")
SWAPPED = {"doctor": "patient", "patient": "doctor"}


class CheckRows:
    """Mixed into Consultations, which gives _db and _now."""

    # ------------------------------------------ the runs of the who-spoke check

    def add_check_run(self, consultation_id: int, parts: int, joined_lines: int) -> int:
        cursor = self._db.execute(
            "INSERT INTO speaker_check (consultation_id, asked_at, outcome, parts, joined_lines) VALUES (?, ?, 'running', ?, ?)",
            (consultation_id, self._now(), int(parts), int(joined_lines)))
        return int(cursor.lastrowid)

    def end_check_run(self, run_id: int, outcome: str, reason: str | None = None, call_ids: list[int] | None = None,
                      labels: dict[int, dict] | None = None, changes: list[tuple[int, str, str]] | None = None,
                      no_first_reading: int = 0, named_twice: int | None = None, dropped: int | None = None) -> None:
        """The end of a run, all at once: the labels of the lines (label,
        changed_by_check, unsure, by line number), one change row for each
        line marked, the edit row of kind check when a line was marked
        (ruling 18), and the run's own row."""
        if outcome not in OUTCOMES[1:]:
            raise ValueError(f"not an end of a run: {outcome}")
        changes = changes or []
        with self._db.transaction() as con:
            cid = con.execute("SELECT consultation_id FROM speaker_check WHERE id = ?", (run_id,)).fetchone()["consultation_id"]
            for n, row in (labels or {}).items():
                con.execute("UPDATE transcript_line SET label = ?, changed_by_check = ?, unsure = ? WHERE consultation_id = ? AND n = ?",
                            (row["label"], int(bool(row.get("changed_by_check"))), int(bool(row.get("unsure"))), cid, n))
            for n, before, after in changes:
                con.execute("INSERT INTO speaker_check_change (check_id, line_n, label_before, label_after) VALUES (?, ?, ?, ?)",
                            (run_id, n, before, after))
            if changes:
                con.execute("INSERT INTO transcript_edit (consultation_id, at, kind, line_n, before, after) VALUES (?, ?, 'check', NULL, NULL, ?)",
                            (cid, self._now(), str(len(changes))))
            con.execute("UPDATE speaker_check SET ended_at = ?, outcome = ?, reason = ?, call_ids = ?, changed = ?, no_first_reading = ?, "
                        "named_twice = ?, dropped = ? WHERE id = ?",
                        (self._now(), outcome, reason, json.dumps(call_ids or []), len(changes), int(no_first_reading), named_twice,
                         dropped, run_id))

    def check_runs(self, consultation_id: int) -> list[dict]:
        rows = self._db.query("SELECT * FROM speaker_check WHERE consultation_id = ? ORDER BY id", (consultation_id,))
        return [{**dict(r), "call_ids": json.loads(r["call_ids"])} for r in rows]

    def running_checks(self) -> list[dict]:
        return [dict(r) for r in self._db.query("SELECT * FROM speaker_check WHERE outcome = 'running' ORDER BY id")]

    def standing_changes(self, consultation_id: int) -> dict[int, dict]:
        """By line number: the change of a check that still stands (not undone)."""
        rows = self._db.query(
            "SELECT ch.* FROM speaker_check_change ch JOIN speaker_check s ON s.id = ch.check_id "
            "WHERE s.consultation_id = ? AND ch.undone_at IS NULL ORDER BY ch.id", (consultation_id,))
        return {r["line_n"]: dict(r) for r in rows}

    def check_changes(self, run_id: int) -> list[dict]:
        return [dict(r) for r in self._db.query("SELECT * FROM speaker_check_change WHERE check_id = ? ORDER BY id", (run_id,))]

    def undo_change(self, consultation_id: int, n: int) -> str | None:
        """Undo on one line: the label before is put back (not the
        answer's, which a Swap or an edit may have changed since), the
        mark goes, and the change row keeps the time. None when no change
        of a check stands on the line."""
        change = self.standing_changes(consultation_id).get(n)
        if change is None:
            return None
        self.set_line_label(consultation_id, n, change["label_before"], kind="undo")
        self._db.execute("UPDATE speaker_check_change SET undone_at = ? WHERE id = ?", (self._now(), change["id"]))
        return change["label_before"]

    def swap_changes(self, consultation_id: int) -> None:
        """A Swap exchanges the stored labels before as well, so an Undo
        after it is still right (the details, Undo)."""
        for change in self.standing_changes(consultation_id).values():
            if change["label_before"] in SWAPPED:
                self._db.execute("UPDATE speaker_check_change SET label_before = ? WHERE id = ?",
                                 (SWAPPED[change["label_before"]], change["id"]))

    def lines_set_one_by_one(self, consultation_id: int) -> set[int]:
        """The lines whose label the doctor set with the control of one
        line: the check never changes them. A Swap is not such a setting."""
        rows = self._db.query("SELECT DISTINCT line_n FROM transcript_edit WHERE consultation_id = ? AND kind = 'label'",
                              (consultation_id,))
        return {r["line_n"] for r in rows}

    # ------------------------------------------- the drug-name call and its marks

    def add_drug_call(self, consultation_id: int, call_id: int | None, outcome: str, reason: str | None, kept: int,
                      dropped: int) -> int:
        cursor = self._db.execute(
            "INSERT INTO drug_name_call (consultation_id, call_id, at, outcome, reason, kept, dropped) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (consultation_id, call_id, self._now(), outcome, reason, int(kept), int(dropped)))
        return int(cursor.lastrowid)

    def drug_call(self, consultation_id: int) -> dict | None:
        found = self._db.query_one("SELECT * FROM drug_name_call WHERE consultation_id = ?", (consultation_id,))
        return dict(found) if found else None

    def add_drug_mark(self, consultation_id: int, drug_call_id: int, joined_line: int, heard: str, meant: str,
                      page_lines: list[int], places: list[dict]) -> int:
        cursor = self._db.execute(
            "INSERT INTO drug_mark (consultation_id, drug_name_call_id, joined_line, heard, meant, page_lines, places, first_line) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (consultation_id, drug_call_id, int(joined_line), heard, meant, json.dumps(page_lines), json.dumps(places),
             min(place["line"] for place in places)))
        return int(cursor.lastrowid)

    def drug_marks(self, consultation_id: int, every: bool = False) -> list[dict]:
        """The marks that stand, in the order of the page. every: the
        record, the cleared ones too. After Approve the transcript is
        read-only, so the marks that stand are those that stood at Approve."""
        rows = self._db.query("SELECT * FROM drug_mark WHERE consultation_id = ? ORDER BY first_line, id", (consultation_id,))
        found = [{**dict(r), "page_lines": json.loads(r["page_lines"]), "places": json.loads(r["places"])} for r in rows]
        return found if every else [m for m in found if m["cleared_at"] is None]

    def set_mark_places(self, mark_id: int, places: list[dict]) -> None:
        self._db.execute("UPDATE drug_mark SET places = ?, first_line = ? WHERE id = ?",
                         (json.dumps(places), min(place["line"] for place in places), mark_id))

    def clear_mark(self, mark_id: int) -> None:
        self._db.execute("UPDATE drug_mark SET cleared_at = ? WHERE id = ?", (self._now(), mark_id))
