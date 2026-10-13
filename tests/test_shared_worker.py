"""The worker of EmbeddingGemma 2 (spec 15.9, ruling 25; the details of
5d): its number format is never float16, and its one fetch sends no token
and reports a gate instead of working round it (rule 7 of the stage). The
two files are read by path, as the worker runs them; no heavy library
loads here, and nothing is fetched."""

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _module(name: str):
    path = REPO / "openconsult" / "bench" / "shared" / "embedding2" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"embedding2_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_15_9_ruling_25_version_2_is_never_run_in_float16():
    precision = _module("precision")
    assert precision.dtype_name("cuda") == "bfloat16" and precision.dtype_name("cpu") == "float32"
    assert precision.FORBIDDEN not in precision.DTYPES.values()
    with pytest.raises(ValueError):
        precision.dtype_name("float16")


def test_15_9_5d_the_fetch_sends_no_token_and_a_gate_is_reported_not_worked_round(tmp_path):
    fetch = _module("fetch")
    given = {}

    def download(repo_id, **kwargs):
        given.update(kwargs, repo_id=repo_id)
        Path(kwargs["local_dir"]).mkdir(parents=True, exist_ok=True)
        (Path(kwargs["local_dir"]) / fetch.WEIGHTS).write_bytes(b"made-up weights")     # the wrong bytes

    env = {}
    report = fetch.fetch(tmp_path / "model", download, env)
    assert given["token"] is False and given["revision"] == fetch.REVISION and env["HF_HUB_DISABLE_IMPLICIT_TOKEN"] == "1"
    assert Path(given["local_dir"]) == tmp_path / "model" and given["repo_id"] == "google/embeddinggemma-2"
    assert not report["ok"] and "not" in report["error"] and not (tmp_path / "model" / fetch.WEIGHTS).exists()

    class Refused(Exception):
        pass

    def gated(repo_id, **kwargs):
        raise Refused("401 Client Error: this repo is gated")

    report = fetch.fetch(tmp_path / "gated", gated, {})
    assert report == {**report, "ok": False, "error": "asks for an account, a token or a licence"}
    assert not (tmp_path / "gated").exists() or not any((tmp_path / "gated").iterdir())

    def right(repo_id, **kwargs):
        folder = Path(kwargs["local_dir"])
        folder.mkdir(parents=True, exist_ok=True)
        (folder / fetch.WEIGHTS).write_bytes(b"x")

    fetch.WEIGHTS_SHA256 = "2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881"      # sha256 of b"x"
    report = fetch.fetch(tmp_path / "right", right, {})
    assert report["ok"] and report["fetched"] and report["bytes"] == 1
    again = fetch.fetch(tmp_path / "right", right, {})
    assert again["ok"] and again["found"] and not again["fetched"]
    assert json.dumps(report)                                                           # the report is plain JSON
