"""The rows of a teaching case (spec 15.14, ruling 22 and the details of
run 10b; 12.7; R24): the case with its scenario as it was held at the
start, each line of the learner with the patient's reply, each
examination request, the three answers, the feedback as the model
answered it, the ties to the record of model calls, and the flags.
Everything is saved as it happens, so a case that is left can be gone on
with from where it stood.

A case moves one way through its steps. Every move names the step it
comes from, and a line or a request the number it will get, so a second
press and a press on a stale page change nothing (R15). Nothing here
talks to a model, reads a setting or touches a table of the clinic; a
delete also removes the case's rows of the shared record of calls."""

from __future__ import annotations

import json

from openconsult.db import Database
from openconsult.patients.audit import Clock, now_local

LEVELS = ("straightforward", "hidden", "noisy")
LABELS = ("ai", "script", "approved")
SOURCES = ("bank", "fresh")
# The steps of a case, in their one order (12.1).
WRITING, HISTORY, EXAMINATION, FEEDBACK, DONE = "writing", "history", "examination", "feedback", "done"
QUESTIONS = ("question_1", "question_2", "question_3")
STEPS = (WRITING, HISTORY, EXAMINATION, *QUESTIONS, FEEDBACK, DONE)
ANSWERS = ("differential", "investigations", "plan")      # the three questions, in order, as the feedback's frame names them
# The rows a delete removes, children first, each with its count's name; the model calls are removed between them.
ROW_DELETIONS = (("turns", "DELETE FROM teaching_turn WHERE case_id = ?"),
                 ("examination_requests", "DELETE FROM teaching_examined WHERE case_id = ?"))


class Cases:
    def __init__(self, db: Database, clock: Clock = now_local):
        self._db = db
        self._clock = clock

    def _now(self) -> str:
        return self._clock().isoformat(timespec="seconds")

    # ------------------------------------------------------------- the case

    def start(self, press: str, source: str, topic: str, level: str, label: str, language_model: str,
              scenario: dict | None = None, bank_number: int | None = None) -> int:
        """The row at the press that starts a case. press is the token the
        page was made with: the same press twice gives the same case. With
        a scenario the case begins at its history; with none it is a fresh
        one still being written."""
        self._db.execute(
            "INSERT OR IGNORE INTO teaching_case (press, started_at, source, bank_number, topic, level, label, language_model, "
            "step, scenario) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (press, self._now(), source, bank_number, topic, level, label, language_model,
             WRITING if scenario is None else HISTORY, None if scenario is None else json.dumps(scenario, ensure_ascii=False)))
        return int(self._db.query_one("SELECT id FROM teaching_case WHERE press = ?", (press,))["id"])

    def get(self, case_id: int) -> dict | None:
        row = self._db.query_one("SELECT * FROM teaching_case WHERE id = ?", (case_id,))
        if row is None:
            return None
        found = dict(row)
        for column in ("scenario", "feedback"):
            found[column] = json.loads(found[column]) if found[column] else None
        return found

    def listed(self) -> list[dict]:
        """Every case begun on this computer, newest first, without its scenario."""
        rows = self._db.query("SELECT id, started_at, source, bank_number, topic, level, label, language_model, step "
                              "FROM teaching_case ORDER BY id DESC")
        return [dict(row) for row in rows]

    def _move(self, case_id: int, was: str, to: str, also: str = "", values: tuple = ()) -> bool:
        """One step forward, only from the step named: a stale press finds another step and changes nothing."""
        done = self._db.execute(f"UPDATE teaching_case SET step = ?{also} WHERE id = ? AND step = ?", (to, *values, case_id, was))
        return done.rowcount == 1

    def written(self, case_id: int, scenario: dict) -> bool:
        """A fresh scenario that passed its checks: the patient can appear."""
        return self._move(case_id, WRITING, HISTORY, ", scenario = ?, failure = NULL", (json.dumps(scenario, ensure_ascii=False),))

    def failed(self, case_id: int, step: str, reason: str) -> None:
        """Why the writing or the feedback did not come; the case stays at its step."""
        self._db.execute("UPDATE teaching_case SET failure = ? WHERE id = ? AND step = ?", (reason, case_id, step))

    def trying(self, case_id: int, step: str) -> None:
        """Asked again by a press: the earlier reason no longer stands."""
        self._db.execute("UPDATE teaching_case SET failure = NULL WHERE id = ? AND step = ?", (case_id, step))

    # ---------------------------------------------------------- the history

    def turns(self, case_id: int) -> list[dict]:
        rows = self._db.query("SELECT n, speaker, text, facts_used, at FROM teaching_turn WHERE case_id = ? ORDER BY n", (case_id,))
        return [dict(row) for row in rows]

    def conversation(self, case_id: int) -> list[tuple[str, str]]:
        """The consultation as the frames read it: (speaker, words), in order; the opening words are no turn."""
        return [(turn["speaker"], turn["text"]) for turn in self.turns(case_id)]

    def add_exchange(self, case_id: int, line: int, doctor: str, reply: str, facts_used: list) -> bool:
        """The learner's line and the patient's reply, together or not at
        all. line is the learner's own count, from 1; it is stored only
        while the history runs and only as the next line, so the turns
        always alternate and line k is turn 2k-1, as the bench numbered them."""
        with self._db.transaction() as con:
            row = con.execute("SELECT step FROM teaching_case WHERE id = ?", (case_id,)).fetchone()
            turns = con.execute("SELECT COUNT(*) FROM teaching_turn WHERE case_id = ?", (case_id,)).fetchone()[0]
            if row is None or row["step"] != HISTORY or turns != 2 * (line - 1):
                return False
            now = self._now()
            con.execute("INSERT INTO teaching_turn (case_id, n, speaker, text, at) VALUES (?, ?, 'doctor', ?, ?)",
                        (case_id, turns + 1, doctor, now))
            con.execute("INSERT INTO teaching_turn (case_id, n, speaker, text, facts_used, at) VALUES (?, ?, 'patient', ?, ?, ?)",
                        (case_id, turns + 2, reply, json.dumps(facts_used), now))
        return True

    def end_history(self, case_id: int) -> bool:
        return self._move(case_id, HISTORY, EXAMINATION, ", history_ended_at = ?", (self._now(),))

    # ------------------------------------------------------ the examination

    def examined(self, case_id: int) -> list[dict]:
        rows = self._db.query("SELECT n, text, asked, not_in_case, at FROM teaching_examined WHERE case_id = ? ORDER BY n", (case_id,))
        return [{**dict(row), "asked": json.loads(row["asked"]), "not_in_case": json.loads(row["not_in_case"])} for row in rows]

    def add_examined(self, case_id: int, n: int, text: str, asked: list, not_in_case: list) -> bool:
        """One request with what came back for it, as it came; only while the examination runs and only as the next."""
        with self._db.transaction() as con:
            row = con.execute("SELECT step FROM teaching_case WHERE id = ?", (case_id,)).fetchone()
            count = con.execute("SELECT COUNT(*) FROM teaching_examined WHERE case_id = ?", (case_id,)).fetchone()[0]
            if row is None or row["step"] != EXAMINATION or n != count + 1:
                return False
            con.execute("INSERT INTO teaching_examined (case_id, n, text, asked, not_in_case, at) VALUES (?, ?, ?, ?, ?, ?)",
                        (case_id, n, text, json.dumps(asked), json.dumps(not_in_case, ensure_ascii=False), self._now()))
        return True

    def finish_examination(self, case_id: int) -> bool:
        return self._move(case_id, EXAMINATION, QUESTIONS[0], ", examination_finished_at = ?", (self._now(),))

    # -------------------------------------------- the answers, the feedback

    def answer(self, case_id: int, question: int, text: str) -> bool:
        """The answer to question 1, 2 or 3, only at that question; the third brings the feedback's turn."""
        after = QUESTIONS[question] if question < len(QUESTIONS) else FEEDBACK
        return self._move(case_id, QUESTIONS[question - 1], after, f", answer_{ANSWERS[question - 1]} = ?", (text,))

    def answers(self, row: dict) -> dict:
        return {name: row[f"answer_{name}"] or "" for name in ANSWERS}

    def fed_back(self, case_id: int, answer: dict) -> bool:
        """The feedback as the door held it to its form, once: the case is finished."""
        return self._move(case_id, FEEDBACK, DONE, ", feedback = ?, failure = NULL, finished_at = ?",
                          (json.dumps(answer, ensure_ascii=False), self._now()))

    # --------------------------------------------- the record of model calls

    def tie(self, case_id: int, call_id: int) -> None:
        """A model call of this case, so that it goes when the case goes."""
        self._db.execute("INSERT OR IGNORE INTO teaching_call (call_id, case_id) VALUES (?, ?)", (call_id, case_id))

    def calls(self, case_id: int) -> list[int]:
        return [row["call_id"] for row in self._db.query("SELECT call_id FROM teaching_call WHERE case_id = ? ORDER BY call_id", (case_id,))]

    # ------------------------------------------------------------- the flags

    def flag(self, case_id: int, note: str) -> int | None:
        """The learner's flag on a finished case, kept with a copy of its
        scenario so that it outlives the case (12.3, rule 7). Once a case."""
        row = self._db.query_one("SELECT * FROM teaching_case WHERE id = ? AND step = ?", (case_id, DONE))
        if row is None or self.flag_of(case_id) is not None:
            return None
        made = self._db.execute(
            "INSERT INTO teaching_flag (case_id, flagged_at, source, bank_number, topic, level, label, note, scenario) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (case_id, self._now(), row["source"], row["bank_number"], row["topic"], row["level"], row["label"], note, row["scenario"]))
        return int(made.lastrowid)

    def flag_of(self, case_id: int) -> dict | None:
        row = self._db.query_one("SELECT id, flagged_at, note FROM teaching_flag WHERE case_id = ?", (case_id,))
        return dict(row) if row else None

    def flags(self) -> list[dict]:
        """Every flag, newest first, without its scenario."""
        rows = self._db.query("SELECT id, case_id, flagged_at, source, bank_number, topic, level, label, note FROM teaching_flag ORDER BY id DESC")
        return [dict(row) for row in rows]

    def flag_row(self, flag_id: int) -> dict | None:
        row = self._db.query_one("SELECT * FROM teaching_flag WHERE id = ?", (flag_id,))
        return {**dict(row), "scenario": json.loads(row["scenario"])} if row else None

    def remove_flag(self, flag_id: int) -> bool:
        return self._db.execute("DELETE FROM teaching_flag WHERE id = ?", (flag_id,)).rowcount == 1

    # ------------------------------------------------------------ the delete

    def delete(self, case_id: int) -> dict | None:
        """Every row of one case and every stored model call of it, in one
        transaction (ruling 22): the counts by name, or None when there is
        no such case, so a second delete removes nothing. A flag stays,
        no longer pointing to a case."""
        with self._db.transaction() as con:
            row = con.execute("SELECT started_at, answer_differential, answer_investigations, answer_plan, feedback "
                              "FROM teaching_case WHERE id = ?", (case_id,)).fetchone()
            if row is None:
                return None
            counts = {name: con.execute(sql, (case_id,)).rowcount for name, sql in ROW_DELETIONS}
            calls = [found[0] for found in con.execute("SELECT call_id FROM teaching_call WHERE case_id = ?", (case_id,)).fetchall()]
            con.execute("DELETE FROM teaching_call WHERE case_id = ?", (case_id,))
            con.executemany("DELETE FROM model_call WHERE id = ?", [(call_id,) for call_id in calls])
            flags = con.execute("UPDATE teaching_flag SET case_id = NULL WHERE case_id = ?", (case_id,)).rowcount
            con.execute("DELETE FROM teaching_case WHERE id = ?", (case_id,))
        return {**counts, "answers": sum(1 for name in ANSWERS if row[f"answer_{name}"] is not None),
                "feedback": 1 if row["feedback"] else 0, "model_calls": len(calls), "flags_kept": flags,
                "date": row["started_at"][:10]}
