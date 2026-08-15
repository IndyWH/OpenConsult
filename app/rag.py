"""RAG service (Phase 4): guideline retrieval + grounded summarisation.

Two hard rules, per PROJECT_PLAN.md:
- Recommendations must be traceable to a retrieved passage: MedGemma may
  use ONLY the passages handed to it, and every claim carries a [n]
  citation that the code validates against the passages actually provided.
- When the corpus doesn't cover a query, the service refuses. Refusal has
  two independent layers: a retrieval-similarity floor in code (queries
  far from every chunk never reach the LLM), and the model's own
  covered=false verdict (retrieval found something, but it doesn't answer
  the question). A covered answer with zero valid citations is demoted to
  a refusal — uncited claims are worthless here.

Queries can come from raw text or from the CDS layer's identified
conditions (query_for_conditions), so the guideline panel follows the
differential, not the transcript's phrasing.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import httpx
import psycopg
import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "embeddinggemma")
RAG_MODEL = os.getenv("CDS_MODEL", "hf.co/unsloth/medgemma-27b-text-it-GGUF:Q4_K_M")
# The shared MedGemma context length — imported, not copied, so the live
# and note paths can never disagree and trigger Ollama's reload again
# (session 5; see the constant's comment in app/cds.py).
from app.cds import CDS_NUM_CTX  # noqa: E402
# Cosine-similarity floor below which we refuse without asking the LLM.
# Calibrated in evals/2026-07-07_rag_grounding_evaluation.md.
MIN_SIMILARITY = float(os.getenv("RAG_MIN_SIMILARITY", "0.45"))
TOP_K = int(os.getenv("RAG_TOP_K", "4"))

_MANIFEST = Path(__file__).parent.parent / "corpus" / "manifest.yaml"

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "covered": {"type": "boolean"},
        "summary": {"type": "string"},
        "passages_cited": {"type": "array", "items": {"type": "integer"}},
    },
    "required": ["covered", "summary", "passages_cited"],
}

SUMMARY_PROMPT = """\
You are preparing a short guideline summary for a doctor during a \
consultation. You are given a QUERY and numbered guideline PASSAGES \
retrieved from a local corpus.

Hard rules:
- Use ONLY the passages. Your own medical knowledge must contribute \
NOTHING — if it isn't in a passage, it does not go in the summary.
- Every clinical statement must end with the citation marker(s) of the \
passage(s) it came from, like [1] or [2][3].
- If the passages do not actually answer the query (wrong condition, \
wrong aspect), set covered=false and state in one sentence what the \
corpus lacks. A partially relevant passage does not justify improvising \
the rest.
- Keep a covered summary under 150 words, telegraphic, clinically dense.
- List every passage number you cited in passages_cited.

Output JSON only.\
"""


# What the guidelines panel shows, and what answer() says, when the
# installation has no corpus manifest at all (a fresh clone before the
# operator has copied corpus/manifest.example.yaml into place).
NO_CORPUS_NAME = "no corpus configured"
NO_CORPUS_VERSION = "-"
NO_CORPUS_SUMMARY = (
    "No guideline corpus is configured on this installation, so no "
    "guideline summary can be given."
)


class RAGService:
    def __init__(self) -> None:
        # The manifest is a per-installation file (like .env). Without it
        # the service still constructs and the app still starts; every
        # query is refused with the same honest shape as an uncovered
        # topic, and the provenance line says why.
        if _MANIFEST.exists():
            manifest = yaml.safe_load(_MANIFEST.read_text())
            self.corpus_name = manifest["corpus_name"]
            self.corpus_version = manifest["corpus_version"]
            self.has_corpus = True
        else:
            logger.warning(
                "no corpus manifest at %s — the guidelines panel will refuse "
                "every query; copy corpus/manifest.example.yaml to that path, "
                "edit it, and run scripts/ingest_guidelines.py",
                _MANIFEST,
            )
            self.corpus_name = NO_CORPUS_NAME
            self.corpus_version = NO_CORPUS_VERSION
            self.has_corpus = False

    # ------------------------------------------------------------ retrieval

    async def _embed_query(self, query: str) -> list[float]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/embed",
                json={
                    "model": EMBED_MODEL,
                    # EmbeddingGemma's retrieval-query prompt convention.
                    "input": [f"task: search result | query: {query}"],
                },
            )
            response.raise_for_status()
        return response.json()["embeddings"][0]

    async def search(self, query: str, k: int = TOP_K) -> list[dict]:
        vector = await self._embed_query(query)
        async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT s.title, s.publisher, s.url, s.date_ingested,
                           c.section_path, c.content,
                           1 - (c.embedding <=> %s::vector) AS similarity
                    FROM guideline_chunk c
                    JOIN guideline_source s ON s.id = c.source_id
                    ORDER BY c.embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (str(vector), str(vector), k),
                )
            ).fetchall()
        return [
            {
                "source": r[0],
                "publisher": r[1],
                "url": r[2],
                "date_ingested": str(r[3]),
                "section": r[4],
                "text": r[5],
                "similarity": round(float(r[6]), 3),
            }
            for r in rows
        ]

    def _no_corpus_provenance(self) -> dict:
        return {
            "corpus_name": self.corpus_name,
            "corpus_version": self.corpus_version,
            "n_sources": 0,
            "n_chunks": 0,
            "date_ingested": "-",
        }

    async def provenance(self) -> dict:
        if not self.has_corpus:
            return self._no_corpus_provenance()
        async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
            row = await (
                await conn.execute(
                    "SELECT count(DISTINCT s.id), count(c.id), max(s.date_ingested)"
                    " FROM guideline_source s JOIN guideline_chunk c ON c.source_id = s.id"
                )
            ).fetchone()
        return {
            "corpus_name": self.corpus_name,
            "corpus_version": self.corpus_version,
            "n_sources": row[0],
            "n_chunks": row[1],
            "date_ingested": str(row[2]),
        }

    # -------------------------------------------------------- summarisation

    @staticmethod
    def query_for_conditions(conditions: list[str]) -> str:
        """Build a retrieval query from the CDS layer's identified conditions."""
        return (
            "Guideline recommendations — assessment, investigations and "
            "management of: " + "; ".join(conditions)
        )

    def _no_corpus_refusal(self, query: str) -> dict:
        """The refusal shape, for an installation with no manifest: no
        retrieval, no LLM call, no citations."""
        return {
            "query": query,
            "provenance": self._no_corpus_provenance(),
            "top_similarity": 0.0,
            "covered": False,
            "summary": NO_CORPUS_SUMMARY,
            "citations": [],
        }

    async def answer(self, query: str) -> dict:
        """Retrieve for a free-text query, then summarise from the passages."""
        if not self.has_corpus:
            return self._no_corpus_refusal(query)
        return await self._summarise(query, await self.search(query))

    async def answer_for_conditions(self, conditions: list[str]) -> dict:
        """Retrieve per CDS condition, merge with per-source diversity.

        One concatenated query lets a single guideline's title vocabulary
        dominate (every NG28 chunk contains "type 2 diabetes", so a
        neuropathy+diabetes query returned NG28 wholesale and never reached
        the cross-referenced neuropathic-pain guideline). Searching each
        condition separately and capping passages per source keeps the set
        clinically diverse.
        """
        if not self.has_corpus:
            return self._no_corpus_refusal(self.query_for_conditions(conditions))
        merged: dict[str, dict] = {}
        for condition in conditions:
            for hit in await self.search(condition, k=12):
                key = hit["text"][:120]
                if key not in merged or hit["similarity"] > merged[key]["similarity"]:
                    merged[key] = hit

        per_source: dict[str, int] = {}
        selected: list[dict] = []
        for hit in sorted(merged.values(), key=lambda h: -h["similarity"]):
            if per_source.get(hit["source"], 0) >= 2:
                continue
            per_source[hit["source"]] = per_source.get(hit["source"], 0) + 1
            selected.append(hit)
            if len(selected) >= 6:
                break

        return await self._summarise(self.query_for_conditions(conditions), selected)

    async def _summarise(self, query: str, passages: list[dict]) -> dict:
        """Summarise strictly from the given passages, or refuse."""
        result: dict = {
            "query": query,
            "provenance": await self.provenance(),
            "top_similarity": passages[0]["similarity"] if passages else 0.0,
        }

        # Refusal layer 1: nothing in the corpus is close to this query.
        if not passages or passages[0]["similarity"] < MIN_SIMILARITY:
            result.update(
                covered=False,
                summary="The local guideline corpus does not cover this topic.",
                citations=[],
            )
            return result

        numbered = "\n\n".join(
            f"[{i + 1}] ({p['source']} — {p['section']})\n{p['text']}"
            for i, p in enumerate(passages)
        )
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": RAG_MODEL,
                    "messages": [
                        {"role": "system", "content": SUMMARY_PROMPT},
                        {"role": "user", "content": f"QUERY: {query}\n\nPASSAGES:\n{numbered}"},
                    ],
                    "format": SUMMARY_SCHEMA,
                    "stream": False,
                    "keep_alive": "30m",
                    "options": {
                        "temperature": float(os.getenv("CDS_TEMPERATURE", "0.0")),
                        "seed": int(os.getenv("CDS_SEED", "42")),
                        "num_ctx": CDS_NUM_CTX,
                    },
                },
            )
            response.raise_for_status()
        verdict = json.loads(response.json()["message"]["content"])

        valid = [n for n in verdict.get("passages_cited", []) if 1 <= n <= len(passages)]
        # Refusal layer 2: the model says the passages don't answer it — or it
        # "answered" without citing anything, which we do not accept.
        if not verdict["covered"] or not valid:
            result.update(
                covered=False,
                summary=(
                    verdict["summary"]
                    if not verdict["covered"]
                    else "Retrieved passages did not support a cited answer."
                ),
                citations=[],
            )
            return result

        result.update(
            covered=True,
            summary=verdict["summary"],
            citations=[
                {
                    "n": n,
                    "source": passages[n - 1]["source"],
                    "publisher": passages[n - 1]["publisher"],
                    "section": passages[n - 1]["section"],
                    "url": passages[n - 1]["url"],
                }
                for n in sorted(set(valid))
            ],
        )
        return result
