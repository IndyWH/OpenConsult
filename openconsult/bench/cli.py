"""The bench command, openconsult-bench (spec 15.7, 15.8): run, repeat,
score and wordcheck. It goes through the same door as the app and can be pointed
at any engine by its kind, its address and the name it knows the model
by. It never writes to the app's data: its results and its own record
of calls go to the folder it is given."""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import sys
from pathlib import Path

import openconsult
from openconsult.bench import score, wordcheck
from openconsult.bench.cases import load_cases
from openconsult.bench.llamacpp import LlamaCppEngine
from openconsult.bench.repeat import run_repeat
from openconsult.bench.replay import CHAINS, arm_differs, first_call, run
from openconsult.bench.vllm import VllmEngine
from openconsult.bench.writer import ResultWriter
from openconsult.db import open_database
from openconsult.llm.door import Door
from openconsult.llm.ollama import DEFAULT_ADDRESS, OllamaEngine
from openconsult.llm.profile import GEMMA_4_QAT
from openconsult.llm.record import ModelCalls
from openconsult.settings import paths

REPO = Path(openconsult.__file__).resolve().parents[1]
# The engines the bench can speak to. The app has the first only (R31).
KINDS = {"ollama": OllamaEngine, "llamacpp": LlamaCppEngine, "vllm": VllmEngine}


def say(line: str) -> None:
    print(f"[{dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}] {line}", flush=True)


def open_arm(args, together: bool = False):
    """The door, its record and the writer of an arm; or the code to stop
    with, when the engine or the model is not the one this arm needs.
    The door gets a copy of the one profile that carries the name this
    engine knows the model by. The app's profile is not touched."""
    out = Path(args.out)
    writer = ResultWriter(out, forbidden=(REPO, paths.default_data_folder()))
    engine = KINDS[args.kind](args.engine)
    profile = dataclasses.replace(GEMMA_4_QAT, tag=args.model or GEMMA_4_QAT.tag, engine=engine.name)
    record = ModelCalls(open_database(out / "calls.db"))
    door = Door(engine, record, profile)
    version, digest = door.identity()
    say(f"engine {profile.engine} at {args.engine} version {version}; model {profile.tag} digest {digest}")
    if version is None or digest is None:
        say("STOP: the engine or the model cannot be reached")
        return 2
    if args.digest and digest != args.digest:
        say(f"STOP: the model's digest is {digest}, not {args.digest}")
        return 3
    held = writer.read_all()
    differs = arm_differs(next(iter(held.values())), door, together) if held else None
    if differs:
        say(f"STOP: {differs}")
        return 5
    return door, record, writer


def warm(door: Door, case) -> bool:
    first = first_call(door, case)
    say(f"the first call, not measured: {first.wall_ms} ms")
    if not first.ok:
        say(f"STOP: the first call failed: {first.failure}: {first.detail}")
    return first.ok


def cmd_run(args) -> int:
    opened = open_arm(args, args.together)
    if isinstance(opened, int):
        return opened
    door, _, writer = opened
    cases = load_cases(Path(args.cases))
    if args.case:
        cases = [c for c in cases if c.name in args.case]
    chains = [c for c in CHAINS if not args.chains or c.name in args.chains]
    if any(not writer.exists(case.name, chain.name) for case in cases for chain in chains):
        if not warm(door, cases[0]):
            return 4
    summary = run(door, cases, writer, chains, log=say, together=args.together)
    say(f"done: ran {summary['run']} chains, kept {summary['kept']}, failed {len(summary['failed'])}")
    for case, chain, why in summary["failed"]:
        say(f"  failed chain {case}/{chain}: {why}")
    return 0


def cmd_repeat(args) -> int:
    opened = open_arm(args)
    if isinstance(opened, int):
        return opened
    door, record, writer = opened
    cases = load_cases(Path(args.cases))
    if not warm(door, cases[0]):
        return 4
    summary = run_repeat(door, record, cases, ResultWriter(Path(args.stale_from)), writer, log=say)
    say(f"done: ran {summary['run']} of the repeat test, kept {summary['kept']}")
    return 0


def cmd_score(args) -> int:
    out = Path(args.out)
    results = ResultWriter(out).read_all()
    scored = score.summary(results)
    calls_db = out / "calls.db"
    if calls_db.exists():
        # Only the calls a result names: not the first call of an arm, nor
        # the calls of a chain that was cut short and run again.
        named = {p[job]["call_id"] for r in results.values() for p in r["passes"] for job in ("alarm", "assessment")}
        rows = [row for row in ModelCalls(open_database(calls_db)).rows() if row["id"] in named]
        scored["calls"] = score.call_times(rows)
    (out / "scores.json").write_text(json.dumps(scored, indent=1, ensure_ascii=False), encoding="utf-8")
    text = score.as_markdown(scored)
    (out / "scores.md").write_text(text, encoding="utf-8")
    print(text)
    return 0 if scored["hard_met"] else 1


def cmd_wordcheck(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cases = load_cases(Path(args.cases))
    door = Door(OllamaEngine(args.engine), ModelCalls(open_database(out / "wordcheck-unused.db")))
    records = [r for path in args.v1_calls for r in wordcheck.load_records(Path(path))]
    if args.workload:
        records = [r for r in records if r["workload"] in args.workload]
    found = wordcheck.check(records, cases, door)
    (out / "wordcheck.json").write_text(json.dumps(found, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"word check: {found['matched']} of {found['total']} calls rebuilt exactly; "
          f"{found['by_workload_and_job']}; mismatches {len(found['mismatches'])}")
    for m in found["mismatches"][:20]:
        print(f"  MISMATCH {m}")
    return 0 if found["matched"] == found["total"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="openconsult-bench")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, fn in (("run", cmd_run), ("repeat", cmd_repeat), ("score", cmd_score),
                     ("wordcheck", cmd_wordcheck)):
        p = sub.add_parser(name)
        p.set_defaults(fn=fn)
        p.add_argument("--out", required=True, help="the bench's own folder, outside the repo and the app's data")
        if name != "score":
            p.add_argument("--cases", required=True, help="the folder holding the case list and the cases")
            p.add_argument("--engine", default=DEFAULT_ADDRESS, help="the engine's address")
    for name in ("run", "repeat"):
        p = sub.choices[name]
        p.add_argument("--kind", choices=sorted(KINDS), default="ollama",
                       help="the kind of engine at that address: ollama, llamacpp or vllm")
        p.add_argument("--model", help="the name the engine knows the model by")
        p.add_argument("--digest", help="refuse to run unless the model has this digest")
    sub.choices["repeat"].add_argument("--stale-from", required=True,
                                       help="a finished run whose chain A1 gives the earlier lists")
    sub.choices["run"].add_argument("--together", action="store_true",
                                    help="send the two calls of a pass at the same moment")
    sub.choices["run"].add_argument("--case", nargs="*", help="only these cases")
    sub.choices["run"].add_argument("--chains", nargs="*", help="only these chains, for a check")
    sub.choices["wordcheck"].add_argument("--v1-calls", nargs="+", required=True, help="v1's recorded calls")
    sub.choices["wordcheck"].add_argument("--workload", nargs="*", help="only these v1 workloads")
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
