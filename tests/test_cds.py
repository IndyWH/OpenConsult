"""CDS engine integration test.

Needs Ollama serving the MedGemma model locally; skipped otherwise, so the
suite still passes on machines without the 17 GB model.
"""

import asyncio

import httpx
import pytest

from app import cds
from app.cds import CDS_MODEL, OLLAMA_URL, CDSEngine


def _ollama_has_model() -> bool:
    try:
        tags = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=2.0).json()
        return any(m["name"] == CDS_MODEL.removeprefix("hf.co/") or CDS_MODEL in m["name"]
                   for m in tags.get("models", []))
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _ollama_has_model(), reason="Ollama with the CDS model is not available"
)


def test_cds_update_returns_valid_assessment():
    engine = CDSEngine()
    transcript = (
        "What brings you in today?\n"
        "I've been getting a pain in my chest, here in the middle. "
        "It comes on when I climb stairs and goes away when I rest. "
        "I smoke about twenty cigarettes a day."
    )
    assessment = asyncio.run(engine.update(transcript, previous=None))

    # patient_affect is ALWAYS present since 2026-08-01: its own call
    # fills it, and a failure of that call falls back to "neutral" rather
    # than omitting it (an absent field and a neutral verdict were
    # indistinguishable in the log and in the face). The assembled shape
    # is the same as when it rode the assessment call.
    assert set(assessment) == {
        "reasoning",
        "differentials",
        "questions_to_ask",
        "signs_to_check",
        "urgency_check",
        "urgent_actions",
        "patient_affect",
    }
    assert assessment["patient_affect"] in {
        "happy", "positive", "neutral", "low", "anxious", "distressed",
        "angry"}
    assert 1 <= len(assessment["differentials"]) <= 5
    conditions = " ".join(d["condition"].lower() for d in assessment["differentials"])
    assert "angina" in conditions or "coronary" in conditions or "cardiac" in conditions
    for d in assessment["differentials"]:
        assert d["likelihood"] in {"high", "moderate", "low"}


def test_an_affect_failure_cannot_cost_the_clinical_output(monkeypatch):
    """Fail-soft, and load-bearing (2026-08-01): the affect call runs LAST
    and is wrapped, because the face is a comfort feature and the rest of
    the pass is the clinical output. If the affect call raises, the doctor
    must still get the differentials, the questions and the alarm, and
    patient_affect must fall back to "neutral" rather than vanish — an
    absent field and a neutral verdict are indistinguishable downstream.

    Needs no model: every call is stubbed. (It still inherits this
    module's Ollama skip.)
    """
    assessment_reply = {
        "reasoning": "exertional chest pain in a smoker",
        "differentials": [{"condition": "Stable angina",
                           "likelihood": "high",
                           "rationale": "exertional, settles with rest"}],
        "questions_to_ask": ["Does it radiate to the jaw or arm?"],
        "signs_to_check": ["Blood pressure"],
    }
    urgency_reply = {
        "reasoning": "new cardiac-sounding chest pain",
        "time_critical_possible": True,
        "already_done_or_arranged": False,
        "urgent_actions": [{"action": "Bedside ECG", "reason": "exclude ACS"}],
    }

    async def fake_chat(self, system, user, schema, **kwargs):
        if system is cds.AFFECT_PROMPT:
            raise httpx.ConnectError("affect call is down")
        return dict(urgency_reply if system is cds.URGENCY_PROMPT
                    else assessment_reply)

    monkeypatch.setattr(CDSEngine, "_chat", fake_chat)
    assessment = asyncio.run(CDSEngine().update("I get chest pain on stairs."))

    assert assessment["patient_affect"] == "neutral"
    # ...and the clinical output of the pass is untouched by that failure.
    assert assessment["differentials"] == assessment_reply["differentials"]
    assert assessment["questions_to_ask"] == assessment_reply["questions_to_ask"]
    assert assessment["signs_to_check"] == assessment_reply["signs_to_check"]
    assert assessment["urgency_check"]["time_critical_possible"] is True
    assert assessment["urgent_actions"] == urgency_reply["urgent_actions"]
