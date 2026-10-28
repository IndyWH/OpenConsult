"""The one fetch of EmbeddingGemma 2 (spec 15.9, ruling 25; the details of
5d): the pinned revision from Google's own page into the data folder,
never into this machine's shared cache, with no token. The hub's library
is told not to send one that is stored on this machine, by its own two
switches: token=False in the call and HF_HUB_DISABLE_IMPLICIT_TOKEN in
the environment. Nothing here reads, copies or prints a token. If the
hub asks for an account, a token or a licence, that is reported and
nothing is kept. Run by openconsult-bench shared-install with the
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
            and (folder / ".revision").read_text(encoding="utf-8").strip() == REVISION:
        report.update(found=True, bytes=weights.stat().st_size, ok=True)
        return report
    environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
    try:
        download(REPO_ID, revision=REVISION, local_dir=str(folder), token=False)
    except Exception as exc:  # noqa: BLE001 - a plain report, never a crash
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in ASKS_FOR_ACCOUNT or "gated" in str(exc).lower() or "401" in str(exc) or "403" in str(exc):
            report["error"] = "asks for an account, a token or a licence"
        else:
            report["error"] = f"{type(exc).__name__}: {exc}"[:300]
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


def main(argv: list[str]) -> int:
    folder = Path(argv[argv.index("--folder") + 1])
    from huggingface_hub import snapshot_download
    report = fetch(folder, snapshot_download)
    print(json.dumps(report), flush=True)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
