"""The settings a page can change (spec 7.3, rule 4; 15.11 ruling 7),
kept in the setting table of the data folder and read fresh at each
use, so a change takes effect at the next sweep or the next consultation
and never during one. Every change is written to the audit log, from
what to what. The first of them is the retention time for recordings:
days, default 90; 0 keeps a recording until its consultation is deleted.
Run 9b adds the path: the language model and the transcription, each on
this computer or at its cloud service, the tick for better accuracy, and
the checksum of the cloud statement last ticked. No other code reads
the table."""

from __future__ import annotations

import json

from openconsult.db import Database
from openconsult.patients.audit import Audit, Clock, now_local
from openconsult.settings.path import LANGUAGE_MODELS, TRANSCRIPTIONS, ChosenPath, beginning
from openconsult.settings.statement import sentences_of, words_checksum

AUDIO_RETENTION_DAYS = "audio_retention_days"
# The path of a consultation (7.3; 15.13, the details of run 9b): where the language model and the transcription
# run, the tick for better accuracy, and the checksum of the cloud statement as it was last ticked.
LANGUAGE_MODEL, TRANSCRIPTION, BETTER_ACCURACY, STATEMENT_TICKED = "language_model", "transcription", "better_accuracy", "statement_ticked"
# Run 9c (15.13, ruling 48): what is kept beside that checksum, so that a path that sends less asks for no new tick.
STATEMENT_KEPT = "statement_ticked_kept"
ON, OFF = "on", "off"
# v1's default (its retention module; V1_LESSONS 10.5).
DEFAULT_RETENTION_DAYS = 90


def retention_problem(text: str) -> int | None:
    """The days a form gave, or None when it is not a whole number of
    days from 0 up."""
    text = (text or "").strip()
    if not text.isdigit():
        return None
    return int(text)


class Stored:
    def __init__(self, db: Database, audit: Audit, clock: Clock = now_local):
        self._db = db
        self._audit = audit
        self._clock = clock

    def _get(self, name: str) -> str | None:
        found = self._db.query_one("SELECT value FROM setting WHERE name = ?", (name,))
        return found["value"] if found else None

    def _set(self, name: str, value: str, was: str | None = None) -> None:
        """was: what the setting read before, where a setting never saved
        reads something better than the default (the path, by the machine)."""
        before = was if was is not None else self._get(name)
        self._db.execute("INSERT OR REPLACE INTO setting (name, value, changed_at) VALUES (?, ?, ?)",
                         (name, value, self._clock().isoformat(timespec="seconds")))
        self._audit.record("setting.changed", f"{name} from {before if before is not None else 'the default'} to {value}")

    @property
    def audio_retention_days(self) -> int:
        value = self._get(AUDIO_RETENTION_DAYS)
        return int(value) if value is not None and value.isdigit() else DEFAULT_RETENTION_DAYS

    def set_audio_retention_days(self, days: int) -> None:
        if not isinstance(days, int) or isinstance(days, bool) or days < 0:
            raise ValueError("days is a whole number from 0 up")
        if days != self.audio_retention_days or self._get(AUDIO_RETENTION_DAYS) is None:
            self._set(AUDIO_RETENTION_DAYS, str(days))

    # ------------------------------------------------------- the path (9b)

    def path(self, machine_case: str) -> ChosenPath:
        """The two settings and the tick as they stand now. A setting never
        saved reads the machine's beginning (10.3)."""
        begin = beginning(machine_case)
        model, speech = self._get(LANGUAGE_MODEL), self._get(TRANSCRIPTION)
        return ChosenPath(model if model in LANGUAGE_MODELS else begin.language_model,
                          speech if speech in TRANSCRIPTIONS else begin.transcription,
                          self._get(BETTER_ACCURACY) == ON)

    def set_path(self, machine_case: str, path: ChosenPath) -> None:
        """Each setting that changes is written and audited, from what to
        what (7.3, rule 4); one that stays is not written."""
        if path.language_model not in LANGUAGE_MODELS or path.transcription not in TRANSCRIPTIONS:
            raise ValueError("not a path the app knows")
        before = self.path(machine_case)
        if path.language_model != before.language_model:
            self._set(LANGUAGE_MODEL, path.language_model, was=before.language_model)
        if path.transcription != before.transcription:
            self._set(TRANSCRIPTION, path.transcription, was=before.transcription)
        if path.better_accuracy != before.better_accuracy:
            self._set(BETTER_ACCURACY, ON if path.better_accuracy else OFF, was=ON if before.better_accuracy else OFF)

    @property
    def ticked_sha256(self) -> str | None:
        """The checksum of the cloud statement as it was last ticked."""
        return self._get(STATEMENT_TICKED)

    def tick_statement(self, sha256: str, path: ChosenPath, statement=None) -> None:
        """The tick, with the checksum of the text ticked and its path, in
        the audit log (15.13, ruling 5; 7.3, rule 4). statement: the
        statement that was ticked, as shown; with it the app also keeps
        its sentences and one checksum of every word a statement can be
        built from, so that a later path that sends less can be told
        (ruling 48). With none, the checksum is kept alone, as before
        run 9c, and nothing that was kept for an earlier tick stays."""
        now = self._clock().isoformat(timespec="seconds")
        self._db.execute("INSERT OR REPLACE INTO setting (name, value, changed_at) VALUES (?, ?, ?)", (STATEMENT_TICKED, sha256, now))
        if statement is None:
            self._db.execute("DELETE FROM setting WHERE name = ?", (STATEMENT_KEPT,))
        else:
            kept = json.dumps({"sentences": list(sentences_of(statement)), "words": words_checksum()}, ensure_ascii=False)
            self._db.execute("INSERT OR REPLACE INTO setting (name, value, changed_at) VALUES (?, ?, ?)", (STATEMENT_KEPT, kept, now))
        self._audit.record("statement.ticked", f"{path.key()}; sha256 {sha256}")

    def ticked(self, statement) -> bool:
        """Whether the statement of a path stands ticked: true for a path
        with nothing to say, false when a choice or a word has changed
        since the tick."""
        return statement is None or statement.sha256 == self.ticked_sha256

    def covers(self, statement) -> bool:
        """Whether a path may be used without a new tick (15.13, ruling 48):
        its statement stands ticked; or it sends less than the statement
        that was ticked, which is so when every sentence of its own list
        What is sent and of its own service parts stood, word for word,
        in that one. That test is made only while no word a statement can
        be built from has changed since the tick, and only where the
        sentences were kept with it: a folder that ticked before run 9c
        holds a checksum alone, and is asked once more."""
        if self.ticked(statement):
            return True
        try:
            kept = json.loads(self._get(STATEMENT_KEPT) or "null")
        except ValueError:
            kept = None
        if not isinstance(kept, dict) or kept.get("words") != words_checksum():
            return False
        return set(sentences_of(statement)) <= set(kept.get("sentences") or [])

    def note_covered(self, path: ChosenPath, statement) -> None:
        """The audit line of a path saved under the wider tick, with both
        checksums (ruling 48; 7.3, rule 4). The tick that stands is not
        touched: it stays the wider one."""
        self._audit.record("statement.covered", f"{path.key()}; saved under the wider tick; sha256 of this path's statement "
                           f"{statement.sha256}; sha256 of the statement ticked {self.ticked_sha256}")
