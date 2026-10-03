#!/usr/bin/env bash
# Build the Nemotron speech environment — SEPARATE from the app's own.
#
# The app's uv.lock pins a CUDA/PyTorch stack that once corrupted itself on
# a re-resolve (see .env.example, Piper). NeMo Speech brings its own torch,
# so it lives in its own checkout with its own lockfile, exactly as the
# diarisation model's ASR_INTEGRATION_GUIDE.md installs it, and the app
# talks to it only as a subprocess (speech_nemotron/worker.py). Nothing
# here touches the app's pyproject.toml or uv.lock.
#
# Re-runnable: an existing checkout is moved to the pinned commit and
# re-synced. No sudo. Needs git, ffmpeg and libsndfile (system packages).
#
#   speech_nemotron/setup.sh                # build or refresh
#   NEMOTRON_HOME=/elsewhere speech_nemotron/setup.sh
set -euo pipefail

# Pinned NeMo Speech commit (main, 3 Oct 2026). The guide asks for a recent
# main because SpeakerTaggedASR is developed alongside the models; pinning
# the commit is what makes this environment reproducible.
NEMO_COMMIT=1688cc3d6a9ade854f544987810c53f605dc86fc
NEMO_REPO=https://github.com/NVIDIA-NeMo/Speech.git

# Model revisions on the Hugging Face Hub (recorded at download, 3 Oct 2026).
# The worker loads these exact revisions, never "main".
ASR_MODEL=nvidia/nemotron-3.5-asr-streaming-0.6b
DIAR_MODEL=nvidia/Nemotron-3-Diarization
ASR_REVISION=ea30d66debe3740a08b573244286791d423d6b3e
DIAR_REVISION=f667ed73aee57d40cc39428eb768b4fd87a0a29e

NEMOTRON_HOME=${NEMOTRON_HOME:-$HOME/.local/share/openconsult-nemotron}
SPEECH_DIR="$NEMOTRON_HOME/Speech"

mkdir -p "$NEMOTRON_HOME"
if [ ! -d "$SPEECH_DIR/.git" ]; then
    git clone --filter=blob:none "$NEMO_REPO" "$SPEECH_DIR"
fi
git -C "$SPEECH_DIR" fetch --quiet origin "$NEMO_COMMIT"
git -C "$SPEECH_DIR" checkout --quiet --detach "$NEMO_COMMIT"

# The guide's command: Python 3.13, ASR extra, CUDA 13 wheels (the driver
# reports CUDA 13.x). --frozen: install exactly NeMo's own committed lock.
(cd "$SPEECH_DIR" && uv sync --frozen --python 3.13 --extra asr --extra cu13 --no-dev)

# Download both checkpoints into the shared HF cache (HF_HOME, as the
# service sets it). Prints the resolved snapshot paths.
"$SPEECH_DIR/.venv/bin/python" - "$ASR_MODEL" "$ASR_REVISION" "$DIAR_MODEL" "$DIAR_REVISION" <<'PY'
import sys
from huggingface_hub import snapshot_download
args = sys.argv[1:]
for repo, rev in zip(args[0::2], args[1::2]):
    path = snapshot_download(repo, revision=rev,
                             allow_patterns=["*.nemo", "*.json", "*.md"])
    print(f"{repo} -> {path}")
PY

echo "Nemotron environment ready: $SPEECH_DIR/.venv/bin/python"
