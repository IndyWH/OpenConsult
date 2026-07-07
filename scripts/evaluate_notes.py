"""Note-quality evaluation: draft SOAP notes from the mock scripts (used as
stand-in diarised transcripts) and mark them against each script's
"Expected clinical content" section.

Marking is two-part:
- Mechanical (code): every claim must cite valid transcript turns.
- Clinical coverage (LLM judge): each expected-content bullet is checked
  against the note — covered or missed — and the judge lists factual
  discrepancies between note and expected content. The judge is the same
  MedGemma model that wrote the note (a stated limitation; the project
  owner reviews the judge's output).

Writes evals/note_results.json and prints a markdown table.

Usage: uv run python scripts/evaluate_notes.py
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.mock_scripts import parse_script
from app.notes import draft_note, note_as_plain_text

ROOT = Path(__file__).parent.parent
SCRIPTS = sorted((ROOT / "mock_consultations").glob("[01]*_en.md"))
OUT_PATH = ROOT / "evals" / "note_results.json"

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
JUDGE_MODEL = os.getenv("CDS_MODEL", "hf.co/unsloth/medgemma-27b-text-it-GGUF:Q4_K_M")

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "expected": {"type": "string"},
                    "covered": {"type": "boolean"},
                },
                "required": ["expected", "covered"],
            },
        },
        "discrepancies": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["items", "discrepancies"],
}

JUDGE_PROMPT = """\
You are marking a draft SOAP note for a scripted mock consultation. You \
receive the consultation TRANSCRIPT, the EXPECTED CONTENT (a marking \
scheme listing the minimum a good note must contain), and the NOTE.

Coverage: for each distinct clinical point in the EXPECTED CONTENT (split \
compound bullets into their component points), judge whether the NOTE \
captures it (covered = true/false). A point counts as covered if its \
clinical substance is present, regardless of wording.

DISCREPANCIES: statements in the note that are WRONG — contradicted by \
the transcript, or clinically distorted (wrong dose, wrong side, invented \
detail, misattributed finding). Judge discrepancies against the \
TRANSCRIPT, which is the ground truth of what was said. The expected \
content is a minimum, not a ceiling: a note entry with correct extra \
detail that appears in the transcript is GOOD and must NOT be listed. \
Wording, style, and unit differences are not discrepancies. An omission \
is not a discrepancy (it shows up as covered=false).

Output JSON only.\
"""


def expected_content(script_path: Path) -> str:
    text = script_path.read_text(encoding="utf-8")
    match = re.search(
        r"## Expected clinical content.*?\n(.*?)(?=\n## |\n---)", text, re.DOTALL
    )
    return match.group(1).strip()


def standin_turns(script_path: Path) -> list[dict]:
    return [
        {"idx": i, "role": "Doctor" if t.speaker == "DOCTOR" else "Patient",
         "start": i * 8.0, "end": i * 8.0 + 7.0, "text": t.text, "confidence": 1.0}
        for i, t in enumerate(parse_script(script_path))
    ]


async def judge(expected: str, note_text: str, transcript: str) -> dict:
    async with httpx.AsyncClient(timeout=600.0) as client:
        response = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": JUDGE_MODEL,
                "messages": [
                    {"role": "system", "content": JUDGE_PROMPT},
                    {"role": "user",
                     "content": (f"TRANSCRIPT:\n{transcript}\n\n"
                                 f"EXPECTED CONTENT:\n{expected}\n\nNOTE:\n{note_text}")},
                ],
                "format": JUDGE_SCHEMA,
                "stream": False,
                "keep_alive": "30m",
                "options": {"temperature": 0.0, "seed": 42, "num_ctx": 16384},
            },
        )
        response.raise_for_status()
    return json.loads(response.json()["message"]["content"])


async def main() -> None:
    results = []
    for script_path in SCRIPTS:
        turns = standin_turns(script_path)
        note = await draft_note(turns)
        sections = ("subjective", "objective", "assessment", "plan")
        claims = [c for s in sections for c in note[s]]
        cited = sum(1 for c in claims if c["turns"])
        transcript = "\n".join(f"{t['role']}: {t['text']}" for t in turns)
        verdict = await judge(
            expected_content(script_path), note_as_plain_text(note), transcript
        )
        covered = sum(1 for i in verdict["items"] if i["covered"])
        results.append(
            {
                "script": script_path.name,
                "claims": len(claims),
                "cited": cited,
                "coverage": f"{covered}/{len(verdict['items'])}",
                "coverage_pct": round(100 * covered / max(1, len(verdict["items"]))),
                "missed": [i["expected"] for i in verdict["items"] if not i["covered"]],
                "discrepancies": verdict["discrepancies"],
                "note_plain": note_as_plain_text(note),
            }
        )
        r = results[-1]
        print(f"{script_path.name}: coverage {r['coverage']}, "
              f"{len(r['discrepancies'])} discrepancies, {cited}/{len(claims)} cited",
              flush=True)

    OUT_PATH.write_text(json.dumps(results, indent=1))

    print("\n| Script | Claims | Cited | Coverage | Discrepancies |")
    print("|---|---|---|---|---|")
    for r in results:
        print(f"| {r['script']} | {r['claims']} | {r['cited']}/{r['claims']} "
              f"| {r['coverage']} ({r['coverage_pct']}%) | {len(r['discrepancies'])} |")
    total_disc = sum(len(r["discrepancies"]) for r in results)
    print(f"\nmean coverage {sum(r['coverage_pct'] for r in results) / len(results):.0f}%"
          f" · {total_disc} discrepancies across {len(results)} notes")


if __name__ == "__main__":
    asyncio.run(main())
