"""The guideline bench (spec 15.12, rulings 9, 10 and 19; the detail The
bench): each approved query through the app's own loader, index, search,
frame and call, once without the reranker and once with it; one search a
query an arm, then 13 chains of the summary call on the passages it sent;
the right passage found by the query's file and heading against the
stored sources and trails, its rank kept. Results go to the writer's
folder, never over an existing one; no query, passage or reply text
enters the repo. A query the floor refuses writes its 13 chains as the
one refusal, with no call."""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from openconsult.bench.replay import CHAINS, Chain
from openconsult.bench.writer import ResultWriter
from openconsult.consult.messages import Patient
from openconsult.guidelines import summary as summary_module
from openconsult.guidelines.search import GUIDELINE_FLOOR, Index, search
from openconsult.guidelines.texts import TRAIL_JOINT
from openconsult.llm.door import Door, Result
from openconsult.llm.profile import Sampling
from openconsult.prompts import loader

KIND = "guideline"
FILES = ("guideline",)
FIXED = ("guideline.frame", "guideline.passage")
SEARCH = "search"             # the chain name of a query's one search


class QueriesChanged(Exception):
    """The queries file's sha256 is not the one the command was given."""


def read_queries(path: Path, expected_sha256: str | None) -> list[dict]:
    data = Path(path).read_bytes()
    found = hashlib.sha256(data).hexdigest()
    if expected_sha256 and found != expected_sha256:
        raise QueriesChanged(f"the queries file has sha256 {found}, not {expected_sha256}")
    queries = json.loads(data.decode("utf-8"))["queries"]
    return [{"id": q["id"], "file": q.get("file") or None, "heading": q.get("heading") or None, "query": q["query"]} for q in queries]


def stamp(door: Door, embedder, reranker: bool, queries_sha256: str | None) -> dict:
    version, digest = door.identity()
    prompts = {name: hashlib.sha256(loader.prompt_bytes(name)).hexdigest() for name in FILES}
    prompts.update({name: hashlib.sha256(loader.file_bytes(name)).hexdigest() for name in FIXED})
    prompts["guideline.form"] = hashlib.sha256(loader.form_bytes("guideline")).hexdigest()
    return {"kind": KIND, "engine": door.profile.engine, "engine_version": version, "model_tag": door.profile.tag,
            "model_digest": digest, "prompts": prompts, "embedding_model": embedder.model_id, "reranker": bool(reranker),
            "worker": embedder.info(), "queries_sha256": queries_sha256, "floor": GUIDELINE_FLOOR}


def arm_differs(held: dict, door: Door, embedder=None, reranker: bool = False, queries_sha256: str | None = None) -> str | None:
    """Why a folder's results cannot be carried on: another engine, model,
    prompt words, embedding model, reranker arm or queries file."""
    now = stamp(door, embedder, reranker, queries_sha256) if embedder is not None else {k: held.get(k) for k in ("kind",)}
    now.pop("worker", None)
    then = {key: held.get(key) for key in now}
    if then == now:
        return None
    return f"this folder holds results from {then}; the arm now is {now}"


SECTION_NUMBER = re.compile(r"^\s*\d+(\.\d+)*\.?(\s+|$)")


def unnumbered(heading: str) -> str:
    """A heading without its section number, lower case (ruling 19: the number is left out of the query)."""
    return SECTION_NUMBER.sub("", heading or "").strip().lower()


def under_heading(trail: str, heading: str) -> bool:
    """Whether a passage's trail passes through the heading: any of its
    headings, its section number left out, equals the query's heading, so
    a passage under a subsection of that heading is under it too."""
    wanted = unnumbered(heading)
    return bool(wanted) and any(unnumbered(part) == wanted for part in trail.split(TRAIL_JOINT))


def right_passages(index: Index, query: dict) -> list[int]:
    """The ids of the passages under the query's heading in its file (ruling 19)."""
    if not query["file"] or not query["heading"]:
        return []
    return [row["id"] for row in index.rows if row["file_name"] == query["file"] and under_heading(row["trail"], query["heading"])]


def rank_of(ids: list[int], hits) -> int | None:
    """The best rank, from 1, of any of the ids among the hits (Hit objects or sent dicts)."""
    for position, hit in enumerate(hits, 1):
        passage_id = hit["passage_id"] if isinstance(hit, dict) else hit.passage_id
        if passage_id in ids:
            return position
    return None


def run_search(index: Index, embedder, query: dict, reranker: bool) -> dict:
    found = search(index, embedder, [query["query"]], reranker=reranker)
    right = right_passages(index, query)
    return {"query_id": query["id"], "real": bool(query["file"]), "right_passages": right, "right_count": len(right),
            "failure": found.failure, "below_floor": found.below_floor, "top_similarity": found.top_similarity,
            "candidates": len(found.candidates), "sent": found.sent, "search_ms": found.search_ms,
            "reranker_ran": found.reranker_ran, "rerank_failure": found.rerank_failure,
            "rank_merged": rank_of(right, found.candidates), "rank_sent": rank_of(right, found.sent),
            "candidate_ranks": [{"passage_id": h.passage_id, "source_id": h.source_id, "similarity": h.similarity, "rerank_score": h.rerank_score}
                                for h in found.candidates], "floor": found.floor}


def _call_row(result: Result) -> dict:
    return {"call_id": result.call_id, "wall_ms": result.wall_ms, "prompt_tokens": result.prompt_tokens, "output_tokens": result.output_tokens}


def run_chain(door: Door, searched: dict, chain: Chain, patient: Patient, query_text: str) -> dict:
    """One chain: the summary call on the search's passages, judged by code; or the floor's refusal with no call."""
    if searched["below_floor"] or searched["failure"]:
        return {"outcome": "below_floor" if searched["below_floor"] else "failed", "covered": None, "summary": None, "cited": [],
                "invalid": 0, "words": 0, "failure": searched["failure"], "call": None, "no_call": True}
    outcome = summary_module.summarise(door, query_text, searched["sent"], patient, Sampling(chain.temperature, chain.seed))
    return {"outcome": outcome.outcome, "covered": outcome.covered, "summary": outcome.summary, "cited": outcome.cited,
            "invalid": outcome.invalid, "words": len((outcome.summary or "").split()) if outcome.outcome == "covered" else 0,
            "failure": outcome.failure, "call": {"call_id": outcome.call_id, "wall_ms": outcome.wall_ms}, "no_call": False}


def first_call(door: Door, searched: dict, patient: Patient, query_text: str) -> Result | None:
    """The one unmeasured call of the arm, on the first query's passages, when the floor let any through."""
    if searched["below_floor"] or searched["failure"]:
        return None
    return door.ask("guideline", summary_module.message(query_text, searched["sent"], patient), Sampling(0.0, 42))


def run(door: Door, index: Index, embedder, queries: list[dict], writer: ResultWriter, patient: Patient, reranker: bool = False,
        chains: list[Chain] = CHAINS, search_only: bool = False, queries_sha256: str | None = None, log: Callable = print) -> dict:
    """Every query's search (once) and every chain that has no result yet."""
    done, skipped = 0, 0
    stamped = stamp(door, embedder, reranker, queries_sha256)
    for query in queries:
        qid = query["id"]
        if writer.exists(qid, SEARCH):
            searched = writer.read(qid, SEARCH)
            skipped += 1
        else:
            started = time.perf_counter()
            searched = run_search(index, embedder, query, reranker)
            writer.write(qid, SEARCH, {**searched, "wall_s": round(time.perf_counter() - started, 3), **stamped})
            done += 1
            log(f"  {qid}: search {searched['search_ms']} ms, top similarity {searched['top_similarity']}, {len(searched['sent'])} sent, "
                f"right passage rank {searched['rank_merged']} (merged) {searched['rank_sent']} (sent)"
                + (f" FAILED {searched['failure']}" if searched["failure"] else "") + (" BELOW THE FLOOR" if searched["below_floor"] else ""))
        if search_only:
            continue
        for chain in chains:
            if writer.exists(qid, chain.name):
                skipped += 1
                continue
            started = time.perf_counter()
            result = run_chain(door, searched, chain, patient, query["query"])
            writer.write(qid, chain.name, {"query_id": qid, "real": searched["real"], "chain": chain.name, "temperature": chain.temperature,
                                           "seed": chain.seed, "patient": asdict(patient), "sent_count": len(searched["sent"]),
                                           "wall_s": round(time.perf_counter() - started, 3), **result, **stamped})
            done += 1
            log(f"  {qid} {chain.name}: {result['outcome']}, {result['words']} words, cited {result['cited']}, invalid {result['invalid']}"
                + (f", {result['call']['wall_ms']} ms" if result["call"] else ", no call") + (f" FAILED {result['failure']}" if result["failure"] else ""))
    return {"run": done, "kept": skipped}
