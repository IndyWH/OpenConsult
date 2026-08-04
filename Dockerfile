# syntax=docker/dockerfile:1
# The app image (DOCKER_DEMO_SPEC.md §§1.2–1.4).
#
# Ubuntu 26.04 EXACTLY — not slim, not an -cuda base, not a newer tag.
# The dependency pins in pyproject.toml were tuned against this release's
# glibc / FFmpeg 8 / CUDA-wheel combination (§1.4): ctranslate2>=4.6
# because 4.4 fails on this glibc ("cannot enable executable stack"),
# pyannote pinned to 3.4.0, torchcodec excluded entirely because 0.7
# cannot load against FFmpeg 8 and its mere presence broke chunked ASR.
# Changing the base image reopens every one of those scars.
#
# Nothing sensitive or heavy goes in a layer: no corpus (an image
# containing it is redistribution — §1.2), no models, no .env, no
# recordings. The .dockerignore enforces that; volumes provide them at
# runtime. GPU access comes from the NVIDIA Container Toolkit at run
# time; the CUDA-side cuBLAS/cuDNN arrive as the pinned pip wheels and
# app.transcription._preload_cuda_libraries() loads them before torch /
# ctranslate2 in each fresh process, exactly as on the host.
FROM ubuntu:26.04

# tzdata: --no-install-recommends leaves the base image without zoneinfo,
# and the uv-managed CPython has no bundled fallback — ZoneInfo("Europe/
# London") then fails at import. The host never shows this (a full
# Ubuntu install ships tzdata); the in-container suite caught it.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        ffmpeg \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

# uv pinned to the version the reference machine runs — the lockfile is
# the contract and the resolver should match it.
COPY --from=ghcr.io/astral-sh/uv:0.11.27 /uv /uvx /usr/local/bin/

WORKDIR /app
ENV UV_LINK_MODE=copy \
    UV_PYTHON_INSTALL_DIR=/opt/uv/python \
    PATH="/app/.venv/bin:${PATH}"

# Dependencies first and alone, so a source edit does not re-resolve 157
# packages. --frozen: the committed uv.lock is authoritative, in the
# container as on the host. The dev group is installed deliberately —
# §1.5 wants `docker compose run --rm app pytest` to work on a fresh
# clone, and the suite is part of what a reviewer should be able to run.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen

COPY . .

# The corpus volume mounts over /app/corpus and hides the committed
# manifest, so a reference copy is kept where the entrypoint can seed it
# into an empty volume (the manifest is provenance, not corpus content).
RUN cp corpus/manifest.yaml /opt/corpus-manifest.yaml \
    && chmod +x docker/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
