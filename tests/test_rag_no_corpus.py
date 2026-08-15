"""Fresh-clone behaviour: no corpus manifest.

The manifest is a per-installation file (like .env) and is never
committed, so a fresh clone has none. The app must still start and the
guidelines panel must refuse honestly — the same shape as an uncovered
topic — without touching Ollama or the database. Needs neither Ollama nor
a corpus, so nothing here skips.
"""

import asyncio
import os

import pytest

import app.rag as rag_module
from app.rag import RAGService


@pytest.fixture
def no_manifest(monkeypatch, tmp_path):
    """Point the service at a manifest path that does not exist."""
    monkeypatch.setattr(rag_module, "_MANIFEST", tmp_path / "manifest.yaml")


@pytest.fixture
def no_backends(monkeypatch):
    """Retrieval and summarisation must not be reached: fail loudly if
    the service tries to embed, search or call the LLM."""

    async def _forbidden(*args, **kwargs):
        raise AssertionError("no-corpus path must not touch Ollama or Postgres")

    monkeypatch.setattr(RAGService, "_embed_query", _forbidden)
    monkeypatch.setattr(RAGService, "search", _forbidden)
    monkeypatch.setattr(RAGService, "_summarise", _forbidden)


def test_service_constructs_with_placeholder_provenance(no_manifest):
    service = RAGService()
    assert service.has_corpus is False
    assert service.corpus_name == "no corpus configured"
    assert service.corpus_version == "-"


def test_answer_is_the_refusal_shape_without_retrieval_or_llm(no_manifest, no_backends):
    answer = asyncio.run(RAGService().answer("management of stable angina"))
    assert answer["covered"] is False
    assert answer["citations"] == []
    assert answer["query"] == "management of stable angina"
    assert answer["top_similarity"] == 0.0
    # One sentence, and it says why.
    summary = answer["summary"]
    assert "no" in summary.lower() and "corpus" in summary.lower()
    assert summary.strip().count(".") == 1
    # The provenance line the panel renders carries the placeholders.
    prov = answer["provenance"]
    assert prov["corpus_name"] == "no corpus configured"
    assert prov["corpus_version"] == "-"
    assert prov["n_sources"] == 0 and prov["n_chunks"] == 0


def test_answer_for_conditions_refuses_the_same_way(no_manifest, no_backends):
    """The live panel's path — per-condition retrieval — refuses too."""
    answer = asyncio.run(RAGService().answer_for_conditions(["angina", "GORD"]))
    assert answer["covered"] is False
    assert answer["citations"] == []
    assert answer["provenance"]["corpus_name"] == "no corpus configured"


def test_provenance_needs_no_database(no_manifest, monkeypatch):
    monkeypatch.setattr(rag_module, "DATABASE_URL", "postgresql://nowhere/none")
    prov = asyncio.run(RAGService().provenance())
    assert prov["corpus_name"] == "no corpus configured"
    assert prov["corpus_version"] == "-"
    assert prov["n_sources"] == 0


def test_a_present_manifest_is_still_read(monkeypatch, tmp_path):
    """Positive control: the manifest path is unchanged when the file exists."""
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text('corpus_name: "Test corpus"\ncorpus_version: "t1"\nsources: []\n')
    monkeypatch.setattr(rag_module, "_MANIFEST", manifest)
    service = RAGService()
    assert service.has_corpus is True
    assert service.corpus_name == "Test corpus"
    assert service.corpus_version == "t1"


def test_ingest_script_refuses_without_a_manifest(monkeypatch, tmp_path, capsys):
    """The ingest script exits non-zero and says what to do, before it
    touches the database."""
    # The script reads DATABASE_URL at import; a bare machine has none.
    os.environ.setdefault("DATABASE_URL", "postgresql://nowhere/none")
    import scripts.ingest_guidelines as ingest

    monkeypatch.setattr(ingest, "MANIFEST", tmp_path / "manifest.yaml")
    with pytest.raises(SystemExit) as exc:
        ingest.main()
    assert exc.value.code not in (0, None)
    err = capsys.readouterr().err
    assert "corpus/manifest.example.yaml" in err
    assert "corpus/manifest.yaml" in err
