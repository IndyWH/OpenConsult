"""CDS differential-restraint evaluation (UK private-GP series 11–15).

Runs the SAME CDS engine and the SAME per-script replay machinery as the
urgency evaluation (imports evaluate_script from evaluate_urgency), on the
five _uk scripts, and adds a differential-breadth / over-commitment metric
that the urgency arm does not measure.

Two arms, one run:

- **Urgency arm** (reused verbatim): 11/12/13 must stay SILENT, 14/15 must
  FIRE. This is buried-red-flag detection (14/15) and false-alarm
  restraint on undifferentiated presentations (11/12).
- **Restraint arm** (new here): does the differential's breadth match the
  evidence? 11/12 must stay BROAD and uncommitted; 13 must NARROW
  confidently to migraine (the calibration control — restraint is not
  blanket caution); 14/15 must let the emergency become the leading dx.

--- Metric design (why these operationalisations) --------------------

The assessment schema has no explicit "leading" flag: differentials are a
ranked list (most-likely-first), each graded likelihood high/moderate/low.
So we read *commitment* from those two signals, measured on the FINAL
update (full information — where calibration should be clearest), while
also recording the whole trajectory in the JSON:

  n_differentials  breadth  = length of the final differential list.
  n_high           how many conditions are graded "high" likelihood.
  top_condition    the rank-1 (leading) condition.
  top_high         is the leading condition graded "high"? — the operational
                   definition of a confident commitment.

Mapping to the scripts' own marking schemes:

  11, 12 (undifferentiated, must stay broad):
     PASS iff n_differentials >= 5 AND n_high == 0
     (broad, with NO condition asserted at high confidence — the schemes'
      "≥5 categories, none high-confidence/leading").
  13 (differentiable positive control, must narrow confidently):
     PASS iff the leading condition IS migraine AND top_high
     (the scheme: "confidently identifies migraine (with aura) as the
      leading diagnosis"). Refusing to commit (top not high) or spurious
      breadth is the FAIL — the mirror image of over-commitment.
  14, 15 (subtle emergencies, restraint arm = escalation anchor):
     PASS iff the emergency concept is the LEADING dx (GCA / cauda equina).
     Their primary pass/fail is the urgency arm; here we check the
     differential also surfaced the emergency as the working diagnosis.

Concept matching is keyword-based on the lowercased leading condition
string (migraine; giant cell / temporal arteritis / gca; cauda equina).

Design choices called out as limitations:
- We count list entries, not semantically-deduplicated categories — a
  model listing two overlapping labels counts as breadth 2. Inspected by
  eye in the writeup; none of the five tripped this.
- "Commitment" is read from the top item's grade, not from prose. The
  schema has no leading flag, and grades are what the UI shows the doctor,
  so the grade is the honest signal.
- Final-update verdict is the pass/fail; premature over-commitment mid
  consultation is reported (breadth/n_high trajectory) but not failed on,
  since the scripts' acceptance criteria are written against the complete
  history.

Deterministic settings: temperature 0, seed 42 (CDS engine defaults),
same as every CDS eval. Writes evals/cds_restraint_results.json.

Usage: uv run python scripts/evaluate_cds_restraint.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.evaluate_urgency import (
    UK_EXPECTATIONS,
    evaluate_script,
    verdict as urgency_verdict,
)

ROOT = Path(__file__).parent.parent
OUT_PATH = ROOT / "evals" / "cds_restraint_results.json"

# What the differential should DO at the end of each consultation.
BROAD = "broad"       # ≥5, none high-confidence
NARROW = "narrow"     # confident leading diagnosis (named concept)
LEAD = "lead"         # a named emergency must be the leading dx

RESTRAINT_SPEC = {
    "11_tired_all_the_time_uk.md": (BROAD, None),
    "12_dizziness_uk.md": (BROAD, None),
    "13_migraine_uk.md": (NARROW, ("migraine",)),
    "14_giant_cell_arteritis_uk.md": (LEAD, ("giant cell", "temporal arteritis", "gca")),
    "15_cauda_equina_uk.md": (LEAD, ("cauda equina",)),
}


def _matches(condition: str, keywords: tuple[str, ...]) -> bool:
    c = condition.lower()
    return any(k in c for k in keywords)


def restraint_metrics(final_update: dict) -> dict:
    grades = final_update["differential_grades"]
    n = len(grades)
    n_high = sum(1 for g in grades if g["likelihood"] == "high")
    top = grades[0] if grades else {"condition": None, "likelihood": None}
    return {
        "n_differentials": n,
        "n_high": n_high,
        "top_condition": top["condition"],
        "top_likelihood": top["likelihood"],
        "top_high": top["likelihood"] == "high",
    }


def restraint_verdict(name: str, m: dict) -> str:
    mode, keywords = RESTRAINT_SPEC[name]
    if mode == BROAD:
        if m["n_differentials"] >= 5 and m["n_high"] == 0:
            return "PASS (broad, uncommitted)"
        if m["n_high"] > 0:
            return f"FAIL (over-committed: {m['n_high']} high-confidence)"
        return f"FAIL (too narrow: {m['n_differentials']} differentials)"
    if mode == NARROW:
        lead_ok = m["top_condition"] and _matches(m["top_condition"], keywords)
        if lead_ok and m["top_high"]:
            return "PASS (confident, correct leader)"
        if not lead_ok:
            return f"FAIL (wrong leader: {m['top_condition']})"
        return "FAIL (spurious breadth: leader not high-confidence)"
    # LEAD (emergency anchors)
    lead_ok = m["top_condition"] and _matches(m["top_condition"], keywords)
    return "PASS (emergency leads)" if lead_ok else f"FAIL (emergency not leading: {m['top_condition']})"


def breadth_trajectory(updates: list[dict]) -> list[dict]:
    return [
        {"end_turn": u["end_turn"],
         "n": len(u["differential_grades"]),
         "n_high": sum(1 for g in u["differential_grades"] if g["likelihood"] == "high"),
         "top": u["differential_grades"][0]["condition"] if u["differential_grades"] else None}
        for u in updates
    ]


async def main() -> None:
    results = []
    for name, expected_fire in UK_EXPECTATIONS.items():
        print(f"=== {name}", flush=True)
        r = await evaluate_script(name, expected_fire=expected_fire)
        final = r["updates"][-1]
        m = restraint_metrics(final)
        r["restraint"] = {
            **m,
            "mode": RESTRAINT_SPEC[name][0],
            "verdict": restraint_verdict(name, m),
            "trajectory": breadth_trajectory(r["updates"]),
        }
        r["urgency_verdict"] = urgency_verdict(r)
        results.append(r)

    OUT_PATH.parent.mkdir(exist_ok=True)
    OUT_PATH.write_text(json.dumps(results, indent=1))

    print("\n### Urgency arm (11/12/13 silent, 14/15 fire)")
    print("| Script | Expected | Fired | First fired | Cleared | Verdict |")
    print("|---|---|---|---|---|---|")
    for r in results:
        first = f"turn {r['first_fire_turn']}/{r['total_turns']}" if r["fired"] else "—"
        cleared = ("yes" if r["cleared_at_end"] else "NO") if r["fired"] else "n/a"
        print(f"| {r['script']} | {'fire' if r['expected_fire'] else 'silent'} "
              f"| {'yes' if r['fired'] else 'no'} | {first} | {cleared} "
              f"| {r['urgency_verdict']} |")

    print("\n### Restraint arm (breadth vs evidence)")
    print("| Script | Mode | # dx | # high | Leading dx | Lead conf | Verdict |")
    print("|---|---|---|---|---|---|---|")
    for r in results:
        m = r["restraint"]
        print(f"| {r['script']} | {m['mode']} | {m['n_differentials']} | {m['n_high']} "
              f"| {m['top_condition']} | {m['top_likelihood']} | {m['verdict']} |")

    u_pass = sum(1 for r in results if r["urgency_verdict"].startswith("PASS"))
    r_pass = sum(1 for r in results if r["restraint"]["verdict"].startswith("PASS"))
    print(f"\nUrgency arm: {u_pass}/{len(results)}   Restraint arm: {r_pass}/{len(results)}")


if __name__ == "__main__":
    asyncio.run(main())
