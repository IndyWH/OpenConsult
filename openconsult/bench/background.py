"""The marks of the background bench (spec 8.6; 15.11 ruling 6), read
from the stored results of the two arms alone, with the marks fixed as
numbers before the run (STAGE7B_PLAN, 21 Oct 2026). A chain fires when
the alarm's actions after bookkeeping are non-empty at any pass; it
names a condition when one of the first three differential names at its
last pass holds the condition's words, after matching.normalise, as a
contiguous whole-word run. Hypo alone does not count; low blood sugar
does. Subarachnoid haemorrhage is reported for case B and is not a mark.
What a model said is counted here, never asserted in a test."""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from openconsult.speech.matching import normalise

CASE_A, CASE_B = "A_hypo", "B_headache"
HYPOGLYCAEMIA = ("hypoglycaemia", "hypoglycemia", "hypoglycaemic", "hypoglycemic", "low blood sugar",
                 "low blood glucose")
SUBARACHNOID = ("subarachnoid",)
CHAINS = 13
TOP = 3
# The marks of ruling 6: case A with the block names hypoglycaemia in the
# top three and fires in at least 12 of 13 chains, and in fewer without;
# case B fires in 13 of 13 both ways.
MARK_A_WITH_BOTH = 12
MARK_B_FIRED = 13


class MarksRefused(Exception):
    pass


def names_match(name: str, targets: tuple[str, ...]) -> bool:
    words = normalise(str(name or ""))
    for target in targets:
        wanted = normalise(target)
        if any(words[i:i + len(wanted)] == wanted for i in range(len(words) - len(wanted) + 1)):
            return True
    return False


def fired(chain: dict) -> bool:
    return any(bool(p["alarm"]["actions"]) for p in chain["passes"])


def top_three(chain: dict) -> list[str]:
    if not chain["passes"]:
        return []
    found = chain["passes"][-1]["assessment"]["differentials"]
    return [d.get("condition", "") for d in found if isinstance(d, dict)][:TOP]


def names(chain: dict, targets: tuple[str, ...]) -> bool:
    return any(names_match(name, targets) for name in top_three(chain))


def had_a_failed_call(chain: dict) -> bool:
    return bool(chain.get("failed")) or any(p["alarm"]["failure"] or p["assessment"]["failure"] for p in chain["passes"])


def arm_table(results: dict, case: str) -> dict:
    """One case in one arm: the counts over its chains and the typical pass."""
    chains = [r for (name, _), r in sorted(results.items()) if name == case]
    walls = [p["wall_ms"] for r in chains for p in r["passes"]]
    return {"chains": len(chains),
            "failed_call": sorted(r["chain"] for r in chains if had_a_failed_call(r)),
            "fired": sum(fired(r) for r in chains),
            "named_hypoglycaemia": sum(names(r, HYPOGLYCAEMIA) for r in chains),
            "both": sum(fired(r) and names(r, HYPOGLYCAEMIA) for r in chains),
            "named_subarachnoid": sum(names(r, SUBARACHNOID) for r in chains),
            "pass_s": round(statistics.median(walls) / 1000, 2) if walls else None}


def score(with_results: dict, without_results: dict) -> dict:
    """The table for each case and arm, and the four marks."""
    cases = sorted({name for name, _ in with_results} | {name for name, _ in without_results})
    for case in (CASE_A, CASE_B):
        for arm, results in (("with", with_results), ("without", without_results)):
            if not any(name == case for name, _ in results):
                raise MarksRefused(f"no result for {case} in the arm {arm}")
    tables = {case: {"with": arm_table(with_results, case), "without": arm_table(without_results, case)} for case in cases}
    a, b = tables[CASE_A], tables[CASE_B]
    marks = [
        {"mark": "A1", "text": f"case A with the block: both at least {MARK_A_WITH_BOTH} of {CHAINS}",
         "figure": f"{a['with']['both']} of {a['with']['chains']}",
         "held": a["with"]["both"] >= MARK_A_WITH_BOTH and a["with"]["chains"] == CHAINS},
        {"mark": "A2", "text": "case A without the block: both fewer than with it",
         "figure": f"{a['without']['both']} of {a['without']['chains']} against {a['with']['both']}",
         "held": a["without"]["both"] < a["with"]["both"] and a["without"]["chains"] == CHAINS},
        {"mark": "B1", "text": f"case B with the block: fired {MARK_B_FIRED} of {CHAINS}",
         "figure": f"{b['with']['fired']} of {b['with']['chains']}",
         "held": b["with"]["fired"] == MARK_B_FIRED and b["with"]["chains"] == CHAINS},
        {"mark": "B2", "text": f"case B without the block: fired {MARK_B_FIRED} of {CHAINS}",
         "figure": f"{b['without']['fired']} of {b['without']['chains']}",
         "held": b["without"]["fired"] == MARK_B_FIRED and b["without"]["chains"] == CHAINS},
    ]
    return {"cases": tables, "marks": marks, "held": all(m["held"] for m in marks)}


def as_markdown(marked: dict) -> str:
    lines = ["| case | arm | chains | failed call | fired | named hypoglycaemia | both | named subarachnoid | typical pass s |",
             "|---|---|---|---|---|---|---|---|---|"]
    for case, arms in marked["cases"].items():
        for arm, t in arms.items():
            lines.append(f"| {case} | {arm} | {t['chains']} | {', '.join(t['failed_call']) or 'none'} | {t['fired']} | "
                         f"{t['named_hypoglycaemia']} | {t['both']} | {t['named_subarachnoid']} | {t['pass_s']} |")
    lines.append("")
    for m in marked["marks"]:
        lines.append(f"- Mark {m['mark']}, {m['text']}: {m['figure']}: {'held' if m['held'] else 'MISSED'}")
    lines.append(f"- Every mark {'held' if marked['held'] else 'did not hold'}.")
    return "\n".join(lines) + "\n"


def write(folder: Path, marked: dict) -> None:
    """marks.json and marks.md, never over a file that exists."""
    folder = Path(folder)
    for name in ("marks.json", "marks.md"):
        if (folder / name).exists():
            raise MarksRefused(f"{folder / name} exists and is never written over")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "marks.json").write_text(json.dumps(marked, indent=1, ensure_ascii=False), encoding="utf-8")
    (folder / "marks.md").write_text(as_markdown(marked), encoding="utf-8")
