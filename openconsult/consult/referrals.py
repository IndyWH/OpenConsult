"""The referral list (spec 15.12, rulings 2 and 8; R2, R5, R11, R20,
R30): one call on the approved note, once per approved note, and the
sorting of its items by code, whatever the model marked. An item is one
the doctor stated when a line it cites is a Plan entry whose words hold
the specialty's words; every other item is the model's suggestion. A
failed call keeps its row with the failure and no item, and nothing is
asked a second time by itself (10.4)."""

from __future__ import annotations

from dataclasses import dataclass

from openconsult.consult import referral_note
from openconsult.consult.letter_rows import ItemRow, Letters, ListRow
from openconsult.consult.referral_note import NoteLine
from openconsult.llm.door import Door
from openconsult.patients.audit import Audit
from openconsult.speech.matching import normalise

STATED, SUGGESTED, NAMED = "stated", "suggested", "named"


@dataclass(frozen=True)
class Item:
    kind: str
    specialty: str
    title: str
    reason: str
    urgency: str
    lines: list
    position: int


def holds_words(text: str, wanted: str) -> bool:
    """The wanted words stand in the text as a contiguous whole-word run,
    both through matching.normalise (as alarms.matched_names matches)."""
    words, run = normalise(str(text or "")), normalise(str(wanted or ""))
    return bool(run) and any(words[i:i + len(run)] == run for i in range(len(words) - len(run) + 1))


def states_referral(line: NoteLine, specialty: str) -> bool:
    """A Plan entry line that holds the specialty's words states that referral (ruling 2)."""
    return line.section == "plan" and not line.heading and holds_words(line.text, specialty)


def sort_items(answer: dict, lines: list[NoteLine]) -> list[Item]:
    """The model's items sorted by code: the specialty empty, dropped; the
    line numbers kept are those that exist; stated when a kept line
    states the referral, else suggested, whatever the model marked.
    Stated first in the model's order, then suggested in the model's
    order, positions from 0."""
    by_number = {line.n: line for line in lines}
    stated, suggested = [], []
    for given in answer.get("referrals") or []:
        if not isinstance(given, dict):
            continue
        specialty = str(given.get("specialty") or "").strip()
        if not specialty:
            continue
        kept = [n for n in (given.get("lines") or []) if isinstance(n, int) and not isinstance(n, bool) and n in by_number]
        is_stated = any(states_referral(by_number[n], specialty) for n in kept)
        fields = (specialty, str(given.get("title") or "").strip(), str(given.get("reason") or "").strip(),
                  given.get("urgency") if given.get("urgency") in ("urgent", "routine") else "routine", kept)
        (stated if is_stated else suggested).append(fields)
    found = []
    for kind, group in ((STATED, stated), (SUGGESTED, suggested)):
        for fields in group:
            found.append(Item(kind, *fields, len(found)))
    return found


def make_list(door: Door, letters: Letters, notes, consultations, audit: Audit, consultation_id: int,
              again: bool = False) -> dict:
    """The one call for the list, once per approved note: the message of
    the detail, the sorting, the rows (the note lines sent as the named
    part of ruling 11), the audit line with counts and never a word. A
    second call for the same approval gives back the list that stands;
    with again, a list whose call failed gives way to a new call (R30):
    its model_call row and its audit line are the record of the failure."""
    with letters.list_lock:
        standing = letters.list_of(consultation_id)
        if standing is not None and again and standing["failure"]:
            letters.drop_failed_list(standing["id"])
            standing = None
        if standing is not None:
            return standing
        approval = notes.approval(consultation_id)
        if approval is None:
            raise ValueError(f"consultation {consultation_id} has no approved note (R5)")
        row = consultations.get(consultation_id)
        lines = referral_note.numbered_lines(approval["text"])
        result = door.ask("referrals", referral_note.list_message(approval["text"], referral_note.patient_of(row)),
                          consultation_id=consultation_id)
        items = sort_items(result.answer, lines) if result.ok else []
        failure = None if result.ok else f"{result.failure}: {result.detail}"
        reasoning = str(result.answer.get("reasoning") or "") if result.ok else None
        list_id = letters.add_list(ListRow(consultation_id, approval["id"], result.call_id, referral_note.list_text(lines),
                                           reasoning, failure, result.wall_ms))
        for item in items:
            letters.add_item(ItemRow(consultation_id, list_id, item.kind, item.specialty, item.title, item.reason, item.urgency,
                                     item.lines, result.call_id, item.position))
        if failure:
            audit.record("referrals.failed", f"consultation {consultation_id}: {failure}")
        else:
            stated = sum(1 for i in items if i.kind == STATED)
            audit.record("referrals.listed", f"consultation {consultation_id}: {stated} stated, {len(items) - stated} suggested, "
                                             f"{result.wall_ms} ms")
        return letters.list_of(consultation_id)


def name_item(letters: Letters, audit: Audit, consultation_id: int, specialty: str, title: str) -> int:
    """The doctor's own item (ruling 8): a specialty and a title typed by
    the doctor, no model call; its position after the named ones so far."""
    position = sum(1 for i in letters.items(consultation_id) if i["kind"] == NAMED)
    item_id = letters.add_item(ItemRow(consultation_id, None, NAMED, specialty.strip(), title.strip(), None, None, [], None, position))
    audit.record("referral.named", f"consultation {consultation_id}: item {item_id}")
    return item_id
