"""RAG grounding evaluation: retrieval accuracy, citation validity, refusal.

Two query sets:
- IN_CORPUS: queries built the way the live system builds them — from the
  CDS layer's identified conditions (taken from actual simulation runs on
  the mock scripts). Expected: covered answer, valid citations, and the
  top-cited source is the right guideline.
- OUT_OF_CORPUS: conditions the corpus does not cover. Expected: refusal
  (covered=false, no citations), whether by the retrieval floor or by the
  model's own verdict.

Writes evals/rag_results.json and prints a markdown table.

Usage: uv run python scripts/evaluate_rag.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.rag import RAGService

OUT_PATH = Path(__file__).parent.parent / "evals" / "rag_results.json"

# (label, conditions as the CDS layer produces them, expected source keyword)
IN_CORPUS = [
    ("chest pain (script 01)", ["Stable Angina", "Acute Coronary Syndrome (ACS)"], "chest pain"),
    ("dyspepsia (script 05)", ["Peptic ulcer disease", "NSAID-related gastritis"], "dyspepsia"),
    ("dengue child (script 02)", ["Dengue fever", "Viral fever"], "dengue"),
    ("asthma (script 04)", ["Poorly controlled asthma"], "asthma"),
    ("diabetes (script 03)", ["Diabetic Peripheral Neuropathy", "Poorly Controlled Diabetes Mellitus"], "diabetes"),
]

OUT_OF_CORPUS = [
    ("TIA (script 06)", ["Transient ischaemic attack", "Atrial fibrillation"]),
    ("torsion (script 10)", ["Testicular torsion"]),
    ("unrelated specialty", ["Postpartum haemorrhage"]),
    ("non-medical", ["Cricket batting technique"]),
]


async def main() -> None:
    svc = RAGService()
    results = []

    for label, conditions, expected_source in IN_CORPUS:
        answer = await svc.answer_for_conditions(conditions)
        top_source = answer["citations"][0]["source"].lower() if answer["citations"] else ""
        ok = answer["covered"] and bool(answer["citations"]) and expected_source in top_source
        results.append(
            {
                "case": label,
                "kind": "in-corpus",
                "conditions": conditions,
                "covered": answer["covered"],
                "top_similarity": answer["top_similarity"],
                "n_citations": len(answer["citations"]),
                "top_cited_source": answer["citations"][0]["source"] if answer["citations"] else None,
                "summary_first_120": answer["summary"][:120],
                "verdict": "PASS" if ok else "FAIL",
            }
        )
        print(f"{label}: {'PASS' if ok else 'FAIL'}", flush=True)

    for label, conditions in OUT_OF_CORPUS:
        answer = await svc.answer_for_conditions(conditions)
        ok = not answer["covered"] and not answer["citations"]
        results.append(
            {
                "case": label,
                "kind": "out-of-corpus",
                "conditions": conditions,
                "covered": answer["covered"],
                "top_similarity": answer["top_similarity"],
                "n_citations": len(answer["citations"]),
                "refusal_layer": (
                    "retrieval floor" if answer["top_similarity"] < 0.45 else "model verdict"
                )
                if ok
                else None,
                "summary_first_120": answer["summary"][:120],
                "verdict": "PASS" if ok else "FAIL (answered uncovered topic)",
            }
        )
        print(f"{label}: {'PASS' if ok else 'FAIL'}", flush=True)

    OUT_PATH.write_text(json.dumps(results, indent=1))

    print("\n| Case | Kind | Covered | Top sim | Citations | Top cited source / refusal layer | Verdict |")
    print("|---|---|---|---|---|---|---|")
    for r in results:
        detail = r.get("top_cited_source") or r.get("refusal_layer") or "—"
        print(
            f"| {r['case']} | {r['kind']} | {'yes' if r['covered'] else 'no'} "
            f"| {r['top_similarity']:.3f} | {r['n_citations']} | {detail} | {r['verdict']} |"
        )
    passes = sum(1 for r in results if r["verdict"] == "PASS")
    print(f"\n{passes}/{len(results)} cases meet expectations")


if __name__ == "__main__":
    asyncio.run(main())
