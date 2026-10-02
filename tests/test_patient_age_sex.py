"""Age and sex reach the model: the front desk and the live path (owner
ruling 2026-10-02, Task 5).

The front desk insists on both when a consultation entry is created —
POST /api/queue and the walk-in — with a 400 and a plain message, before
anything is written. The live session reads them once from the patient
row and hands them to engine.update at every pass, a runaway pass
included. Rows already in the table are not touched: no migration, and a
row without age or sex gives a pass exactly as before (no patient
argument at all). The model side — the line itself and which calls carry
it — is pinned in tests/test_cds_patient_line.py.
"""

from __future__ import annotations

import asyncio
import os
import secrets
import types

import psycopg
import pytest
from conftest import approve_account
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from app import audit, auth, consultations, frontdesk, system_utterances
from app import main as appmain
from app.cds import CDSRunaway
from test_cds_first_call import (EMPTY_ASSESSMENT, QueueTranscriber, _drain_for_cds,
                                 _feed_audio)

load_dotenv()


def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=2):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")


def _query(sql: str, params: tuple = ()) -> list[tuple]:
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        return conn.execute(sql, params).fetchall()


def _patients_named(name: str) -> int:
    return _query("SELECT count(*) FROM patient WHERE name = %s", (name,))[0][0]


@pytest.fixture(scope="module")
def clients():
    """A receptionist and a doctor, each with its own session cookie."""
    auth.ensure_schema()
    frontdesk.ensure_schema()
    consultations.ensure_schema()
    audit.ensure_schema()
    out = {}
    for role in ("doctor", "receptionist"):
        client = TestClient(appmain.app)
        username = f"{role}_{secrets.token_hex(4)}"
        assert client.post("/api/register", json={
            "username": username, "password": "test-password-123",
            "display_name": role.title(), "role": role}).status_code == 200
        approve_account(username)
        assert client.post("/api/login", json={
            "username": username, "password": "test-password-123"}).status_code == 200
        out[role] = client
    return out


def _close_active(client) -> None:
    for q in client.get("/api/queue").json():
        if q["status"] == "in_consultation":
            client.post(f"/api/queue/{q['entry_id']}/close", json={"outcome": "cancelled"})


REFUSED = [
    ({}, "age"),
    ({"sex": "F"}, "age"),
    ({"age": None, "sex": "F"}, "age"),
    ({"age": -1, "sex": "F"}, "age"),
    ({"age": 121, "sex": "M"}, "age"),
    ({"age": 31.5, "sex": "F"}, "age"),
    ({"age": "31", "sex": "F"}, "age"),
    ({"age": True, "sex": "M"}, "age"),
    ({"age": 31}, "sex"),
    ({"age": 31, "sex": None}, "sex"),
    ({"age": 31, "sex": ""}, "sex"),
    ({"age": 31, "sex": "X"}, "sex"),
    ({"age": 31, "sex": "f"}, "sex"),
    ({"age": 31, "sex": "female"}, "sex"),
]


# ------------------------------------------------------------ front desk

@pytest.mark.parametrize("extra, missing", REFUSED)
def test_add_to_queue_refuses_without_age_and_sex(clients, extra, missing):
    name = f"Refused {secrets.token_hex(4)}"
    response = clients["receptionist"].post("/api/queue", json={"name": name, **extra})
    assert response.status_code == 400
    error = response.json()["error"]
    assert isinstance(error, str) and error.startswith(f"{missing} is required")
    assert _patients_named(name) == 0, "a refused entry must write nothing"


@pytest.mark.parametrize("extra, missing", REFUSED)
def test_walk_in_refuses_without_age_and_sex(clients, extra, missing):
    doctor = clients["doctor"]
    _close_active(doctor)
    name = f"Refused walk-in {secrets.token_hex(4)}"
    response = doctor.post("/api/queue/walk-in", json={"name": name, **extra})
    assert response.status_code == 400
    assert response.json()["error"].startswith(f"{missing} is required")
    assert _patients_named(name) == 0
    assert all(q["status"] != "in_consultation" for q in doctor.get("/api/queue").json()), \
        "a refused walk-in must not take the live slot"


def test_the_refusal_comes_before_the_slot_guard(clients):
    """A walk-in with no age or sex is refused for that, even while another
    consultation holds the slot — the plain message, not the 409."""
    doctor = clients["doctor"]
    _close_active(doctor)
    held = doctor.post("/api/queue/walk-in", json={"name": "Slot Holder", "age": 50, "sex": "M"})
    assert held.status_code == 200
    try:
        response = doctor.post("/api/queue/walk-in", json={"name": "No Details"})
        assert response.status_code == 400
        assert response.json()["error"].startswith("age is required")
    finally:
        _close_active(doctor)


@pytest.mark.parametrize("age, sex", [(31, "F"), (46, "M"), (0, "F"), (120, "M"), (15, "M")])
def test_both_routes_accept_and_store_age_and_sex(clients, age, sex):
    name = f"Accepted {secrets.token_hex(4)}"
    added = clients["receptionist"].post("/api/queue", json={"name": name, "age": age, "sex": sex})
    assert added.status_code == 200
    assert set(added.json()) == {"entry_id", "patient_id", "position"}   # the shape is unchanged
    assert _query("SELECT age, sex FROM patient WHERE id = %s",
                  (added.json()["patient_id"],)) == [(age, sex)]

    doctor = clients["doctor"]
    _close_active(doctor)
    walk = doctor.post("/api/queue/walk-in", json={"name": name + " w", "age": age, "sex": sex})
    try:
        assert walk.status_code == 200
        assert (walk.json()["age"], walk.json()["sex"]) == (age, sex)
        assert _query("SELECT age, sex FROM patient WHERE id = %s",
                      (walk.json()["patient_id"],)) == [(age, sex)]
    finally:
        _close_active(doctor)


def test_old_rows_are_not_touched():
    """No migration: the columns still take NULL, and a row without age or
    sex made before 2026-10-02 still reads back as it was."""
    nullable = dict(_query(
        "SELECT column_name, is_nullable FROM information_schema.columns "
        "WHERE table_name = 'patient' AND column_name IN ('age', 'sex')"))
    assert nullable == {"age": "YES", "sex": "YES"}
    old = asyncio.run(frontdesk.add_to_queue(f"Old row {secrets.token_hex(4)}", None, None))
    row = asyncio.run(frontdesk.get_patient(old["patient_id"]))
    assert (row["age"], row["sex"]) == (None, None)


def test_the_forms_mark_age_and_sex_required_and_show_the_servers_message():
    today = open("app/static/today.html").read()
    live = open("app/static/live.html").read()
    for page, form_id in ((today, "addForm"), (today, "walkinForm"), (live, "liveWalkin")):
        start = page.index(f'id="{form_id}"')
        form = page[start:page.index("</form>", start)]
        assert '<input name="age" type="number"' in form
        age = form[form.index('<input name="age"'):]
        assert age[:age.index(">")].rstrip().endswith("required"), form_id
        assert '<select name="sex" required>' in form, form_id
        assert 'class="err"' in form and 'role="alert"' in form, form_id
    # Each handler writes the server's {"error"} into its form's message.
    assert "errEl.textContent = await serverError(response);" in today
    assert today.count("errEl.textContent = await serverError(response);") == 2
    assert "body.error" in today[today.index("async function serverError"):]
    walkin = live[live.index("getElementById('liveWalkin').addEventListener"):]
    walkin = walkin[:walkin.index("\n});") + 4]
    assert "response.status === 400" in walkin
    assert "(await response.json()).error" in walkin
    assert "errEl.textContent = detail" in walkin


# -------------------------------------------------------------- live path

class PatientCDS:
    """Records what each pass was given. Pass `runaway_on` raises a runaway
    carrying an alarm, as CDSEngine.update does when its assessment call
    hits its cap."""

    def __init__(self, runaway_on: int | None = None):
        self.calls: list[dict] = []
        self.runaway_on = runaway_on

    async def update(self, transcript, previous=None, **kwargs):
        self.calls.append({"transcript": transcript, **kwargs})
        if len(self.calls) == self.runaway_on:
            exc = CDSRunaway("assessment", reason="cap", tokens=1500, elapsed_ms=9000, cap=1500)
            exc.urgency = {"urgency_check": {"time_critical_possible": True,
                                             "already_done_or_arranged": False,
                                             "reason": "possible ectopic"},
                           "urgent_actions": [{"action": "Pregnancy test",
                                               "reason": "possible ectopic"}]}
            raise exc
        return dict(EMPTY_ASSESSMENT)


@pytest.fixture()
def live_env(monkeypatch, tmp_path):
    consultations.ensure_schema()
    system_utterances.ensure_schema()
    frontdesk.ensure_schema()
    state = appmain.app.state
    missing = object()
    installed = {
        "transcriber": QueueTranscriber(),
        "speech": object(),
        "cds_engine": None,
        "rag": types.SimpleNamespace(answer_for_conditions=None),
        "live_sessions": {},
        "finalize_queue": asyncio.Queue(),
    }
    previous = {name: getattr(state, name, missing) for name in installed}
    for name, value in installed.items():
        setattr(state, name, value)
    monkeypatch.setattr(appmain, "RECORDINGS_DIR", tmp_path)
    try:
        yield state
    finally:
        for name, old in previous.items():
            if old is missing:
                delattr(state, name)
            else:
                setattr(state, name, old)


def _doctor() -> TestClient:
    auth.ensure_schema()
    user = asyncio.run(auth.create_user(
        f"doctor_{secrets.token_hex(4)}", "test-password-123", "Doctor", "doctor"))
    client = TestClient(appmain.app)
    client.cookies.set(auth.COOKIE_NAME, auth.sign_session(user["id"]))
    return client


def _three_passes(state, patient_id) -> list[dict]:
    """A session with three CDS passes; returns what each pass was given."""
    transcriber: QueueTranscriber = state.transcriber
    config = {"session_id": secrets.token_hex(8)}
    if patient_id is not None:
        config["patient_id"] = patient_id
    with _doctor().websocket_connect("/ws/transcribe") as ws:
        ws.send_json(config)
        transcriber.say("I have a pain low down in my tummy.")
        seq = _feed_audio(ws, 12.0, 0)
        for long_turn in (
                "It started two days ago on the right side and it has been getting "
                "steadily worse since then, sharp and constant, and walking about or "
                "coughing makes it much worse than it was yesterday.",
                "My last period was about seven weeks ago, which is late for me, and this "
                "morning I had some spotting and felt quite dizzy when I stood up in the kitchen "
                "to make the tea."):
            transcriber.say(long_turn)
            seq = _feed_audio(ws, 12.0, seq)
        _drain_for_cds(ws)
    return state.cds_engine.calls


def _patient_row(age, sex) -> int:
    entry = asyncio.run(frontdesk.add_to_queue(f"Live {secrets.token_hex(4)}", age, sex))
    return entry["patient_id"]


def test_every_pass_gets_the_patients_age_and_sex(live_env):
    live_env.cds_engine = PatientCDS()
    calls = _three_passes(live_env, _patient_row(31, "F"))
    assert len(calls) == 3, "three passes ran"
    for call in calls:
        assert call["patient"] == {"age": 31, "sex": "F"}   # age and sex only, never the name


def test_a_runaway_pass_does_not_lose_the_patient(live_env):
    """The runaway path: the pass that ran away was given the patient (its
    urgency call is told who the patient is, in app/cds.py), and so is
    every pass after it."""
    live_env.cds_engine = PatientCDS(runaway_on=1)
    calls = _three_passes(live_env, _patient_row(15, "M"))
    assert len(calls) == 3
    assert [c["patient"] for c in calls] == [{"age": 15, "sex": "M"}] * 3


@pytest.mark.parametrize("age, sex", [(None, None), (40, None), (None, "F"), (40, "X")])
def test_an_old_row_without_age_or_sex_gives_todays_call(live_env, age, sex):
    live_env.cds_engine = PatientCDS()
    calls = _three_passes(live_env, _patient_row(age, sex))
    assert len(calls) == 3
    assert all(set(c) == {"transcript"} for c in calls), "no patient argument at all"


def test_no_linked_patient_gives_todays_call(live_env):
    live_env.cds_engine = PatientCDS()
    calls = _three_passes(live_env, None)
    assert len(calls) == 3
    assert all(set(c) == {"transcript"} for c in calls)
