"""Replay a mock consultation through the CDS engine as if it were live.

Feeds the script to the engine a few turns at a time — the way a real
consultation trickles in — and prints how the assessment evolves, plus
stability metrics (how much the differential list churns between updates).

Usage:
    uv run python scripts/simulate_cds.py mock_consultations/01_chest_pain_en.md
    uv run python scripts/simulate_cds.py --turns-per-update 6 mock_consultations/03_*.md
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.cds import CDSEngine
from app.mock_scripts import as_live_transcript, parse_script


def churn(prev: list[str], curr: list[str]) -> str:
    """Describe what changed between two differential lists."""
    prev_set, curr_set = set(prev), set(curr)
    added = [c for c in curr if c not in prev_set]
    removed = [c for c in prev if c not in curr_set]
    kept = [c for c in curr if c in prev_set]
    reordered = kept != [c for c in prev if c in curr_set]
    bits = []
    if added:
        bits.append(f"+{len(added)} ({', '.join(added)})")
    if removed:
        bits.append(f"-{len(removed)} ({', '.join(removed)})")
    if reordered:
        bits.append("reordered")
    return "; ".join(bits) if bits else "unchanged"


async def simulate(script_path: Path, turns_per_update: int) -> None:
    turns = parse_script(script_path)
    print(f"=== {script_path.name}: {len(turns)} turns, "
          f"updating every {turns_per_update} ===\n")

    engine = CDSEngine()
    assessment: dict | None = None
    churn_log: list[str] = []

    for cut in range(turns_per_update, len(turns) + turns_per_update, turns_per_update):
        window = turns[:cut]
        transcript = as_live_transcript(window)
        started = time.perf_counter()
        new_assessment = await engine.update(transcript, assessment)
        elapsed = time.perf_counter() - started

        prev_names = [d["condition"] for d in (assessment or {}).get("differentials", [])]
        curr_names = [d["condition"] for d in new_assessment["differentials"]]
        delta = churn(prev_names, curr_names)
        churn_log.append(delta)

        print(f"--- after turn {min(cut, len(turns))}/{len(turns)}  "
              f"({elapsed:.1f}s)  [{delta}]")
        for d in new_assessment["differentials"]:
            print(f"  dx: ({d['likelihood']:>8}) {d['condition']} — {d['rationale']}")
        for q in new_assessment["questions_to_ask"]:
            print(f"  ask: {q}")
        for s in new_assessment["signs_to_check"]:
            print(f"  check: {s}")
        print()
        assessment = new_assessment

    stable = sum(1 for c in churn_log[1:] if c == "unchanged")
    print(f"=== stability: {stable}/{len(churn_log) - 1} updates left the "
          f"differential list untouched ===")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("script", type=Path)
    parser.add_argument("--turns-per-update", type=int, default=4)
    args = parser.parse_args()
    asyncio.run(simulate(args.script, args.turns_per_update))


if __name__ == "__main__":
    main()
