#!/usr/bin/env bash
# Container entrypoint (DOCKER_DEMO_SPEC.md §§1.3, 1.7).
#
# Loud and bounded, for a technical reader on a first run: every wait
# says what it is waiting for and every failure says what to do. The app
# itself adds its own fail-fast on SECRET_KEY — a missing or placeholder
# key refuses at startup with the openssl command to run.
set -euo pipefail

# Seed the committed corpus manifest into the (possibly empty) corpus
# volume. The volume shadows /app/corpus, so the image keeps a reference
# copy. The manifest is provenance and is version-controlled: a newer
# image's copy wins, loudly. Corpus CONTENT is never seeded — first-run
# ingestion is the operator's explicit step:
#   docker compose run --rm app python scripts/ingest_guidelines.py
# It validates what it fetched and exits non-zero listing every failed
# source; a partially ingested corpus does not present as ready (§1.2).
if [ ! -f corpus/manifest.yaml ]; then
    cp /opt/corpus-manifest.yaml corpus/manifest.yaml
    echo "[entrypoint] seeded corpus/manifest.yaml into the corpus volume"
elif ! cmp -s /opt/corpus-manifest.yaml corpus/manifest.yaml; then
    cp /opt/corpus-manifest.yaml corpus/manifest.yaml
    echo "[entrypoint] corpus/manifest.yaml updated from this image (the" \
         "committed manifest is authoritative); re-run ingestion if" \
         "sources changed"
fi

echo "[entrypoint] waiting for PostgreSQL (${DATABASE_URL%%\?*})..."
for i in $(seq 1 60); do
    if python - <<'PY' 2>/dev/null
import os, psycopg
psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=2).close()
PY
    then
        echo "[entrypoint] PostgreSQL is answering"
        break
    fi
    [ "$i" = 60 ] && { echo "[entrypoint] FATAL: PostgreSQL did not answer" \
        "after 120 s — is the db service healthy? (docker compose ps)"; exit 1; }
    sleep 2
done

# Ollama is only a prerequisite for SERVING — `docker compose run app
# pytest` must work without it (model-dependent tests self-skip).
if [ "${1:-}" = "uvicorn" ]; then
    echo "[entrypoint] waiting for Ollama at ${OLLAMA_URL:-http://127.0.0.1:11434}..."
    for i in $(seq 1 60); do
        if curl -fsS --max-time 2 "${OLLAMA_URL:-http://127.0.0.1:11434}/api/tags" >/dev/null 2>&1; then
            echo "[entrypoint] Ollama is answering"
            break
        fi
        if [ "$i" = 60 ]; then
            echo "[entrypoint] FATAL: Ollama did not answer at" \
                 "${OLLAMA_URL:-http://127.0.0.1:11434} after 120 s."
            echo "  Host Ollama (the default): make sure it listens on an" \
                 "address the container can reach (OLLAMA_HOST=0.0.0.0" \
                 "for the host service), or"
            echo "  Bundled Ollama: start with --profile ollama and set" \
                 "OLLAMA_URL=http://ollama:11434 in .env"
            exit 1
        fi
        sleep 2
    done
fi

exec "$@"
