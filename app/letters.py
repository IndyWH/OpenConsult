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

LETTER_PROMPT = """\
You draft the body of a UK-style GP referral letter ("Dear Colleague" \
register, formal and concise) to the requested specialty.

Your ONLY source is the numbered APPROVED CONSULTATION NOTE provided. \
Rules, all hard:
- Each paragraph's `note_lines` lists the note line number(s) it draws \
on. Every clinical statement must come from those lines. Do not add \
findings, doses, dates, or history the note does not contain.
- Where a referral letter would normally include something the note \
lacks (e.g. examination findings), either omit it or write exactly \
"[to be completed by the referring doctor]" in its place.
- Do NOT write the salutation, the "Re:" line, or the sign-off — only \
the body paragraphs. A short courtesy closing sentence is fine.

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


def format_note_lines(lines: list[str]) -> str:
    return "\n".join(f"[{i + 1}] {line}" for i, line in enumerate(lines))


async def suggest_referrals(note_text: str) -> list[dict]:
    result = await _chat(
        SUGGEST_PROMPT,
        "APPROVED CONSULTATION NOTE:\n" + format_note_lines(note_lines(note_text)),
        SUGGEST_SCHEMA,
    )
    return result["referrals"]


def validate_letter(paragraphs: list[dict], lines: list[str],
                    allowed_numbers: set[str] | None = None) -> dict:
    """Code-side grounding gate, the letter counterpart of
    notes.validate_and_gate. Per paragraph:

    - citations must point at real note lines;
    - a paragraph with clinical load-bearing content (numbers, dose units,
      laterality — the classes that hurt when invented) and no valid
      citations is replaced by the explicit placeholder;
    - every number in a paragraph must literally appear in its cited note
      lines (or in allowed_numbers, e.g. the patient's age which code adds
      to the Re: line) — an unmatched number is an invented number, and
      the paragraph is replaced rather than trusted;
    - a paragraph with no load-bearing content passes uncited only when it
      reads as courtesy boilerplate; otherwise it too must cite.
    """
    allowed = allowed_numbers or set()
    out: list[str] = []
    total = grounded = placeholders = 0
    for para in paragraphs:
        text = para["text"].strip()
        if not text:
            continue
        total += 1
        valid = [n for n in para.get("note_lines", []) if 1 <= n <= len(lines)]
        cited_text = " ".join(lines[n - 1] for n in valid)
        cited_numbers = set(_NUMBER.findall(cited_text)) | allowed
        numbers_ok = all(n in cited_numbers for n in _NUMBER.findall(text))
        needs_citation = bool(_LOAD_BEARING.search(text)) or not _BOILERPLATE.search(text)
        if needs_citation and not valid:
            out.append(PLACEHOLDER)
            placeholders += 1
            continue
        if not numbers_ok:
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
        + format_note_lines(lines),
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
