"""The guideline commands of openconsult-bench (spec 15.12, rulings 9, 10,
18 and 19): guideline-load, guideline and guideline-score, in their own
module beside the bench's command line, which hands them its common
pieces (the arm opener, the writer, the engines). No model's words
asserted; results never written over."""

from __future__ import annotations

import json
from pathlib import Path

from openconsult.bench import guideline, guideline_load, guideline_marks
from openconsult.bench.replay import CHAINS
from openconsult.bench.writer import Refused, ResultWriter
from openconsult.consult.messages import Patient
from openconsult.db import open_database
from openconsult.guidelines.embedder import make_embedder
from openconsult.guidelines.search import Index
from openconsult.guidelines.sources import Sources
from openconsult.settings import paths


def _say():
    from openconsult.bench.cli import say
    return say


def _open_arm(args, differs):
    from openconsult.bench.cli import open_arm
    return open_arm(args, differs=differs)


def cmd_guideline(args) -> int:
    """The guideline bench of 8b (15.12 rulings 9, 10 and 19): the approved queries through the app's own
    search, frame and call, 13 chains a query, once without the reranker and once with it."""
    say = _say()
    try:
        queries = guideline.read_queries(Path(args.queries), args.queries_sha256)
    except (guideline.QueriesChanged, OSError, KeyError, ValueError) as refused:
        say(f"STOP: {refused}")
        return 3
    if args.query:
        queries = [q for q in queries if q["id"] in args.query]
    try:
        ResultWriter(Path(args.out), forbidden=[guideline_load.REPO, paths.default_data_folder(), Path(args.data_folder)])
    except Refused as refused:
        say(f"STOP: {refused}")
        return 6
    embedder = make_embedder(Path(args.data_folder), args.where, reranker=args.reranker, reranker_where=args.reranker_where or args.where)
    try:
        not_ready = embedder.ready()
        if not_ready:
            say(f"STOP: {not_ready}")
            return 7
        say(f"the embedding worker: {json.dumps(embedder.info(), sort_keys=True)}")
        opened = _open_arm(args, lambda held, door: guideline.arm_differs(held, door, embedder, args.reranker, args.queries_sha256))
        if isinstance(opened, int):
            return opened
        door, _, writer = opened
        corpus = open_database(Path(args.data_folder) / "openconsult.db")
        index = Index(Sources(corpus, None))
        say(f"the corpus: {len(index.rows)} passages, models {sorted(index.models)}")
        patient = Patient(args.age, args.sex)
        chains = [c for c in CHAINS if not args.chains or c.name in args.chains]
        if not args.search_only and any(not writer.exists(q["id"], c.name) for q in queries for c in chains):
            first = guideline.first_call(door, guideline.run_search(index, embedder, queries[0], args.reranker), patient, queries[0]["query"])
            say(f"the first call, not measured: {first.wall_ms} ms" if first else "the first query is below the floor: no first call")
            if first is not None and not first.ok:
                say(f"STOP: the first call failed: {first.failure}: {first.detail}")
                return 4
        summary = guideline.run(door, index, embedder, queries, writer, patient, args.reranker, chains, args.search_only,
                                args.queries_sha256, log=say)
        say(f"done: ran {summary['run']}, kept {summary['kept']}")
        return 0
    finally:
        embedder.close()


def cmd_guideline_score(args) -> int:
    """With --data-folder and --queries, the right passages are matched again from the corpus by the rule as it stands."""
    say = _say()
    try:
        without = ResultWriter(Path(args.without)).read_all()
        with_ = ResultWriter(Path(getattr(args, "with"))).read_all() if getattr(args, "with") else None
        if args.data_folder:
            rows = Index(Sources(open_database(Path(args.data_folder) / "openconsult.db"), None)).rows
            queries = guideline.read_queries(Path(args.queries), None)
            without = guideline_marks.rematch(without, rows, queries)
            with_ = guideline_marks.rematch(with_, rows, queries) if with_ else None
        marked = guideline_marks.score(without, with_)
        guideline_marks.write(Path(args.write), marked)
    except (Refused, guideline_marks.MarksRefused) as refused:
        say(f"STOP: {refused}")
        return 6
    print(guideline_marks.as_markdown(marked), end="")
    return 0 if marked["held"] else 1


def cmd_guideline_load(args) -> int:
    """The loader command of 8b (15.12 ruling 18): a folder of documents into a bench data folder's corpus."""
    say = _say()
    return guideline_load.guideline_load(Path(args.folder), args.publisher, Path(args.data_folder), args.statement_accepted,
                                         args.where, say=say, into_my_data_folder=args.into_my_data_folder)




def add_guideline_commands(sub, command) -> None:
    """The three parsers; command(name, fn) is the bench's own helper for a command with --out."""
    from openconsult.bench.cli import DEFAULT_ADDRESS, KINDS
    p = command("guideline", cmd_guideline)
    p.add_argument("--queries", required=True, help="the approved queries file")
    p.add_argument("--queries-sha256", help="refuse to run unless the queries file has this sha256")
    p.add_argument("--data-folder", required=True, help="the bench data folder holding the corpus and the worker; results may not go under it")
    p.add_argument("--engine", default=DEFAULT_ADDRESS, help="the engine's address")
    p.add_argument("--kind", choices=sorted(KINDS), default="ollama", help="the kind of engine at that address")
    p.add_argument("--model", help="the name the engine knows the model by")
    p.add_argument("--digest", help="refuse to run unless the model has this digest")
    p.add_argument("--age", type=int, required=True, help="the patient line's age, the same for every query")
    p.add_argument("--sex", choices=["F", "M"], required=True, help="the patient line's sex")
    p.add_argument("--where", choices=["card", "processor"], default="card", help="where the embedding worker runs")
    p.add_argument("--reranker", action="store_true", help="the arm with the reranker")
    p.add_argument("--reranker-where", choices=["card", "processor"], help="where the reranker runs; the worker's place if not given")
    p.add_argument("--search-only", action="store_true", help="the searches alone, no summary call: a timing pass")
    p.add_argument("--query", nargs="*", help="only these queries, by id")
    p.add_argument("--chains", nargs="*", help="only these chains, for a check")
    p = sub.add_parser("guideline-score")
    p.set_defaults(fn=cmd_guideline_score)
    p.add_argument("--without", required=True, help="the result folder of the arm without the reranker")
    p.add_argument("--with", help="the result folder of the arm with the reranker")
    p.add_argument("--write", required=True, help="where marks.json and marks.md go; never written over")
    p.add_argument("--data-folder", help="the corpus's data folder: the right passages matched again from it by the rule as it stands")
    p.add_argument("--queries", help="the queries file, with --data-folder")
    p = sub.add_parser("guideline-load")
    p.set_defaults(fn=cmd_guideline_load)
    p.add_argument("--folder", required=True, help="the folder of documents, every file loaded")
    p.add_argument("--publisher", required=True, help="the publisher's name, given here and never written into the repository")
    p.add_argument("--data-folder", required=True, help="the data folder whose corpus is loaded: a bench folder, or your own with the flag below")
    p.add_argument("--into-my-data-folder", action="store_true",
                   help="accept your own data folder, named by its path, with OpenConsult closed; the repository is never accepted")
    p.add_argument("--statement-accepted", action="store_true", help="the statement of the Guidelines section, given as the owner's")
    p.add_argument("--where", choices=["card", "processor"], default="card", help="where the embedding worker runs")
