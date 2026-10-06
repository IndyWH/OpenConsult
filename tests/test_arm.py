"""An arm of the engine bench, run by the bench command against a made-up
server (spec 15.8, the clock; stage 3b, rule 19; R19; V1_LESSONS 9.6)."""

import json

from openconsult.bench.cli import main
from openconsult.bench.vllm import VllmEngine
from openconsult.bench.writer import ResultWriter
from openconsult.db import open_database
from openconsult.llm.record import ModelCalls
from tests.fakes import CALL, REVISION, answer_by_job, describe

OTHER_REVISION = "f" * 40


def run_args(cases, out, server, *more):
    return ["run", "--cases", str(cases), "--out", str(out), "--case", "seven", "--kind", "vllm",
            "--engine", server.address, "--model", CALL.tag, *more]


def test_rule_19_an_arm_is_never_carried_on_with_another_engine_or_model(server, bench_folders, capsys):
    cases, out = bench_folders
    describe(server, VllmEngine)
    server.routes["/v1/chat/completions"] = answer_by_job
    assert main(run_args(cases, out, server, "--chains", "A1")) == 0
    # The same folder, another revision of the model: refused, and nothing is added.
    describe(server, VllmEngine, root=f"/made-up/snapshots/{OTHER_REVISION}")
    sent_before = len(server.chats())
    assert main(run_args(cases, out, server, "--chains", "A1", "A2")) == 5
    said = capsys.readouterr().out
    assert "STOP: this folder holds results from" in said and REVISION in said and OTHER_REVISION in said
    assert len(server.chats()) == sent_before and not ResultWriter(out).exists("seven", "A2")
    # Nor carried on with the calls sent another way.
    describe(server, VllmEngine)
    assert main(run_args(cases, out, server, "--chains", "A1", "A2", "--together")) == 5
    # The twin: the same engine and model carry on, and the finished chain is not run again.
    assert main(run_args(cases, out, server, "--chains", "A1", "A2")) == 0
    assert ResultWriter(out).exists("seven", "A2")
    assert len(server.chats()) == sent_before + 1 + 4      # the first call, then A2's two passes
    capsys.readouterr()


def test_15_8_the_first_call_of_an_arm_is_recorded_and_enters_no_time(server, bench_folders, capsys):
    cases, out = bench_folders
    describe(server, VllmEngine)
    server.routes["/v1/chat/completions"] = answer_by_job
    assert main(run_args(cases, out, server, "--chains", "A1")) == 0
    assert "the first call, not measured:" in capsys.readouterr().out
    rows = ModelCalls(open_database(out / "calls.db")).rows(newest_first=False)
    result = ResultWriter(out).read("seven", "A1")
    named = {p[job]["call_id"] for p in result["passes"] for job in ("alarm", "assessment")}
    assert len(rows) == 5 and rows[0]["job"] == "alarm" and rows[0]["outcome"] == "ok"
    assert rows[0]["id"] not in named and named == {row["id"] for row in rows[1:]}
    # It is the alarm call of the first point, with no word written for it.
    assert json.loads(rows[0]["request"])["messages"] == json.loads(rows[1]["request"])["messages"]
    main(["score", "--out", str(out)])
    calls = json.loads((out / "scores.json").read_text(encoding="utf-8"))["calls"]
    assert calls["alarm"]["calls"] == 2 and calls["assessment"]["calls"] == 2
    capsys.readouterr()


def test_15_8_an_arm_does_not_start_when_its_first_call_fails(server, bench_folders, capsys):
    cases, out = bench_folders
    describe(server, VllmEngine, context=8192)        # a server started at half the context
    server.routes["/v1/chat/completions"] = answer_by_job
    assert main(run_args(cases, out, server, "--chains", "A1")) == 4
    said = capsys.readouterr().out
    assert "STOP: the first call failed" in said and "8192" in said and "16384" in said
    assert ResultWriter(out).read_all() == {} and server.chats() == []
