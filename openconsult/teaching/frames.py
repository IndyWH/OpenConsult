"""The words of the four teaching jobs (spec 12.2, 12.3; 15.14, rulings 10
to 13 and the details of run 10a): a scenario written into the frames of
the prompts folder by the patterns of teaching.layout.json. No sentence,
heading, label or pattern a model reads is typed here.

A scenario is the form of teaching_case: part one is the patient's side,
part two the examiner's. The actor is given part one alone, so it cannot
name a diagnosis it was never told. A conversation is a list of
(speaker, words), the speaker doctor or patient.

Nothing else of teaching is in the app yet: no table, page, route or
setting (R31)."""

from __future__ import annotations

import secrets

from openconsult.llm.profile import Sampling
from openconsult.prompts import loader
from openconsult.prompts.loader import fill_once

LAYOUT = "teaching"
# Part one of a scenario, the patient's side (ruling 10). The actor is given these and nothing else.
PART_ONE = ("patient", "opening_words", "facts", "ideas", "concerns", "expectations", "hidden_agenda")
HEADINGS = ("data_gathering", "management", "relating")   # the order the marking points are numbered in
NO_URGENCY = "none"
# The case alone is not sent at the profile's steady values: one topic and one level would give every learner the
# same patient. Design choices of Cowork's, measured by the bench of run 10a at exactly this setting (the details).
CASE_TEMPERATURE = 0.7
SEED_BELOW = 2 ** 31


def _text(value, lay: dict) -> str:
    """A part as it is given, or the layout's word for nothing when it is empty."""
    return str(value) if value is not None and str(value).strip() else lay["empty"]


def _rows(rows: list[str], lay: dict) -> str:
    return "\n".join(rows) if rows else lay["empty"]


def part_one(scenario: dict) -> dict:
    """The patient's side alone: what the actor may be given (ruling 10)."""
    return {key: scenario[key] for key in PART_ONE}


def who(scenario: dict, lay: dict) -> str:
    """Who the patient is; for a child, the parent who speaks on the next line."""
    patient = scenario["patient"]
    first = fill_once(lay["who"], name=patient["name"], age=patient["age"], sex=patient["sex"],
                      occupation=patient["occupation"], manner=patient["manner"])
    parent = str(patient.get("parent") or "").strip()
    return first + ("\n" + fill_once(lay["who_parent"], parent=parent) if parent else "")


def facts(scenario: dict, lay: dict) -> str:
    """The facts, numbered from 1 in the order of the list, each with how it is told."""
    return _rows([fill_once(lay["fact"], n=n, tells=fact["tells"], fact=fact["fact"])
                  for n, fact in enumerate(scenario["facts"], 1)], lay)


def findings(scenario: dict, lay: dict) -> str:
    """The findings, numbered from 1: the entries of examination, then the entries of results."""
    rows = [fill_once(lay["finding"], n=n, examination=found["examination"], finding=found["finding"])
            for n, found in enumerate(scenario["examination"], 1)]
    rows += [fill_once(lay["result"], n=n, test=found["test"], result=found["result"])
             for n, found in enumerate(scenario["results"], len(rows) + 1)]
    return _rows(rows, lay)


def points(scenario: dict, lay: dict) -> str:
    """The marking points under their three headings, numbered from 1 across the headings."""
    rows, n = [], 0
    for heading in HEADINGS:
        rows.append(lay["points_heading"][heading])
        under = scenario["marking_points"][heading]
        for point in under:
            n += 1
            rows.append(fill_once(lay["point"], n=n, point=point))
        if not under:
            rows.append(lay["empty"])
    return "\n".join(rows)


def differential(scenario: dict, lay: dict) -> str:
    return _rows([fill_once(lay["diagnosis_must" if found["must_not_miss"] else "diagnosis"], n=n, diagnosis=found["diagnosis"])
                  for n, found in enumerate(scenario["differential"], 1)], lay)


def investigations(scenario: dict, lay: dict) -> str:
    return _rows([fill_once(lay["investigation"], n=n, investigation=found["investigation"])
                  for n, found in enumerate(scenario["investigations"], 1)], lay)


def plan(scenario: dict, lay: dict) -> str:
    """A step whose urgency is none is written without it."""
    return _rows([fill_once(lay["step"], n=n, step=found["step"]) if found["urgency"] == NO_URGENCY else
                  fill_once(lay["step_referral"], n=n, step=found["step"], urgency=found["urgency"])
                  for n, found in enumerate(scenario["plan"], 1)], lay)


def said(conversation: list[tuple[str, str]], lay: dict) -> str:
    """The consultation so far as the actor reads it: who spoke and the words, no numbers."""
    return _rows([fill_once(lay["said_" + speaker], text=text) for speaker, text in conversation], lay)


def turns(conversation: list[tuple[str, str]], lay: dict) -> str:
    """The consultation as the feedback reads it: the turns numbered from 1, doctor and patient alike."""
    return _rows([fill_once(lay["turn_" + speaker], n=n, text=text) for n, (speaker, text) in enumerate(conversation, 1)], lay)


def case_message(topic: str, level: str) -> str:
    return fill_once(loader.frame("teaching_case"), topic=topic, level=level)


def case_sampling() -> Sampling:
    """The sampling of one case: the temperature of the details and a seed drawn afresh, kept in the stored request."""
    return Sampling(CASE_TEMPERATURE, secrets.randbelow(SEED_BELOW))


def patient_message(scenario: dict, conversation: list[tuple[str, str]], doctor: str) -> str:
    """The words of one reply of the patient. Built from part one alone: whatever else the scenario holds is
    dropped before a word is written (ruling 10)."""
    lay, mine = loader.layout(LAYOUT), part_one(scenario)
    return fill_once(loader.frame("teaching_patient"), patient=who(mine, lay), opening_words=_text(mine["opening_words"], lay),
                     facts=facts(mine, lay), ideas=_text(mine["ideas"], lay), concerns=_text(mine["concerns"], lay),
                     expectations=_text(mine["expectations"], lay), hidden_agenda=_text(mine["hidden_agenda"], lay),
                     conversation=said(conversation, lay), doctor=_text(doctor, lay))


def examination_message(scenario: dict, doctor: str) -> str:
    lay = loader.layout(LAYOUT)
    return fill_once(loader.frame("teaching_examination"), findings=findings(scenario, lay), doctor=_text(doctor, lay))


def feedback_message(scenario: dict, conversation: list[tuple[str, str]], examined: list[str], answers: dict) -> str:
    """The whole scenario, the numbered turns, what was asked at the examination and the three answers."""
    lay = loader.layout(LAYOUT)
    case = fill_once(lay["case"], who=who(scenario, lay), opening_words=_text(scenario["opening_words"], lay),
                     facts=facts(scenario, lay), ideas=_text(scenario["ideas"], lay), concerns=_text(scenario["concerns"], lay),
                     expectations=_text(scenario["expectations"], lay), hidden_agenda=_text(scenario["hidden_agenda"], lay),
                     findings=findings(scenario, lay), safety_net=_text(scenario["safety_net"], lay))
    return fill_once(loader.frame("teaching_feedback"), case=case, points=points(scenario, lay),
                     differential=differential(scenario, lay), investigations=investigations(scenario, lay),
                     plan=plan(scenario, lay), turns=turns(conversation, lay),
                     examined=_rows([fill_once(lay["examined"], text=text) for text in examined], lay),
                     answer_differential=_text(answers["differential"], lay),
                     answer_investigations=_text(answers["investigations"], lay), answer_plan=_text(answers["plan"], lay))
