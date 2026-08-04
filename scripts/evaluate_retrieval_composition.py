"""Retrieval-composition harness — docket item 12. REPORT ONLY.

The finding (consultation 450, measured 2026-07-28): the per-source cap
of 2 is SYMMETRIC — it caps the correct guideline exactly as hard as the
wrong one — and the bare condition word "Anaemia" let NG203 (CKD
anaemia, 75 chunks) outweigh the CKS iron-deficiency topic (32 chunks).
Three candidate fixes were recorded then; none had been tried. This
harness implements all three as switchable strategies INSIDE THE HARNESS
ONLY — `app/rag.py` is untouched, and nothing here ships. The owner
chooses.

Strategies (each a pure selection function over the same per-condition
search results, so the comparison isolates composition):

  production          what ships: hits deduped across conditions, sorted
                      by similarity, per-source cap 2, global 6.
  slot_budget         (a) the global six divided into per-condition
                      budgets (remainder to earlier conditions — the CDS
                      ranks them); each condition fills its own budget by
                      similarity with the per-source cap applied inside
                      its picks. A weak condition cannot be crowded out
                      by a strong one's vocabulary.
  citation_diversity  (b) diversity at citation level instead of passage
                      caps: first the best passage of EVERY distinct
                      source in similarity order, then remaining slots
                      filled by pure similarity. The cited-source set is
                      as wide as the retrieval supports; depth comes
                      second.
  specific_naming     (c) production selection, but the QUERY carries the
                      specific condition name the CDS could emit —
                      simulated here by a per-case renaming table (the
                      450 case: "Anaemia" -> "Iron deficiency anaemia").
                      Identical to production wherever no renaming
                      applies, and the report says so.

Evaluation: the FULL existing RAG eval case set (evaluate_rag.py's nine,
currently 9/9 — any strategy that drops a case is reported as FAILING
regardless of what it does for composition) PLUS the 450 anaemia case as
a composition case: its slot composition is reported per strategy rather
than pass/failed, because what "right" looks like there is the owner's
call.

Safety: READ-ONLY against the live corpus (search + summarise; no
writes anywhere); MedGemma is used for the summaries exactly as the live
panel uses it and reloads on demand. Run it while nothing else needs the
GPU.

Usage: uv run python scripts/evaluate_retrieval_composition.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.rag import RAGService  # noqa: E402

OUT_PATH = Path(__file__).parent.parent / "evals" / "retrieval_composition_results.json"

# The existing eval set, verbatim from scripts/evaluate_rag.py — any
# strategy must hold all nine before its composition numbers matter.
IN_CORPUS = [
    ("chest pain (script 01)", ["Stable Angina", "Acute Coronary Syndrome (ACS)"], ("chest pain", "angina")),
    ("dyspepsia (script 05)", ["Peptic ulcer disease", "NSAID-related gastritis"], "dyspepsia"),
    ("dengue child (script 02)", ["Dengue fever", "Viral fever"], "dengue"),
    ("asthma (script 04)", ["Poorly controlled asthma"], "asthma"),
    ("diabetes (script 03)", ["Diabetic Peripheral Neuropathy", "Poorly Controlled Diabetes Mellitus"], "diabetes"),
    ("TIA (script 06)", ["Transient ischaemic attack", "Atrial fibrillation"], "stroke"),
]
OUT_OF_CORPUS = [
    ("torsion (script 10)", ["Testicular torsion"]),
    ("unrelated specialty", ["Postpartum haemorrhage"]),
    ("non-medical", ["Cricket batting technique"]),
]

# The 450 composition case: the bare word the CDS actually emitted.
ANAEMIA_CASE = ("anaemia (450 composition)", ["Anaemia"])

# Strategy (c)'s simulated specific naming — what a more specific CDS
# condition name would have been. Only the 450 case renames; the eval
# set's conditions are already specific, which the report states.
SPECIFIC_NAMES = {"Anaemia": "Iron deficiency anaemia"}

PER_SOURCE_CAP = 2
SLOTS = 6
SEARCH_K = 12


# --- selection strategies (pure; tested) ------------------------------------

def _dedup(per_condition: dict[str, list[dict]]) -> list[dict]:
    """The production dedup: same leading text keeps its best similarity."""
    merged: dict[str, dict] = {}
    for hits in per_condition.values():
        for hit in hits:
            key = hit["text"][:120]
            if key not in merged or hit["similarity"] > merged[key]["similarity"]:
                merged[key] = hit
    return sorted(merged.values(), key=lambda h: -h["similarity"])


def select_production(per_condition: dict[str, list[dict]]) -> list[dict]:
    """Mirrors app/rag.py::answer_for_conditions selection EXACTLY — the
    baseline every candidate is compared against. A mirror, clearly
    marked: if production changes, this comparison must be re-run."""
    per_source: dict[str, int] = {}
    selected: list[dict] = []
    for hit in _dedup(per_condition):
        if per_source.get(hit["source"], 0) >= PER_SOURCE_CAP:
            continue
        per_source[hit["source"]] = per_source.get(hit["source"], 0) + 1
        selected.append(hit)
        if len(selected) >= SLOTS:
            break
    return selected


def select_slot_budget(per_condition: dict[str, list[dict]]) -> list[dict]:
    """(a) Per-condition budgets: 6 // n each, remainder to the earlier
    conditions (the CDS ranks its differentials). Each condition fills
    its own budget by similarity, per-source cap inside its picks;
    passages already selected for an earlier condition are not
    re-selected. Unfilled budgets fall through to the pooled remainder."""
    conditions = list(per_condition)
    base, extra = divmod(SLOTS, max(1, len(conditions)))
    budgets = {c: base + (1 if i < extra else 0)
               for i, c in enumerate(conditions)}
    chosen_keys: set[str] = set()
    selected: list[dict] = []
    for condition in conditions:
        per_source: dict[str, int] = {}
        taken = 0
        for hit in sorted(per_condition[condition],
                          key=lambda h: -h["similarity"]):
            key = hit["text"][:120]
            if key in chosen_keys or taken >= budgets[condition]:
                continue
            if per_source.get(hit["source"], 0) >= PER_SOURCE_CAP:
                continue
            per_source[hit["source"]] = per_source.get(hit["source"], 0) + 1
            chosen_keys.add(key)
            selected.append(hit)
            taken += 1
    if len(selected) < SLOTS:   # unfilled budgets: pooled best-of-rest
        for hit in _dedup(per_condition):
            if len(selected) >= SLOTS:
                break
            if hit["text"][:120] not in chosen_keys:
                chosen_keys.add(hit["text"][:120])
                selected.append(hit)
    return sorted(selected, key=lambda h: -h["similarity"])[:SLOTS]


def select_citation_diversity(per_condition: dict[str, list[dict]]) -> list[dict]:
    """(b) Diversity at citation level: the best passage of every distinct
    source first (in similarity order), then remaining slots by pure
    similarity with no cap at all."""
    pool = _dedup(per_condition)
    selected: list[dict] = []
    seen_sources: set[str] = set()
    for hit in pool:                      # one per source, breadth first
        if len(selected) >= SLOTS:
            break
        if hit["source"] not in seen_sources:
            seen_sources.add(hit["source"])
            selected.append(hit)
    chosen = {h["text"][:120] for h in selected}
    for hit in pool:                      # depth second, uncapped
        if len(selected) >= SLOTS:
            break
        if hit["text"][:120] not in chosen:
            chosen.add(hit["text"][:120])
            selected.append(hit)
    return sorted(selected, key=lambda h: -h["similarity"])


STRATEGIES = {
    "production": select_production,
    "slot_budget": select_slot_budget,
    "citation_diversity": select_citation_diversity,
    # specific_naming uses select_production over RENAMED queries — the
    # change is in what is asked, not how slots are filled.
    "specific_naming": select_production,
}


def composition(selected: list[dict]) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for hit in selected:
        counts[hit["source"]] = counts.get(hit["source"], 0) + 1
    return sorted(counts.items(), key=lambda kv: -kv[1])


# --- the runs ---------------------------------------------------------------

class HarnessRAG(RAGService):
    """Search + summarise reused from production; only SELECTION differs,
    and it differs here, in the harness, not in the app."""

    async def gather(self, conditions: list[str]) -> dict[str, list[dict]]:
        return {c: await self.search(c, k=SEARCH_K) for c in conditions}

    async def answer_with(self, conditions: list[str], strategy: str):
        queried = ([SPECIFIC_NAMES.get(c, c) for c in conditions]
                   if strategy == "specific_naming" else conditions)
        per_condition = await self.gather(queried)
        selected = STRATEGIES[strategy](per_condition)
        answer = await self._summarise(
            self.query_for_conditions(queried), selected)
        return answer, selected, queried


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--write-baseline", action="store_true",
        help="overwrite the committed baseline results file — re-baselines "
             "every future comparison — instead of writing a dated file "
             "beside it")
    args = parser.parse_args()
    out_path = OUT_PATH if args.write_baseline else OUT_PATH.with_name(
        f"{OUT_PATH.stem}_{date.today().isoformat()}{OUT_PATH.suffix}")

    svc = HarnessRAG()
    report: dict = {"note": "REPORT ONLY — strategies exist in this harness "
                            "only; app/rag.py is untouched and nothing ships. "
                            "The owner chooses.",
                    "strategies": {}}

    for strategy in STRATEGIES:
        rows = []
        passes = 0
        print(f"\n=== strategy: {strategy} ===")
        for label, conditions, expected in IN_CORPUS:
            answer, selected, queried = await svc.answer_with(conditions, strategy)
            top = answer["citations"][0]["source"].lower() if answer["citations"] else ""
            accepted = (expected,) if isinstance(expected, str) else expected
            ok = (answer["covered"] and bool(answer["citations"])
                  and any(k in top for k in accepted))
            passes += ok
            rows.append({"case": label, "kind": "in-corpus", "pass": ok,
                         "queried": queried,
                         "slots": composition(selected),
                         "top_cited": answer["citations"][0]["source"]
                         if answer["citations"] else None})
            print(f"  {label}: {'PASS' if ok else 'FAIL'}"
                  f"  slots={composition(selected)}")
        for label, conditions in OUT_OF_CORPUS:
            answer, selected, queried = await svc.answer_with(conditions, strategy)
            ok = not answer["covered"] and not answer["citations"]
            passes += ok
            rows.append({"case": label, "kind": "out-of-corpus", "pass": ok,
                         "queried": queried, "slots": composition(selected)})
            print(f"  {label}: {'PASS' if ok else 'FAIL (answered)'}")

        label, conditions = ANAEMIA_CASE
        answer, selected, queried = await svc.answer_with(conditions, strategy)
        anaemia = {"case": label, "kind": "composition", "queried": queried,
                   "covered": answer["covered"],
                   "slots": composition(selected),
                   "top_cited": answer["citations"][0]["source"]
                   if answer["citations"] else None}
        print(f"  {label}: slots={anaemia['slots']}  "
              f"top={anaemia['top_cited']}")

        report["strategies"][strategy] = {
            "eval_pass_rate": f"{passes}/{len(IN_CORPUS) + len(OUT_OF_CORPUS)}",
            "cases": rows, "anaemia_450": anaemia}

    out_path.write_text(json.dumps(report, indent=1))
    print(f"\nWritten: {out_path}")
    if not args.write_baseline:
        print(f"\nWrote evals/{out_path.name}; baseline evals/{OUT_PATH.name}"
              f" untouched. Compare:\n"
              f"  diff evals/{OUT_PATH.name} evals/{out_path.name}")

    print("\n| Strategy | Eval | 450 slots | 450 top cited |")
    print("|---|---|---|---|")
    for name, data in report["strategies"].items():
        a = data["anaemia_450"]
        slots = ", ".join(f"{s}×{n}" for s, n in a["slots"]) or "—"
        print(f"| {name} | {data['eval_pass_rate']} | {slots} | {a['top_cited'] or '—'} |")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
