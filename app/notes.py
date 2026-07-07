"""SOAP note drafting from a diarised transcript (Phase 2).

Grounding follows the Phase 4 pattern: every claim cites the transcript
turn(s) it came from, and the code validates citations against the turns
actually provided — an uncited or invalidly-cited claim is marked rather
than trusted.

Confidence flagging is deterministic and code-side: a claim gets
`flagged: true` when it is clinically load-bearing (contains a number,
dose unit, or laterality — the things that hurt when misheard) AND at
least one of its cited turns has low ASR confidence. The model is not
asked to judge its own transcription risk.
"""

from __future__ import annotations

import json
import os
import re

import httpx

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
NOTE_MODEL = os.getenv("CDS_MODEL", "hf.co/unsloth/medgemma-27b-text-it-GGUF:Q4_K_M")

LOW_CONFIDENCE = float(os.getenv("ASR_LOW_CONFIDENCE", "0.60"))
# Numbers, dose units, laterality: the content classes where an ASR slip
# changes clinical meaning (gliclazide 80 vs 18; left vs right).
_LOAD_BEARING = re.compile(
    r"\d|\b(mg|ml|mcg|microgram|unit|units|left|right|bilateral)\b", re.IGNORECASE
)

_CLAIM_LIST = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "turns": {"type": "array", "items": {"type": "integer"}},
        },
        "required": ["text", "turns"],
    },
}

NOTE_SCHEMA = {
    "type": "object",
    "properties": {
        "reasoning": {"type": "string"},
        "subjective": _CLAIM_LIST,
        "objective": _CLAIM_LIST,
        "assessment": _CLAIM_LIST,
        "plan": _CLAIM_LIST,
    },
    "required": ["reasoning", "subjective", "objective", "assessment", "plan"],
}

NOTE_PROMPT = """\
You draft a SOAP note from the diarised transcript of a GP consultation. \
The transcript turns are numbered; speaker roles are labelled.

Style: concise doctor-style telegraphic notes, the kind written in a GP \
record. Abbreviate conventionally (HTN, T2DM, SOB, BP 150/95). One claim \
per entry.

Sections:
- subjective: history as the patient gave it — symptoms, timeline, risk \
factors, medications, relevant negatives.
- objective: examination findings and measurements actually stated.
- assessment: the diagnoses/impressions THE DOCTOR stated or clearly \
implied in the consultation — do not add your own.
- plan: investigations, prescriptions, referrals, safety-netting the \
doctor stated.

Grounding rules:
- Every entry's `turns` lists the turn number(s) it came from. Only claim \
what the transcript supports; invent nothing, and use no outside medical \
knowledge beyond standard abbreviations.
- The transcript is rough ASR output: interpret garbled words charitably \
(a drug name mangled phonetically), but if you cannot tell what was \
meant, write the uncertainty into the entry ("medication name unclear").

Fill `reasoning` first (under 80 words): main problem, what belongs in \
each section. Output JSON only.\
"""


def format_turns(turns: list[dict]) -> str:
    return "\n".join(f"[{t['idx']}] {t['role']}: {t['text']}" for t in turns)


async def draft_note(turns: list[dict]) -> dict:
    """Generate a cited SOAP note; validate citations; flag risky claims."""
    async with httpx.AsyncClient(timeout=600.0) as client:
        response = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": NOTE_MODEL,
                "messages": [
                    {"role": "system", "content": NOTE_PROMPT},
                    {"role": "user", "content": "TRANSCRIPT:\n" + format_turns(turns)},
                ],
                "format": NOTE_SCHEMA,
                "stream": False,
                "keep_alive": "30m",
                "options": {
                    "temperature": float(os.getenv("CDS_TEMPERATURE", "0.0")),
                    "seed": int(os.getenv("CDS_SEED", "42")),
                    "num_ctx": 16384,  # a full consultation is long
                },
            },
        )
        response.raise_for_status()
    note = json.loads(response.json()["message"]["content"])

    by_idx = {t["idx"]: t for t in turns}
    for section in ("subjective", "objective", "assessment", "plan"):
        for claim in note[section]:
            valid = sorted({n for n in claim["turns"] if n in by_idx})
            claim["turns"] = valid
            claim["uncited"] = not valid
            claim["flagged"] = bool(
                valid
                and _LOAD_BEARING.search(claim["text"])
                and any(by_idx[n]["confidence"] < LOW_CONFIDENCE for n in valid)
            )
    return note


def note_as_plain_text(note: dict) -> str:
    """EMR-friendly plain text: clean line breaks, no markdown, no citations."""
    lines: list[str] = []
    for section, heading in (
        ("subjective", "S:"),
        ("objective", "O:"),
        ("assessment", "A:"),
        ("plan", "P:"),
    ):
        lines.append(heading)
        for claim in note.get(section, []):
            lines.append(f"  {claim['text']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
