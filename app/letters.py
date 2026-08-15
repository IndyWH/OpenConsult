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

# Expectation-class sentences may exist ONLY when the note records the
# patient's expectations (the ICE bullet): seen live on the #66 regen —
# the model invented "Patient wants investigation of his chest pain"
# from a Plan line. No bullet → no sentence, dropped not placeholdered.
_EXPECTATION_CLASS = re.compile(
    r"patient'?s expectations|patient (?:wants|would like|hopes|expects|"
    r"was hoping|is hoping)", re.IGNORECASE,
)
_EXPECTATION_LINE = re.compile(r"^patient'?s expectations\s*:", re.IGNORECASE)

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
# specialist draw the conclusion. Revised 2026-08-15 by owner decision,
# its craft taken from the owner's Meddbase referral-letter method: four
# paragraphs in a plain spoken register, a silent differential in the
# reasoning field that selects the content and never reaches the page,
# negatives that must earn their place, and a Plan-only exception for
# naming a concern the note itself states. Structure and hard rules below
# are the owner's; the citation/masking gates in code are the guarantee.
LETTER_PROMPT = """\
You draft the body of a GP referral letter to the requested specialty. \
Write it the way a GP hands a case over to a colleague at the desk: \
plain spoken medical English, short sentences, one idea per sentence, \
active voice, verbs doing the work. Past tense for what was found, \
present tense for what is true now. Say "worse at night", not \
"nocturnally exacerbated"; "while", not "whilst"; state the fact instead \
of "it is of note that". No essay style, no filler, no repeated \
demographics. British English.

Before writing, in the `reasoning` field only: list the three or four \
conditions the receiving consultant will weigh, including any that would \
be dangerous to miss. Choose and order the letter's content by what \
separates those conditions. That differential drives every selection and \
NEVER appears in the letter.

Exactly FOUR body paragraphs, in this order:
1. Why you are writing, and the history. Open with one sentence: thank \
you, the patient, and the problem you want an opinion on, stated as \
symptoms, never a diagnosis ("Thank you for seeing this 55-year-old man \
with two weeks of exertional chest tightness."). Then the story in the \
note's chronological order: onset, trigger, how it has changed, what it \
stops the patient doing now. Then the negatives that earn their place — \
a negative earns its place only if it separates conditions in your \
differential, records that a red flag was asked about and absent, or \
saves the consultant repeating a test; every other negative goes. Past \
history that bears directly on this problem belongs here. If the note \
contains a "Patient's expectations:" line, give it in one sentence here, \
citing that line; if there is no such line, write no expectation \
sentence at all.
2. What you found. Examination findings exactly as the note records \
them, in examining order — inspection, palpation, movement, specific \
tests — giving the side. Include a normal finding only where its \
normality narrows the differential. If the note records no examination, \
omit this paragraph.
3. What the tests showed. Results only as the note records them, with \
their units. Planned, performed and resulted are three different claims \
— use the note's wording class ("An ECG was arranged today", never an \
upgrade to performed or showed). If the note records no investigations, \
omit this paragraph.
4. Background. Past history not already covered, current medication with \
doses, allergy status, and the social or occupational detail that \
changes what the patient needs from treatment — all only as the note \
records them. End with the patient's awareness of and agreement to the \
referral, only if the note records it.

Hard rules:
- The differential never reaches the page: no diagnosis, no "?query", no \
list of possibilities — with ONE exception: a concern the note's PLAN \
itself states (a suspected-cancer pathway referral, a red-flag urgency, \
an established diagnosis the consultant is inheriting) may be stated in \
one factual sentence citing that Plan line, together with what raised \
it.
- Ask the consultant for nothing, and tell them nothing to do. No \
"please arrange", no "please consider", no suggested investigations, no \
management advice.
- Never comment on the record: do not write that a symptom, change or \
finding "was not documented" or "was not recorded". Omit it, or use the \
placeholder.
- Your ONLY source is the numbered APPROVED CONSULTATION NOTE. Each \
paragraph's `note_lines` lists the line number(s) it draws on; every \
clinical statement must come from those lines. The Assessment section is \
withheld and must not be cited. Do not add findings, doses, dates, or \
history the note does not contain — where something is missing, omit it \
or write exactly "[to be completed by the referring doctor]".
- Do NOT write the salutation, the "Re:" line, or the sign-off — only \
the body paragraphs.

Fill `reasoning` first (under 80 words). Output JSON only.\
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
    notes.validate_and_gate. Validation is per SENTENCE (owner's spec:
    "every clinical sentence traceable to the note"), each sentence
    checked against its paragraph's cited lines — a bad sentence costs
    itself, not its paragraph. Rules:

    - an expectation-class sentence is kept only when the paragraph cites
      a "Patient's expectations:" note line (the ICE bullet); otherwise
      it is DROPPED entirely — no bullet, no sentence;
    - citations must point at real, CITABLE note lines — Subjective /
      Objective / Plan content only; a citation into the Assessment
      section is discarded (owner's rule: the letter must not carry the
      differential), so a paragraph grounded solely there is replaced;
    - a paragraph with clinical load-bearing content (numbers, dose units,
      laterality — the classes that hurt when invented) and no valid
      citations is replaced by the explicit placeholder;
    - every number in a sentence must literally appear in the cited note
      lines (or in allowed_numbers, e.g. the patient's age which code adds
      to the Re: line) — an unmatched number is an invented number, and
      the sentence is replaced rather than trusted;
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
    total = grounded = placeholders = dropped_expectations = 0
    for para in paragraphs:
        text = para["text"].strip()
        if not text:
            continue
        valid = [n for n in para.get("note_lines", []) if n in citable]
        cited_text = " ".join(lines[n - 1] for n in valid)
        cited_numbers = set(_NUMBER.findall(cited_text)) | allowed
        cites_expectation_line = any(
            _EXPECTATION_LINE.match(lines[n - 1]) for n in valid
        )
        # Sentence-level, per the owner's spec ("every clinical sentence
        # traceable"): one bad sentence costs itself, not the paragraph.
        # All sentences share the paragraph's cited lines.
        kept: list[str] = []
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            sentence = sentence.strip()
            if not sentence:
                continue
            total += 1
            if _EXPECTATION_CLASS.search(sentence) and not cites_expectation_line:
                # An expectation the note never recorded is an invention;
                # the rule is omission ("no bullet → no sentence"), not a
                # placeholder inviting the doctor to fill it in.
                dropped_expectations += 1
                continue
            numbers_ok = all(n in cited_numbers for n in _NUMBER.findall(sentence))
            needs_citation = (bool(_LOAD_BEARING.search(sentence))
                              or not _BOILERPLATE.search(sentence))
            tense_upgrade = bool(
                valid
                and _RESULT_WORDS.search(sentence)
                and _PLANNED_WORDS.search(cited_text)
                and not _RESULT_WORDS.search(cited_text)
            )
            if (needs_citation and not valid) or not numbers_ok or tense_upgrade:
                placeholders += 1
                if not kept or kept[-1] != PLACEHOLDER:  # collapse runs
                    kept.append(PLACEHOLDER)
                continue
            grounded += 1
            kept.append(sentence)
        if kept:
            out.append(" ".join(kept))
    return {
        "body_paragraphs": out,
        "sentences_total": total,
        "sentences_grounded": grounded,
        "placeholders": placeholders,
        "dropped_expectations": dropped_expectations,
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
                      ("sentences_total", "sentences_grounded", "placeholders",
                       "dropped_expectations")},
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
