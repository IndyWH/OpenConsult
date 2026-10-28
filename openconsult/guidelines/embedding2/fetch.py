"""The one fetch of EmbeddingGemma 2 (spec 15.9, ruling 25; the details of
5d) and, with --model reranker, the one fetch of the reranker (15.12,
ruling 9; the plan review of 8b, points 1 and 4): the pinned revision
from the maker's own page into the data folder, never into this machine's
shared cache, with no token. The hub's library is told not to send one
that is stored on this machine, by its own two switches: token=False in
the call and HF_HUB_DISABLE_IMPLICIT_TOKEN in the environment. Nothing
here reads, copies or prints a token. If the hub asks for an account, a
token or a licence, that is reported and nothing is kept. A model whose
weights are there and match the pinned hash is found and never fetched
again; the reranker's revision and hash are pinned at its first fetch
and kept beside it. Run by openconsult install-guidelines with the
environment's own Python. One JSON line at the end: found or fetched,
the size, the revision, and ok or the error."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

REPO_ID = "google/embeddinggemma-2"
REVISION = "914f7f89142e33e77833254d9c9b90c3cef7303b"
WEIGHTS = "model.safetensors"
WEIGHTS_SHA256 = "197a32965d4b1105faf060417baa899e193fb73cd401f42ec9295234d5553d79"
RERANKER_ID = "BAAI/bge-reranker-v2-m3"
# The reranker's files worth fetching: its weights in one format, its tokenizer and its configs.
RERANKER_PATTERNS = ["*.json", "*.safetensors", "*.txt", "*.model", "tokenizer*"]
ASKS_FOR_ACCOUNT = (401, 403)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(folder: Path, download, environ: dict = os.environ) -> dict:
    """Find the weights at the pinned revision in the folder, or fetch the
    snapshot there with no token. download is the hub's snapshot_download
    or a made-up one."""
    folder = Path(folder)
    report = {"model": REPO_ID, "revision": REVISION, "found": False, "fetched": False, "bytes": 0, "ok": False,
              "error": None, "folder": str(folder)}
    weights = folder / WEIGHTS
    if weights.is_file() and (folder / ".revision").is_file() \
            and (folder / ".revision").read_text(encoding="utf-8").strip() == REVISION and sha256_of(weights) == WEIGHTS_SHA256:
        report.update(found=True, bytes=weights.stat().st_size, ok=True)
        return report
    environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
    try:
        download(REPO_ID, revision=REVISION, local_dir=str(folder), token=False)
    except Exception as exc:  # noqa: BLE001 - a plain report, never a crash
        report["error"] = _said(exc)
        return report
    if not weights.is_file():
        report["error"] = f"{WEIGHTS} was not fetched"
        return report
    found = sha256_of(weights)
    if found != WEIGHTS_SHA256:
        weights.unlink()
        report["error"] = f"the weights file has sha256 {found}, not {WEIGHTS_SHA256}; it was not kept"
        return report
    (folder / ".revision").write_text(REVISION + "\n", encoding="utf-8")
    report.update(fetched=True, bytes=weights.stat().st_size, ok=True)
    return report


def _said(exc: Exception) -> str:
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status in ASKS_FOR_ACCOUNT or "gated" in str(exc).lower() or "401" in str(exc) or "403" in str(exc):
        return "asks for an account, a token or a licence"
    return f"{type(exc).__name__}: {exc}"[:300]


def fetch_reranker(folder: Path, download, model_info, environ: dict = os.environ) -> dict:
    """The reranker: found when its weights match the hash pinned beside
    them at the first fetch; else the hub's current revision is read with
    no token, fetched at that revision, and pinned with the weights' hash."""
    folder = Path(folder)
    report = {"model": RERANKER_ID, "revision": None, "found": False, "fetched": False, "bytes": 0, "ok": False,
              "error": None, "folder": str(folder)}
    weights, revision, pinned = folder / WEIGHTS, folder / ".revision", folder / ".sha256"
    if weights.is_file() and revision.is_file() and pinned.is_file() \
            and sha256_of(weights) == pinned.read_text(encoding="utf-8").strip():
        report.update(found=True, revision=revision.read_text(encoding="utf-8").strip(), bytes=weights.stat().st_size, ok=True)
        return report
    environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
    try:
        sha = str(model_info(RERANKER_ID, token=False).sha)
        download(RERANKER_ID, revision=sha, local_dir=str(folder), token=False, allow_patterns=RERANKER_PATTERNS)
    except Exception as exc:  # noqa: BLE001 - a plain report, never a crash
        report["error"] = _said(exc)
        return report
    if not weights.is_file():
        report["error"] = f"{WEIGHTS} was not fetched"
        return report
    found = sha256_of(weights)
    revision.write_text(sha + "\n", encoding="utf-8")
    pinned.write_text(found + "\n", encoding="utf-8")
    report.update(fetched=True, revision=sha, bytes=weights.stat().st_size, ok=True)
    return report


def main(argv: list[str]) -> int:
    folder = Path(argv[argv.index("--folder") + 1])
    which = argv[argv.index("--model") + 1] if "--model" in argv else "embedding"
    from huggingface_hub import HfApi, snapshot_download
    if which == "reranker":
        report = fetch_reranker(folder, snapshot_download, HfApi().model_info)
    else:
        report = fetch(folder, snapshot_download)
    print(json.dumps(report), flush=True)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
