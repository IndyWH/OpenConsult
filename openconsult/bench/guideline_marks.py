"""The marks of the guideline bench (spec 15.12, rulings 9 and 10), read
from the stored results alone, fixed as numbers before the run
(STAGE8B_PLAN, 28 Oct 2026, item 6): G1 to G3 on each arm, R1 to R3
between the arm without the reranker and the arm with it. What a model
said is counted here, never asserted in a test."""

from __future__ import annotations

import json
import statistics
from pathlib import Path

CHAINS = 13
WORDS_LIMIT = 150            # G2: under 150 words
TOP_THREE = 3                # R2
SECOND = 1000                # R3: under one second, in milliseconds
REFUSALS = ("below_floor", "not_covered", "no_citation")


class MarksRefused(Exception):
    pass


def rematch(results: dict, rows: list[dict], queries: list[dict]) -> dict:
    """The right passages and their ranks found again from the stored
    candidate order and the corpus's rows, by the rule as it now stands
    (the first scoring of 28 Oct matched the trail's last heading alone
    and missed a numbered section's subsections). Nothing stored changes."""
    from openconsult.bench.guideline import under_heading
    by_id = {q["id"]: q for q in queries}
    found = {}
    for key, data in results.items():
        qid, chain = key
        if chain != "search":
            found[key] = data
            continue
        query = by_id.get(qid, {})
        right = [r["id"] for r in rows if query.get("file") and r["file_name"] == query["file"] and under_heading(r["trail"], query.get("heading") or "")]
        merged = [c["passage_id"] for c in data.get("candidate_ranks") or []]
        sent = [p["passage_id"] for p in data.get("sent") or []]
        rank = lambda ids: next((i for i, pid in enumerate(ids, 1) if pid in right), None)  # noqa: E731
        found[key] = {**data, "right_passages": right, "right_count": len(right), "rank_merged": rank(merged), "rank_sent": rank(sent), "rematched": True}
    return found


def by_query(results: dict) -> dict:
    """{query id: {"search": ..., "chains": [...]}} from a result folder's files."""
    found: dict = {}
    for (qid, chain), data in sorted(results.items()):
        entry = found.setdefault(qid, {"search": None, "chains": []})
        if chain == "search":
            entry["search"] = data
        else:
            entry["chains"].append(data)
    return found


def cites_only_given(chain: dict) -> bool:
    return chain["outcome"] != "failed" and chain["invalid"] == 0


def under_limit(chain: dict) -> bool:
    return chain["outcome"] != "failed" and chain["words"] < WORDS_LIMIT


def refused(chain: dict) -> bool:
    return chain["outcome"] in REFUSALS


def query_table(entry: dict) -> dict:
    chains, searched = entry["chains"], entry["search"] or {}
    walls = [c["call"]["wall_ms"] for c in chains if c.get("call")]
    return {"real": bool(searched.get("real")), "chains": len(chains), "failed": sum(c["outcome"] == "failed" for c in chains),
            "covered": sum(c["outcome"] == "covered" for c in chains), "cites_only_given": sum(cites_only_given(c) for c in chains),
            "under_150": sum(under_limit(c) for c in chains), "refused": sum(refused(c) for c in chains),
            "no_call": sum(1 for c in chains if c.get("no_call")),
            "top_similarity": searched.get("top_similarity"), "below_floor": bool(searched.get("below_floor")),
            "sent": len(searched.get("sent") or []), "candidates": searched.get("candidates"),
            "rank_merged": searched.get("rank_merged"), "rank_sent": searched.get("rank_sent"), "right_count": searched.get("right_count"),
            "search_ms": searched.get("search_ms"), "reranker_ran": bool(searched.get("reranker_ran")),
            "call_s": round(statistics.median(walls) / 1000, 2) if walls else None,
            "longest_s": round(max(walls) / 1000, 2) if walls else None,
            "words_max": max((c["words"] for c in chains), default=0)}


def arm_marks(arm: str, tables: dict) -> list[dict]:
    marks = []
    for qid, t in tables.items():
        full = t["chains"] == CHAINS
        if t["real"]:
            marks.append({"mark": "G1", "arm": arm, "query": qid, "text": f"cites only passage numbers it was given, {CHAINS} of {CHAINS}",
                          "figure": f"{t['cites_only_given']} of {t['chains']}", "held": full and t["cites_only_given"] == CHAINS})
            marks.append({"mark": "G2", "arm": arm, "query": qid, "text": f"under {WORDS_LIMIT} words, {CHAINS} of {CHAINS}",
                          "figure": f"{t['under_150']} of {t['chains']}", "held": full and t["under_150"] == CHAINS})
        else:
            marks.append({"mark": "G3", "arm": arm, "query": qid, "text": f"refused, {CHAINS} of {CHAINS}",
                          "figure": f"{t['refused']} of {t['chains']}", "held": full and t["refused"] == CHAINS})
    return marks


def reranker_marks(without: dict, with_: dict) -> list[dict]:
    real = [q for q, t in without.items() if t["real"]]
    firsts_without = sum(1 for q in real if without[q]["rank_merged"] == 1)
    firsts_with = sum(1 for q in real if with_.get(q, {}).get("rank_merged") == 1)
    lost = [q for q in real if without[q]["rank_merged"] == 1 and not (with_.get(q, {}).get("rank_merged") or 99) <= TOP_THREE]
    slow = [q for q, t in with_.items() if t["search_ms"] is None or t["search_ms"] >= SECOND]
    return [{"mark": "R1", "text": "the right passage first in more queries with the reranker than without",
             "figure": f"{firsts_with} with, {firsts_without} without, of {len(real)}", "held": firsts_with > firsts_without},
            {"mark": "R2", "text": f"no query first without the reranker outside the top {TOP_THREE} with it",
             "figure": f"{len(lost)} lost" + (f" ({', '.join(lost)})" if lost else ""), "held": not lost and bool(real)},
            {"mark": "R3", "text": f"every search with the reranker under {SECOND} ms on this card",
             "figure": f"{len(with_) - len(slow)} of {len(with_)} under; slowest {max((t['search_ms'] or 0) for t in with_.values()) if with_ else None} ms",
             "held": bool(with_) and not slow}]


def score(without: dict, with_: dict | None = None) -> dict:
    """The tables per query for each arm, G1 to G3 per arm, R1 to R3 between them."""
    tables = {"without": {q: query_table(e) for q, e in by_query(without).items()}}
    if not tables["without"]:
        raise MarksRefused("no result to score")
    marks = arm_marks("without", tables["without"])
    reranker = None
    if with_:
        tables["with"] = {q: query_table(e) for q, e in by_query(with_).items()}
        marks += arm_marks("with", tables["with"])
        reranker = reranker_marks(tables["without"], tables["with"])
    g_without = all(m["held"] for m in marks if m["arm"] == "without")
    g_with = all(m["held"] for m in marks if m["arm"] == "with") if with_ else None
    r_held = all(m["held"] for m in reranker) if reranker else None
    return {"tables": tables, "marks": marks, "reranker_marks": reranker,
            "panel_held": g_without, "reranker_held": bool(r_held and g_with) if with_ else None,
            "held": g_without and (reranker is None or (r_held and g_with))}


HEAD = ("| query | real | chains | failed | covered | cites only given | under 150 | refused | no call | top similarity | below floor | sent | "
        "candidates | right rank (merged) | right rank (sent) | right passages | search ms | reranker ran | call s | longest s | words max |")


def as_markdown(marked: dict) -> str:
    lines = []
    for arm, tables in marked["tables"].items():
        lines += [f"Arm {arm}:", "", HEAD, "|" + "---|" * 21]
        for q, t in tables.items():
            lines.append(f"| {q} | {'yes' if t['real'] else 'made'} | {t['chains']} | {t['failed']} | {t['covered']} | {t['cites_only_given']} | "
                         f"{t['under_150']} | {t['refused']} | {t['no_call']} | {t['top_similarity']} | {'yes' if t['below_floor'] else 'no'} | "
                         f"{t['sent']} | {t['candidates']} | {t['rank_merged']} | {t['rank_sent']} | {t['right_count']} | {t['search_ms']} | "
                         f"{'yes' if t['reranker_ran'] else 'no'} | {t['call_s']} | {t['longest_s']} | {t['words_max']} |")
        lines.append("")
    for m in marked["marks"]:
        lines.append(f"- Mark {m['mark']}, arm {m['arm']}, {m['query']}, {m['text']}: {m['figure']}: {'held' if m['held'] else 'MISSED'}")
    for m in marked["reranker_marks"] or []:
        lines.append(f"- Mark {m['mark']}, {m['text']}: {m['figure']}: {'held' if m['held'] else 'MISSED'}")
    lines.append(f"- The panel's marks (G1 to G3 without the reranker) {'held' if marked['panel_held'] else 'did not hold'}.")
    if marked["reranker_held"] is not None:
        lines.append(f"- The reranker's marks (R1 to R3, and G1 to G3 with it) {'held' if marked['reranker_held'] else 'did not hold'}.")
    return "\n".join(lines) + "\n"


def write(folder: Path, marked: dict) -> None:
    folder = Path(folder)
    for name in ("marks.json", "marks.md"):
        if (folder / name).exists():
            raise MarksRefused(f"{folder / name} exists and is never written over")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "marks.json").write_text(json.dumps(marked, indent=1, ensure_ascii=False), encoding="utf-8")
    (folder / "marks.md").write_text(as_markdown(marked), encoding="utf-8")
