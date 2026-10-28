"""openconsult install-guidelines (spec 15.12, The embedding worker in
the app; 15.9 ruling 25; the plan review of 8b, points 1 and 4): the
environment from the lock file, each model's one fetch with no token,
skipped when its weights are there and match the pinned hash, a gate
reported and nothing kept; the bench's shared-install the same code
without the reranker. Made-up runs; nothing is fetched."""

import hashlib
import importlib.util
import json
from pathlib import Path

from openconsult import words
from openconsult.bench.shared import commands
from openconsult.cli import main
from openconsult.guidelines import environment

REPO = Path(__file__).resolve().parents[1]


def fetch_module():
    path = REPO / "openconsult" / "guidelines" / "embedding2" / "fetch.py"
    spec = importlib.util.spec_from_file_location("embedding2_fetch_8b", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Done:
    def __init__(self, code, out="", err=""):
        self.returncode, self.stdout, self.stderr = code, out, err


def test_ruling_5_install_guidelines_builds_the_environment_and_fetches_with_no_token(tmp_path):
    data = tmp_path / "data"
    calls = []

    def run(command, env=None, **kwargs):
        calls.append((command, env))
        if command[1:2] == ["sync"]:
            assert command[3:5] == ["--project", str(environment.WORKER_FOLDER)] and env["UV_PROJECT_ENVIRONMENT"] == str(environment.venv(data))
            return Done(0, err="Installed 63 packages")
        assert env["HF_HUB_DISABLE_IMPLICIT_TOKEN"] == "1" and "HF_HUB_OFFLINE" not in env and env["HF_HOME"] == str(environment.folder(data) / "hub")
        which = command[command.index("--model") + 1]
        report = {"ok": True, "fetched": which == "reranker", "bytes": 1_488_915_288 if which == "embedding" else 2_270_000_000,
                  "revision": "r-" + which, "error": None}
        return Done(0, out=json.dumps(report) + "\n")
    said = []
    assert environment.install(data, say=said.append, run=run, which=lambda name: "/made-up/uv", environ={"HF_HUB_OFFLINE": "1", "PATH": "x"}) == 0
    assert [c[0][-1] for c in calls[1:]] == ["embedding", "reranker"] and calls[1][0][-3] == str(environment.model_folder(data))
    assert calls[2][0][-3] == str(environment.reranker_folder(data))
    assert words.EMBED_BUILT in said and words.EMBED_FOUND.format(revision="r-embedding", size="1.5 GB") in said
    assert words.RERANKER_FETCHED.format(revision="r-reranker", size="2.3 GB") in said and said[-1] == words.GUIDELINES_INSTALLED
    # A gated reranker is said and the install stops; the bench's shared-install never asks for the reranker.
    def gated(command, env=None, **kwargs):
        if command[1:2] == ["sync"]:
            return Done(0)
        which = command[command.index("--model") + 1]
        if which == "reranker":
            return Done(1, out=json.dumps({"ok": False, "error": "asks for an account, a token or a licence"}) + "\n")
        return Done(0, out=json.dumps({"ok": True, "fetched": False, "bytes": 1, "revision": "r", "error": None}) + "\n")
    said = []
    assert environment.install(data, say=said.append, run=gated, which=lambda name: "/made-up/uv", environ={}) == 8
    assert said[-1] == words.RERANKER_GATED
    said = []
    assert commands.shared_install(data, say=said.append, run=gated, which=lambda name: "/made-up/uv", environ={}) == 0
    assert said[-1] == words.EMBED_FOUND.format(revision="r", size="1 kB") and words.RERANKER_FETCHING.split("{")[0] not in " ".join(said)
    assert environment.install(data, say=said.append, run=gated, which=lambda name: None) == 7 and said[-1] == words.UV_MISSING
    # The command line reaches the same code.
    said = []
    assert main(["install-guidelines", "--data-folder", str(data)], say=said.append, run_process=run, which=lambda name: "/made-up/uv") == 0


def test_plan_review_4_a_model_whose_weights_match_the_pinned_hash_is_found_and_not_fetched_again(tmp_path):
    fetch = fetch_module()
    folder = tmp_path / "model"
    folder.mkdir()
    downloads = []

    def download(repo_id, **kwargs):
        downloads.append((repo_id, kwargs))
        (folder / fetch.WEIGHTS).write_bytes(b"made-up weights")

    # EmbeddingGemma 2: the revision file alone is not enough; the weights must hash to the pinned value.
    (folder / fetch.WEIGHTS).write_bytes(b"other bytes")
    (folder / ".revision").write_text(fetch.REVISION + "\n")
    report = fetch.fetch(folder, download, {})
    assert downloads and not report["ok"] and "not" in report["error"]            # fetched, and the wrong bytes refused
    # The reranker: pinned at its first fetch, found by the hash beside it, never fetched again.
    reranker = tmp_path / "reranker"
    reranker.mkdir()
    infos = []

    class Info:
        sha = "abc123"

    def model_info(repo_id, token=None):
        infos.append((repo_id, token))
        return Info()

    def download_reranker(repo_id, **kwargs):
        downloads.append((repo_id, kwargs))
        (reranker / fetch.WEIGHTS).write_bytes(b"reranker weights")
    env = {}
    report = fetch.fetch_reranker(reranker, download_reranker, model_info, env)
    assert report["ok"] and report["fetched"] and report["revision"] == "abc123" and env["HF_HUB_DISABLE_IMPLICIT_TOKEN"] == "1"
    assert infos == [(fetch.RERANKER_ID, False)] and downloads[-1][1]["revision"] == "abc123" and downloads[-1][1]["token"] is False
    assert downloads[-1][1]["allow_patterns"] == fetch.RERANKER_PATTERNS
    assert (reranker / ".revision").read_text().strip() == "abc123"
    assert (reranker / ".sha256").read_text().strip() == hashlib.sha256(b"reranker weights").hexdigest()
    before = len(downloads)
    again = fetch.fetch_reranker(reranker, download_reranker, model_info, env)
    assert again["ok"] and again["found"] and not again["fetched"] and len(downloads) == before and again["revision"] == "abc123"
    (reranker / fetch.WEIGHTS).write_bytes(b"changed weights")
    changed = fetch.fetch_reranker(reranker, download_reranker, model_info, env)
    assert changed["fetched"] and len(downloads) == before + 1                   # a changed file is fetched again and pinned again

    class Gated(Exception):
        pass

    def refusing(repo_id, **kwargs):
        raise Gated("401 Client Error: gated")
    gated = fetch.fetch_reranker(tmp_path / "gated", refusing, model_info, env)
    assert not gated["ok"] and gated["error"] == "asks for an account, a token or a licence" and not (tmp_path / "gated" / ".revision").exists()
