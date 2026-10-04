"""The bench kit: cases, chains, replay and the writer (spec 15.7;
V1_LESSONS 9.1, 9.4, 9.5; spec 6.1). Every case here is made up."""

import json

import pytest

from openconsult.bench.cases import CaseChanged, case_named, cuts, live_transcript, load_cases, parse_script, sha256_of
from openconsult.bench.replay import CHAINS, run, run_chain
from openconsult.bench.writer import Refused, ResultWriter
from openconsult.db import open_database
from openconsult.llm.door import Door
from openconsult.llm.engine import EngineUnreachable
from openconsult.llm.record import ModelCalls
from tests.fakes import ALARM_QUIET, ASSESSMENT, FakeEngine, reply

SCRIPT = """# A made-up script

**Fictional patient:** Someone Made-up, 40

**DOCTOR:** Made-up turn one?
**PATIENT:** *(coughs)* Made-up turn two.
Not a turn at all.
**DOCTOR:** Made-up turn three.
**PATIENT:** Made-up turn four.
**DOCTOR:** Made-up turn five.
**PATIENT:** *(sighs)*
"""


def made_up_folder(tmp_path, script=SCRIPT):
    folder = tmp_path / "cases"
    folder.mkdir()
    (folder / "made_up.md").write_text(script, encoding="utf-8")
    rows = [{"consultation": 7, "pass": 2, "transcript": "Made-up pass two."},
            {"consultation": 7, "pass": 1, "transcript": "Made-up pass one."},
            {"consultation": 8, "pass": 1, "transcript": "Another consultation."}]
    (folder / "passes.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    listed = {"cases": [
        {"name": "madeup", "group": "script", "kind": "script", "file": "made_up.md",
         "sha256": sha256_of(folder / "made_up.md"), "age": 40, "sex": "M", "expected": {"fire": True}},
        {"name": "seven", "group": "495", "kind": "passes", "file": "passes.jsonl", "consultation": 7,
         "sha256": sha256_of(folder / "passes.jsonl"), "age": 31, "sex": "F"},
    ]}
    (folder / "cases.json").write_text(json.dumps(listed), encoding="utf-8")
    return folder


@pytest.fixture
def bench(tmp_path, clock):
    out = tmp_path / "bench"
    out.mkdir()
    db = open_database(out / "calls.db")

    def make(script=None):
        engine = FakeEngine(script)
        return Door(engine, ModelCalls(db, clock)), engine, ResultWriter(out), out

    yield make
    db.close()


def test_6_1_the_script_parser_gives_v1s_live_transcript():
    turns = parse_script(SCRIPT)
    assert [t.speaker for t in turns] == ["DOCTOR", "PATIENT", "DOCTOR", "PATIENT", "DOCTOR"]
    assert turns[1].text == "Made-up turn two."       # the stage direction is not spoken
    assert live_transcript(turns[:2]) == "Made-up turn one?\nMade-up turn two."
    assert cuts(5) == [4, 5] and cuts(8) == [4, 8] and cuts(9) == [4, 8, 9]


def test_15_7_cases_come_only_from_the_list_and_a_changed_file_is_refused(tmp_path):
    folder = made_up_folder(tmp_path)
    found = load_cases(folder)
    script, passes = case_named(found, "madeup"), case_named(found, "seven")
    assert script.patient.age == 40 and script.points() == [
        (4, "Made-up turn one?\nMade-up turn two.\nMade-up turn three.\nMade-up turn four."),
        (5, "Made-up turn one?\nMade-up turn two.\nMade-up turn three.\nMade-up turn four.\nMade-up turn five.")]
    assert passes.points() == [(1, "Made-up pass one."), (2, "Made-up pass two.")]
    with pytest.raises(KeyError):
        case_named(found, "not-listed")
    (folder / "made_up.md").write_text(SCRIPT + "\n**PATIENT:** A changed line.\n", encoding="utf-8")
    with pytest.raises(CaseChanged):
        load_cases(folder)
    (folder / "made_up.md").unlink()
    with pytest.raises(CaseChanged):
        load_cases(folder)


def test_9_4_the_writer_refuses_to_write_over_an_existing_result(tmp_path):
    writer = ResultWriter(tmp_path / "out")
    first = writer.write("case", "A1", {"n": 1})
    with pytest.raises(Refused):
        writer.write("case", "A1", {"n": 2})
    assert writer.read("case", "A1") == {"n": 1} and first.read_text(encoding="utf-8")
    assert writer.exists("case", "A1") and not writer.exists("case", "A2")
    with pytest.raises(Refused):
        writer.path("../..", "escape")


def test_9_4_the_writer_refuses_the_repo_and_the_apps_data_folder(tmp_path):
    repo, data = tmp_path / "repo", tmp_path / "data"
    for place in (repo / "a" / "b", data):
        with pytest.raises(Refused):
            ResultWriter(place, forbidden=(repo, data))
    ResultWriter(tmp_path / "elsewhere", forbidden=(repo, data))


def test_9_1_the_thirteen_chains_carry_their_temperature_and_seed(tmp_path, bench):
    assert [(c.name, c.temperature, c.seed) for c in CHAINS] == (
        [("A1", 0.0, 42), ("A2", 0.0, 42), ("A3", 0.0, 42)] + [(f"B{s}", 0.5, s) for s in range(1, 11)])
    door, engine, writer, _ = bench()
    case = case_named(load_cases(made_up_folder(tmp_path)), "seven")
    run(door, [case], writer, log=lambda line: None)
    assert len(engine.calls) == 13 * 2 * 2
    seen = sorted({(c.temperature, c.seed) for c in engine.calls})
    assert seen == sorted({(c.temperature, c.seed) for c in CHAINS})
    for chain in CHAINS:
        assert writer.read("seven", chain.name)["seed"] == chain.seed


def test_15_7_the_bench_goes_through_the_door_and_records_in_its_own_folder(tmp_path, bench):
    door, engine, writer, out = bench()
    case = case_named(load_cases(made_up_folder(tmp_path)), "madeup")
    result = run_chain(door, case, CHAINS[0], log=lambda line: None)
    assert result["failed"] is None and [p["point"] for p in result["passes"]] == [4, 5]
    assert result["passes"][1]["names"] == ["Made-up condition A", "Made-up condition B"]
    assert result["model_tag"] == door.profile.tag and result["engine_version"] == "0.0-made-up"
    assert set(result["prompts"]) == {"alarm", "assessment"}
    rows = ModelCalls(open_database(out / "calls.db")).rows()
    assert len(rows) == 4 and {r["job"] for r in rows} == {"alarm", "assessment"}
    assert not (tmp_path / "openconsult.db").exists()
    # The second pass carried the first's names as the stale list.
    assert "Made-up condition A" in engine.calls[3].user


def test_9_4_a_stopped_run_carries_on_and_never_reruns_a_complete_chain(tmp_path, bench):
    door, engine, writer, _ = bench()
    found = load_cases(made_up_folder(tmp_path))
    first = run(door, found, writer, chains=CHAINS[:2], log=lambda line: None)
    assert first == {"run": 4, "kept": 0, "failed": []}
    calls_before = len(engine.calls)
    again = run(door, found, writer, chains=CHAINS[:3], log=lambda line: None)
    assert again == {"run": 2, "kept": 4, "failed": []}
    assert len(engine.calls) == calls_before + 2 * (2 + 2)   # only A3's passes, both cases


def test_change_4_a_failed_call_fails_a_script_chain_but_not_a_495_chain(tmp_path, bench):
    found = load_cases(made_up_folder(tmp_path))
    script, passes = case_named(found, "madeup"), case_named(found, "seven")
    door, engine, writer, _ = bench([ALARM_QUIET, reply(ASSESSMENT, ended="cut"), ALARM_QUIET, ASSESSMENT])
    result = run_chain(door, script, CHAINS[0], log=lambda line: None)
    assert result["failed"] and "too_long" in result["failed"] and len(result["passes"]) == 1
    assert len(engine.calls) == 2   # the chain stopped there
    door, engine, writer, _ = bench([EngineUnreachable("gone"), ASSESSMENT, ALARM_QUIET, ASSESSMENT])
    result = run_chain(door, passes, CHAINS[0], log=lambda line: None)
    assert result["failed"] is None and len(result["passes"]) == 2
    assert result["passes"][0]["alarm"]["judged"] is False and result["passes"][1]["alarm"]["judged"] is True
    # Unreachable twice in a row fails any chain.
    door, engine, writer, _ = bench([EngineUnreachable("gone")] * 4)
    result = run_chain(door, passes, CHAINS[0], log=lambda line: None)
    assert "unreachable 2 times" in result["failed"]
