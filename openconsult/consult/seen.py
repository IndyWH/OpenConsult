"""What the model saw (spec 15.12, rulings 11 and 28; 15.8 ruling 1; R2,
R11, R20, R25): every call of a consultation read back from the record,
each named by the row that references it, its request taken apart into
the parts the builder put in, by the same code that builds each message
for the calls of stages 3 to 7 and from the parts stored by name for the
three calls of stage 8. The reader proves itself by rebuilding: the
parts it reads must give the user text byte for byte through the
builder, or the call is shown whole, marked not taken apart, with the
reason, never guessed at. The prompt is given by its file name and hash
only; nothing here holds its text. Nothing here writes."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime

from openconsult.consult import labels, note as note_module, referral_note
from openconsult.consult.messages import Patient, alarm_message, assessment_message, patient_line, with_background, with_patient
from openconsult.guidelines import summary
from openconsult.llm.jobs import JOBS
from openconsult.prompts import loader

WITH_PATIENT = ("alarm", "assessment", "referrals", "letter", "guideline")
# Why a request was not taken apart; the sentences are words.py's.
NOT_JSON, NO_USER_TEXT, NO_PATIENT_LINE, FRAME_NOT_FOUND, REBUILD_DIFFERS, UNKNOWN_JOB = (
    "not_json", "no_user_text", "no_patient_line", "frame_not_found", "rebuild_differs", "unknown_job")
# The prompt file today against the hash the call was made with.
SAME, DIFFERS, NONE = "same", "differs", "none"
NUMBERED = re.compile(r"^\[(\d+)\] (.*)$")
TURN = re.compile(r"^\[(\d+)\] (Doctor|Patient|Unknown): (.*)$")


@dataclass(frozen=True)
class Part:
    source: str                 # patient_line, background, frame, transcript, stale, lines, turns, note_lines, specialty, query, passages
    text: str
    file: str | None = None     # the frame's file name, for a frame part
    items: list = field(default_factory=list)   # the passages sent, for the passages part


@dataclass
class Seen:
    call: dict                  # the model_call row, less the request and the reply, which the fields below hold as shown
    kind: str                   # the call's job
    name: dict                  # how the record names it: pass_n, n, asked_by, specialty, referenced
    parts: list[Part]
    taken_apart: bool
    reason: str | None
    user_text: str | None       # what is shown whole when the call is not taken apart
    answer: str | None          # the model's answer, word for word
    prompt: dict                # name, hash, today (same, differs or none)
    row: dict | None = None     # the referencing row


# ------------------------------------------------------ the request's texts

def texts_of(request: str) -> tuple[str | None, str | None, str | None]:
    """The system text and the user text of a request as sent: the chat
    body's two messages (vLLM, llama.cpp, Ollama), or the job-and-user
    pair of the made engine and the Call's own parts of a call that never
    reached its engine. Gives (system, user, reason) with the reason set
    when no user text is found."""
    try:
        body = json.loads(request)
    except (ValueError, TypeError):
        return None, None, NOT_JSON
    if not isinstance(body, dict):
        return None, None, NOT_JSON
    found = body.get("messages")
    if isinstance(found, list):
        users = [m.get("content") for m in found if isinstance(m, dict) and m.get("role") == "user"]
        systems = [m.get("content") for m in found if isinstance(m, dict) and m.get("role") == "system"]
        if len(users) == 1 and isinstance(users[0], str):
            return (systems[0] if len(systems) == 1 and isinstance(systems[0], str) else None), users[0], None
        return None, None, NO_USER_TEXT
    user = body.get("user")
    if isinstance(user, str):
        system = body.get("system")
        return (system if isinstance(system, str) else None), user, None
    return None, None, NO_USER_TEXT


def answer_of(reply: str | None) -> str | None:
    """The model's answer word for word: the content of the first choice's
    message (a chat body) or of the message (Ollama's and the made engine's);
    the whole body where neither is there."""
    if reply is None:
        return None
    try:
        body = json.loads(reply)
    except ValueError:
        return reply
    if isinstance(body, dict):
        choices = body.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            content = (choices[0].get("message") or {}).get("content")
            if isinstance(content, str):
                return content
        message = body.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"]
    return reply


PROMPT_WITHHELD = "[the prompt's words, not shown]"


def whole_text(request: str, user: str | None) -> str:
    """What a call not taken apart shows whole: the user text where one
    was found; otherwise the request as sent with every prompt's words
    replaced by a mark, so that the page quotes no prompt even then
    (15.8 ruling 1)."""
    if user is not None:
        return user
    for found in JOBS.values():
        try:
            text = loader.prompt(found.prompt)
        except FileNotFoundError:
            continue
        # As plain text, and as a JSON string's inside with either escaping, which is how a body carries it.
        for form in (text, json.dumps(text)[1:-1], json.dumps(text, ensure_ascii=False)[1:-1]):
            request = request.replace(form, PROMPT_WITHHELD)
    return request


def prompt_of(job: str, prompt_sha256: str) -> dict:
    """The prompt by name and hash, never its text (15.8 ruling 1), and
    whether the file of that name today has the same hash: same, differs,
    or none when there is no such file or job (a prompt renamed later)."""
    found = JOBS.get(job)
    if found is None:
        return {"name": None, "hash": prompt_sha256, "today": NONE}
    name = f"{found.prompt}.prompt.txt"
    try:
        today = loader.sha256(loader.prompt(found.prompt))
    except FileNotFoundError:
        return {"name": name, "hash": prompt_sha256, "today": NONE}
    return {"name": name, "hash": prompt_sha256, "today": SAME if today == prompt_sha256 else DIFFERS}


# ------------------------------------------------------------ the splitting

def unfill(frame_text: str, filled: str, slots: tuple[str, ...]) -> dict | None:
    """The slots' values from a filled frame: the fixed words before, between
    and after the slots must stand where the frame puts them; a middle slot
    runs to the first occurrence of the fixed words after it, the last to
    the end less the frame's tail. None when the fixed words are not found."""
    fixed, remaining = [], frame_text
    for slot in slots:
        before, mark, remaining = remaining.partition("{" + slot + "}")
        if not mark:
            return None
        fixed.append(before)
    fixed.append(remaining)
    if not filled.startswith(fixed[0]):
        return None
    position, values = len(fixed[0]), {}
    for k, slot in enumerate(slots):
        after = fixed[k + 1]
        if k == len(slots) - 1:
            end = len(filled) - len(after)
            if end < position or not filled.endswith(after):
                return None
        else:
            end = filled.find(after, position)
            if end < 0:
                return None
        values[slot] = filled[position:end]
        position = end + len(after)
    return values


def patients_for(row: dict, call_at: str) -> list[Patient]:
    """The patient the line may name: the details the consultation ran with
    (15.11 ruling 2), on the day of the call as the live calls read it, or
    on the day of Start as the stage 8 calls read it (R11)."""
    if not row.get("patient_date_of_birth") or not row.get("patient_sex"):
        return []
    on_call = referral_note.patient_on(row, datetime.fromisoformat(call_at).date())
    at_start = referral_note.patient_of(row)
    return [on_call] if on_call == at_start else [on_call, at_start]


def split_patient(user: str, row: dict, call_at: str) -> tuple[Patient, str, str] | None:
    head, mark, rest = user.partition("\n\n")
    for patient in patients_for(row, call_at):
        if mark and patient_line(patient.age, patient.sex) == head:
            return patient, head, rest
    return None


def split_background(rest: str) -> tuple[str | None, str]:
    """The block of 15.11 ruling 5 by the fixed words of background.frame.txt
    before and after {notes}, read through the loader; one part."""
    head, _, tail = loader.file_text("background.frame").partition("{notes}")
    if rest.startswith(head):
        end = rest.find(tail, len(head))
        if end >= 0 and rest.startswith("\n\n", end + len(tail)):
            return rest[:end + len(tail)], rest[end + len(tail) + 2:]
    return None, rest


def frame_part(name: str) -> Part:
    return Part("frame", loader.frame(name), file=f"{name}.frame.txt")


# --------------------------------------------------------- the kinds' readers

def read_pass_call(kind: str, user: str, row: dict, call: dict) -> tuple[list[Part], str | None]:
    """The alarm and the assessment: the patient line, the block where one
    was sent, the frame, the stale names (later passes) and the transcript;
    rebuilt through cds_pass's own builders."""
    split = split_patient(user, row, call["at"])
    if split is None:
        return [], NO_PATIENT_LINE
    patient, line, rest = split
    block, rest = split_background(rest)
    parts = [Part("patient_line", line)] + ([Part("background", block)] if block else [])
    if kind == "alarm":
        values = unfill(loader.frame("alarm"), rest, ("transcript",))
        if values is None:
            return [], FRAME_NOT_FOUND
        names, frame = (), "alarm"
        rebuilt = alarm_message(values["transcript"])
    else:
        values = unfill(loader.frame("assessment.first"), rest, ("transcript",))
        names, frame = (), "assessment.first"
        if values is None:
            values = unfill(loader.frame("assessment.later"), rest, ("stale", "transcript"))
            if values is None:
                return [], FRAME_NOT_FOUND
            names, frame = tuple(values["stale"].split("\n")), "assessment.later"
        rebuilt = assessment_message(values["transcript"], names)
    if with_background(with_patient(rebuilt, patient), block) != user:
        return [], REBUILD_DIFFERS
    parts.append(frame_part(frame))
    if names:
        parts.append(Part("stale", values["stale"]))
    parts.append(Part("transcript", values["transcript"]))
    return parts, None


def read_lines_call(kind: str, user: str) -> tuple[list[Part], str | None]:
    """The label check and the note: the frame around the numbered lines or
    the turns; no patient line (D3) and no block; rebuilt through the
    builders of labels.py and note.py from the lines read back."""
    values = unfill(loader.frame(kind), user, ("transcript",))
    if values is None:
        return [], FRAME_NOT_FOUND
    text = values["transcript"]
    if kind == "label_check":
        rows = [{"n": int(m.group(1)), "text": m.group(2)} for m in (NUMBERED.match(line) for line in text.split("\n")) if m]
        rebuilt = labels.lines_text(rows)
    else:
        by_word = {word: label for label, word in note_module.ROLE_WORDS.items()}
        turns = [{"n": int(m.group(1)), "label": by_word[m.group(2)], "text": m.group(3)}
                 for m in (TURN.match(line) for line in text.split("\n")) if m]
        rebuilt = note_module.turns_text(turns)
    if rebuilt != user:
        return [], REBUILD_DIFFERS
    return [frame_part(kind), Part("lines" if kind == "label_check" else "turns", text)], None


def read_note_call(kind: str, user: str, row: dict, call: dict, reference: dict | None) -> tuple[list[Part], str | None]:
    """The referral list and the letter: the patient line, the frame, the
    specialty (letter) and the note lines as sent, which are the named part
    of ruling 11 (referral_list.note_lines, letter.note_lines)."""
    split = split_patient(user, row, call["at"])
    if split is None:
        return [], NO_PATIENT_LINE
    patient, line, rest = split
    if kind == "referrals":
        values = unfill(loader.frame("referrals"), rest, ("note",))
        rebuilt = loader.fill(loader.frame("referrals"), note=values["note"]) if values else None
    else:
        values = unfill(loader.frame("letter"), rest, ("specialty", "note"))
        rebuilt = loader.fill(loader.frame("letter"), specialty=values["specialty"], note=values["note"]) if values else None
    if values is None:
        return [], FRAME_NOT_FOUND
    if with_patient(rebuilt, patient) != user:
        return [], REBUILD_DIFFERS
    if reference is not None and reference.get("note_lines") != values["note"]:
        return [], REBUILD_DIFFERS
    parts = [Part("patient_line", line), frame_part(kind)]
    if kind == "letter":
        parts.append(Part("specialty", values["specialty"]))
    parts.append(Part("note_lines", values["note"]))
    return parts, None


def read_guideline_call(user: str, row: dict, call: dict, answer: dict | None) -> tuple[list[Part], str | None]:
    """The summary call from guideline_answer's named parts alone: the
    query and the passages sent, through summary.message, byte for byte."""
    if answer is None:
        return [], FRAME_NOT_FOUND
    for patient in patients_for(row, call["at"]):
        if summary.message(answer["query"], answer["passages"], patient) == user:
            return [Part("patient_line", patient_line(patient.age, patient.sex)),
                    frame_part("guideline"), Part("query", answer["query"]),
                    Part("passages", summary.passages_text(answer["passages"]), items=list(answer["passages"]))], None
    return [], REBUILD_DIFFERS


def read_parts(kind: str, user: str, row: dict, call: dict, reference: dict | None) -> tuple[list[Part], str | None]:
    if kind in ("alarm", "assessment"):
        return read_pass_call(kind, user, row, call)
    if kind in ("label_check", "note"):
        return read_lines_call(kind, user)
    if kind in ("referrals", "letter"):
        return read_note_call(kind, user, row, call, reference)
    if kind == "guideline":
        return read_guideline_call(user, row, call, reference)
    return [], UNKNOWN_JOB


# -------------------------------------------------------- the consultation

def references(consultations, notes, letters, sources, consultation_id: int) -> dict[int, tuple[dict, dict]]:
    """By call id: how the record names the call, and the row that does."""
    found = {}
    for pass_row in consultations.passes(consultation_id):
        for column, kind in (("alarm_call_id", "alarm"), ("assessment_call_id", "assessment")):
            if pass_row[column] is not None:
                found[pass_row[column]] = ({"kind": kind, "pass_n": pass_row["n"]}, pass_row)
    for draft in notes.drafts(consultation_id):
        if draft["call_id"] is not None:
            found[draft["call_id"]] = ({"kind": "note", "n": draft["n"], "asked_by": draft["asked_by"]}, draft)
    listed = letters.list_of(consultation_id)
    if listed is not None and listed["call_id"] is not None:
        found[listed["call_id"]] = ({"kind": "referrals"}, listed)
    for letter in letters.letters(consultation_id):
        if letter["call_id"] is not None:
            item = letters.item(letter["item_id"]) or {}
            found[letter["call_id"]] = ({"kind": "letter", "n": letter["n"], "specialty": item.get("specialty", "")}, letter)
    for answer in sources.answers(consultation_id):
        if answer["call_id"] is not None:
            found[answer["call_id"]] = ({"kind": "guideline", "pass_n": answer["pass_n"], "search_ms": answer["search_ms"]}, answer)
    return found


def seen_call(call: dict, row: dict, named: tuple[dict, dict] | None) -> Seen:
    name, reference = named if named else ({"kind": call["job"]}, None)
    name = {**name, "referenced": named is not None}
    system, user, reason = texts_of(call["request"])
    parts: list[Part] = []
    if reason is None:
        parts, reason = read_parts(call["job"], user, row, call, reference)
    shown = {key: value for key, value in call.items() if key not in ("request", "reply")}
    return Seen(shown, call["job"], name, parts, reason is None, reason, whole_text(call["request"], user),
                answer_of(call["reply"]), prompt_of(call["job"], call["prompt_sha256"]), reference)


def calls_of(consultations, notes, letters, sources, consultation_id: int) -> list[Seen]:
    """Every call of the consultation in time order (model_call.at, then
    id), each named by its row and taken apart; empty for a consultation
    that is not final yet, whose calls are read after it (ruling 28)."""
    row = consultations.get(consultation_id)
    if row is None or row["state"] != "final":
        return []
    named = references(consultations, notes, letters, sources, consultation_id)
    calls = sorted(consultations.model_calls(consultation_id), key=lambda c: (c["at"], c["id"]))
    return [seen_call(call, row, named.get(call["id"])) for call in calls]
