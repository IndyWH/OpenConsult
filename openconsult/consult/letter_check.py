"""The letter check (spec 15.12, ruling 4 and its detail; R4, R5): code
reads each sentence of each paragraph against the note lines the
paragraph cites. A heading and an Assessment line are never citable: a
citation into Assessment is dropped and recorded on the paragraph, and
the sentences are judged on the valid lines left (the plan review of
8a, point 1). A sentence fails when its paragraph has no valid line,
when a number in it is not in those lines (the patient's age excepted;
a figure inside a word, as the 2 of T2DM, is a number), when it turns a
planned test into a result, judged per sentence, or when it holds the
placeholder anywhere (ruling 15); an expectation sentence stands only
where a valid line holds the words Patient's expectations followed by a
colon, and is dropped otherwise, never replaced. A failed sentence
becomes the placeholder, one for a run; the letter is refused when fewer
than half its sentences are grounded, or there is none. Ported from v1's
letters.validate_letter as plain functions (6.1), to the spec's rules."""

from __future__ import annotations

import re
from dataclasses import dataclass

from openconsult import words
from openconsult.consult.note import LETTER_GROUNDED_HALF
from openconsult.consult.referral_note import NoteLine
from openconsult.speech.matching import normalise

PLACEHOLDER = words.LETTER_PLACEHOLDER
KEPT, REPLACED, DROPPED = "kept", "placeholder", "dropped"
NO_LINE, NUMBER, UPGRADE, MODEL_PLACEHOLDER = "no_line", "number", "upgrade", "model_placeholder"

_SENTENCE_END = re.compile(r"(?<=[.!?\]])\s+")   # a closing bracket ends the placeholder, so it stands alone
# v1's word lists: a result-class verb over cited lines that only plan the test is an upgrade the note never made.
_RESULT_WORDS = re.compile(
    r"\b(performed|undertaken|carried out|showed|shows|showing|revealed|demonstrated|confirmed|"
    r"was (?:normal|abnormal)|were (?:normal|abnormal))\b", re.IGNORECASE)
_PLANNED_WORDS = re.compile(r"\b(arranged|planned|requested|ordered|booked|organised|organized|will be|to be done)\b",
                            re.IGNORECASE)
# An expectation-class sentence, and the words of the note line that may ground it.
_EXPECTATION_CLASS = re.compile(r"patient'?s expectations|patient (?:wants|would like|hopes|expects|was hoping|is hoping)",
                                re.IGNORECASE)
_EXPECTATION_LINE = re.compile(r"patient'?s expectations\s*:", re.IGNORECASE)
_FIGURE = re.compile(r"\d+(?:\.\d+)?")   # a figure, also inside a word (ruling 15)


@dataclass(frozen=True)
class Checked:
    paragraphs: list      # the body as the check left it, one string a paragraph, empty ones gone
    detail: dict          # per paragraph: the valid lines, the Assessment lines cited, each sentence's verdict
    total: int
    grounded: int
    placeholders: int
    dropped: int
    refused: bool


def sentences_of(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_END.split(str(text or "").strip()) if s.strip()]


def numbers_in(text: str) -> set[str]:
    """The numbers of a text as the normaliser reads them: number words
    become figures, a slash between figures is over, a hyphen is a space
    (so 2-week and two-week are both 2 week), decimals stay, and a figure
    inside a word counts, so type 2 diabetes and T2DM both hold the 2."""
    found = set()
    for word in normalise(str(text or "").replace("-", " ")):
        found.update(_FIGURE.findall(word))
    return found


def expectation_sentence(sentence: str) -> bool:
    return bool(_EXPECTATION_CLASS.search(sentence))


def _upgrade(sentence: str, cited: list[str], allowed: set[str]) -> bool:
    """A result-class verb over cited lines of which one only plans a
    test is an upgrade, judged per sentence (ruling 15): only when no
    cited line holds every number of the sentence (a sentence with no
    number has none held), or when every cited line plans and none holds
    a result verb. So a true result with its own line stands."""
    if not _RESULT_WORDS.search(sentence) or not any(_PLANNED_WORDS.search(text) for text in cited):
        return False
    numbers = numbers_in(sentence)
    held = any(numbers and numbers <= numbers_in(text) | allowed for text in cited)
    all_planned = all(_PLANNED_WORDS.search(text) and not _RESULT_WORDS.search(text) for text in cited)
    return not held or all_planned


def _verdict(sentence: str, cited: list[str], allowed: set[str], has_expectation_line: bool) -> tuple[str, str | None]:
    """cited holds the words of the paragraph's valid lines, one each."""
    if expectation_sentence(sentence) and not has_expectation_line:
        return DROPPED, None
    if not cited:
        return REPLACED, NO_LINE
    if PLACEHOLDER in sentence:
        return REPLACED, MODEL_PLACEHOLDER
    if not numbers_in(sentence) <= (numbers_in(" ".join(cited)) | allowed):
        return REPLACED, NUMBER
    if _upgrade(sentence, cited, allowed):
        return REPLACED, UPGRADE
    return KEPT, None


def check(paragraphs: list[dict], lines: list[NoteLine], allowed_numbers: set[str] = frozenset()) -> Checked:
    """The check over the model's paragraphs (each text and note_lines)
    against the numbered note; allowed_numbers is the patient's age."""
    by_number = {line.n: line for line in lines}
    out, detail = [], []
    total = grounded = placeholders = dropped = 0
    for paragraph in paragraphs:
        cited = [n for n in (paragraph.get("note_lines") or []) if isinstance(n, int) and not isinstance(n, bool)]
        assessment = sorted({n for n in cited if n in by_number and by_number[n].section == "assessment" and not by_number[n].heading})
        valid = sorted({n for n in cited if n in by_number and by_number[n].citable})
        cited = [by_number[n].text for n in valid]
        has_line = any(_EXPECTATION_LINE.search(by_number[n].text) for n in valid)
        kept, verdicts = [], []
        for sentence in sentences_of(paragraph.get("text", "")):
            total += 1
            verdict, reason = _verdict(sentence, cited, set(allowed_numbers), has_line)
            verdicts.append({"text": sentence, "verdict": verdict, "reason": reason})
            if verdict == DROPPED:
                dropped += 1
            elif verdict == REPLACED:
                placeholders += 1
                if not kept or kept[-1] != PLACEHOLDER:
                    kept.append(PLACEHOLDER)
            else:
                grounded += 1
                kept.append(sentence)
        detail.append({"valid": valid, "assessment_cited": assessment, "sentences": verdicts})
        if kept:
            out.append(" ".join(kept))
    refused = total == 0 or grounded / total < LETTER_GROUNDED_HALF
    return Checked(out, {"paragraphs": detail}, total, grounded, placeholders, dropped, refused)


def cites_assessment(detail: dict | None) -> bool:
    return any(p.get("assessment_cited") for p in (detail or {}).get("paragraphs", []))


def reasons_of(detail: dict | None) -> list[str]:
    """Every failed sentence's reason, for the bench's counts."""
    return [s["reason"] for p in (detail or {}).get("paragraphs", []) for s in p["sentences"] if s["reason"]]
