"""RAG grounding tests.

Need Ollama (MedGemma + embeddinggemma) and an ingested corpus; skipped
otherwise so the suite passes on machines without them.
"""

import asyncio
import os

import httpx
import psycopg
import pytest
from dotenv import load_dotenv

from app.rag import OLLAMA_URL, RAGService

load_dotenv()


def _rag_ready() -> bool:
    try:
        httpx.get(f"{OLLAMA_URL}/api/tags", timeout=2.0).raise_for_status()
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            n = conn.execute("SELECT count(*) FROM guideline_chunk").fetchone()[0]
        return n > 0
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _rag_ready(), reason="Ollama or ingested guideline corpus not available"
)


def test_retrieval_finds_the_right_guideline():
    hits = asyncio.run(RAGService().search("stable angina assessment"))
    assert hits and "chest pain" in hits[0]["source"].lower()
    assert hits[0]["similarity"] > 0.5


def test_covered_answer_cites_provided_passages():
    answer = asyncio.run(RAGService().answer("management of stable angina"))
    assert answer["covered"] is True
    assert answer["citations"], "a covered answer must cite passages"
    assert all(1 <= c["n"] <= 4 for c in answer["citations"])
    assert answer["provenance"]["n_sources"] >= 6


def test_uncovered_topic_is_refused_not_improvised():
    """The corpus has nothing on testicular torsion — the service must
    decline rather than answer from model memory."""
    answer = asyncio.run(RAGService().answer("testicular torsion management"))
    assert answer["covered"] is False
    assert answer["citations"] == []
    summary = answer["summary"].lower()
    # A refusal, not a treatment plan: must not contain management advice.
    assert not any(word in summary for word in ("surgical exploration", "orchidopexy", "detorsion"))
