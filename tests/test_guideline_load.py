"""The loader command of the bench kit (spec 15.12, ruling 18; R18; R21):
the publisher from the command and nowhere else, the statement as the
owner's, the titles from the files' own title lines, the default data
folder and the repository refused. Made-up files, a made-up embedder."""

from pathlib import Path

from openconsult import words
from openconsult.bench import guideline_load
from openconsult.bench.cli import main
from openconsult.db import open_database
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
