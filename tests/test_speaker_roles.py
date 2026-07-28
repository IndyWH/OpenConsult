"""Speaker-role correction, and the two gates that come with it.

Why any of this exists: pyannote was called with a fixed `num_speakers=2`, so
a consultation with one human voice in the room had that voice SPLIT into two
clusters, and half of one person's speech was labelled Doctor. It happened in
every 7a consultation — 446 turn 0, 447 turns 0/2/4, 448 turns 0/2 — and it
stayed hidden for three of them because the notes were correct: the model
inferred the speakers from content and wrote accurate notes over wrong
labels. A downstream component doing its job well concealed an upstream
defect.

The count is now unpinned (min 1, max 2), which fixes 446 and 448 but NOT
447, where pyannote still returns two clusters for one voice. So per-turn
correction is not a nicety — it is the only thing that repairs a split, and
the only thing that can repair the consultations already recorded.

Swap Doctor/Patient stays, because a genuine whole-consultation inversion is
a real case. It must not be the ONLY tool: a split is not an inversion, and
swapping one makes it worse (on 448 a swap corrects two turns and breaks the
third).
"""

import asyncio
import os
import secrets

import psycopg
import pytest
from conftest import approve_account
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from app import auth, consultations

load_dotenv()


def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=2):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")


def _doctor_client() -> TestClient:
    auth.ensure_schema()
    from app.main import app

    client = TestClient(app)
    username = f"doc_{secrets.token_hex(4)}"
    assert client.post("/api/register", json={
        "username": username, "password": "test-password-123",
        "display_name": "Doc", "role": "doctor"}).status_code == 200
    approve_account(username)
    assert client.post("/api/login", json={
        "username": username, "password": "test-password-123"}).status_code == 200
    return client


def _make_consultation(*, single_voice: bool = False, with_note: bool = True) -> int:
    consultations.ensure_schema()

    async def build() -> int:
        cid = await consultations.create_consultation()
        await consultations.save_turns(cid, [
            {"role": "Patient", "start": 0.0, "end": 4.0,
             "text": "Oh hi, I have tummy ache.", "confidence": 0.9},
            {"role": "Patient", "start": 4.0, "end": 9.0,
             "text": "It is in the lower tummy.", "confidence": 0.9},
        ])
        if with_note:
            await consultations.save_note(cid, {
                "subjective": [{"text": "Lower abdominal pain [0].", "turns": [0],
                                "uncited": False, "flagged": False}],
                "objective": [], "assessment": [], "plan": []})
        if single_voice:
            await consultations.set_single_voice(cid)
        await consultations.set_status(cid, "awaiting_review")
        return cid

    return asyncio.run(build())


# --------------------------------------------------------- per-turn correction

def test_a_single_turns_role_can_be_corrected():
    cid = _make_consultation()
    client = _doctor_client()

    response = client.patch(f"/api/consultations/{cid}/turns/0", json={"role": "Doctor"})
    assert response.status_code == 200

    turns = client.get(f"/api/consultations/{cid}").json()["turns"]
    assert turns[0]["role"] == "Doctor"
    assert turns[1]["role"] == "Patient", "the other turn must be untouched"


def test_correcting_one_turn_is_not_a_swap():
    """The distinction the whole commit exists for. On a split cluster some
    labels are already right; a swap would break exactly those."""
    cid = _make_consultation()
    client = _doctor_client()

    client.patch(f"/api/consultations/{cid}/turns/0", json={"role": "Doctor"})
    roles = [t["role"] for t in client.get(f"/api/consultations/{cid}").json()["turns"]]
    assert roles == ["Doctor", "Patient"]

    # ...whereas the swap moves both, which is right for an inversion and
    # wrong for a split.
    client.post(f"/api/consultations/{cid}/swap-roles")
    roles = [t["role"] for t in client.get(f"/api/consultations/{cid}").json()["turns"]]
    assert roles == ["Patient", "Doctor"]


def test_a_role_change_records_both_the_old_and_the_new_role():
    """A speaker relabel changes who the record says said something. That has
    to be reconstructible from the audit trail alone."""
    cid = _make_consultation()
    client = _doctor_client()
    client.patch(f"/api/consultations/{cid}/turns/1", json={"role": "Doctor"})

    async def read() -> list[tuple]:
        async with await psycopg.AsyncConnection.connect(os.environ["DATABASE_URL"]) as c:
            rows = await (await c.execute(
                "SELECT detail FROM audit_event WHERE action = 'turn.role_changed'"
                " AND subject_id = %s ORDER BY at", (cid,))).fetchall()
            return rows

    (detail,), = asyncio.run(read())
    assert detail == {"turn": 1, "from": "Patient", "to": "Doctor"}


def test_role_and_text_can_be_corrected_together_or_separately():
    cid = _make_consultation()
    client = _doctor_client()

    # Text only: role untouched, and confidence goes to 1.0 (doctor-corrected).
    assert client.patch(f"/api/consultations/{cid}/turns/0",
                        json={"text": "Oh hi, I have tummy pain."}).status_code == 200
    turn = client.get(f"/api/consultations/{cid}").json()["turns"][0]
    assert turn["text"] == "Oh hi, I have tummy pain."
    assert turn["role"] == "Patient"
    assert turn["confidence"] == 1.0

    # Both at once.
    assert client.patch(f"/api/consultations/{cid}/turns/1",
                        json={"text": "Lower tummy.", "role": "Doctor"}).status_code == 200
    turn = client.get(f"/api/consultations/{cid}").json()["turns"][1]
    assert turn["text"] == "Lower tummy." and turn["role"] == "Doctor"


def test_an_invalid_or_empty_turn_patch_is_refused():
    cid = _make_consultation()
    client = _doctor_client()
    assert client.patch(f"/api/consultations/{cid}/turns/0",
                        json={"role": "Nurse"}).status_code == 400
    assert client.patch(f"/api/consultations/{cid}/turns/0", json={}).status_code == 400
    # And a turn that does not exist is a 404, not a silent success.
    assert client.patch(f"/api/consultations/{cid}/turns/99",
                        json={"role": "Doctor"}).status_code == 404


def test_role_correction_is_refused_on_an_approved_consultation():
    """Same refusals as a text edit: approved is a signed record."""
    cid = _make_consultation()
    client = _doctor_client()
    client.post(f"/api/consultations/{cid}/approve", json={"text": "S:\n"})
    assert client.patch(f"/api/consultations/{cid}/turns/0",
                        json={"role": "Doctor"}).status_code == 409


def test_a_receptionist_cannot_change_a_speaker_label():
    """Role correction is clinical content; the RBAC wall is unchanged."""
    auth.ensure_schema()
    from app.main import app

    cid = _make_consultation()
    client = TestClient(app)
    username = f"rec_{secrets.token_hex(4)}"
    client.post("/api/register", json={
        "username": username, "password": "test-password-123",
        "display_name": "Rec", "role": "receptionist"})
    approve_account(username)
    client.post("/api/login", json={
        "username": username, "password": "test-password-123"})
    assert client.patch(f"/api/consultations/{cid}/turns/0",
                        json={"role": "Doctor"}).status_code == 403


# ------------------------------------------------- the single-voice notice (3)

def test_single_voice_blocks_approval_until_acknowledged():
    """Acknowledge-gated, like the urgency banner. Enforced server-side as
    well as in the UI: a disabled button can be re-enabled from the console,
    a 409 cannot."""
    cid = _make_consultation(single_voice=True)
    client = _doctor_client()

    state = client.get(f"/api/consultations/{cid}").json()
    assert state["single_voice_detected"] is True
    assert state["single_voice_ack_at"] is None

    response = client.post(f"/api/consultations/{cid}/approve", json={"text": "S:\n"})
    assert response.status_code == 409
    assert "one voice" in response.json()["error"]

    assert client.post(f"/api/consultations/{cid}/acknowledge-single-voice"
                       ).status_code == 200
    assert client.get(f"/api/consultations/{cid}").json()["single_voice_ack_at"]
    assert client.post(f"/api/consultations/{cid}/approve",
                       json={"text": "S:\n"}).status_code == 200


def test_a_normal_consultation_has_no_single_voice_gate():
    cid = _make_consultation()
    client = _doctor_client()
    assert client.get(f"/api/consultations/{cid}").json()["single_voice_detected"] is False
    assert client.post(f"/api/consultations/{cid}/approve",
                       json={"text": "S:\n"}).status_code == 200


# ------------------------------------------- the stale-labels gate (item 5)

def test_a_role_change_marks_the_note_as_drafted_against_older_labels():
    cid = _make_consultation()
    client = _doctor_client()

    assert client.get(f"/api/consultations/{cid}").json()["labels"]["stale"] is False

    client.patch(f"/api/consultations/{cid}/turns/0", json={"role": "Doctor"})
    labels = client.get(f"/api/consultations/{cid}").json()["labels"]
    assert labels["stale"] is True
    assert labels["acknowledged"] is False

    response = client.post(f"/api/consultations/{cid}/approve", json={"text": "S:\n"})
    assert response.status_code == 409
    assert "changed after this note was drafted" in response.json()["error"]

    assert client.post(f"/api/consultations/{cid}/acknowledge-labels").status_code == 200
    assert client.get(f"/api/consultations/{cid}").json()["labels"]["acknowledged"] is True
    assert client.post(f"/api/consultations/{cid}/approve",
                       json={"text": "S:\n"}).status_code == 200


def test_the_whole_transcript_swap_also_marks_the_note_stale():
    """Swap has always run after the note was drafted and never re-validated.
    That is the defect this gate closes, and swap is where it started."""
    cid = _make_consultation()
    client = _doctor_client()
    client.post(f"/api/consultations/{cid}/swap-roles")
    assert client.get(f"/api/consultations/{cid}").json()["labels"]["stale"] is True
    assert client.post(f"/api/consultations/{cid}/approve",
                       json={"text": "S:\n"}).status_code == 409


def test_a_second_role_change_re_arms_the_gate_after_an_acknowledgement():
    """Why the ack is a timestamp compared against the change, not a boolean:
    acknowledging one correction must not pre-authorise the next."""
    cid = _make_consultation()
    client = _doctor_client()

    client.patch(f"/api/consultations/{cid}/turns/0", json={"role": "Doctor"})
    client.post(f"/api/consultations/{cid}/acknowledge-labels")
    assert client.get(f"/api/consultations/{cid}").json()["labels"]["acknowledged"] is True

    client.patch(f"/api/consultations/{cid}/turns/1", json={"role": "Doctor"})
    labels = client.get(f"/api/consultations/{cid}").json()["labels"]
    assert labels["stale"] is True
    assert labels["acknowledged"] is False, "a later change must re-arm the gate"
    assert client.post(f"/api/consultations/{cid}/approve",
                       json={"text": "S:\n"}).status_code == 409


def test_a_consultation_with_no_note_is_never_stale():
    """Nothing was drafted, so nothing can be drafted against old labels."""
    cid = _make_consultation(with_note=False)
    client = _doctor_client()
    client.patch(f"/api/consultations/{cid}/turns/0", json={"role": "Doctor"})
    assert client.get(f"/api/consultations/{cid}").json()["labels"]["stale"] is False


# ------------------------------------------------------------------- the page

def _review_html() -> str:
    from pathlib import Path
    return Path("app/static/review.html").read_text()


def test_the_label_itself_is_the_control():
    """The place a person looks when they notice a label is wrong is the
    label. Same reasoning as the live page's companion rule."""
    html = _review_html()
    assert "el('button', 'rolebtn', t.role)" in html
    assert "Wrong speaker? Click to change this line to" in html
    assert ".turn .who .rolebtn {" in html


def test_the_swap_control_survives():
    """A genuine whole-consultation inversion is still a real case; per-turn
    correction is an addition, not a replacement."""
    assert 'id="swap"' in _review_html()


def test_both_role_banners_sit_above_the_transcript():
    """The uncertainty must be visible at the thing it applies to — not left
    silent because the note happens to read well."""
    html = _review_html()
    single = html.index('id="singleVoiceBanner"')
    labels = html.index('id="labelsBanner"')
    transcript = html.index('<h2>Diarised transcript</h2>')
    assert single < transcript and labels < transcript


def test_one_writer_owns_the_approve_button():
    """Three acknowledge-gated banners now feed one button. Each renderer
    drawing itself AND setting approveBtn.disabled would mean the last one to
    run decided — which is how a gate quietly stops gating."""
    html = _review_html()
    assert "function refreshApproveGate()" in html
    urgent = html[html.index("function renderUrgentBanner()"):]
    urgent = urgent[:urgent.index("\n}")]
    assert "approveBtn.disabled" not in urgent, (
        "only refreshApproveGate may write the Approve button's disabled flag")
    # And the reason is on the control, per the standing rule.
    assert "'Before approving: ' + reasons.join" in html


def test_the_note_is_never_regenerated_silently():
    """The note is the doctor's document. A role change must not rewrite it —
    it must ask. Asserted on the stored note text, not on the UI."""
    cid = _make_consultation()
    client = _doctor_client()
    before = asyncio.run(consultations.latest_note(cid))

    client.patch(f"/api/consultations/{cid}/turns/0", json={"role": "Doctor"})

    after = asyncio.run(consultations.latest_note(cid))
    assert after["version"] == before["version"]
    assert after["content"] == before["content"]
