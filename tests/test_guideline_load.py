"""The loader command of the bench kit (spec 15.12, ruling 18; R18; R21):
the publisher from the command and nowhere else, the statement as the
owner's, the titles from the files' own title lines, the default data
folder and the repository refused. Made-up files, a made-up embedder."""

from datetime import date
from pathlib import Path

from openconsult import words
from openconsult.bench import guideline_load
from openconsult.bench.cli import main
from openconsult.consult.consultations import Consultations
from openconsult.db import open_database
from openconsult.patients.patients import Patients
from openconsult.guidelines.sources import Sources
from openconsult.patients.audit import Audit
from openconsult.settings import paths
from tests.fakes import MadeUpEmbedder
from tests.test_passages import PAGE, paragraph


def test_R21_R18_the_loader_command_takes_the_publisher_from_the_command_and_refuses_the_owners_folder(tmp_path, monkeypatch):
    folder, data = tmp_path / "docs", tmp_path / "data"
    folder.mkdir()
    (folder / "b_made.html").write_bytes(PAGE.encode())
    (folder / "a_notes.txt").write_text(f"A typed title line\n\n{paragraph(80)}\n", encoding="utf-8")
    (folder / "c_short.txt").write_text("too short to make a passage\n", encoding="utf-8")
    said = []
    embedder = MadeUpEmbedder()
    load = lambda **kw: guideline_load.guideline_load(folder, kw.pop("publisher", "Made-up publisher"), kw.pop("data_folder", data),  # noqa: E731
                                                      kw.pop("statement", True), say=said.append, make_embedder=lambda d, w: embedder, **kw)
    assert load(publisher=" ") == 2 and said[-1] == words.LOAD_NEEDS_PUBLISHER
    assert load(statement=False) == 2 and said[-1] == words.LOAD_NEEDS_STATEMENT
    monkeypatch.setattr(paths, "default_data_folder", lambda: tmp_path / "owner")
    assert load(data_folder=tmp_path / "owner") == 6 and said[-1] == words.LOAD_FOLDER_REFUSED
    assert load(data_folder=guideline_load.REPO / "x") == 6
    assert not (data / "openconsult.db").exists()
    code = load()
    assert code == 1                                                   # the short file was not loaded
    assert said[-1] == words.LOAD_DONE.format(files=2, given=3, passages=said and _passages(said), outside=0, seconds=_seconds(said))
    assert any(line.startswith("c_short.txt: not loaded: no_passages") for line in said)
    db = open_database(data / "openconsult.db")
    sources = Sources(db, Audit(db))
    loaded = sources.loaded()
    assert [(s["title"], s["publisher"], s["added_by"], s["file_name"], s["statement_accepted"]) for s in reversed(loaded)] == [
        ("A typed title line", "Made-up publisher", "command", "a_notes.txt", 1),
        ("Made-up guideline: a made-up condition", "Made-up publisher", "command", "b_made.html", 1)]
    lines = [line.detail for line in Audit(db).lines() if line.event == "guideline.added"]
    assert len(lines) == 2 and all("by the command, the statement accepted" in d and "Made-up" not in d for d in lines)
    db.close()
    # The worker not ready: nothing loaded, the reason said.
    said.clear()
    assert guideline_load.guideline_load(folder, "P", tmp_path / "data2", True, say=said.append,
                                         make_embedder=lambda d, w: MadeUpEmbedder(installed=False)) == 7
    assert said[-1] == words.GUIDELINE_ADD_NEEDS_WORKER.format(reason=words.GUIDELINE_NOT_INSTALLED)
    # The command line: --publisher and --statement-accepted are the flags; the default embedder of a bare folder is not installed.
    assert main(["guideline-load", "--folder", str(folder), "--publisher", "P", "--data-folder", str(tmp_path / "data3"),
                 "--statement-accepted"]) == 7


def _passages(said) -> int:
    return sum(int(line.split(", ")[1].split()[0]) for line in said if ": html, " in line or ": text, " in line)


def _seconds(said) -> float:
    return round(sum(float(line.rsplit(", ", 1)[1].split()[0]) for line in said if ": html, " in line or ": text, " in line), 1)


def test_7_3_rule_4_the_owners_folder_is_loaded_only_when_named_by_its_path_and_asked_for(tmp_path, monkeypatch, clock):
    # The plan review of 28 Oct, point 3: the owner's own data folder is refused unless he gives it by its path with
    # --into-my-data-folder, and then only with the app closed (a consultation live or stopping is the one sign, the app
    # keeping no lock or pid file); every row as the page writes it; the repository never; the flag nothing for a bench folder.
    folder, owner, bench = tmp_path / "docs", tmp_path / "owner", tmp_path / "bench"
    folder.mkdir()
    (folder / "b_made.html").write_bytes(PAGE.encode())
    monkeypatch.setattr(paths, "default_data_folder", lambda: owner)
    said = []
    load = lambda data, **kw: guideline_load.guideline_load(folder, "Made-up publisher", data, True, say=said.append,  # noqa: E731
                                                            make_embedder=lambda d, w: MadeUpEmbedder(), **kw)
    assert load(owner) == 6 and said[-1] == words.LOAD_FOLDER_REFUSED and not (owner / "openconsult.db").exists()
    assert load(owner / "deeper") == 6 and "--into-my-data-folder" in words.LOAD_FOLDER_REFUSED
    assert load(guideline_load.REPO / "x", into_my_data_folder=True) == 6 and said[-1] == words.LOAD_REPO_REFUSED
    assert load(owner, into_my_data_folder=True) == 0
    db = open_database(owner / "openconsult.db")
    sources = Sources(db, Audit(db))
    assert [(s["added_by"], s["statement_accepted"], s["publisher"]) for s in sources.loaded()] == [("command", 1, "Made-up publisher")]
    added = [line.detail for line in Audit(db).lines() if line.event == "guideline.added"]
    assert len(added) == 1 and "by the command, the statement accepted" in added[0] and "Made-up" not in added[0]
    # The app running on it, by its one sign: a consultation live, then stopping, refuses and loads nothing.
    patient = Patients(db, Audit(db), clock).add("Made-up patient", date(1990, 1, 1), "F")
    cid = Consultations(db, clock).start(patient.id, 15, "nemotron", "vllm", "0", "tag", None, 2)
    assert load(owner, into_my_data_folder=True) == 8 and said[-1] == words.LOAD_APP_RUNNING and len(sources.loaded()) == 1
    Consultations(db, clock).set(cid, state="stopping")
    assert load(owner, into_my_data_folder=True) == 8 and len(sources.loaded()) == 1
    Consultations(db, clock).set(cid, state="final")
    assert load(owner, into_my_data_folder=True) == 0 and len(sources.loaded()) == 2
    db.close()
    # A bench folder loads the same with the flag and without; the command line carries the flag.
    assert load(bench) == 0 and load(bench, into_my_data_folder=True) == 0
    assert main(["guideline-load", "--folder", str(folder), "--publisher", "P", "--data-folder", str(owner), "--statement-accepted"]) == 6
    assert main(["guideline-load", "--folder", str(folder), "--publisher", "P", "--data-folder", str(owner), "--statement-accepted",
                 "--into-my-data-folder"]) == 7                           # past the refusal; the bare folder's worker is not installed
