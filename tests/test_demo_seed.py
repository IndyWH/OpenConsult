"""Demo data isolation (DOCKER_DEMO_SPEC.md §2.1): seed and reset touch
only what seeding created, and refuse anything they cannot prove is
theirs. The refusal property is the point of this file — the #70 lesson
says the demo must be structurally unable to touch a real row."""

import json
import os

import psycopg
import pytest
from dotenv import load_dotenv

from scripts.reset_demo import reset
from scripts.seed_demo import MARKER, seed

load_dotenv()


def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=2):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")


def _query(sql, params=()):
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        return conn.execute(sql, params).fetchall()


@pytest.fixture()
def control_rows():
    """A NON-demo patient with a consultation — the rows reset must
    never touch. Cleaned up by this fixture, not by reset (that is the
    property under test)."""
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        pid = conn.execute(
            "INSERT INTO patient (name, age, sex)"
            " VALUES ('Control Patient', 40, 'F') RETURNING id").fetchone()[0]
        cid = conn.execute(
            "INSERT INTO consultation (patient_id) VALUES (%s) RETURNING id",
            (pid,)).fetchone()[0]
    yield pid, cid
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        conn.execute("DELETE FROM consultation WHERE id = %s", (cid,))
        conn.execute("DELETE FROM patient WHERE id = %s", (pid,))


def test_seed_reset_roundtrip_touches_only_demo_rows(tmp_path, control_rows):
    control_pid, control_cid = control_rows
    manifest_path = tmp_path / "demo_seed.json"
    manifest = seed(manifest_path)

    # The demo rows exist and are visibly marked.
    for pid in manifest["patients"]:
        (name,), = _query("SELECT name FROM patient WHERE id = %s", (pid,))
        assert name.startswith(MARKER)
    # A consultation recorded against a demo patient DURING the demo.
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        demo_cid = conn.execute(
            "INSERT INTO consultation (patient_id) VALUES (%s) RETURNING id",
            (manifest["patients"][0],)).fetchone()[0]

    report = reset(manifest_path)

    assert report["refused"] == []
    assert sorted(report["patients_deleted"]) == sorted(manifest["patients"])
    assert demo_cid in report["consultations_deleted"]
    assert not manifest_path.exists()  # clean teardown consumes the manifest
    # Demo rows gone; queue entries went with their patients (cascade).
    assert _query("SELECT 1 FROM patient WHERE id = ANY(%s)",
                  (manifest["patients"],)) == []
    assert _query("SELECT 1 FROM queue_entry WHERE id = ANY(%s)",
                  (manifest["queue_entries"],)) == []
    # The demo account is deactivated, never deleted.
    (active, pending), = _query(
        "SELECT active, pending_approval FROM app_user WHERE id = %s",
        (manifest["demo_user_id"],))
    assert (active, pending) == (False, False)
    # And the control rows survived untouched.
    assert _query("SELECT 1 FROM patient WHERE id = %s", (control_pid,))
    assert _query("SELECT 1 FROM consultation WHERE id = %s", (control_cid,))


def test_reset_refuses_a_row_that_lost_its_marker(tmp_path):
    """The tamper case: a manifest id whose row no longer carries the
    marker cannot be proven synthetic, so reset must leave it alone and
    say so — refusing, not skipping silently."""
    manifest_path = tmp_path / "demo_seed.json"
    manifest = seed(manifest_path)
    victim = manifest["patients"][0]
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        # The attack reaches the thing tested: the row IS in the manifest
        # but now looks like a real patient.
        conn.execute("UPDATE patient SET name = 'Realish Patient'"
                     " WHERE id = %s", (victim,))
    try:
        report = reset(manifest_path)
        assert any(r.get("patient_id") == victim for r in report["refused"])
        assert _query("SELECT 1 FROM patient WHERE id = %s", (victim,))
        # A refusal keeps the manifest for inspection.
        assert manifest_path.exists()
        # The other, still-marked rows were cleaned normally.
        others = [p for p in manifest["patients"] if p != victim]
        assert _query("SELECT 1 FROM patient WHERE id = ANY(%s)",
                      (others,)) == []
    finally:  # the refused row is ours to clean, outside reset
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            conn.execute("DELETE FROM patient WHERE id = %s", (victim,))


def test_seed_refuses_to_double_seed(tmp_path):
    manifest_path = tmp_path / "demo_seed.json"
    seed(manifest_path)
    try:
        with pytest.raises(SystemExit, match="reset"):
            seed(manifest_path)
        # The first manifest was not clobbered.
        assert json.loads(manifest_path.read_text())["patients"]
    finally:
        reset(manifest_path)


def test_reset_refuses_with_no_manifest(tmp_path):
    with pytest.raises(SystemExit, match="nothing was seeded"):
        reset(tmp_path / "never_seeded.json")
