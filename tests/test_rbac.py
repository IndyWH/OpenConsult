"""Role-based access control and the full front-desk loop.

The critical assertion set: the receptionist role must get 403s on ALL
clinical content — live page, review page, transcripts, notes, and every
mutation endpoint — while retaining queue management. Enforcement is
server-side; the UI merely hides what the server already refuses.
"""

import asyncio
import os
import secrets

import psycopg
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from app import audit, auth, consultations, frontdesk

load_dotenv()


def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=2):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")


@pytest.fixture(scope="module")
def clients():
    """One TestClient per role, each with its own session cookie."""
    auth.ensure_schema()
    frontdesk.ensure_schema()
    consultations.ensure_schema()
    audit.ensure_schema()
    from app.main import app

    out = {}
    for role in ("doctor", "receptionist"):
        client = TestClient(app)
        username = f"{role}_{secrets.token_hex(4)}"
        response = client.post(
            "/api/register",
            json={"username": username, "password": "test-password-123",
                  "display_name": role.title(), "role": role},
        )
        assert response.status_code == 200
        # NB: the very first user ever registered becomes admin (bootstrap);
        # make sure this fixture's users really carry the intended role.
        if response.json()["user"]["role"] != role:
            client = TestClient(app)
            username = f"{role}_{secrets.token_hex(4)}"
            response = client.post(
                "/api/register",
                json={"username": username, "password": "test-password-123",
                      "display_name": role.title(), "role": role},
            )
            assert response.json()["user"]["role"] == role
        out[role] = client
    return out


@pytest.fixture()
def consultation_id():
    async def build() -> int:
        cid = await consultations.create_consultation()
        await consultations.save_turns(
            cid, [{"role": "Doctor", "start": 0.0, "end": 2.0,
                   "text": "Hello.", "confidence": 0.9}]
        )
        await consultations.save_note(
            cid, {"subjective": [{"text": "Hi", "turns": [0], "uncited": False,
                                  "flagged": False}],
                  "objective": [], "assessment": [], "plan": []}
        )
        await consultations.set_status(cid, "awaiting_review")
        return cid

    return asyncio.run(build())


def _close_active(client) -> None:
    """Close any in-consultation entries so the concurrency guard doesn't
    refuse the start under test (also how real zombies get cleaned up)."""
    for q in client.get("/api/queue").json():
        if q["status"] == "in_consultation":
            client.post(f"/api/queue/{q['entry_id']}/close",
                        json={"outcome": "cancelled"})


def test_anonymous_is_locked_out():
    from app.main import app

    client = TestClient(app)
    assert client.get("/api/queue").status_code == 401
    assert client.get("/api/consultations/1").status_code == 401
    # Pages redirect anonymous users to login
    response = client.get("/today", follow_redirects=False)
    assert response.status_code == 307 and response.headers["location"] == "/login"


def test_monitor_pulse_is_deliberately_public_and_aggregate_only(clients):
    """/api/monitor/pulse is the one deliberate exception to the
    logged-in wall: unauthenticated by design for external-demo
    observation. The counterpart obligation is that it exposes aggregate
    counts ONLY — never a username, patient name, or clinical content —
    which the shape assertion makes structural: every value is a number
    or boolean except one ISO timestamp, so a name cannot leak."""
    from app import monitor
    from app.main import app

    anon = TestClient(app)  # no session cookie at all
    monitor.invalidate_cache()
    response = anon.get("/api/monitor/pulse")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "server_time", "registrations_today", "logins_today",
        "consultations_started_today", "finalisations_failed_today",
        "live_consultation_active", "live_slot_rejections_today",
        "registrations_last_hour", "logins_last_hour",
        "consultations_started_last_hour", "finalisations_failed_last_hour",
        "live_slot_rejections_last_hour",
        "errors_last_hour", "audio_disk_used_mb",
    }
    assert isinstance(body["live_consultation_active"], bool)
    assert isinstance(body["server_time"], str)
    for key in body.keys() - {"server_time", "live_consultation_active"}:
        assert isinstance(body[key], (int, float)), key
    # This module's fixture registered users today, so the counters are
    # provably live, not hardcoded zeros.
    assert body["registrations_today"] >= 2

    # Belt and braces on top of the shape assertion: no username,
    # display name, or patient name actually in the database appears
    # anywhere in the serialised response.
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        names = [r[0] for r in conn.execute(
            "SELECT username FROM app_user"
            " UNION SELECT display_name FROM app_user"
            " UNION SELECT name FROM patient").fetchall()]
    text = response.text.lower()
    for name in names:
        if name and len(name) >= 4:  # short test junk can't match digits anyway
            assert name.lower() not in text


def test_monitor_pulse_counts_slot_rejections(clients):
    """The one-active-consultation guard firing is expected under
    concurrent demo users — the pulse counts it separately from errors."""
    from app import monitor
    from app.main import app

    doctor = clients["doctor"]
    _close_active(doctor)
    monitor.invalidate_cache()
    before = TestClient(app).get("/api/monitor/pulse").json()

    first = doctor.post("/api/queue/walk-in", json={"name": "Pulse Guard Patient"})
    assert first.status_code == 200
    blocked = doctor.post("/api/queue/walk-in", json={"name": "Pulse Second Patient"})
    assert blocked.status_code == 409  # the guard fired…

    monitor.invalidate_cache()
    after = TestClient(app).get("/api/monitor/pulse").json()
    # …and was counted as a rejection, not an error.
    assert after["live_slot_rejections_today"] == before["live_slot_rejections_today"] + 1
    assert after["errors_last_hour"] == before["errors_last_hour"]
    _close_active(doctor)


def test_receptionist_gets_403_on_all_clinical_content(clients, consultation_id):
    recep = clients["receptionist"]
    cid = consultation_id

    assert recep.get("/live", follow_redirects=False).status_code == 403
    assert recep.get(f"/review/{cid}", follow_redirects=False).status_code == 403
    assert recep.get(f"/api/consultations/{cid}").status_code == 403  # transcript+note
    assert recep.post(f"/api/consultations/{cid}/approve", json={"text": "S:"}).status_code == 403
    assert recep.post(f"/api/consultations/{cid}/regenerate").status_code == 403
    assert recep.post(f"/api/consultations/{cid}/swap-roles").status_code == 403
    assert recep.post(f"/api/consultations/{cid}/acknowledge-urgent").status_code == 403
    assert recep.patch(f"/api/consultations/{cid}/turns/0", json={"text": "x"}).status_code == 403
    assert recep.get("/api/audit").status_code == 403
    # Doctor-only queue actions:
    assert recep.post("/api/queue/999999/start").status_code == 403
    assert recep.post("/api/queue/walk-in", json={"name": "X"}).status_code == 403
    assert recep.get("/api/queue/999999/resume").status_code == 403


def test_doctor_cannot_manage_queue_but_can_open_clinical(clients, consultation_id):
    doctor = clients["doctor"]
    assert doctor.post("/api/queue", json={"name": "X"}).status_code == 403  # front desk job
    assert doctor.get(f"/api/consultations/{consultation_id}").status_code == 200
    assert doctor.get(f"/review/{consultation_id}").status_code == 200


def test_doctor_walk_in_grants_no_broader_queue_rights(clients):
    doctor = clients["doctor"]
    _close_active(doctor)

    # The walk-in shortcut works: patient registered + entry created
    # directly in consultation, distinct audit event recorded.
    response = doctor.post(
        "/api/queue/walk-in", json={"name": "Walk-in Test Patient", "age": 61, "sex": "M"}
    )
    assert response.status_code == 200
    entry = response.json()
    queue = doctor.get("/api/queue").json()
    mine = next(q for q in queue if q["entry_id"] == entry["entry_id"])
    assert mine["status"] == "in_consultation"
    assert mine["name"] == "Walk-in Test Patient"
    events = asyncio.run(audit.recent(50))
    assert ("queue.walk_in_started", entry["entry_id"]) in {
        (e["action"], e["subject_id"]) for e in events
    }
    # A walk-in entry was never 'waiting', so it cannot be started again.
    assert doctor.post(f"/api/queue/{entry['entry_id']}/start").status_code == 409

    # The live page's patient banner reads identity from the server, not the
    # URL: the entry-state API carries name/age/sex for the walk-in path.
    detail = doctor.get(f"/api/queue/{entry['entry_id']}").json()
    assert (detail["name"], detail["age"], detail["sex"], detail["status"]) == (
        "Walk-in Test Patient", 61, "M", "in_consultation"
    )
    # …and via /current (how /live resolves identity when opened by nav tab).
    current = doctor.get("/api/queue/current").json()
    assert current["patient_id"] == entry["patient_id"]
    assert doctor.get("/api/queue/999999").status_code == 404

    # …but the doctor still has NO other queue management rights.
    assert doctor.post("/api/queue", json={"name": "X"}).status_code == 403
    assert doctor.post(
        f"/api/queue/{entry['entry_id']}/move?direction=up"
    ).status_code == 403

    # Blank names are rejected (the form requires one; so does the API).
    assert doctor.post("/api/queue/walk-in", json={"name": "  "}).status_code == 400


def test_zombie_lifecycle_resume_close_and_concurrency_guard(clients):
    recep, doctor = clients["receptionist"], clients["doctor"]
    _close_active(doctor)

    # An abandoned session: walk-in started, browser closed, no Stop.
    zombie = doctor.post(
        "/api/queue/walk-in", json={"name": "Zombie Patient", "age": 30, "sex": "F"}
    ).json()

    # (1) Resume: no consultation record exists yet → back to the live page.
    resume = doctor.get(f"/api/queue/{zombie['entry_id']}/resume")
    assert resume.status_code == 200
    assert resume.json() == {"mode": "live", "entry_id": zombie["entry_id"]}

    # (3) Concurrency guard: starting anything else while the zombie is
    # active is refused, and the refusal names the active entry.
    blocked = doctor.post("/api/queue/walk-in", json={"name": "Second Patient"})
    assert blocked.status_code == 409
    assert blocked.json()["active"]["entry_id"] == zombie["entry_id"]
    waiting = recep.post("/api/queue", json={"name": "Waiting Patient", "age": 25}).json()
    blocked = doctor.post(f"/api/queue/{waiting['entry_id']}/start")
    assert blocked.status_code == 409
    assert blocked.json()["active"]["entry_id"] == zombie["entry_id"]

    # (2) Close-without-consultation — receptionist may do it too; the
    # audit event is distinct from a completed consultation.
    assert recep.post(
        f"/api/queue/{zombie['entry_id']}/close", json={"outcome": "cancelled"}
    ).status_code == 200
    queue = recep.get("/api/queue").json()
    assert next(q for q in queue if q["entry_id"] == zombie["entry_id"])["status"] == "cancelled"
    events = asyncio.run(audit.recent(50))
    cancel = next(e for e in events if e["action"] == "queue.cancelled"
                  and e["subject_id"] == zombie["entry_id"])
    assert cancel["detail"]["from_status"] == "in_consultation"
    # Closing an already-closed entry is refused; bad outcomes are rejected.
    assert recep.post(f"/api/queue/{zombie['entry_id']}/close",
                      json={"outcome": "cancelled"}).status_code == 409
    assert doctor.post(f"/api/queue/{waiting['entry_id']}/close",
                       json={"outcome": "destroyed"}).status_code == 400

    # Guard lifted: the waiting patient can start now…
    started = doctor.post(f"/api/queue/{waiting['entry_id']}/start")
    assert started.status_code == 200

    # …and once a consultation record exists for that patient, Resume
    # routes to its review page instead of the live page.
    cid = asyncio.run(consultations.create_consultation(started.json()["patient_id"], None))
    resume = doctor.get(f"/api/queue/{waiting['entry_id']}/resume")
    assert resume.json() == {"mode": "review", "consultation_id": cid}

    # RBAC unchanged: doctor still cannot add/move; receptionist still
    # cannot resume (it leads into clinical pages).
    assert doctor.post("/api/queue", json={"name": "X"}).status_code == 403
    assert recep.get(f"/api/queue/{waiting['entry_id']}/resume").status_code == 403

    _close_active(doctor)  # leave the queue clean for later tests


def test_live_page_gates_recording_on_linked_patient(clients):
    recep, doctor = clients["receptionist"], clients["doctor"]
    _close_active(doctor)

    page = doctor.get("/live")
    assert page.status_code == 200
    # Start ships disabled in the markup — only a server-resolved active
    # patient enables it (JS); unlinked recording is impossible by default.
    assert 'id="btn" disabled' in page.text
    # The no-patient state embeds the same walk-in flow plus a Today link.
    assert 'id="liveWalkin"' in page.text
    assert "/api/queue/walk-in" in page.text
    assert 'href="/today"' in page.text

    # Stale-code prevention: pages and static JS must revalidate on load.
    assert page.headers["cache-control"] == "no-cache"
    assert doctor.get("/static/nav.js").headers["cache-control"] == "no-cache"

    # The state chain the page's JS binds to: unlinked ⇒ /current 404
    # (Start stays disabled); in-place walk-in ⇒ /current resolves ⇒
    # the banner re-resolution enables Start.
    assert doctor.get("/api/queue/current").status_code == 404
    entry = doctor.post(
        "/api/queue/walk-in", json={"name": "In-Place Walkin", "age": 33, "sex": "F"}
    ).json()
    current = doctor.get("/api/queue/current").json()
    assert current["entry_id"] == entry["entry_id"]
    assert (current["name"], current["status"]) == ("In-Place Walkin", "in_consultation")

    # RBAC unchanged: the receptionist sees neither the form nor Start
    # (no live page at all) and cannot hit the endpoint behind them.
    assert recep.get("/live", follow_redirects=False).status_code == 403
    assert recep.post("/api/queue/walk-in", json={"name": "X"}).status_code == 403

    _close_active(doctor)


def test_full_front_desk_loop(clients):
    recep, doctor = clients["receptionist"], clients["doctor"]
    _close_active(doctor)

    # Receptionist queues a patient…
    entry = recep.post(
        "/api/queue", json={"name": "Loop Test Patient", "age": 40, "sex": "F"}
    ).json()
    queue = recep.get("/api/queue").json()
    mine = next(q for q in queue if q["entry_id"] == entry["entry_id"])
    assert mine["status"] == "waiting"

    # …doctor starts the consultation from the queue…
    started = doctor.post(f"/api/queue/{entry['entry_id']}/start")
    assert started.status_code == 200
    assert started.json()["name"] == "Loop Test Patient"
    queue = doctor.get("/api/queue").json()
    assert next(q for q in queue if q["entry_id"] == entry["entry_id"])["status"] == "in_consultation"
    # …the live page's banner can fetch the patient identity server-side
    # (queue-Start path — same guarantee as the walk-in path)…
    detail = doctor.get(f"/api/queue/{entry['entry_id']}").json()
    assert (detail["name"], detail["age"], detail["sex"], detail["status"]) == (
        "Loop Test Patient", 40, "F", "in_consultation"
    )
    # …a second start on the same entry is rejected…
    assert doctor.post(f"/api/queue/{entry['entry_id']}/start").status_code == 409

    # (live audio session happens here in reality; simulate its outcome)
    cid = asyncio.run(consultations.create_consultation(started.json()["patient_id"], None))
    asyncio.run(consultations.save_turns(
        cid, [{"role": "Doctor", "start": 0.0, "end": 2.0, "text": "Hello.",
               "confidence": 0.9}]))
    asyncio.run(consultations.save_note(
        cid, {"subjective": [{"text": "Hi", "turns": [0], "uncited": False,
                              "flagged": False}],
              "objective": [], "assessment": [], "plan": []}))
    asyncio.run(consultations.set_status(cid, "awaiting_review"))
    asyncio.run(frontdesk.finish_entry(entry["entry_id"]))

    # …queue entry is done, worklist shows the consultation with the patient…
    queue = recep.get("/api/queue").json()
    assert next(q for q in queue if q["entry_id"] == entry["entry_id"])["status"] == "done"
    worklist = recep.get("/api/consultations").json()  # statuses visible to all roles
    row = next(w for w in worklist if w["id"] == cid)
    assert row["patient_name"] == "Loop Test Patient"
    assert row["status"] == "awaiting_review"

    # …doctor approves; the consultation becomes read-only (archived).
    assert doctor.post(f"/api/consultations/{cid}/approve", json={"text": "S:\n  Hi"}).status_code == 200
    assert doctor.get(f"/api/consultations/{cid}").json()["status"] == "approved"
    assert doctor.post(f"/api/consultations/{cid}/regenerate").status_code == 409
    assert doctor.patch(f"/api/consultations/{cid}/turns/0", json={"text": "y"}).status_code == 409
    assert doctor.post(f"/api/consultations/{cid}/swap-roles").status_code == 409

    # The audit trail recorded the loop.
    events = asyncio.run(audit.recent(500))
    actions = {(e["action"], e["subject_id"]) for e in events}
    assert ("queue.patient_added", entry["entry_id"]) in actions
    assert ("queue.started", entry["entry_id"]) in actions
    assert ("note.approved", cid) in actions
    assert ("consultation.viewed", cid) in actions
