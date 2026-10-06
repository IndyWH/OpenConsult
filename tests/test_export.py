"""The public form of the engine bench (spec 15.8, rulings 2 and 11;
stage 3b rule 9; plan review change 1; V1_LESSONS 9.4). Every case, every
reply and every figure here is made up."""

import getpass
import gzip
import json
import socket

import pytest

from openconsult.bench import export, score
from openconsult.bench.cases import load_cases
from openconsult.bench.cli import REPO, main
from openconsult.bench.repeat import run_repeat
from openconsult.bench.replay import CHAINS, run
from openconsult.bench.writer import Refused, ResultWriter
from openconsult.db import open_database
from openconsult.llm.door import Door
from openconsult.llm.engine import EngineUnreachable
from openconsult.llm.record import ModelCalls
from openconsult.prompts import loader
from tests.fakes import ALARM_FIRES, ALARM_QUIET, ASSESSMENT, FakeEngine, reply
from tests.test_bench import made_up_folder
from tests.test_together import ByJob

EMPTY = {**ASSESSMENT, "differentials": []}
OTHER_CONSULTATION = "Another consultation."


@pytest.fixture
def arm(tmp_path, bench_folders, clock):
    """A made-up arm as a run leaves it: results and a record of calls,
    with a kept list, a cut reply, a call that never came back, and one
    call that no result names."""
    cases, out = bench_folders
    db = open_database(out / "calls.db")
    record = ModelCalls(db, clock)
    # The script's chain A1 keeps a list at its second point; A2 loses its alarm call; A3's assessment is cut.
    engine = ByJob(alarm=[ALARM_QUIET, ALARM_FIRES, ALARM_FIRES, EngineUnreachable("gone")],
                   assessment=[ASSESSMENT, EMPTY, ASSESSMENT, reply(ASSESSMENT, ended="cut")])
    door = Door(engine, record)
    door.ask("alarm", "the first call of an arm, which no result names")
    run(door, load_cases(cases), ResultWriter(out), CHAINS[:3], log=lambda line: None)
    # The sampler's file: the test's clock stands at 09:00:00, so two readings fall inside the arm.
    (tmp_path / "card.csv").write_text(
        "2026/10/04 08:59:59.000, 800 MiB, 24564 MiB\n2026/10/04 09:00:00.000, 17000 MiB, 24564 MiB\n"
        "2026/10/04 09:00:00.000, 17400 MiB, 24564 MiB\n2026/10/04 09:00:00.001, 900 MiB, 24564 MiB\n", encoding="utf-8")
    yield cases, out, tmp_path / "public", record
    db.close()


def every_text(public):
    """Each file of the public folder as text, the packed ones unpacked."""
    found = {}
    for path in sorted(p for p in public.rglob("*") if p.is_file()):
        data = path.read_bytes()
        found[path.relative_to(public).as_posix()] = (gzip.decompress(data) if path.suffix == ".gz" else data).decode("utf-8")
    return found


def export_all(arm, capsys=None):
    cases, out, public, _ = arm
    assert main(["export", "--public", str(public), "--cases", str(cases)]) == 0
    assert main(["export", "--public", str(public), "--arm", "made-up-arm", "--out", str(out),
                 "--card", str(public.parent / "card.csv"), "--fact", "start_to_first_answer_s=12.5"]) == 0
    if capsys:
        capsys.readouterr()
    return every_text(public)


def test_rule_9_only_the_rows_of_the_listed_consultation_are_published(arm, capsys):
    cases, _, public, _ = arm
    assert OTHER_CONSULTATION in (cases / "passes.jsonl").read_text(encoding="utf-8")   # it is in the private file
    texts = export_all(arm, capsys)
    rows = [json.loads(line) for line in texts["cases/seven.jsonl"].splitlines()]
    assert [(row["consultation"], row["transcript"]) for row in rows] == [(7, "Made-up pass two."), (7, "Made-up pass one.")]
    for name, text in texts.items():
        assert OTHER_CONSULTATION not in text, name
    assert not (public / "cases" / "passes.jsonl").exists()


def test_15_8_the_public_form_holds_every_reply_and_no_request(arm, capsys):
    cases, out, public, record = arm
    texts = export_all(arm, capsys)
    assert set(texts) == {"cases/cases.json", "cases/made_up.md", "cases/seven.jsonl", "arms/made-up-arm/arm.json",
                          "arms/made-up-arm/replies.jsonl.gz", "arms/made-up-arm/marks.json", "arms/made-up-arm/times.json"}
    lines = [json.loads(line) for line in texts["arms/made-up-arm/replies.jsonl.gz"].splitlines()]
    results = ResultWriter(out).read_all()
    named = [p[job]["call_id"] for _, r in sorted(results.items()) for p in r["passes"] for job in ("alarm", "assessment")]
    assert len(lines) == len(named) == len(record.rows()) - 1          # every call a result names, and not the first call
    first = lines[0]
    assert (first["case"], first["chain"], first["point"], first["job"]) == ("madeup", "A1", 4, "alarm")
    assert first["outcome"] == "ok" and json.loads(first["text"]) == ALARM_FIRES
    assert (first["prompt_tokens"], first["output_tokens"], first["temperature"], first["seed"]) == (50, 20, 0.0, 42)
    assert first["wall_ms"] >= 0 and first["pass_ms"] >= 0 and first["thinking"] is None
    assert {line["outcome"] for line in lines} == {"ok", "unreachable", "too_long"}
    assert sum(1 for line in lines if line["kept"]) == 1
    arm_said = json.loads(texts["arms/made-up-arm/arm.json"])
    assert (arm_said["engine"], arm_said["engine_version"], arm_said["model_digest"]) == ("ollama", "0.0-made-up", "made-up-digest")
    assert arm_said["calls"] == len(lines) and arm_said["facts"] == {"start_to_first_answer_s": "12.5"}
    assert arm_said["card"] == {"samples": 2, "lowest_mib": 17000, "median_mib": 17200.0, "highest_mib": 17400}
    assert json.loads(texts["arms/made-up-arm/times.json"])["calls"]["alarm"]["calls"] == sum(1 for l in lines if l["job"] == "alarm")
    # No request: not the prompt, not the patient line, not a transcript, in any file of the arm.
    for name, text in texts.items():
        if name.startswith("arms/"):
            for words in (loader.prompt("alarm")[:60], loader.prompt("assessment")[:60], "The patient is a",
                          "Made-up pass one.", "Made-up turn one?", "which no result names"):
                assert words not in text, (name, words)
    # No path of this machine, no user name and no host name, in any file the exporter writes.
    machine = [str(public.parent), "/home/", "/mnt/", "\\\\Users\\\\", "/Users/"]
    machine += [name for name in (getpass.getuser(), socket.gethostname()) if len(name) >= 4]
    for name, text in texts.items():
        for words in machine:
            assert words not in text, (name, words)
    # The same run gives the same packed file, byte for byte.
    assert export.arm_files("made-up-arm", out)["arms/made-up-arm/replies.jsonl.gz"] == \
        (public / "arms" / "made-up-arm" / "replies.jsonl.gz").read_bytes()


def test_15_8_the_public_cases_load_with_their_checksums(arm, capsys):
    cases, _, public, _ = arm
    texts = export_all(arm, capsys)
    private, published = load_cases(cases), load_cases(public / "cases")
    assert [(c.name, c.group, c.kind, c.patient, c.points()) for c in published] == \
        [(c.name, c.group, c.kind, c.patient, c.points()) for c in private]
    assert (public / "cases" / "made_up.md").read_bytes() == (cases / "made_up.md").read_bytes()
    listed = json.loads(texts["cases/cases.json"])
    assert listed["note"] == export.NOTE and "\r" not in texts["cases/seven.jsonl"]


def test_15_8_the_marks_are_rebuilt_from_the_public_replies(arm, capsys):
    cases, out, public, _ = arm
    export_all(arm)
    private = score.summary(ResultWriter(out).read_all())
    rebuilt = score.summary(export.results_from_replies(export.read_replies(public / "arms" / "made-up-arm" / "replies.jsonl.gz")))
    for key in ("marks", "per_chain", "failed_chains", "empty_replies", "kept_lists", "candidate"):
        assert rebuilt[key] == private[key], key
    assert private["failed_chains"] and private["kept_lists"] == 1     # the made-up arm has both to rebuild
    capsys.readouterr()
    assert main(["score", "--replies", str(public / "arms" / "made-up-arm" / "replies.jsonl.gz")]) == 1
    assert "| H1 | hard |" in capsys.readouterr().out
    assert sorted(p.name for p in public.parent.glob("scores.*")) == []   # nothing is written


def test_9_4_the_exporter_never_writes_over_a_published_file_nor_into_the_repo(arm, monkeypatch, capsys):
    cases, out, public, _ = arm
    export_all(arm)
    before = every_text(public)
    assert main(["export", "--public", str(public), "--cases", str(cases)]) == 6
    assert main(["export", "--public", str(public), "--arm", "made-up-arm", "--out", str(out)]) == 6
    assert "is never written over" in capsys.readouterr().out and every_text(public) == before
    # Never straight into the repo: the folder goes there by the owner's word, after the second gate.
    assert main(["export", "--public", str(REPO / "engine-bench-made-up"), "--cases", str(cases)]) == 6
    assert not (REPO / "engine-bench-made-up").exists()
    # Never past 30 MB: all or none.
    monkeypatch.setattr(export, "LIMIT", 200)
    with pytest.raises(Refused, match="over 30 MB"):
        export.publish(public.parent / "second", export.case_files(cases))
    assert not (public.parent / "second").exists()
    capsys.readouterr()


def test_ruling_11_the_replies_of_the_repeat_test_are_published_with_their_counts(arm, capsys, tmp_path):
    cases, out, public, record = arm
    repeat_out = ResultWriter(tmp_path / "repeat")
    door = Door(FakeEngine(), ModelCalls(open_database(tmp_path / "repeat" / "calls.db")))
    record = ModelCalls(open_database(tmp_path / "repeat" / "calls.db"))
    run_repeat(door, record, load_cases(cases), ResultWriter(out), repeat_out, points=(("seven", None),),
               between_case="madeup", log=lambda line: None)
    assert main(["export", "--public", str(public), "--arm", "made-up-repeat", "--out", str(tmp_path / "repeat")]) == 0
    texts = every_text(public)
    counts = json.loads(texts["arms/made-up-repeat/repeat.json"])
    assert [(c["job"], c["way"], c["same_as_first"], c["times"]) for c in counts] == [
        ("alarm", "bare", 10, 10), ("alarm", "between", 10, 10), ("assessment", "bare", 10, 10), ("assessment", "between", 10, 10)]
    lines = [json.loads(line) for line in texts["arms/made-up-repeat/replies.jsonl.gz"].splitlines()]
    assert len(lines) == 2 * (10 + 19) and {line["role"] for line in lines} == {"test", "between"}
    assert json.loads(texts["arms/made-up-repeat/arm.json"])["kind"] == "repeat"
    assert "arms/made-up-repeat/marks.json" not in texts
    capsys.readouterr()
