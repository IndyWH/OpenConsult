"""The matching of words (spec 15.9, the details of 5c; ruling 15). Words
of a page are set against the words they are compared with, in order, and
each word of the page is then one of three things: the spoken word, a word
standing in place of a spoken word, or a word standing where nothing was
spoken. It lives in the app because the check for missing speech needs
it (11.5 rule 2); the bench takes it from here.

Capitals and punctuation are ignored. The steps run in one fixed order:
apostrophes, then hyphens and the joining of split words, then numbers,
then units, then spellings. Plain Python only (spec 5.1)."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "`": "'", "´": "'"})
_EDGE_PUNCTUATION = re.compile(r"^[^\w']+|[^\w']+$")
_SLASH_NUMBERS = re.compile(r"^(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)$")
_FIGURE_UNIT = re.compile(r"^(\d+(?:\.\d+)?)([a-z%]+)$")
_SPLIT = re.compile(r"[\s/]+|(?<=\d)/(?=\d)")

# A unit is the same whether written in full or short.
UNITS = {"milligram": "mg", "milligrams": "mg", "mgs": "mg", "gram": "g", "grams": "g",
         "microgram": "mcg", "micrograms": "mcg", "µg": "mcg", "ug": "mcg",
         "millilitre": "ml", "millilitres": "ml", "milliliter": "ml", "milliliters": "ml", "mls": "ml",
         "millimole": "mmol", "millimoles": "mmol", "kilogram": "kg", "kilograms": "kg", "kilo": "kg", "kilos": "kg",
         "centimetre": "cm", "centimetres": "cm", "centimeter": "cm", "centimeters": "cm",
         "percent": "%", "litre": "l", "litres": "l", "liter": "l", "liters": "l"}

# The British and American spellings that count as the same word (ruling
# 15), mapped to the British form. One named table.
SPELLINGS = {
    "anemia": "anaemia", "anemic": "anaemic", "hemoglobin": "haemoglobin", "esophagus": "oesophagus",
    "edema": "oedema", "diarrhea": "diarrhoea", "celiac": "coeliac", "pediatric": "paediatric",
    "fetal": "foetal", "hemorrhage": "haemorrhage", "ischemic": "ischaemic", "leukemia": "leukaemia",
    "gynecology": "gynaecology", "orthopedic": "orthopaedic", "tumor": "tumour", "color": "colour",
    "favorite": "favourite", "behavior": "behaviour", "labor": "labour", "center": "centre",
    "liter": "litre", "meter": "metre", "fiber": "fibre", "program": "programme", "practice": "practise",
    "analyze": "analyse", "organize": "organise", "realize": "realise", "recognize": "recognise",
    "mold": "mould", "gray": "grey", "judgment": "judgement", "aluminum": "aluminium", "sulfur": "sulphur",
    "aging": "ageing", "estrogen": "oestrogen", "anesthetic": "anaesthetic", "hematology": "haematology",
}

_UNITS_WORDS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
                "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
                "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}
_TENS_WORDS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
               "eighty": 80, "ninety": 90}
_SCALE_WORDS = {"hundred": 100, "thousand": 1000}
NUMBER_WORDS = set(_UNITS_WORDS) | set(_TENS_WORDS) | set(_SCALE_WORDS)


def _tokens(text: str) -> list[str]:
    """Step one: apostrophes made plain, lower case, punctuation at the
    edges of a word stripped, a slash between two figures read as the
    word over, a figure against its unit split."""
    found = []
    for raw in text.translate(APOSTROPHES).lower().split():
        slash = _SLASH_NUMBERS.match(raw.strip(".,;:!?()[]\"'"))
        if slash:
            found += [slash.group(1), "over", slash.group(2)]
            continue
        word = _EDGE_PUNCTUATION.sub("", raw)
        if not word:
            continue
        glued = _FIGURE_UNIT.match(word)
        if glued and (glued.group(2) in UNITS or glued.group(2) in UNITS.values()):
            found += [glued.group(1), glued.group(2)]
        else:
            found.append(word)
    return found


def _hyphens(tokens: list[str], joinable: frozenset[str]) -> list[str]:
    """Step two: a hyphen inside a word goes (a name is the same with a
    hyphen, a space or neither), except between two number words, which
    are split. Then adjacent words whose letters joined make a word that is
    hyphenated on the other side are joined."""
    flat = []
    for word in tokens:
        parts = [p for p in word.split("-") if p]
        if len(parts) > 1 and all(p in NUMBER_WORDS for p in parts):
            flat += parts
        else:
            flat.append("".join(parts) if parts else word)
    joined, i = [], 0
    while i < len(flat):
        if i + 1 < len(flat) and flat[i] + flat[i + 1] in joinable:
            joined.append(flat[i] + flat[i + 1])
            i += 2
        else:
            joined.append(flat[i])
            i += 1
    return joined


def _number_of(words: list[str]) -> str:
    total, current, decimal = 0, 0, None
    for word in words:
        if word == "point":
            decimal = ""
        elif decimal is not None:
            decimal += str(_UNITS_WORDS[word])
        elif word in _SCALE_WORDS:
            current = (current or 1) * _SCALE_WORDS[word]
            if word == "thousand":
                total, current = total + current, 0
        elif word != "and":
            current += _UNITS_WORDS.get(word, _TENS_WORDS.get(word, 0))
    figure = str(total + current)
    return figure + ("." + decimal if decimal else "")


def _continues(previous: str, word: str, after: str | None) -> bool:
    """Whether word carries the number on from previous: a scale word
    follows anything; a units word follows a tens word; after a scale word
    any number word or an and followed by one; point before a decimal."""
    if word in _SCALE_WORDS:
        return previous != "and"
    if previous in _SCALE_WORDS:
        return word in NUMBER_WORDS or (word == "and" and after in NUMBER_WORDS)
    if previous in _TENS_WORDS:
        return word in _UNITS_WORDS and 0 < _UNITS_WORDS[word] < 10
    if previous == "and":
        return word in NUMBER_WORDS
    if word == "point":
        return after in _UNITS_WORDS
    return previous == "point" and word in _UNITS_WORDS


def _numbers(tokens: list[str]) -> list[str]:
    """Step three: a number is the same whether written in words or in
    figures. A run of number words becomes one figure; the run ends where
    the grammar of a number ends, so a list of numbers stays a list."""
    out, i = [], 0
    while i < len(tokens):
        if tokens[i] in NUMBER_WORDS:
            j = i + 1
            while j < len(tokens) and _continues(tokens[j - 1], tokens[j], tokens[j + 1] if j + 1 < len(tokens) else None):
                j += 1
            out.append(_number_of(tokens[i:j]))
            i = j
        else:
            out.append(tokens[i])
            i += 1
    return out


def _units(tokens: list[str]) -> list[str]:
    """Step four: a unit written in full becomes its short form; per cent
    becomes %."""
    out, i = [], 0
    while i < len(tokens):
        if tokens[i] == "per" and i + 1 < len(tokens) and tokens[i + 1] == "cent":
            out.append("%")
            i += 2
        else:
            out.append(UNITS.get(tokens[i], tokens[i]))
            i += 1
    return out


def normalise(text: str, joinable: frozenset[str] = frozenset()) -> list[str]:
    """The words of a text, normalised in the fixed order. joinable holds
    the hyphenated words of the other side, with their hyphens removed."""
    tokens = _tokens(text)
    tokens = _hyphens(tokens, joinable)
    tokens = _numbers(tokens)
    tokens = _units(tokens)
    return [SPELLINGS.get(word, word) for word in tokens]


def hyphenated(text: str) -> frozenset[str]:
    """The words of a text that hold a hyphen, as they will read with it
    removed, so the other side's split words can be joined to them."""
    return frozenset("".join(w.split("-")) for w in _tokens(text) if "-" in w.strip("-"))


@dataclass(frozen=True)
class Pair:
    """One place of the alignment. Both indexes set: the page word stands
    at a spoken word's place, as the word itself (heard) or in its place
    (replaced). Page index only: a word where nothing was spoken (nowhere).
    Spoken index only: a spoken word the page has not (missing)."""
    spoken: int | None
    page: int | None
    kind: str          # heard, replaced, missing, nowhere


def align(spoken: list[str], page: list[str]) -> list[Pair]:
    """The words of the page set against the spoken words, in order. A
    block of words that differ pairs up in order; the longer side's extras
    are missing or stand where nothing was spoken."""
    pairs = []
    matcher = difflib.SequenceMatcher(None, spoken, page, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            pairs += [Pair(i, j, "heard") for i, j in zip(range(i1, i2), range(j1, j2))]
            continue
        paired = min(i2 - i1, j2 - j1)
        pairs += [Pair(i1 + k, j1 + k, "replaced") for k in range(paired)]
        pairs += [Pair(i, None, "missing") for i in range(i1 + paired, i2)]
        pairs += [Pair(None, j, "nowhere") for j in range(j1 + paired, j2)]
    return pairs
