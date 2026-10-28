"""The bench command, openconsult-bench (spec 15.7, 15.8, 15.9): run,
repeat, score, figures, export and wordcheck for the language model
bench, and speech-fetch, speech-run and speech-score for the speech
bench. It goes through the same doors as the app. It never writes to the
app's data: its results go to the folder it is given."""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import sys
from pathlib import Path

import openconsult
from openconsult.bench import background, export, figures, letter_marks, letters, score, wordcheck
from openconsult.bench.cases import load_cases
from openconsult.bench.llamacpp import LlamaCppEngine
from openconsult.bench.repeat import run_repeat
from openconsult.bench.replay import CHAINS, arm_differs, first_call, run
from openconsult.bench.shared import commands as shared_commands
from openconsult.bench.speech import commands as speech_commands
from openconsult.bench.speech import commands2 as speech_commands2
from openconsult.bench.speech.arms import ARMS
from openconsult.bench.writer import Refused, ResultWriter
from openconsult.db import open_database
from openconsult.llm.door import Door
from openconsult.llm.ollama import DEFAULT_ADDRESS, OllamaEngine
from openconsult.llm.profile import GEMMA_4_QAT
from openconsult.llm.record import ModelCalls
from openconsult.llm.vllm import VllmEngine
from openconsult.settings import paths

REPO = Path(openconsult.__file__).resolve().parents[1]
# The engines the bench can speak to. The app has Ollama and vLLM (15.8, ruling 30); llama.cpp is the bench's alone.
KINDS = {"ollama": OllamaEngine, "llamacpp": LlamaCppEngine, "vllm": VllmEngine}


def say(line: str) -> None:
    print(f"[{dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}] {line}", flush=True)


def open_arm(args, together: bool = False, with_background: bool = False, differs=None):
    """The door, its record and the writer of an arm; or the code to stop
    with, when the engine or the model is not the one this arm needs.
    The door gets the one profile as this engine knows the model, or with
    the name given. The app's profile is not touched. An arm's seconds
    and memory depend on the room the engine was started with, so a
    server whose context is not exactly the profile's is refused before
    the arm starts; the app's own rule is at least (15.8, 3c)."""
    out = Path(args.out)
    forbidden = [REPO, paths.default_data_folder()] + ([Path(args.data_folder)] if args.data_folder else [])
    try:
        writer = ResultWriter(out, forbidden=forbidden)
    except Refused as refused:
        say(f"STOP: {refused}")
        return 6
    engine = KINDS[args.kind](args.engine)
    profile = GEMMA_4_QAT.for_engine(engine.name) if engine.name in GEMMA_4_QAT.tags else GEMMA_4_QAT
    profile = dataclasses.replace(profile, tag=args.model or profile.tag, engine=engine.name)
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
    context = engine.status(profile.tag).context
    if context is not None and context != profile.context:
        say(f"STOP: the engine runs at a context of {context}, not {profile.context}; an arm is measured at the profile's")
        return 8
    held = writer.read_all()
    first = next(iter(held.values())) if held else None
    # The letters bench (8a) carries its own stamp; the replay's is the default.
    why = (differs(first, door) if differs else arm_differs(first, door, together, with_background)) if held else None
    if why:
        say(f"STOP: {why}")
        return 5
    return door, record, writer


def warm(door: Door, case) -> bool:
    first = first_call(door, case)
    say(f"the first call, not measured: {first.wall_ms} ms")
    if not first.ok:
        say(f"STOP: the first call failed: {first.failure}: {first.detail}")
    return first.ok


def cmd_run(args) -> int:
    opened = open_arm(args, args.together, args.background)
    if isinstance(opened, int):
        return opened
    door, _, writer = opened
    cases = load_cases(Path(args.cases))
    if args.case:
        cases = [c for c in cases if c.name in args.case]
    without = [c.name for c in cases if c.background() is None]
    if args.background and without:
        say(f"STOP: no earlier note for {', '.join(without)}, so the arm with the background block cannot run")
        return 9
    chains = [c for c in CHAINS if not args.chains or c.name in args.chains]
    if any(not writer.exists(case.name, chain.name) for case in cases for chain in chains):
        if not warm(door, cases[0]):
            return 4
    summary = run(door, cases, writer, chains, log=say, together=args.together, background=args.background)
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


def cmd_letters(args) -> int:
    """The letters bench of 8a (15.12 ruling 10): the list call and the
    letter calls on the approved notes, 13 chains a case, through the
    app's own numbering, frames and check."""
    opened = open_arm(args, differs=letters.arm_differs)
    if isinstance(opened, int):
        return opened
    door, _, writer = opened
    cases = load_cases(Path(args.cases))
    if args.case:
        cases = [c for c in cases if c.name in args.case]
    named = dict(item.split("=", 1) for item in args.letter or [])
    try:
        for case in cases:
            letters.specialties_for(case, named)
    except ValueError as refused:
        say(f"STOP: {refused}")
        return 9
    chains = [c for c in CHAINS if not args.chains or c.name in args.chains]
    if any(not writer.exists(case.name, chain.name) for case in cases for chain in chains):
        first = letters.first_call(door, cases[0])
        say(f"the first call, not measured: {first.wall_ms} ms")
        if not first.ok:
            say(f"STOP: the first call failed: {first.failure}: {first.detail}")
            return 4
    summary = letters.run(door, cases, writer, named, chains, log=say)
    say(f"done: ran {summary['run']} chains, kept {summary['kept']}")
    return 0


def cmd_letters_score(args) -> int:
    """The marks of 15.12 ruling 10 from the stored results alone: the
    table to the write folder, never over a file that exists; 0 when
    every mark holds."""
    try:
        marked = letter_marks.score(ResultWriter(Path(args.out)).read_all())
        letter_marks.write(Path(args.write), marked)
    except (Refused, letter_marks.MarksRefused) as refused:
        say(f"STOP: {refused}")
        return 6
    print(letter_marks.as_markdown(marked), end="")
    return 0 if marked["held"] else 1


def cmd_background_score(args) -> int:
    """The marks of 15.11 ruling 6 from the two arms' stored results alone
    (spec 8.6): the table to the write folder, never over a file that
    exists; 0 when every mark holds."""
    try:
        marked = background.score(ResultWriter(Path(getattr(args, "with"))).read_all(),
                                  ResultWriter(Path(args.without)).read_all())
        background.write(Path(args.write), marked)
    except (Refused, background.MarksRefused) as refused:
        say(f"STOP: {refused}")
        return 6
    print(background.as_markdown(marked), end="")
    return 0 if marked["held"] else 1


def cmd_export(args) -> int:
    """The public form: the cases, or one arm (spec 15.8)."""
    public = Path(args.public)
    try:
        ResultWriter(public, forbidden=(REPO, paths.default_data_folder()))   # never straight into the repo
        if args.arm:
            facts = dict(item.split("=", 1) for item in args.fact or [])
            steps = export.steps_of(Path(args.steps), args.arm) if args.steps else None
            files = export.arm_files(args.arm, Path(args.out), Path(args.card) if args.card else None, facts, steps)
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
    records, v1_prompts = [], {}
    for path in args.v1_calls:
        try:
            v1_prompts = wordcheck.v1_prompts_as_recorded(Path(path), Path(args.v1_prompts))
        except ValueError as refused:
            say(f"STOP: {refused}")
            return 1
        records += wordcheck.load_records(Path(path))
    if args.workload:
        records = [r for r in records if r["workload"] in args.workload]
    found = wordcheck.check(records, cases, door, v1_prompts)
    (out / "wordcheck.json").write_text(json.dumps(found, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"word check: {found['matched']} of {found['total']} calls rebuilt exactly; "
          f"{found['by_workload_and_job']}; mismatches {len(found['mismatches'])}")
    for m in found["mismatches"][:20]:
        print(f"  MISMATCH {m}")
    return 0 if found["matched"] == found["total"] else 1


def cmd_speech_fetch(args) -> int:
    return speech_commands.speech_fetch(Path(args.data_folder), say=say)


def cmd_speech_run(args) -> int:
    return speech_commands.speech_run(Path(args.recordings), args.arm, Path(args.data_folder), Path(args.out),
                                      args.recording, say=say,
                                      started_file=Path(args.started_file) if args.started_file else None,
                                      pause_at_stop=Path(args.pause_at_stop) if args.pause_at_stop else None)


def cmd_speech_score(args) -> int:
    return speech_commands.speech_score(Path(args.out), Path(args.recordings), [Path(f) for f in args.scripts],
                                        Path(args.marks), Path(args.write), say=say,
                                        key_facts_path=Path(args.key_facts) if args.key_facts else None,
                                        drug_list_path=Path(args.drug_list) if args.drug_list else None)


def cmd_speech_voice(args) -> int:
    return speech_commands2.speech_voice(Path(args.out), Path(args.recordings), Path(args.data_folder), args.recording,
                                         args.arm, say=say)


def cmd_speech_drugs(args) -> int:
    return speech_commands2.speech_drugs(args.month, getattr(args, "from"), Path(args.out), say=say,
                                         recordings_folder=Path(args.recordings) if args.recordings else None,
                                         data_folder=Path(args.data_folder) if args.data_folder else None)


def cmd_speech_calls(args) -> int:
    return speech_commands2.speech_calls(Path(args.out), Path(args.recordings), [Path(f) for f in args.scripts], args.job,
                                         args.round, Path(args.data_folder) if args.data_folder else None, args.recording,
                                         args.arm, engine_address=args.engine, say=say, engine_kind=args.kind)


def cmd_shared(args) -> int:
    """The commands of the test of 5d (spec 15.9, the details of 5d)."""
    path = lambda value: Path(value) if value else None  # noqa: E731
    if args.command == "shared-install":
        return shared_commands.shared_install(Path(args.data_folder), say=say)
    if args.command == "shared-search":
        return shared_commands.shared_search(Path(args.out), args.embedding, args.where, path(args.data_folder), args.service,
                                             args.every, args.searches, path(args.until), args.load_only, path(args.recordings), say=say,
                                             after=path(args.after), delay_s=args.delay)
    if args.command == "shared-index":
        return shared_commands.shared_index(Path(args.out), args.embedding, args.where, path(args.data_folder), args.service,
                                            path(args.recordings), say=say)
    if args.command == "shared-watch":
        return shared_commands.shared_watch(Path(args.out), Path(args.until), args.service, args.private, args.vllm, args.every,
                                            path(args.data_folder), path(args.recordings), say=say)
    return shared_commands.shared_judge(Path(args.run), path(args.write), path(args.card), path(args.apps), args.ask_wayround,
                                        say=say, data_folder=path(args.data_folder), recordings=path(args.recordings))


def add_shared_commands(sub) -> None:
    """The test of 5d: the three models together on one card."""
    def common(p, out=True):
        p.set_defaults(fn=cmd_shared)
        if out:
            p.add_argument("--out", required=True, help="the setup's folder: not the repo, not a data folder, not where recordings are kept")
        p.add_argument("--data-folder", help="the data folder of the workers, which results may not go under")
        p.add_argument("--recordings", help="the folder of recordings, which results may not go under")
        return p

    p = sub.add_parser("shared-install")
    p.set_defaults(fn=cmd_shared)
    p.add_argument("--data-folder", required=True, help="where the environment and the model of EmbeddingGemma 2 go")
    for name in ("shared-search", "shared-index"):
        p = common(sub.add_parser(name))
        p.add_argument("--embedding", required=True, choices=["first", "second"], help="the first EmbeddingGemma, or version 2")
        p.add_argument("--where", required=True, choices=["card", "processor"], help="where the model runs")
        p.add_argument("--service", default=DEFAULT_ADDRESS, help="the Ollama service's address, for the first model")
    p = sub.choices["shared-search"]
    p.add_argument("--every", type=float, default=5.0, help="seconds between searches")
    p.add_argument("--searches", type=int, help="how many searches, for a base line")
    p.add_argument("--until", help="a file whose appearance ends the searches, in a setup")
    p.add_argument("--load-only", action="store_true", help="one call, so the model is placed; placed.json, not a search")
    p.add_argument("--after", help="the file the speech replay writes when its feed begins: the searches start --delay s after")
    p.add_argument("--delay", type=float, default=15.0, help="seconds after the feed began at which the searches start")
    p = common(sub.add_parser("shared-watch"))
    p.add_argument("--until", required=True, help="a file whose appearance ends the watch, after one last reading")
    p.add_argument("--service", default=DEFAULT_ADDRESS, help="the Ollama service's address")
    p.add_argument("--private", help="the private Ollama's address, for the together way")
    p.add_argument("--vllm", help="vLLM's address, for its two ways")
    p.add_argument("--every", type=float, default=5.0, help="seconds between readings")
    p = common(sub.add_parser("shared-judge"), out=False)
    p.add_argument("--run", required=True, help="the run folder: base-before, setups, base-after, wayround")
    p.add_argument("--write", help="where tables.json and tables.md go; never written over")
    p.add_argument("--card", help="the sampler's file of the card's memory")
    p.add_argument("--apps", help="the sampler's file of the programs on the card")
    p.add_argument("--ask-wayround", action="store_true", help="print the engines whose stored results call for the way round, and stop")


def add_speech_commands(sub) -> None:
    """The speech bench (spec 15.9, the details of 5c)."""
    p = sub.add_parser("speech-calls")
    p.set_defaults(fn=cmd_speech_calls)
    p.add_argument("--out", required=True, help="the results folder of speech-run; the calls' results go under it")
    p.add_argument("--recordings", required=True, help="the folder holding recordings.json")
    p.add_argument("--scripts", action="append", required=True, help="a folder of scripts; may be given more than once")
    p.add_argument("--job", required=True, choices=["label_check", "drug_name", "note", "script_note"], help="the job to run")
    p.add_argument("--round", type=int, help="the round of the notes, 1 or 2")
    p.add_argument("--data-folder", help="the data folder of the workers, which results may not go under")
    p.add_argument("--engine", default=DEFAULT_ADDRESS, help="the engine's address")
    p.add_argument("--kind", choices=sorted(speech_commands2.KINDS), default="ollama",
                   help="the kind of engine at that address: ollama, llamacpp or vllm")
    p.add_argument("--recording", nargs="*", help="only these recordings, by name")
    p.add_argument("--arm", nargs="*", help="only these arms")
    p = sub.add_parser("speech-drugs")
    p.set_defaults(fn=cmd_speech_drugs)
    p.add_argument("--month", required=True, help="the month of the drug file, as YYYYMM")
    p.add_argument("--from", required=True, help="the address of that month's file on the portal")
    p.add_argument("--out", required=True, help="where the file and the list go: not the repo, not a data folder")
    p.add_argument("--recordings", help="the folder holding recordings.json, so that its folders are refused as well")
    p.add_argument("--data-folder", help="the data folder of the workers, which the file and the list may not go under")
    p = sub.add_parser("speech-voice")
    p.set_defaults(fn=cmd_speech_voice)
    p.add_argument("--out", required=True, help="the results folder of speech-run; the voice results go under it")
    p.add_argument("--recordings", required=True, help="the folder holding recordings.json and the recordings")
    p.add_argument("--data-folder", required=True, help="the data folder whose WhisperX environment runs the voice worker")
    p.add_argument("--recording", nargs="*", help="only these recordings, by name")
    p.add_argument("--arm", nargs="*", help="only these arms")
    p = sub.add_parser("speech-fetch")
    p.set_defaults(fn=cmd_speech_fetch)
    p.add_argument("--data-folder", required=True, help="the data folder whose Nemotron environment fetches the tied pair's model")
    p = sub.add_parser("speech-run")
    p.set_defaults(fn=cmd_speech_run)
    p.add_argument("--recordings", required=True, help="the folder holding recordings.json and the recordings")
    p.add_argument("--arm", required=True, choices=list(ARMS), help="the arm to feed")
    p.add_argument("--data-folder", required=True, help="the data folder whose environments run the workers")
    p.add_argument("--out", required=True, help="the results folder: not the repo, not a data folder, not where recordings are kept")
    p.add_argument("--recording", nargs="*", help="only these recordings, by name")
    p.add_argument("--started-file", help="5d: a file written when the feed begins, with the moment")
    p.add_argument("--pause-at-stop", help="5d: a folder where stop.wanted is written before Stop, which then waits for stop.go")
    p = sub.add_parser("speech-score")
    p.set_defaults(fn=cmd_speech_score)
    p.add_argument("--out", required=True, help="the results folder of speech-run")
    p.add_argument("--recordings", required=True, help="the folder holding recordings.json")
    p.add_argument("--scripts", action="append", required=True, help="a folder of scripts; may be given more than once")
    p.add_argument("--marks", required=True, help="the file of drug names, test names and safety nets")
    p.add_argument("--write", required=True, help="where scores.json and report.md go; never written over")
    p.add_argument("--key-facts", help="the key-fact file, needed when the results of part two are there")
    p.add_argument("--drug-list", help="the drug list, needed when the results of part two are there")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="openconsult-bench")
    sub = parser.add_subparsers(dest="command", required=True)
    add_speech_commands(sub)
    add_shared_commands(sub)

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
        p.add_argument("--data-folder", help="an app data folder results may not go under, beside the real one")
        p.add_argument("--model", help="the name the engine knows the model by")
        p.add_argument("--digest", help="refuse to run unless the model has this digest")
    p = sub.choices["run"]
    p.add_argument("--case", nargs="*", help="only these cases")
    p.add_argument("--chains", nargs="*", help="only these chains, for a check")
    p.add_argument("--together", action="store_true", help="send the two calls of a pass at the same moment")
    p.add_argument("--background", action="store_true",
                   help="7b: every pass takes the case's earlier note as the background block, placed as the app places it")
    sub.choices["repeat"].add_argument("--stale-from", required=True,
                                       help="a finished run whose chain A1 gives the earlier lists")
    p = sub.choices["wordcheck"]
    p.add_argument("--v1-calls", nargs="+", required=True, help="v1's recorded calls")
    p.add_argument("--v1-prompts", required=True,
                   help="the folder holding v1's two prompt files, proven against the arm-start records of the calls")
    p.add_argument("--workload", nargs="*", help="only these v1 workloads")
    p = command("score", cmd_score, out=False)
    p.add_argument("--replies", help="score a published replies file")
    p = command("letters", cmd_letters)
    p.add_argument("--cases", required=True, help="the folder holding the case list and the approved notes")
    p.add_argument("--engine", default=DEFAULT_ADDRESS, help="the engine's address")
    p.add_argument("--kind", choices=sorted(KINDS), default="ollama", help="the kind of engine at that address")
    p.add_argument("--data-folder", help="an app data folder results may not go under, beside the real one")
    p.add_argument("--model", help="the name the engine knows the model by")
    p.add_argument("--digest", help="refuse to run unless the model has this digest")
    p.add_argument("--case", nargs="*", help="only these cases")
    p.add_argument("--chains", nargs="*", help="only these chains, for a check")
    p.add_argument("--letter", action="append", help="CASE=SPECIALTY, the specialty a case that states no referral drafts to")
    p = command("letters-score", cmd_letters_score)
    p.add_argument("--write", required=True, help="where marks.json and marks.md go; never written over")
    p = sub.add_parser("background-score")
    p.set_defaults(fn=cmd_background_score)
    p.add_argument("--with", required=True, help="the result folder of the arm with the background block")
    p.add_argument("--without", required=True, help="the result folder of the arm without it")
    p.add_argument("--write", required=True, help="where marks.json and marks.md go; never written over")
    p = command("figures", cmd_figures, out=False)
    p.add_argument("--public", help="the public folder: its rounds.json and the replies of its arms")
    p.add_argument("--rounds", help="the rounds file, when the arms are private result folders")
    p.add_argument("--arm", action="append", help="NAME=FOLDER, a private result folder for each arm the rounds file names")
    p = command("export", cmd_export, out=False)
    p.add_argument("--public", required=True, help="the public folder to write")
    p.add_argument("--cases", help="the private folder of cases, to publish the cases")
    p.add_argument("--arm", help="the public name of the arm in --out, to publish an arm")
    p.add_argument("--card", help="the sampler's file")
    p.add_argument("--steps", help="the steps file: the card is taken over the arm's own steps")
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
