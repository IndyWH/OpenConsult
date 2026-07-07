"""Build (or rebuild) the local guideline corpus and its pgvector store.

Reads corpus/manifest.yaml, fetches each source (cached in corpus/ — which
is gitignored; the manifest is the committed record of provenance), chunks
it with the structure-aware chunker, embeds every chunk locally via Ollama
(embeddinggemma), and loads the lot into PostgreSQL.

Idempotent: re-running replaces each source's chunks.

Usage: uv run python scripts/ingest_guidelines.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
import psycopg
import yaml
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


def fetch(url: str, cache_path: Path) -> str:
    if cache_path.exists():
        print(f"  using cached {cache_path.name}")
        return cache_path.read_text(encoding="utf-8")
    print(f"  fetching {url}")
    response = httpx.get(
        url, headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=60.0
    )
    response.raise_for_status()
    cache_path.write_text(response.text, encoding="utf-8")
    return response.text


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


def main() -> None:
    manifest = yaml.safe_load(MANIFEST.read_text())
    version = manifest["corpus_version"]
    print(f"Corpus: {manifest['corpus_name']} v{version}\n")

    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute(SCHEMA_SQL)

        for source in manifest["sources"]:
            slug = source["slug"]
            print(f"[{slug}]")
            urls = source.get("urls") or [source["url"]]
            chunks = []
            for i, url in enumerate(urls):
                suffix = f"-{i}" if len(urls) > 1 else ""
                html = fetch(url, CORPUS_DIR / f"{slug}{suffix}.html")
                chunks.extend(chunk_html(html, source["title"]))
            if not chunks:
                print("  !! no chunks extracted — check the parser for this source")
                continue
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
        conn.commit()

        total = conn.execute("SELECT count(*) FROM guideline_chunk").fetchone()[0]
        print(f"\nDone: {total} chunks in the store.")


if __name__ == "__main__":
    main()
