"""The UK drug list (spec 15.9, ruling 2; the details of part two of 5c).
Its source is the monthly data of the Prescription Cost Analysis on the
Open Data Portal of the NHS Business Services Authority, under the Open
Government Licence v3.0 (NOTICE). One command fetches one named month and
makes the list from it; the file and the list stay outside the repo. A
name is a generic name without the words for its salt or its form, or a
brand name as it stands at the front of a branded product's name, before
the strength. A drug is a whole name of the list, never one word of a
longer name (the plan review of part two, change 1)."""

from __future__ import annotations

import csv
import datetime as dt
import difflib
import hashlib
import json
import os
import urllib.request
from pathlib import Path
from typing import Callable

from openconsult.bench.writer import Refused
from openconsult.speech.matching import normalise

SOURCE_PAGE = "https://opendata.nhsbsa.net/dataset/prescription-cost-analysis-pca-monthly-data"
LICENCE = "Open Government Licence v3.0"
NEEDED_COLUMNS = ("YEAR_MONTH", "BNF_PRESENTATION_NAME", "GENERIC_BNF_EQUIVALENT_NAME", "BNF_CHEMICAL_SUBSTANCE",
                  "BNF_CHAPTER_CODE", "BNF_SECTION_CODE", "PREP_CLASS")
# Dressings and appliances are BNF chapters 20 to 23; foods are the section
# of borderline substances and nutrition (the details of part two).
LEFT_OUT_CHAPTERS = ("20", "21", "22", "23")
LEFT_OUT_SECTIONS = ("0904",)
LEAST_NAME_LETTERS = 4
# A name is split at these into names of their own (the plan review of part two).
SPLIT_WORDS = ("with", "and")
SPLIT_MARKS = "()/+"
# The words for a salt or a form, dropped from a name. One named list; a
# draft for the owner.
SALT_AND_FORM_WORDS = frozenset("""
hydrochloride hydrobromide sodium potassium calcium magnesium zinc maleate mesilate mesylate besilate besylate
tosilate sulfate sulphate tartrate bitartrate citrate acetate succinate fumarate phosphate diphosphate bromide
chloride nitrate pamoate embonate stearate oxalate lactate gluconate benzoate propionate valerate
dipropionate furoate palmitate decanoate hyclate pivalate aspartate trometamol hemihydrate monohydrate dihydrate trihydrate anhydrous base free tablet tablets capsule
capsules oral solution suspension injection infusion cream ointment gel drops spray inhaler inhalation powder syrup
elixir liquid sachet sachets patch patches suppository suppositories pessary pessaries enema lozenge lozenges
mouthwash shampoo lotion foam eye ear nasal nebuliser modified release prolonged sustained dispersible effervescent
soluble chewable orodispersible sugar m/r s/r sr mr xl la sf
""".split())
# The list as a way to spot a doubtful name: a page word of fewer letters is
# never in doubt, and a word is close at this share of matching letters, as
# difflib gives it (Cowork's draft from four garbled names of the rehearsal).
LEAST_DOUBT_LETTERS = 5
CLOSE_AT = 0.75


class BadFile(Exception):
    """The month's file cannot be used as it stands."""


# ---------------------------------------------------------------- the fetch

def fetch(url: str, target: Path, urlopen: Callable = urllib.request.urlopen) -> dict:
    """The month's file to target, streamed in bytes, never over a file that
    exists. Gives its size and sha256."""
    target = Path(target)
    if target.exists():
        raise Refused(f"{target} exists and is never written over")
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    digest, size = hashlib.sha256(), 0
    with urlopen(url) as answer, open(partial, "wb") as out:
        for chunk in iter(lambda: answer.read(1 << 20), b""):
            out.write(chunk)
            digest.update(chunk)
            size += len(chunk)
    os.replace(partial, target)
    return {"url": url, "bytes": size, "sha256": digest.hexdigest()}


# ----------------------------------------------------------------- the rule

def _letters(words: list[str]) -> int:
    return sum(1 for w in words for c in w if c.isalpha())


def parts_of(name: str) -> list[str]:
    """The names a product name gives: split at a bracket, a slash, a plus
    sign and the words with and and; each part less the salt and form
    words; a name whose words are all such words is kept whole; a name of
    fewer than four letters is left out."""
    text = name.lower()
    for mark in SPLIT_MARKS:
        text = text.replace(mark, " | ")
    for word in SPLIT_WORDS:
        text = f" {text} ".replace(f" {word} ", " | ")
    whole = [w for w in text.replace("|", " ").split() if w]
    if whole and all(w in SALT_AND_FORM_WORDS for w in whole):
        parts = [whole]
    else:
        parts = [[w for w in part.split() if w not in SALT_AND_FORM_WORDS] for part in text.split("|")]
    found = []
    for words in parts:
        words = normalise(" ".join(words))
        if words and _letters(words) >= LEAST_NAME_LETTERS:
            found.append(" ".join(words))
    return found


def brand_front(presentation: str) -> str:
    """The words at the front of a branded product's name, before the first
    word that holds a digit (the strength) or is a form word."""
    front = []
    for word in presentation.split():
        if any(c.isdigit() for c in word) or word.lower() in SALT_AND_FORM_WORDS:
            break
        front.append(word)
    return " ".join(front)


def make_list(path: Path, month: str) -> dict:
    """The list from one month's file: every row but dressings, appliances
    and foods; a generic name from the chemical substance, a brand name from
    the front of a product that is not its own generic equivalent."""
    names: dict[str, dict] = {}
    rows = kept = 0
    dropped = {"chapters": {}, "sections": {}, "no_substance": 0}
    classes: dict[str, dict[str, int]] = {}
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in NEEDED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise BadFile(f"{Path(path).name} lacks the columns {', '.join(missing)}")
        for row in reader:
            rows += 1
            if str(row["YEAR_MONTH"]).strip() != month:
                raise BadFile(f"row {rows} is of {row['YEAR_MONTH']}, not {month}")
            chapter, section = str(row["BNF_CHAPTER_CODE"]).strip(), str(row["BNF_SECTION_CODE"]).strip()
            substance = str(row["BNF_CHEMICAL_SUBSTANCE"]).strip()
            if chapter in LEFT_OUT_CHAPTERS:
                dropped["chapters"][chapter] = dropped["chapters"].get(chapter, 0) + 1
                continue
            if section[:4] in LEFT_OUT_SECTIONS:
                dropped["sections"][section[:4]] = dropped["sections"].get(section[:4], 0) + 1
                continue
            if not substance:
                dropped["no_substance"] += 1
                continue
            kept += 1
            presentation = str(row["BNF_PRESENTATION_NAME"]).strip()
            own_generic = presentation == str(row["GENERIC_BNF_EQUIVALENT_NAME"]).strip()
            by_class = classes.setdefault(str(row["PREP_CLASS"]).strip(), {"own_generic_equivalent": 0, "not": 0})
            by_class["own_generic_equivalent" if own_generic else "not"] += 1
            for name in parts_of(substance):
                _count(names, name, "generic")
            if not own_generic:
                for name in parts_of(brand_front(presentation)):
                    _count(names, name, "brand")
    listed = sorted(names.values(), key=lambda n: n["name"])
    return {"source": SOURCE_PAGE, "licence": LICENCE, "month": month, "file": Path(path).name,
            "file_sha256": _sha256(path), "file_bytes": Path(path).stat().st_size, "rows": rows, "rows_kept": kept,
            "dropped": dropped, "prep_class": classes, "made_on": dt.date.today().isoformat(),
            "names_count": len(listed), "one_word_names": sum(1 for n in listed if " " not in n["name"]),
            "longer_names": sum(1 for n in listed if " " in n["name"]), "names": listed}


def _count(names: dict, name: str, kind: str) -> None:
    entry = names.setdefault(name, {"name": name, "kind": kind, "rows": 0})
    entry["rows"] += 1
    if kind == "generic":
        entry["kind"] = "generic"             # a brand that is also a generic name is kept once, as generic


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_list(target: Path, listed: dict) -> Path:
    target = Path(target)
    if target.exists():
        raise Refused(f"{target} exists and is never written over")
    target.write_text(json.dumps(listed, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


# ------------------------------------------------------------- the lookups

class DrugList:
    """The stored list, for the three ways and the notes."""

    def __init__(self, listed: dict):
        self.names = {n["name"]: n for n in listed["names"]}
        self.one_word = sorted(n for n in self.names if " " not in n)
        self.longer = [tuple(n.split()) for n in self.names if " " in n]
        self.longest = max((len(n) for n in self.longer), default=1)
        self.month = listed.get("month")
        self.count = len(self.names)

    @classmethod
    def read(cls, path: Path) -> "DrugList":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def is_whole_name(self, words: list[str]) -> bool:
        return " ".join(words) in self.names

    def in_list_at(self, words: list[str], index: int) -> str | None:
        """The whole name the word is in: the word equals a name of one word,
        or it and its neighbours in order equal a whole name of more than one
        word. None when it is in no name."""
        if words[index] in self.names and " " not in words[index]:
            return words[index]
        for length in range(2, self.longest + 1):
            for start in range(max(0, index - length + 1), index + 1):
                if tuple(words[start:start + length]) in self.longer_set:
                    return " ".join(words[start:start + length])
        return None

    @property
    def longer_set(self) -> set:
        if not hasattr(self, "_longer_set"):
            self._longer_set = set(self.longer)
        return self._longer_set

    def close_to(self, word: str) -> str | None:
        """The one-word name the word is close to, letter by letter, or none."""
        found = difflib.get_close_matches(word, self.one_word, n=1, cutoff=CLOSE_AT)
        return found[0] if found else None

    def brand_only(self, name: str) -> bool:
        return self.names.get(name, {}).get("kind") == "brand"


def doubtful_by_list(words: list[str], drugs: DrugList) -> list[dict]:
    """The list as a way: each page word in doubt, with the name it is close
    to; and each page word that is in the list only as a brand, listed so
    that an everyday word that stopped a mark can be seen."""
    marks = []
    for index, word in enumerate(words):
        if len(word) < LEAST_DOUBT_LETTERS or not word.isalpha():
            continue
        whole = drugs.in_list_at(words, index)
        if whole is not None:
            if drugs.brand_only(whole):
                marks.append({"word": index, "brand_only": whole})
            continue
        near = drugs.close_to(word)
        if near is not None:
            marks.append({"word": index, "close_to": near})
    return marks
