"""The settings a page can change (spec 7.3 rule 4; 15.11 ruling 7):
read fresh each time, audited from what to what."""

import pytest

from openconsult.db import open_database
from openconsult.patients.audit import Audit
from openconsult.settings.stored import DEFAULT_RETENTION_DAYS, Stored, retention_problem


def test_ruling_7_7_3_the_retention_days_default_to_90_and_a_change_is_audited_from_what_to_what(tmp_path, clock):
    db = open_database(tmp_path / "openconsult.db")
    audit = Audit(db, clock)
    stored = Stored(db, audit, clock)
    assert stored.audio_retention_days == DEFAULT_RETENTION_DAYS == 90
    stored.set_audio_retention_days(30)
    assert stored.audio_retention_days == 30
    assert (audit.lines()[0].event, audit.lines()[0].detail) == ("setting.changed", "audio_retention_days from the default to 30")
    stored.set_audio_retention_days(0)                 # 0 keeps
    assert stored.audio_retention_days == 0 and audit.lines()[0].detail == "audio_retention_days from 30 to 0"
    stored.set_audio_retention_days(0)                 # the same value writes nothing
    assert len([l for l in audit.lines() if l.event == "setting.changed"]) == 2
    assert Stored(db, audit, clock).audio_retention_days == 0    # read from the table, not from memory
    for bad in (-1, True, "7"):
        with pytest.raises(ValueError):
            stored.set_audio_retention_days(bad)
    assert retention_problem(" 45 ") == 45 and retention_problem("0") == 0
    assert retention_problem("-1") is None and retention_problem("ten") is None and retention_problem("") is None
    db.close()
