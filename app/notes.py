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

The patient's age and sex come from the record, not the transcript (owner
decision 3 Oct 2026, Task 5d). The note call opens with the CDS's patient
line, and the gate checks every claim's stated age and sex noun against
the record: one that disagrees, and is not someone else's age spoken in a
cited turn, gets `record_mismatch: true` and `flagged: true`. Nothing is
dropped for it. Pronouns are not checked: a note about a woman may rightly
say "he" of her husband.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping

import httpx

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
NOTE_MODEL = os.getenv("CDS_MODEL", "hf.co/unsloth/medgemma-27b-text-it-GGUF:Q4_K_M")
# The shared MedGemma context length (session 5): one value across CDS,
# RAG and this note call, so Ollama never reloads the model between the
# live path and the note path. See the constant's comment in app/cds.py.
from app.cds import CDS_NUM_CTX, patient_line, think_field, with_patient  # noqa: E402

LOW_CONFIDENCE = float(os.getenv("ASR_LOW_CONFIDENCE", "0.60"))
# Below this fraction of validly-cited claims the note is demoted to a
# refusal (same rule as the RAG layer: uncited claims are worthless, and a
# note that is substantially uncited is fabrication, not documentation).
# Seen in the wild: a mic-check transcript produced a fully fabricated
# angina consultation, every claim uncited (consultation #78, 2026-07-15).
MIN_CITED_FRACTION = float(os.getenv("NOTE_MIN_CITED_FRACTION", "0.5"))
# Numbers, dose units, laterality: the content classes where an ASR slip
# changes clinical meaning (gliclazide 80 vs 18; left vs right).
_LOAD_BEARING = re.compile(
    r"\d|\b(mg|ml|mcg|microgram|unit|units|left|right|bilateral)\b", re.IGNORECASE
)
# A stated age ("47yo", "47 y/o", "47-year-old", "47 year old", "aged 47",
# "age 47") and the sex nouns the record check reads. "aged 6 months" is not
# an age in years and is left alone.
_AGE = re.compile(
    r"\b(\d{1,3})\s*(?:yo|y/o)\b"
    r"|\b(\d{1,3})[\s-]*years?[\s-]*old\b"
    r"|\bage[d]?\s+(\d{1,3})\b(?!\s*(?:months?|weeks?|days?)\b)",
    re.IGNORECASE,
)
_SEX_NOUNS = {"male": "M", "man": "M", "boy": "M", "gentleman": "M",
              "female": "F", "woman": "F", "girl": "F", "lady": "F"}
_SEX = r"\b(" + "|".join(_SEX_NOUNS) + r")\b"
_SEX_AFTER_AGE = re.compile(r"[\s,-]*" + _SEX, re.IGNORECASE)    # "47yo male"
_SEX_BEFORE_AGE = re.compile(_SEX + r"[\s,]*$", re.IGNORECASE)   # "male, 47yo"
_SEX_OPENING = re.compile(r"\W*" + _SEX, re.IGNORECASE)          # "Male presenting…"

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
factors, medications, relevant negatives. IF (and only if) the \
transcript contains them, END this section with the patient's ICE as up \
to three labelled entries, in this order: "Patient's ideas: …" (what \
they think is going on), "Patient's concerns: …" (what they are worried \
about), "Patient's expectations: …" (what they hoped for from the \
visit — a test, a referral, reassurance, a certificate). ICE is what \
the PATIENT volunteered or answered, never what the doctor proposed or \
offered. Each ICE entry cites its turns like any claim. If the \
transcript has no ICE content, omit the labelled entries entirely — no \
"not elicited" filler.
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


SECTIONS = ("subjective", "objective", "assessment", "plan")


def record_mismatch(text: str, cited_text: str, age: int, sex: str) -> bool:
    """Whether a claim states an age or a sex the record contradicts.

    An age that is not the record's is a mismatch unless the number is in
    the text of the claim's cited turns: then it is someone else's age
    ("mum died of a stroke aged 72") and the sex noun tied to it is theirs
    too. A sex noun is read where it is tied to the stated age ("47yo male",
    "woman aged 31") or opens the claim ("Male presenting with…"). Pronouns
    are not read."""
    for match in _AGE.finditer(text):
        stated = int(next(group for group in match.groups() if group))
        if stated != age:
            if re.search(rf"(?<!\d){stated}(?!\d)", cited_text):
                continue                 # spoken in a cited turn: not the patient's
            return True
        tied = [_SEX_AFTER_AGE.match(text, match.end()),
                _SEX_BEFORE_AGE.search(text[:match.start()])]
        if any(m and _SEX_NOUNS[m[1].lower()] != sex for m in tied):
            return True
    opening = _SEX_OPENING.match(text)
    return bool(opening and _SEX_NOUNS[opening[1].lower()] != sex)


def validate_and_gate(note: dict, turns: list[dict],
                      patient: Mapping | None = None) -> dict:
    """Validate citations, flag risky claims, and demote ungrounded notes.

    Pure post-processing on the model's output — separated from the model
    call so the gating logic is testable without Ollama.

    The demotion rule mirrors the RAG layer: every claim must cite real
    transcript turns; when fewer than MIN_CITED_FRACTION of claims do (or
    the note has no claims at all), the whole draft is replaced by a
    refusal. A substantially-uncited note is fabrication — the model
    inventing a plausible consultation the transcript never contained —
    and must never be presented for review or approval.

    With a patient whose age and sex are usable (the ones that give the
    patient line), each claim is also checked against the record
    (record_mismatch): a claim that contradicts it is kept, cited as
    before, and gets `record_mismatch: true` and `flagged: true`. Without
    one, the output is exactly what it was before the check existed.
    """
    check = patient is not None and patient_line(patient.get("age"),
                                                 patient.get("sex")) is not None
    by_idx = {t["idx"]: t for t in turns}
    total = cited = 0
    for section in SECTIONS:
        for claim in note[section]:
            valid = sorted({n for n in claim["turns"] if n in by_idx})
            claim["turns"] = valid
            claim["uncited"] = not valid
            total += 1
            cited += bool(valid)
            claim["flagged"] = bool(
                valid
                and _LOAD_BEARING.search(claim["text"])
                and any(by_idx[n]["confidence"] < LOW_CONFIDENCE for n in valid)
            )
            if check and record_mismatch(
                    claim["text"], "\n".join(by_idx[n]["text"] for n in valid),
                    patient["age"], patient["sex"]):
                claim["record_mismatch"] = True
                claim["flagged"] = True

    if total == 0 or cited / total < MIN_CITED_FRACTION:
        return {
            "refusal": True,
            "refusal_reason": (
                "The transcript contains no or insufficient clinical content "
                "to draft a note: "
                + (
                    f"only {cited} of {total} draft claims could cite a "
                    "transcript turn"
                    if total
                    else "the draft contained no claims at all"
                )
                + f" (threshold: {MIN_CITED_FRACTION:.0%} cited). "
                "The suppressed draft was discarded as ungrounded."
            ),
            "claims_total": total,
            "claims_cited": cited,
            **{section: [] for section in SECTIONS},
        }
    return note


async def draft_note(turns: list[dict], patient: Mapping | None = None) -> dict:
    """Generate a cited SOAP note; validate citations; flag risky claims.

    `patient` is the consultation's patient record. Its age and sex open
    the user message as the CDS's patient line (cds.with_patient), and the
    gate checks the claims against them. Nothing else in it is read, so
    the name never reaches the model. Without a usable age and sex the
    request is byte for byte what it was before."""
    async with httpx.AsyncClient(timeout=600.0) as client:
        response = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": NOTE_MODEL,
                "messages": [
                    {"role": "system", "content": NOTE_PROMPT},
                    {"role": "user", "content": with_patient(
                        "TRANSCRIPT:\n" + format_turns(turns), patient)},
                ],
                "format": NOTE_SCHEMA,
                "stream": False,
                "keep_alive": "30m",
                "options": {
                    "temperature": float(os.getenv("CDS_TEMPERATURE", "0.0")),
                    "seed": int(os.getenv("CDS_SEED", "42")),
                    "num_ctx": CDS_NUM_CTX,  # a full consultation is long
                },
                **think_field(),
            },
        )
        response.raise_for_status()
    note = json.loads(response.json()["message"]["content"])
    return validate_and_gate(note, turns, patient)


def note_as_plain_text(note: dict) -> str:
    """EMR-friendly plain text: clean line breaks, no markdown, no citations."""
    if note.get("refusal"):
        return note["refusal_reason"] + "\n"
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
