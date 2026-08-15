"""Build (or rebuild) the local guideline corpus and its pgvector store.

Reads corpus/manifest.yaml (the per-installation record of provenance —
local and uncommitted, like .env; corpus/manifest.example.yaml is the
committed example of its format), fetches each source (cached in corpus/,
which is gitignored), chunks it with the structure-aware chunker, embeds
every chunk locally via Ollama (embeddinggemma), and loads the lot into
PostgreSQL.

Idempotent: re-running replaces each source's chunks.

Validation (the replaced-source lesson — a source that downloads is not
a source that works):
- Fetch time: a redirect to a different page is a failure (some publishers
  retire pages by redirecting them to overview stubs instead of returning
  an error), and every page's <title> must contain the manifest's
  expect_title (catches wrong or replaced guideline codes).
- After ingestion: every expected_query in the manifest must retrieve a
  chunk from its own source within the global top VALIDATE_TOP_K at
  similarity >= the retrieval refusal floor. This is what proves the
  source is actually reachable by the live RAG path — chunk counts prove
  nothing.

Any fetch or validation failure is collected, reported loudly at the end,
and makes the script exit non-zero. Other sources still ingest.

Usage: uv run python scripts/ingest_guidelines.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import psycopg
import yaml
from bs4 import BeautifulSoup
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.chunking import chunk_html  # noqa: E402

ROOT = Path(__file__).parent.parent
CORPUS_DIR = ROOT / "corpus"
MANIFEST = CORPUS_DIR / "manifest.yaml"

load_dotenv(ROOT / ".env")
DATABASE_URL = os.environ["DATABASE_URL"]
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "embeddinggemma")
EMBED_DIM = 768
# Same floor the live RAG path refuses below (app/rag.py).
MIN_SIMILARITY = float(os.getenv("RAG_MIN_SIMILARITY", "0.45"))
# An expected query must place a chunk of its own source this high in the
# GLOBAL ranking — generous enough for genuine cross-source overlap
# (sepsis adult/child, chest pain/angina), tight enough to catch a source
# that retrieval can never surface (crowding by a larger source on an
# overlapping topic).
VALIDATE_TOP_K = 8

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"

SCHEMA_SQL = f"""
CREATE TABLE IF NOT EXISTS guideline_source (
    id serial PRIMARY KEY,
    slug text UNIQUE NOT NULL,
    title text NOT NULL,
    publisher text NOT NULL,
    url text NOT NULL,
    date_ingested date NOT NULL,
    corpus_version text NOT NULL
);
CREATE TABLE IF NOT EXISTS guideline_chunk (
    id serial PRIMARY KEY,
    source_id int NOT NULL REFERENCES guideline_source(id) ON DELETE CASCADE,
    section_path text NOT NULL,
    content text NOT NULL,
    embedding vector({EMBED_DIM}) NOT NULL
);
CREATE INDEX IF NOT EXISTS guideline_chunk_embedding_idx
    ON guideline_chunk USING hnsw (embedding vector_cosine_ops);
"""


class IngestError(Exception):
    """A source failed fetching or verification; reported, not fatal."""


def _same_page(requested: str, final: str) -> bool:
    """True if a redirect stayed on the same page (scheme/trailing-slash)."""
    a, b = urlsplit(requested), urlsplit(final)
    return (a.netloc, a.path.rstrip("/")) == (b.netloc, b.path.rstrip("/"))


def fetch(url: str, cache_path: Path, expect_title: str) -> str:
    if cache_path.exists():
        print(f"  using cached {cache_path.name}")
        html = cache_path.read_text(encoding="utf-8")
    else:
        print(f"  fetching {url}")
        response = httpx.get(
            url, headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=60.0
        )
        response.raise_for_status()
        if not _same_page(url, str(response.url)):
            # Some publishers retire pages by redirecting them to overview
            # stubs (or research-only chapters) instead of returning an
            # error — that is a dead source, not a fetched one.
            raise IngestError(f"redirected to a different page: {url} -> {response.url}")
        html = response.text
        cache_path.write_text(html, encoding="utf-8")

    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text().strip() if soup.title else ""
    if expect_title and expect_title.lower() not in title.lower():
        raise IngestError(
            f"page title {title!r} does not contain {expect_title!r} "
            f"(wrong or replaced guideline code?): {url}"
        )
    return html


def embed_documents(chunks: list) -> list[list[float]]:
    """Embed with EmbeddingGemma's document prompt convention."""
    inputs = [f"title: {c.section_path} | text: {c.text}" for c in chunks]
    embeddings: list[list[float]] = []
    # Batch to keep request sizes sane.
    for i in range(0, len(inputs), 16):
        response = httpx.post(
            f"{OLLAMA_URL}/api/embed",
            json={"model": EMBED_MODEL, "input": inputs[i : i + 16]},
            timeout=300.0,
        )
        response.raise_for_status()
        embeddings.extend(response.json()["embeddings"])
    return embeddings


def embed_query(query: str) -> list[float]:
    """Embed with EmbeddingGemma's retrieval-query prompt convention
    (must match app/rag.py exactly — validation stands in for the live path)."""
    response = httpx.post(
        f"{OLLAMA_URL}/api/embed",
        json={"model": EMBED_MODEL, "input": [f"task: search result | query: {query}"]},
        timeout=60.0,
    )
    response.raise_for_status()
    return response.json()["embeddings"][0]


def ingest_source(conn: psycopg.Connection, source: dict, version: str) -> str:
    slug = source["slug"]
    urls = source.get("urls") or [source["url"]]
    expect_title = source.get("expect_title", "")

    chunks = []
    for i, url in enumerate(urls):
        suffix = f"-{i}" if len(urls) > 1 else ""
        html = fetch(url, CORPUS_DIR / f"{slug}{suffix}.html", expect_title)
        chunks.extend(chunk_html(html, source["title"]))
    if not chunks:
        raise IngestError("no chunks extracted — check the parser for this source")
    vectors = embed_documents(chunks)

    row = conn.execute(
        """
        INSERT INTO guideline_source
            (slug, title, publisher, url, date_ingested, corpus_version)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (slug) DO UPDATE SET
            title = EXCLUDED.title, publisher = EXCLUDED.publisher,
            url = EXCLUDED.url, date_ingested = EXCLUDED.date_ingested,
            corpus_version = EXCLUDED.corpus_version
        RETURNING id
        """,
        (
            slug,
            source["title"],
            source["publisher"],
            urls[0],
            source["date_ingested"],
            version,
        ),
    ).fetchone()
    source_id = row[0]
    conn.execute("DELETE FROM guideline_chunk WHERE source_id = %s", (source_id,))
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO guideline_chunk
                (source_id, section_path, content, embedding)
            VALUES (%s, %s, %s, %s::vector)
            """,
            [
                (source_id, c.section_path, c.text, str(v))
                for c, v in zip(chunks, vectors)
            ],
        )
    words = [c.word_count for c in chunks]
    print(f"  {len(chunks)} chunks, {min(words)}-{max(words)} words each")
    return slug


def validate_source(conn: psycopg.Connection, source: dict) -> list[str]:
    """Check every expected query surfaces this source in the global
    ranking above the refusal floor. Returns failure descriptions."""
    failures: list[str] = []
    for query in source.get("expected_queries", []):
        vector = str(embed_query(query))
        row = conn.execute(
            """
            WITH ranked AS (
                SELECT s.slug,
                       1 - (c.embedding <=> %s::vector) AS similarity,
                       row_number() OVER (ORDER BY c.embedding <=> %s::vector) AS rank
                FROM guideline_chunk c
                JOIN guideline_source s ON s.id = c.source_id
            )
            SELECT rank, similarity FROM ranked
            WHERE slug = %s ORDER BY rank LIMIT 1
            """,
            (vector, vector, source["slug"]),
        ).fetchone()
        if row is None:
            failures.append(f"{source['slug']}: {query!r} — source has no chunks at all")
            continue
        rank, similarity = row
        if rank > VALIDATE_TOP_K or similarity < MIN_SIMILARITY:
            failures.append(
                f"{source['slug']}: {query!r} — best own-chunk rank {rank} "
                f"(need <= {VALIDATE_TOP_K}), similarity {similarity:.3f} "
                f"(need >= {MIN_SIMILARITY})"
            )
        else:
            print(f"  ok  rank {rank}, sim {similarity:.3f}  {query!r}")
    return failures


def main() -> None:
    if not MANIFEST.exists():
        # A fresh clone: the manifest is a per-installation file (like
        # .env) and is never committed. Say what to do, then stop — there
        # is nothing to ingest, and the app runs without a corpus.
        print(
            f"No corpus manifest at {MANIFEST}.\n"
            "Copy corpus/manifest.example.yaml to corpus/manifest.yaml, edit it "
            "to list the sources you hold licences to use this way, then re-run "
            "this script.",
            file=sys.stderr,
        )
        sys.exit(1)
    manifest = yaml.safe_load(MANIFEST.read_text())
    version = manifest["corpus_version"]
    print(f"Corpus: {manifest['corpus_name']} v{version}\n")

    fetch_failures: list[str] = []
    ingested: list[str] = []

    # The app's own schema, in one order (app/schema.py) — then this
    # script's corpus tables, which it owns and the app never creates.
    from app import schema

    schema.ensure_all()

    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute(SCHEMA_SQL)

        for source in manifest["sources"]:
            print(f"[{source['slug']}]")
            try:
                ingested.append(ingest_source(conn, source, version))
            except (IngestError, httpx.HTTPError) as exc:
                print(f"  !! FAILED: {exc}")
                fetch_failures.append(f"{source['slug']}: {exc}")
        conn.commit()

        total = conn.execute("SELECT count(*) FROM guideline_chunk").fetchone()[0]
        n_sources = conn.execute("SELECT count(*) FROM guideline_source").fetchone()[0]
        print(f"\nIngested: {total} chunks across {n_sources} sources.")

        print("\nValidating expected queries against the live retrieval path...")
        query_failures: list[str] = []
        for source in manifest["sources"]:
            if source["slug"] not in ingested:
                continue  # already reported as a fetch failure
            if source.get("expected_queries"):
                print(f"[{source['slug']}]")
                query_failures.extend(validate_source(conn, source))

    if fetch_failures or query_failures:
        print("\n" + "=" * 72)
        print("INGESTION FAILED — the corpus is NOT fully valid:")
        for f in fetch_failures:
            print(f"  fetch/verify: {f}")
        for f in query_failures:
            print(f"  expected-query: {f}")
        print("=" * 72)
        sys.exit(1)

    print("\nDone: all sources ingested and all expected queries validated.")


if __name__ == "__main__":
    main()
