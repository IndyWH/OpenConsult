"""Referral letters (2026-07-24 design pass).

The two-hats principles extend from notes to letters, as hard rules:

- Suggestions and drafts are generated from the APPROVED NOTE TEXT ONLY —
  never the raw transcript, never before approval. A letter must not cite
  content the doctor hasn't signed.
- Letter drafting introduces no new clinical claims: the note is given to
  the model as numbered lines, every paragraph cites the lines it came
  from, and code validates (same spirit as notes.validate_and_gate) —
  an uncited clinical paragraph, or one whose numbers don't appear in its
  cited lines, is replaced by an explicit placeholder rather than trusted.
  Never invent examination findings, doses, or dates.
- Letters are draft-until-approved with their own approve step, and ride
  along with the consultation's void/purge behaviour (FK cascade).
"""

from __future__ import annotations

import json
import os
import re

import httpx
import psycopg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
LETTER_MODEL = os.getenv("CDS_MODEL", "hf.co/unsloth/medgemma-27b-text-it-GGUF:Q4_K_M")

PLACEHOLDER = "[to be completed by the referring doctor]"

# Same content classes notes.py flags: the things that hurt when invented.
_LOAD_BEARING = re.compile(
    r"\d|\b(mg|ml|mcg|microgram|unit|units|left|right|bilateral)\b", re.IGNORECASE
)
# Courtesy boilerplate a letter legitimately contains with nothing to cite.
_BOILERPLATE = re.compile(
    r"thank you|grateful|hesitate to contact|earliest opportunity|"
    r"further information|happy to discuss", re.IGNORECASE
)
_NUMBER = re.compile(r"\d+(?:\.\d+)?")

# Tense fidelity for investigations (owner's QA finding on the #66 letter):
# planned ≠ performed ≠ resulted. A paragraph claiming a result-class verb
# whose cited note lines only use planned-class wording is an upgrade the
# note never made.
_RESULT_WORDS = re.compile(
    r"\b(performed|undertaken|carried out|showed|shows|showing|revealed|"
    r"demonstrated|confirmed|was (?:normal|abnormal)|were (?:normal|abnormal))\b",
    re.IGNORECASE,
)
_PLANNED_WORDS = re.compile(
    r"\b(arranged|planned|requested|ordered|booked|organised|organized|"
    r"will be|to be done)\b", re.IGNORECASE,
)

# The approved note's plain-text section headings, as the review UI
# serialises them ("S:" … "P:"; long forms tolerated defensively).
_HEADING = re.compile(
    r"^(s|o|a|p|subjective|objective|assessment|plan)\s*:?\s*$", re.IGNORECASE
)
_SECTION_KEY = {"s": "subjective", "o": "objective", "a": "assessment", "p": "plan"}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS letter (
    id serial PRIMARY KEY,
    consultation_id int NOT NULL REFERENCES consultation(id) ON DELETE CASCADE,
    specialty text NOT NULL,
    reason text,
    body_draft text NOT NULL,
    body_edited text,
    grounding jsonb,             -- paragraphs total/grounded/placeholders
    status text NOT NULL DEFAULT 'draft',   -- 'draft' | 'approved'
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by int REFERENCES app_user(id),
    approved_at timestamptz,
    approved_by int REFERENCES app_user(id)
);
-- Suggestion cache, one row per note version (regenerating the note
-- invalidates the old suggestions naturally).
CREATE TABLE IF NOT EXISTS letter_suggestion (
    consultation_id int NOT NULL REFERENCES consultation(id) ON DELETE CASCADE,
    note_version int NOT NULL,
    suggestions jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (consultation_id, note_version)
);
"""


def ensure_schema() -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute(SCHEMA_SQL)


async def _conn() -> psycopg.AsyncConnection:
    return await psycopg.AsyncConnection.connect(DATABASE_URL)


# ------------------------------------------------------------- model calls

SUGGEST_SCHEMA = {
    "type": "object",
    "properties": {
        "reasoning": {"type": "string"},
        "referrals": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "specialty": {"type": "string"},
                    "reason": {"type": "string"},
                    "urgency": {"type": "string", "enum": ["routine", "urgent"]},
                },
                "required": ["specialty", "reason", "urgency"],
            },
        },
    },
    "required": ["reasoning", "referrals"],
}

SUGGEST_PROMPT = """\
You review an APPROVED GP consultation note and list the specialist \
referrals the note itself indicates. Use ONLY what the note states — \
typically its Assessment and Plan. Do not propose referrals from your own \
medical judgement of what might additionally be wise: if the note does \
not indicate a referral, the correct output is an empty list, and that is \
a common answer. For each indicated referral give the specialty, a \
one-line reason QUOTING OR CLOSELY PARAPHRASING the note, and whether \
the note frames it as urgent or routine. Fill `reasoning` first (under \
60 words). Output JSON only.\
"""

LETTER_SCHEMA = {
    "type": "object",
    "properties": {
        "reasoning": {"type": "string"},
        "paragraphs": {
            "type": "array",
            "maxItems": 8,
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "note_lines": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["text", "note_lines"],
            },
        },
    },
    "required": ["reasoning", "paragraphs"],
}

# Owner's clinical framework (REFERRAL_LETTER_STYLE.md addendum,
# 2026-07-24): a real GP letter presents the evidence and lets the
# specialist draw the conclusion. Structure and hard rules below are the
# owner's; the citation/masking gates in code are the guarantee.
LETTER_PROMPT = """\
You draft the body of a GP referral letter to the requested specialty, \
in the register of a real GP letter: concise, evidence-first, well under \
a page, every sentence carrying clinical information. No essay style, no \
sympathy padding, no repetition of demographics.

Body paragraphs, in this order:
1. Opening sentence — who is being referred and the presenting problem \
stated as SYMPTOMS, never a diagnosis (e.g. "I would be grateful if you \
would see this 55-year-old man with a two-week history of exertional \
chest tightness."). Add "urgently" only when the note's plan says so.
2. History — the positive and relevant negative points from the note: \
symptoms with duration and pattern, past medical history, family \
history, drug history and allergies, relevant social history. \
Compressed, bullet-like prose; no narrative padding.
3. Examination findings — as recorded in the note, nothing more. Omit \
if none are recorded.
4. Investigations — results only if the note records them. If a test \
was arranged but no result is in the note, say exactly that ("An ECG \
was arranged today") — never upgrade to performed/showed. Planned, \
performed, and resulted are different claims; use the note's wording \
class.
5. Patient expectation — ONE sentence, ONLY if the note contains a \
"Patient's expectations:" entry; cite that line. If there is no such \
entry, omit this entirely — never invent it.
6. Close — at most one neutral sentence ("Thank you for seeing him."). \
Nothing else.

Hard rules:
- NEVER state or imply a diagnosis or differential, yours or the GP's. \
The selection of facts carries the differential; the letter must not \
name it. The note's Assessment section is withheld and must not be \
cited.
- No advice to the consultant: nothing that reads as directing \
specialist management, no "please arrange X", no restating the GP's \
actions as instructions.
- Your ONLY source is the numbered APPROVED CONSULTATION NOTE. Each \
paragraph's `note_lines` lists the line number(s) it draws on; every \
clinical statement must come from those lines. Do not add findings, \
doses, dates, or history the note does not contain — where something is \
missing, omit it or write exactly "[to be completed by the referring \
doctor]".
- Do NOT write the salutation, the "Re:" line, or the sign-off — only \
the body paragraphs.

Fill `reasoning` first (under 60 words). Output JSON only.\
"""


async def _chat(system: str, user: str, schema: dict) -> dict:
    async with httpx.AsyncClient(timeout=600.0) as client:
        response = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": LETTER_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "format": schema,
                "stream": False,
                "keep_alive": "30m",
                "options": {
                    # Deterministic like every clinical output in the app.
                    "temperature": float(os.getenv("CDS_TEMPERATURE", "0.0")),
                    "seed": int(os.getenv("CDS_SEED", "42")),
                    "num_ctx": 8192,
                },
            },
        )
        response.raise_for_status()
    return json.loads(response.json()["message"]["content"])


def note_lines(note_text: str) -> list[str]:
    """The approved note as numbered, non-empty lines — the letter calls'
    only source material and the citation targets for validation."""
    return [line.strip() for line in note_text.splitlines() if line.strip()]


def line_sections(lines: list[str]) -> list[str | None]:
    """Which SOAP section each line belongs to; heading lines are
    'heading'. Lines before any heading are None (cite-able free text)."""
    out: list[str | None] = []
    current: str | None = None
    for line in lines:
        match = _HEADING.match(line)
        if match:
            key = match.group(1).lower()
            current = _SECTION_KEY.get(key, key)
            out.append("heading")
        else:
            out.append(current)
    return out


def citable_line_numbers(lines: list[str]) -> set[int]:
    """1-based line numbers a letter may cite: Subjective, Objective, and
    Plan content. NEVER Assessment (owner's rule: the letter presents the
    evidence and lets the specialist draw the conclusion — a paragraph
    grounded in the GP's stated differential would name it), and headings
    carry no content to ground anything in."""
    return {
        i + 1 for i, section in enumerate(line_sections(lines))
        if section not in ("assessment", "heading")
    }


def format_note_lines(lines: list[str], for_letter: bool = False) -> str:
    """Numbered note. With for_letter, Assessment content is masked in the
    model's copy — the drafting model never even sees the differential, so
    it cannot leak what the citation gate would anyway reject. Numbering
    is preserved so citations validate against the same indices."""
    sections = line_sections(lines) if for_letter else None
    out = []
    for i, line in enumerate(lines):
        text = line
        if for_letter and sections[i] == "assessment":
            text = "[assessment — withheld from referral letters]"
        out.append(f"[{i + 1}] {text}")
    return "\n".join(out)


async def suggest_referrals(note_text: str) -> list[dict]:
    result = await _chat(
        SUGGEST_PROMPT,
        "APPROVED CONSULTATION NOTE:\n" + format_note_lines(note_lines(note_text)),
        SUGGEST_SCHEMA,
    )
    return result["referrals"]


def validate_letter(paragraphs: list[dict], lines: list[str],
                    allowed_numbers: set[str] | None = None,
                    citable: set[int] | None = None) -> dict:
    """Code-side grounding gate, the letter counterpart of
    notes.validate_and_gate. Per paragraph:

    - citations must point at real, CITABLE note lines — Subjective /
      Objective / Plan content only; a citation into the Assessment
      section is discarded (owner's rule: the letter must not carry the
      differential), so a paragraph grounded solely there is replaced;
    - a paragraph with clinical load-bearing content (numbers, dose units,
      laterality — the classes that hurt when invented) and no valid
      citations is replaced by the explicit placeholder;
    - every number in a paragraph must literally appear in its cited note
      lines (or in allowed_numbers, e.g. the patient's age which code adds
      to the Re: line) — an unmatched number is an invented number, and
      the paragraph is replaced rather than trusted;
    - tense fidelity for investigations: a result-class verb (performed /
      showed / revealed…) whose cited lines carry only planned-class
      wording (arranged / requested…) is an upgrade the note never made —
      replaced;
    - a paragraph with no load-bearing content passes uncited only when it
      reads as courtesy boilerplate; otherwise it too must cite.
    """
    allowed = allowed_numbers or set()
    if citable is None:
        citable = citable_line_numbers(lines)
    out: list[str] = []
    total = grounded = placeholders = 0
    for para in paragraphs:
        text = para["text"].strip()
        if not text:
            continue
        total += 1
        valid = [n for n in para.get("note_lines", []) if n in citable]
        cited_text = " ".join(lines[n - 1] for n in valid)
        cited_numbers = set(_NUMBER.findall(cited_text)) | allowed
        numbers_ok = all(n in cited_numbers for n in _NUMBER.findall(text))
        needs_citation = bool(_LOAD_BEARING.search(text)) or not _BOILERPLATE.search(text)
        tense_upgrade = bool(
            valid
            and _RESULT_WORDS.search(text)
            and _PLANNED_WORDS.search(cited_text)
            and not _RESULT_WORDS.search(cited_text)
        )
        if (needs_citation and not valid) or not numbers_ok or tense_upgrade:
            out.append(PLACEHOLDER)
            placeholders += 1
            continue
        grounded += 1
        out.append(text)
    return {
        "body_paragraphs": out,
        "paragraphs_total": total,
        "paragraphs_grounded": grounded,
        "placeholders": placeholders,
    }


def assemble_letter(body_paragraphs: list[str], patient: dict,
                    doctor_name: str) -> str:
    """Salutation, Re: line, and sign-off are code, not model output —
    demographics come from the server-side patient record, never the model."""
    demo = ", ".join(
        str(part) for part in (
            patient.get("name"),
            f"{patient['age']} y" if patient.get("age") is not None else None,
            patient.get("sex"),
        ) if part
    )
    lines = ["Dear Colleague,", ""]
    if demo:
        lines += [f"Re: {demo}", ""]
    for para in body_paragraphs:
        lines += [para, ""]
    lines += ["Yours faithfully,", doctor_name]
    return "\n".join(lines)


async def draft_letter(note_text: str, specialty: str, patient: dict,
                       doctor_name: str) -> dict:
    """Draft + validate a referral letter body from the approved note."""
    lines = note_lines(note_text)
    result = await _chat(
        LETTER_PROMPT,
        f"SPECIALTY: {specialty}\n\nAPPROVED CONSULTATION NOTE:\n"
        + format_note_lines(lines, for_letter=True),
        LETTER_SCHEMA,
    )
    allowed = {str(patient["age"])} if patient.get("age") is not None else set()
    validated = validate_letter(result["paragraphs"], lines, allowed)
    body = assemble_letter(validated["body_paragraphs"], patient, doctor_name)
    return {
        "body": body,
        "grounding": {k: validated[k] for k in
                      ("paragraphs_total", "paragraphs_grounded", "placeholders")},
    }


# ------------------------------------------------------------- persistence

async def cached_suggestions(cid: int, note_version: int) -> list | None:
    async with await _conn() as conn:
        row = await (
            await conn.execute(
                "SELECT suggestions FROM letter_suggestion"
                " WHERE consultation_id = %s AND note_version = %s",
                (cid, note_version),
            )
        ).fetchone()
    return row[0] if row else None


async def save_suggestions(cid: int, note_version: int, suggestions: list) -> None:
    async with await _conn() as conn:
        await conn.execute(
            "INSERT INTO letter_suggestion (consultation_id, note_version, suggestions)"
            " VALUES (%s, %s, %s)"
            " ON CONFLICT (consultation_id, note_version)"
            " DO UPDATE SET suggestions = EXCLUDED.suggestions",
            (cid, note_version, json.dumps(suggestions)),
        )


async def create_letter(cid: int, specialty: str, reason: str | None,
                        body: str, grounding: dict, created_by: int) -> int:
    async with await _conn() as conn:
        row = await (
            await conn.execute(
                "INSERT INTO letter (consultation_id, specialty, reason,"
                " body_draft, grounding, created_by)"
                " VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                (cid, specialty, reason, body, json.dumps(grounding), created_by),
            )
        ).fetchone()
        return row[0]


async def list_letters(cid: int) -> list[dict]:
    async with await _conn() as conn:
        rows = await (
            await conn.execute(
                "SELECT l.id, l.specialty, l.reason, l.body_draft, l.body_edited,"
                " l.grounding, l.status, l.created_at, l.approved_at, u.display_name"
                " FROM letter l LEFT JOIN app_user u ON u.id = l.approved_by"
                " WHERE l.consultation_id = %s ORDER BY l.id",
                (cid,),
            )
        ).fetchall()
    return [
        {"id": r[0], "specialty": r[1], "reason": r[2],
         "body": r[4] if r[4] is not None else r[3],
         "grounding": r[5], "status": r[6],
         "created_at": str(r[7])[:16],
         "approved_at": str(r[8])[:16] if r[8] else None,
         "approved_by": r[9]}
        for r in rows
    ]


async def get_letter(cid: int, lid: int) -> dict | None:
    async with await _conn() as conn:
        row = await (
            await conn.execute(
                "SELECT id, status FROM letter"
                " WHERE id = %s AND consultation_id = %s", (lid, cid),
            )
        ).fetchone()
    return {"id": row[0], "status": row[1]} if row else None


async def update_letter_body(cid: int, lid: int, body: str) -> bool:
    """Doctor's edit of a draft; refused once approved."""
    async with await _conn() as conn:
        row = await (
            await conn.execute(
                "UPDATE letter SET body_edited = %s"
                " WHERE id = %s AND consultation_id = %s AND status = 'draft'"
                " RETURNING id",
                (body, lid, cid),
            )
        ).fetchone()
    return row is not None


async def approve_letter(cid: int, lid: int, approved_by: int) -> bool:
    async with await _conn() as conn:
        row = await (
            await conn.execute(
                "UPDATE letter SET status = 'approved', approved_at = now(),"
                " approved_by = %s"
                " WHERE id = %s AND consultation_id = %s AND status = 'draft'"
                " RETURNING id",
                (approved_by, lid, cid),
            )
        ).fetchone()
    return row is not None
