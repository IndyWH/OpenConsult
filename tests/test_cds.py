"""CDS engine integration test.

Needs Ollama serving the MedGemma model locally; skipped otherwise, so the
suite still passes on machines without the 17 GB model.
"""

import asyncio

import httpx
import pytest

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

    assert set(assessment) == {
        "reasoning",
        "differentials",
        "questions_to_ask",
        "signs_to_check",
        "urgency_check",
        "urgent_actions",
    }
    assert 1 <= len(assessment["differentials"]) <= 5
    conditions = " ".join(d["condition"].lower() for d in assessment["differentials"])
    assert "angina" in conditions or "coronary" in conditions or "cardiac" in conditions
    for d in assessment["differentials"]:
        assert d["likelihood"] in {"high", "moderate", "low"}
