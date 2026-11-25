"""The bank of scenarios and the topic menu (spec 12.3, rules 5 and 6;
12.5; 15.14, rulings 1 to 4, 17 and 23, and the details of run 10b).
The files of the folder bank are Cowork's, made from a clinician's
scripts, and lie here byte for byte: topics.json, the 26 titles of the
menu in its order, and one file for each scenario. A file is read once,
at start, and held to the form of the case, to a level of the three, to
a topic of the menu and to a label of two. One that does not hold is not
offered, and is counted so that the page can say so. A new file joins by
being put in the folder (ruling 4).

The name of a file and the id inside it name the diagnosis. Neither
leaves this module: a page is given a case's number, its topic, its
level, its label and its scenario, and nothing else of the file."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from openconsult.llm import forms
from openconsult.prompts import loader
from openconsult.teaching.cases import LEVELS

FOLDER = Path(__file__).parent / "bank"
TOPICS_FILE = "topics.json"
TOPIC_GROUPS = ("clinical", "life_stage")          # the order of the menu (ruling 1)
SCRIPT, APPROVED = "script", "approved"
BANK_LABELS = (SCRIPT, APPROVED)                   # a scenario of the bank before and after the owner's word (ruling 3)
CASE_FORM = "teaching_case"


@dataclass(frozen=True)
class BankCase:
    number: int          # Case 1, Case 2, ... in the order of the file names
    topic: str
    level: str
    label: str
    scenario: dict


@dataclass(frozen=True)
class Bank:
    topics: tuple[str, ...]
    cases: tuple[BankCase, ...]
    unread: int          # the files that did not hold and are not offered

    def case(self, number: int) -> BankCase | None:
        return next((case for case in self.cases if case.number == number), None)


def read_topics(folder: Path = FOLDER) -> tuple[str, ...]:
    held = json.loads((Path(folder) / TOPICS_FILE).read_text(encoding="utf-8"))
    return tuple(title for group in TOPIC_GROUPS for title in held[group])


def holds(card, topics: tuple[str, ...]) -> bool:
    """Whether a file of the bank can be offered: the scenario fits the
    form of the case, by the door's own check, and the level, the topic
    and the label are ones the app knows."""
    if not isinstance(card, dict) or not isinstance(card.get("scenario"), dict):
        return False
    if card.get("level") not in LEVELS or card.get("topic") not in topics or card.get("label") not in BANK_LABELS:
        return False
    return forms.misfit(card["scenario"], loader.form(CASE_FORM)) is None


def read_bank(folder: Path = FOLDER) -> Bank:
    """Every scenario file of the folder, in the order of the file names.
    A file that does not hold takes no number."""
    topics = read_topics(folder)
    cases, unread = [], 0
    for path in sorted(Path(folder).glob("*.json")):
        if path.name == TOPICS_FILE:
            continue
        try:
            card = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            card = None
        if holds(card, topics):
            cases.append(BankCase(len(cases) + 1, card["topic"], card["level"], card["label"], card["scenario"]))
        else:
            unread += 1
    return Bank(topics, tuple(cases), unread)
