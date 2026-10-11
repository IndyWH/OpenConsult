"""The commands of part two (spec 15.9, the details of part two of 5c;
R18; R20; R31; rule 22 of the stage prompt; V1_LESSONS 9.4). A made-up
voice worker and a made-up language model."""

import pytest

from openconsult import words
from openconsult.bench import cli
from openconsult.bench.speech import commands, commands2
from openconsult.llm.door import Door
from openconsult.llm.profile import GEMMA_4_QAT
from openconsult.llm.record import ModelCalls
from openconsult.db import open_database
from tests.fakes import FakeEngine
from tests.made_up_part_two import build
from tests.test_voice import MadeUpVoiceWorker


@pytest.fixture
def part_two(tmp_path, recordings_kept, monkeypatch):
    return build(tmp_path, recordings_kept, monkeypatch, MadeUpVoiceWorker)


def test_speech_calls_writes_one_result_per_page_and_job_keeps_a_failure_and_never_asks_twice(part_two):
    results, engine, codes, said = part_two["results"], part_two["engine"], part_two["codes"], part_two["said"]
    assert codes == [5, 0, 0, 0, 0, 0]                       # the first label check failed and was kept; the rest ran
    pages = ["nemotron--one", "nemotron_tied_pair--one", "whisperx_pyannote--one"]   # the failed cloud arm has no page
    assert sorted(c for (job, c) in results if job == "label_check") == pages
    assert sorted(c for (job, c) in results if job == "note") == sorted(p + r for p in pages for r in ("--r1", "--r2"))
    assert sorted(c for (job, c) in results if job == "script_note") == ["script--one--r1", "script--one--r2"]
    failed = results[("label_check", "nemotron--one")]
    assert not failed["call"]["ok"] and failed["call"]["failure"] == "too_slow" and failed["labels"] is None
    refused = results[("label_check", "nemotron_tied_pair--one")]
    assert refused["call"]["ok"] and refused["labels"] is None and refused["refusal"]["missing"] == [1] or refused["refusal"]["missing"]
    whole = results[("label_check", "whisperx_pyannote--one")]
    assert whole["labels"] and whole["refusal"] is None and whole["user"].startswith("TRANSCRIPT:\n[1] ")
    drug = results[("drug_name", "nemotron--one")]
    assert [k["heard"] for k in drug["kept"]] == ["metformin"] and [d["heard"] for d in drug["dropped"]] == ["zzz"]
    note = results[("note", "nemotron--one--r1")]
    assert note["note"]["reasoning"] == "Made up." and note["roles"] == {"S1": "DOCTOR", "S2": "PATIENT"}
    assert note["user"].startswith("TRANSCRIPT:\n[0] Doctor: ") and results[("note", "nemotron--one--r2")]["note"]["reasoning"] == "Made up"
    script = results[("script_note", "script--one--r1")]
    assert script["user"].startswith("TRANSCRIPT:\n[0] Doctor: Any chest pain") and len(script["turns"]) == 6
    assert len(engine.calls) == 3 + 3 + 3 + 1 + 3 + 1 == 14
    rows = ModelCalls(open_database(part_two["out"] / "calls" / "calls.db")).rows()
    assert len(rows) == 14 and {r["job"] for r in rows} == {"bench_label_check", "bench_drug_name", "bench_note"}
    # Asked again: every result is there, and the model is not asked (the failed one stays failed).
    door = part_two["door"]
    code = commands2.speech_calls(part_two["out"], part_two["folder"], [part_two["scripts"]], "label_check", None,
                                  part_two["data"], say=said.append, make_door=lambda p: door)
    assert code == 0 and len(engine.calls) == 14 and said[-1] == words.BENCH_CALLS_DONE.format(made=0, failed=0, kept=3)
    assert words.BENCH_CALL_FAILED.format(job="label_check", arm="nemotron", name="one", failure="too_slow",
                                          detail=failed["call"]["detail"]) in said


def test_R18_the_commands_refuse_before_anything_is_started(tmp_path, part_two):
    out, folder, data, scripts, said = (part_two[k] for k in ("out", "folder", "data", "scripts", "said"))
    for place in (commands.REPO / "x", tmp_path / "owner-data" / "o", data / "o", folder / "o"):
        assert commands2.speech_calls(place, folder, [scripts], "note", 1, data, say=said.append) == 6
    assert commands2.speech_calls(out, folder, [scripts], "made-up-job", 1, data, say=said.append) == 2
    absent = Door(FakeEngine(version=None), ModelCalls(open_database(tmp_path / "x.db")), GEMMA_4_QAT)
    assert commands2.speech_calls(tmp_path / "o2", folder, [scripts], "note", 1, data, say=said.append, make_door=lambda p: absent) == 2
    assert said[-1].startswith("The language model") and not (tmp_path / "o2" / "calls" / "results").exists()


def test_R31_the_bench_command_names_the_commands_of_part_two_and_the_two_options(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(commands2, "speech_calls", lambda *a, **k: seen.append((a, k)) or 0)
    assert cli.main(["speech-calls", "--out", str(tmp_path / "o"), "--recordings", str(tmp_path / "r"), "--scripts", "a",
                     "--job", "note", "--round", "2", "--arm", "nemotron"]) == 0
    assert seen[0][0][3:5] == ("note", 2) and seen[0][0][7] == ["nemotron"]
    with pytest.raises(SystemExit):
        cli.main(["speech-calls", "--out", "o", "--recordings", "r", "--scripts", "a", "--job", "made-up"])
    monkeypatch.setattr(commands, "speech_score", lambda *a, **k: seen.append((a, k)) or 0)
    assert cli.main(["speech-score", "--out", "o", "--recordings", "r", "--scripts", "a", "--marks", "m", "--write", "w",
                     "--key-facts", "k.json", "--drug-list", "d.json"]) == 0
    assert seen[1][1]["key_facts_path"].name == "k.json" and seen[1][1]["drug_list_path"].name == "d.json"
