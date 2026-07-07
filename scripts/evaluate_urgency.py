"""Urgency-escalation evaluation: replay all nine mock consultations through
the CDS engine and check the urgent_actions behaviour against expectations.

Success criteria:
- FIRES on all five emergency presentations (01 chest pain, 06 TIA,
  07 GI bleed, 08 PE, 09 septic child)
- Stays SILENT on all four routine presentations (02 dengue-watch child,
  03 diabetes review, 04 asthma, 05 uncomplicated dyspepsia)
- Where it fires, it should CLEAR once the transcript shows the action
  done or arranged (every emergency script ends with the doctor arranging it)

Writes evals/urgency_results.json and prints a markdown results table.

Usage: uv run python scripts/evaluate_urgency.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.cds import CDSEngine
from app.mock_scripts import as_live_transcript, parse_script

ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = ROOT / "mock_consultations"
OUT_PATH = ROOT / "evals" / "urgency_results.json"
TURNS_PER_UPDATE = 4

# Ground truth: should the urgency alarm fire for this consultation?
EXPECTATIONS = {
    "01_chest_pain_en.md": True,   # possible ACS → ECG now
    "02_febrile_child_en.md": False,  # dengue watch, no warning signs yet
    "03_diabetes_review_en.md": False,
    "04_asthma_en.md": False,      # poorly controlled but mild, sats 98%
    "05_epigastric_pain_en.md": False,  # alarm-symptom screen all negative
    "06_tia_funny_turn_en.md": True,   # resolved focal deficit → TIA pathway
    "07_gi_bleed_en.md": True,     # melaena + haemodynamic compromise
    "08_pulmonary_embolism_en.md": True,   # pleuritic pain + hypoxia + DVT leg
    "09_septic_child_en.md": True,  # shocked child → emergency transfer
    # Held-out generalisation case: a condition the urgency prompt never
    # mentions. Added AFTER the 2026-07-07 evaluation was finalised.
    "10_testicular_torsion_en.md": True,  # torsion as abdo pain → immediate surgery
}


async def evaluate_script(name: str) -> dict:
    turns = parse_script(SCRIPTS_DIR / name)
    engine = CDSEngine()
    assessment: dict | None = None
    updates: list[dict] = []
    prev_dx: list[str] = []
    unchanged = 0

    for cut in range(TURNS_PER_UPDATE, len(turns) + TURNS_PER_UPDATE, TURNS_PER_UPDATE):
        end_turn = min(cut, len(turns))
        transcript = as_live_transcript(turns[:end_turn])
        started = time.perf_counter()
        assessment = await engine.update(transcript, assessment)
        dx = [d["condition"] for d in assessment["differentials"]]
        if updates and dx == prev_dx:
            unchanged += 1
        prev_dx = dx
        updates.append(
            {
                "end_turn": end_turn,
                "seconds": round(time.perf_counter() - started, 1),
                "urgent_actions": assessment["urgent_actions"],
                "differentials": dx,
            }
        )
        print(f"  {name} turn {end_turn}/{len(turns)}: "
              f"{len(assessment['urgent_actions'])} urgent", flush=True)

    fired = [u for u in updates if u["urgent_actions"]]
    return {
        "script": name,
        "expected_fire": EXPECTATIONS[name],
        "total_turns": len(turns),
        "n_updates": len(updates),
        "fired": bool(fired),
        "first_fire_turn": fired[0]["end_turn"] if fired else None,
        "first_fire_actions": [u["action"] for u in fired[0]["urgent_actions"]] if fired else [],
        "cleared_at_end": bool(fired) and not updates[-1]["urgent_actions"],
        "stability": f"{unchanged}/{len(updates) - 1}",
        "leading_dx_final": updates[-1]["differentials"][0] if updates[-1]["differentials"] else None,
        "updates": updates,
    }


def verdict(r: dict) -> str:
    if r["expected_fire"]:
        if not r["fired"]:
            return "FAIL (missed emergency)"
        return "PASS" + ("" if r["cleared_at_end"] else " (did not clear)")
    return "PASS" if not r["fired"] else "FAIL (false alarm)"


async def main() -> None:
    results = []
    for name in EXPECTATIONS:
        print(f"=== {name}", flush=True)
        results.append(await evaluate_script(name))

    OUT_PATH.parent.mkdir(exist_ok=True)
    OUT_PATH.write_text(json.dumps(results, indent=1))

    print("\n| Script | Expected | Fired | First fired | First action said | Cleared | Dx stability | Verdict |")
    print("|---|---|---|---|---|---|---|---|")
    for r in results:
        first = f"turn {r['first_fire_turn']}/{r['total_turns']}" if r["fired"] else "—"
        said = "; ".join(r["first_fire_actions"]) if r["fired"] else "—"
        cleared = ("yes" if r["cleared_at_end"] else "NO") if r["fired"] else "n/a"
        print(f"| {r['script']} | {'fire' if r['expected_fire'] else 'silent'} "
              f"| {'yes' if r['fired'] else 'no'} | {first} | {said} | {cleared} "
              f"| {r['stability']} | {verdict(r)} |")

    passes = sum(1 for r in results if verdict(r).startswith("PASS"))
    print(f"\n{passes}/{len(results)} scripts meet expectations")


if __name__ == "__main__":
    asyncio.run(main())
