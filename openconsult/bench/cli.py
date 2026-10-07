"""The bench command, openconsult-bench (spec 15.7, 15.8): run, repeat,
score, figures, export and wordcheck. It goes through the same door as the app and can be pointed
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
from openconsult.bench import export, figures, score, wordcheck
from openconsult.bench.cases import load_cases
from openconsult.bench.llamacpp import LlamaCppEngine
from openconsult.bench.repeat import run_repeat
from openconsult.bench.replay import CHAINS, arm_differs, first_call, run
from openconsult.bench.vllm import VllmEngine
from openconsult.bench.writer import Refused, ResultWriter
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
    if args.replies:
        # From what is published alone: no engine, no private file, nothing written.
        scored = score.summary(export.results_from_replies(export.read_replies(Path(args.replies))))
        print(score.as_markdown(scored))
        return 0 if scored["hard_met"] else 1
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


def cmd_export(args) -> int:
    """The public form: the cases, or one arm (spec 15.8)."""
    public = Path(args.public)
    try:
        ResultWriter(public, forbidden=(REPO, paths.default_data_folder()))   # never straight into the repo
        if args.arm:
            facts = dict(item.split("=", 1) for item in args.fact or [])
            files = export.arm_files(args.arm, Path(args.out), Path(args.card) if args.card else None, facts)
            what = f"{args.arm}: {json.loads(files[f'arms/{args.arm}/arm.json'])['calls']} replies"
        else:
            files = export.case_files(Path(args.cases))
            what = f"the cases: {len(files) - 1} files and their list"
        total = export.publish(public, files)
    except Refused as refused:
        say(f"STOP: {refused}")
        return 6
    say(f"exported {what}, {sum(len(d) for d in files.values())} bytes; the public folder is now {total} bytes")
    return 0


def cmd_figures(args) -> int:
    """The figures of the public report, by the rules of 7 Oct (spec 15.8,
    ruling 26): from the public folder alone, or from the private result
    folders with the same rounds file. Prints them; writes only with --out,
    and never over a file that exists."""
    try:
        if args.public:
            rounds = figures.read_rounds(Path(args.public) / "rounds.json")
            arms = figures.public_arms(Path(args.public), rounds)
        else:
            rounds = figures.read_rounds(Path(args.rounds))
            arms = {name: figures.private_arm(Path(folder)) for name, folder in (item.split("=", 1) for item in args.arm)}
        found = figures.figures(rounds, arms)
        if args.out:
            figures.write(Path(args.out), found)
    except (figures.FiguresRefused, Refused) as refused:
        say(f"STOP: {refused}")
        return 7
    print(figures.as_markdown(found), end="")
    return 0


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

    def command(name: str, fn, out: bool = True):
        p = sub.add_parser(name)
        p.set_defaults(fn=fn)
        p.add_argument("--out", required=out, help="the bench's own folder, outside the repo and the app's data")
        return p

    for name, fn in (("run", cmd_run), ("repeat", cmd_repeat), ("wordcheck", cmd_wordcheck)):
        p = command(name, fn)
        p.add_argument("--cases", required=True, help="the folder holding the case list and the cases")
        p.add_argument("--engine", default=DEFAULT_ADDRESS, help="the engine's address")
    for name in ("run", "repeat"):
        p = sub.choices[name]
        p.add_argument("--kind", choices=sorted(KINDS), default="ollama",
                       help="the kind of engine at that address: ollama, llamacpp or vllm")
        p.add_argument("--model", help="the name the engine knows the model by")
        p.add_argument("--digest", help="refuse to run unless the model has this digest")
    p = sub.choices["run"]
    p.add_argument("--case", nargs="*", help="only these cases")
    p.add_argument("--chains", nargs="*", help="only these chains, for a check")
    p.add_argument("--together", action="store_true", help="send the two calls of a pass at the same moment")
    sub.choices["repeat"].add_argument("--stale-from", required=True,
                                       help="a finished run whose chain A1 gives the earlier lists")
    p = sub.choices["wordcheck"]
    p.add_argument("--v1-calls", nargs="+", required=True, help="v1's recorded calls")
    p.add_argument("--workload", nargs="*", help="only these v1 workloads")
    p = command("score", cmd_score, out=False)
    p.add_argument("--replies", help="score a published replies file")
    p = command("figures", cmd_figures, out=False)
    p.add_argument("--public", help="the public folder: its rounds.json and the replies of its arms")
    p.add_argument("--rounds", help="the rounds file, when the arms are private result folders")
    p.add_argument("--arm", action="append", help="NAME=FOLDER, a private result folder for each arm the rounds file names")
    p = command("export", cmd_export, out=False)
    p.add_argument("--public", required=True, help="the public folder to write")
    p.add_argument("--cases", help="the private folder of cases, to publish the cases")
    p.add_argument("--arm", help="the public name of the arm in --out, to publish an arm")
    p.add_argument("--card", help="the sampler's file")
    p.add_argument("--fact", action="append", help="KEY=VALUE, a measured fact to keep with the arm")
    args = parser.parse_args(argv)
    if args.command == "score" and not (args.out or args.replies):
        parser.error("score needs --out or --replies")
    if args.command == "figures" and bool(args.public) == bool(args.rounds and args.arm):
        parser.error("figures needs --public, or --rounds with --arm")
    if args.command == "export" and bool(args.arm) == bool(args.cases):
        parser.error("export needs --cases, or --arm with --out")
    if args.command == "export" and args.arm and not args.out:
        parser.error("export --arm needs --out")
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
