"""The teaching commands of openconsult-bench (spec 15.14, rulings 7 and
14, the details of run 10a): teaching and teaching-score, in their own
module beside the bench's command line, which hands them its common
pieces (the arm opener, the engines). The material is read and never
changed; results go under --out or --write and never over a file."""

from __future__ import annotations

from pathlib import Path

from openconsult.bench import teaching, teaching_marks
from openconsult.bench.writer import Refused


def cmd_teaching(args) -> int:
    """The bench of teaching for one arm. With --trial, the four calls of the trial alone, judged by the door's
    own check; without it, every call that has no file yet, and only in a folder whose trial held."""
    from openconsult.bench.cli import CLOUD, open_arm, say, stopped
    if not teaching.ARM_NAME.fullmatch(args.arm):
        say(f"STOP: the arm's name goes into every file's name: small letters, figures and hyphens, not {args.arm!r}")
        return 9
    try:
        material = teaching.read_material(Path(args.material))
    except (teaching.MaterialRefused, OSError, ValueError, KeyError) as refused:
        say(f"STOP: the material cannot be read: {refused}")
        return 3
    opened = open_arm(args, differs=lambda held, door: teaching.arm_differs(held, door, args.arm))
    if isinstance(opened, int):
        return opened
    door, record, writer = opened
    why = [] if args.trial else teaching.trial_holds(writer)
    if why:
        say("STOP: the trial has not held in this folder, so nothing is sent: " + "; ".join(why))
        return 4
    parts = tuple(part for part in teaching.PARTS if not args.part or part in args.part)
    summary = teaching.run(door, record, writer, material, args.arm, parts, args.rounds, args.case, args.trial,
                           args.max_dollars if args.kind in CLOUD else None, log=say)
    say(f"done: sent {summary['run']} calls, kept {summary['kept']}, failed {summary['failed']}"
        + (f"; {summary['dollars']:.3f} US dollars at {teaching.PRICE_READ} and {teaching.PRICE_WRITTEN} a million tokens "
           f"(the prices of {teaching.PRICES_OF})" if args.kind in CLOUD else ""))
    code = stopped(summary)
    why = teaching.trial_holds(writer) if args.trial and not code else []
    if why:
        say("STOP: the trial did not hold: " + "; ".join(why))
        return 4
    return code


def cmd_teaching_score(args) -> int:
    """The counts and the hard marks that code can count, the times and the proof of the words, from the stored
    files alone: marks.json and marks.md under --write. 0 when no counted hard mark is crossed and the words hold."""
    from openconsult.bench.cli import say
    try:
        arms = {name: teaching_marks.read_arm(Path(folder)) for name, folder in (item.split("=", 1) for item in args.arm)}
        marked = teaching_marks.score(arms, teaching.read_material(Path(args.material)))
        teaching_marks.write(Path(args.write), marked)
    except (Refused, teaching_marks.MarksRefused, teaching.MaterialRefused, OSError, ValueError, KeyError) as refused:
        say(f"STOP: {refused}")
        return 6
    crossed = {arm: {mark: len(files) for mark, files in found.items()} for arm, found in marked["hard_marks_code_can_count"].items()}
    say(f"written {Path(args.write) / 'marks.md'}; hard marks code can count, crossed: {crossed}; the words hold: {marked['words']['held']}")
    return 0 if marked["held"] and marked["words"]["held"] else 1


def add_teaching_commands(sub, command) -> None:
    """The two parsers; command(name, fn) is the bench's own helper for a command with --out."""
    from openconsult.bench.cli import DEFAULT_ADDRESS, KINDS
    p = command("teaching", cmd_teaching)
    p.add_argument("--material", required=True, help="the folder of the bench material: case_*.json and writer_runs.json; read, never changed")
    p.add_argument("--arm", required=True, help="the arm's name, which goes into every stored file's name: gemma-vllm, claude-haiku")
    p.add_argument("--part", action="append", choices=teaching.PARTS, help="only this part; may be given more than once; all four when not given")
    p.add_argument("--rounds", type=int, default=2, help="the rounds of the actor, the examination and the feedback; the writer runs once")
    p.add_argument("--case", nargs="*", help="only these cases, by id")
    p.add_argument("--trial", action="store_true", help="the four calls of the trial alone, one of each job, judged by the door's own check")
    p.add_argument("--engine", default=DEFAULT_ADDRESS, help="the engine's address")
    p.add_argument("--kind", choices=sorted(KINDS), default="ollama", help="the kind of engine at that address")
    p.add_argument("--data-folder", help="an app data folder results may not go under, beside the real one")
    p.add_argument("--key-folder", help="the claude kind: the folder whose .env holds the service's key, read inside the process; "
                                        "results may not go under it")
    p.add_argument("--model", help="the name the engine knows the model by")
    p.add_argument("--digest", help="refuse to run unless the model has this digest")
    p.add_argument("--max-dollars", type=float, default=3.0, help="a cloud kind: the arm stops when its cost passes this, at the prices the bench names")
    p = sub.add_parser("teaching-score")
    p.set_defaults(fn=cmd_teaching_score)
    p.add_argument("--arm", action="append", required=True, help="NAME=FOLDER, the --out folder of an arm; may be given more than once")
    p.add_argument("--material", required=True, help="the folder of the bench material, for what each line expects")
    p.add_argument("--write", required=True, help="where marks.json and marks.md go; never written over")
