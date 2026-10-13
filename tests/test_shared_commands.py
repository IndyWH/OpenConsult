"""The commands of the test of 5d and its tables (spec 15.9, the details
of 5d; R18; R31; 15.8 ruling 26; V1_LESSONS 9.4): the folders they refuse,
a result never written over, the same bytes twice, and that the app
cannot reach any of it. Every result here is made up."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from openconsult.bench.cli import main
from openconsult.bench.shared import commands, tables
from openconsult.bench.shared.embed import Vectors
from openconsult.cli import main as app_main
from openconsult.settings import paths
from tests import made_up_run as made
from tests.test_shared_runner import MadeUpEmbedder, MovedClock

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def folders(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "default_data_folder", lambda: tmp_path / "owners-data")
    (tmp_path / "data").mkdir()
    (tmp_path / "recordings").mkdir()
    return tmp_path


def a_clock():
    clock = MovedClock()
    return clock, lambda *a, **k: MadeUpEmbedder(clock)


def test_R18_the_commands_refuse_the_repo_the_data_folders_and_the_recordings_folder(folders):
    said = []
    clock, make = a_clock()
    for out in (REPO / "x", folders / "owners-data" / "x", folders / "data" / "x", folders / "recordings" / "x"):
        assert commands.shared_search(out, "first", "card", folders / "data", recordings=folders / "recordings",
                                      say=said.append, make_embedder=make, searches=1, sleep=clock.sleep, clock=clock) == 6
        assert commands.shared_index(out, "first", "card", folders / "data", recordings=folders / "recordings",
                                     say=said.append, make_embedder=make) == 6
        assert commands.shared_watch(out, folders / "stop", data_folder=folders / "data", recordings=folders / "recordings",
                                     say=said.append, readers={}) == 6
        assert commands.shared_judge(folders / "run", out, data_folder=folders / "data", recordings=folders / "recordings",
                                     say=said.append) == 6
        assert not out.exists()
    assert all(s.startswith("Results may not go under") for s in said) and len(said) == 16


def test_V1_LESSONS_9_4_a_result_is_never_written_over_and_the_searches_are_stored(folders, tmp_path):
    out = folders / "out"
    clock, make = a_clock()
    said = []
    assert commands.shared_search(out, "first", "card", searches=3, say=said.append, make_embedder=make,
                                  sleep=clock.sleep, clock=clock, wall=lambda: 1.0) == 0
    stored = json.loads((out / "searches.json").read_text(encoding="utf-8"))
    assert len(stored["searches"]) == 3 and stored["searches"][0]["names"][0] == "Depressive episode"
    assert any("search 0 of 4 names took" in s for s in said)
    assert commands.shared_search(out, "first", "card", searches=1, say=said.append, make_embedder=make,
                                  sleep=clock.sleep, clock=clock) == 6
    assert said[-1].endswith("exists and is never written over.")
    assert commands.shared_search(out, "first", "card", load_only=True, say=said.append, make_embedder=make) == 0
    assert json.loads((out / "placed.json").read_text(encoding="utf-8"))["ok"] is True
    assert commands.shared_search(folders / "out2", "second", "card", data_folder=tmp_path / "no-env", searches=1, say=said.append) == 7
    assert "is not installed" in said[-1]


def test_15_9_5d_the_side_reading_and_the_watch_write_once(folders, tmp_path):
    from tests.test_shared_runner import made_up_sources
    (tmp_path / "src").mkdir()
    lessons, cases = made_up_sources(tmp_path / "src")
    out = folders / "out"
    clock, make = a_clock()
    from openconsult.bench.shared import pieces
    cut_files = pieces.public_files(lessons, cases)
    assert commands.shared_index(out, "first", "card", say=lambda s: None, make_embedder=make, sources=cut_files,
                                 allowed=(lessons, cases)) == 0
    assert commands.shared_index(out, "first", "card", say=lambda s: None, make_embedder=make, sources=cut_files,
                                 allowed=(lessons, cases)) == 6
    index = json.loads((out / "index.json").read_text(encoding="utf-8"))
    assert index["pieces"] == 250 and len(index["files"]) == 26 and sum(f["pieces"] for f in index["files"]) == 250
    stop = folders / "stop"
    moved = MovedClock()
    readers = {"made": lambda: {"available": True, "n": 1}}

    def sleep(s):
        moved.sleep(s)
        if moved.t > 104:
            stop.write_text("x", encoding="utf-8")
    assert commands.shared_watch(out, stop, say=lambda s: None, readers=readers, sleep=sleep, clock=moved, wall=lambda: 7.0) == 0
    watched = json.loads((out / "watch.json").read_text(encoding="utf-8"))
    assert len(watched["readings"]) == 2 and watched["readings"][0]["made"] == {"available": True, "n": 1}
    assert commands.shared_watch(out, stop, say=lambda s: None, readers=readers) == 6


def test_15_8_ruling_26_the_tables_are_the_same_bytes_twice_and_name_the_way_round_apart(folders):
    run = folders / "run"
    made.write_base(run, "base-before")
    made.write_base(run, "base-after")
    made.write_setup(run, "ollama-one-whisperx-first-card", speech="whisperx",
                     speech_failure={"at": "stop", "piece": None, "failure": "worker_error", "detail": "CUDA out of memory"})
    made.write_setup(run, "ollama-one-nemotron-first-card")
    made.write_setup(run, "ollama-whisperx-first-processor", speech="whisperx", where="processor", kind="wayround",
                     setup_extra={"wayround": {"wanted_epoch": made.T0 + 314.5, "back_epoch": made.T0 + 325.0}})
    card, apps = folders / "gpu.csv", folders / "apps.csv"
    card.write_text("2027/01/15 12:00:00.000, 18000, 24564\n", encoding="utf-8")
    apps.write_text("2027/01/15 12:00:00.000, 1234, /made-up/x, 4000\n", encoding="utf-8")
    said = []
    assert commands.shared_judge(run, folders / "w1", card, apps, say=said.append) == 0
    assert commands.shared_judge(run, folders / "w2", card, apps, say=said.append) == 0
    assert (folders / "w1" / "tables.json").read_bytes() == (folders / "w2" / "tables.json").read_bytes()
    assert (folders / "w1" / "tables.md").read_bytes() == (folders / "w2" / "tables.md").read_bytes()
    assert b"\r" not in (folders / "w1" / "tables.md").read_bytes()
    text = (folders / "w1" / "tables.md").read_text(encoding="utf-8")
    assert "| Ollama, one after another, Nemotron | works | not run | not run | not run |" in text
    assert "| Ollama, one after another, WhisperX with pyannote | not working (line 1) |" in text
    assert "On Ollama: 1 setups work, 1 do not, 0 not judged." in text and "On vLLM: 0 setups work" in text
    assert "## The ways round, kept apart" in text and "| ollama-whisperx-first-processor | " in text
    assert "GB" not in text and "MiB" in text
    assert commands.shared_judge(run, folders / "w1", card, apps, say=said.append) == 6
    assert said[-1].endswith("exists and is never written over.")
    asked = []
    assert commands.shared_judge(run, None, ask_wayround=True, say=asked.append) == 0 and asked == ["ollama"]
    assert commands.shared_judge(run, None, say=asked.append) == 2


def test_15_9_5d_the_sampler_files_are_read_in_mib_with_their_moments(tmp_path):
    card, apps = tmp_path / "gpu.csv", tmp_path / "apps.csv"
    card.write_text("timestamp, memory.used [MiB], memory.total [MiB]\n2027/01/15 12:00:00.500, 829, 24564\n", encoding="utf-8")
    apps.write_text("2027/01/15 12:00:00.500, 77, /a/b, c, 61\n", encoding="utf-8")
    found = commands.read_sampler(card, apps)
    assert found["samples"][0]["used"] == 829 and found["samples"][0]["total"] == 24564 and len(found["samples"]) == 1
    assert found["programs"][0] == {**found["programs"][0], "pid": 77, "name": "/a/b,c", "mib": 61}
    assert found["samples"][0]["epoch"] == found["programs"][0]["epoch"] and commands.read_sampler(None, None) is None


def test_15_9_5d_the_commands_print_their_help_on_the_base_app():
    for name in ("shared-install", "shared-search", "shared-index", "shared-watch", "shared-judge"):
        with pytest.raises(SystemExit) as left:
            main([name, "--help"])
        assert left.value.code == 0


def test_R31_the_app_cannot_reach_the_shared_bench(tmp_path):
    """No command of the app names the test of 5d, and the app's own modules
    import nothing from the bench: with the bench made unimportable, the
    app still builds."""
    with pytest.raises(SystemExit) as left:
        app_main(["shared-search", "--data-folder", str(tmp_path)])
    assert left.value.code == 2
    code = ("import sys; sys.modules['openconsult.bench'] = None; "
            "import openconsult.app, openconsult.cli, openconsult.web.routes, openconsult.speech.door, openconsult.llm.door; "
            "print('built')")
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=REPO, timeout=60)
    assert done.returncode == 0 and done.stdout.strip() == "built", done.stderr[-500:]


def test_15_9_5d_an_install_that_cannot_find_uv_or_whose_fetch_is_gated_says_so(tmp_path):
    said = []
    assert commands.shared_install(tmp_path / "data", say=said.append, which=lambda name: None) == 7
    assert said == ["uv is not installed. Install uv first; see the README."] or said[-1]

    class Done:
        def __init__(self, code, out="", err=""):
            self.returncode, self.stdout, self.stderr = code, out, err

    def run(command, env=None, **kwargs):
        if command[1:2] == ["sync"]:
            assert env["UV_PROJECT_ENVIRONMENT"].endswith(str(Path("embedding") / "embeddinggemma2" / ".venv"))
            return Done(0, err="Installed 61 packages")
        assert env["HF_HUB_DISABLE_IMPLICIT_TOKEN"] == "1" and "HF_HUB_OFFLINE" not in env
        return Done(1, out=json.dumps({"ok": False, "error": "asks for an account, a token or a licence"}) + "\n")
    said = []
    assert commands.shared_install(tmp_path / "data", say=said.append, run=run, which=lambda name: "/made-up/uv",
                                   environ={"HF_HUB_OFFLINE": "1", "PATH": "x"}) == 8
    assert said[-1].startswith("EmbeddingGemma 2 could not be fetched: the hub asks for an account")
    assert "The environment of EmbeddingGemma 2 is ready." in said

    def run_ok(command, env=None, **kwargs):
        if command[1:2] == ["sync"]:
            return Done(0, err="")
        return Done(0, out=json.dumps({"ok": True, "fetched": True, "bytes": 1_488_915_288, "revision": "r", "error": None}) + "\n")
    said = []
    assert commands.shared_install(tmp_path / "data", say=said.append, run=run_ok, which=lambda name: "/made-up/uv", environ={}) == 0
    assert said[-1] == "Downloaded EmbeddingGemma 2 at revision r (1.5 GB)."
    assert Vectors(True).ok and tables.cell(None) == "not run"
