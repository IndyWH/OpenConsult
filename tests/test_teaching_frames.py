"""The one module that fills the four frames of teaching (spec 15.14,
rulings 10 to 13 and the details of run 10a: How a frame is filled,
Sampling; 12.3 rules 1 and 3; R24, R31). Every scenario here is made up,
and nothing a model wrote is read."""

import copy
import re
import types

from openconsult.db import open_database
from openconsult.llm.profile import Sampling
from openconsult.prompts import loader
from openconsult.teaching import frames

# A made-up scenario. Every word of its second part begins with q or z and stands nowhere in its first.
SCENARIO = {
    "reasoning": "zzreasoning zzmade zzup",
    "patient": {"name": "Made Up", "age": 40, "sex": "female", "occupation": "tester", "manner": "Speaks plainly.", "parent": ""},
    "opening_words": "I have a made-up ache.",
    "facts": [{"fact": "The ache began on a made-up day.", "tells": "open"}, {"fact": "No made-up fever.", "tells": "asked"}],
    "ideas": "I think it is a made-up strain.",
    "concerns": "I worry about made-up work.",
    "expectations": "I hope for a made-up note.",
    "hidden_agenda": "",
    "examination": [{"examination": "Qexamone", "finding": "qfindone"}, {"examination": "Qexamtwo", "finding": "qfindtwo"}],
    "results": [{"test": "Qtestone", "result": "qresultone"}],
    "differential": [{"diagnosis": "Qdiagone", "must_not_miss": True}, {"diagnosis": "Qdiagtwo", "must_not_miss": False}],
    "investigations": [{"investigation": "Qinvone", "reason": "qreasonone"}],
    "plan": [{"step": "Qstepone", "urgency": "urgent"}, {"step": "Qsteptwo", "urgency": "none"}],
    "safety_net": "Qsafety qnet.",
    "marking_points": {"data_gathering": ["Qpointone.", "Qpointtwo."], "management": ["Qpointthree."], "relating": []},
}
SPOKEN = [("doctor", "first line"), ("patient", "first reply"), ("doctor", "second line"), ("patient", "second reply")]
ANSWERS = {"differential": "an answer x", "investigations": "", "plan": "an answer z"}
CASE_BLOCK = ("THE CASE:\nPATIENT: Made Up, 40, female, tester. Speaks plainly.\nOPENING WORDS: I have a made-up ache.\nFACTS:\n"
              "1. (open) The ache began on a made-up day.\n2. (asked) No made-up fever.\nIDEAS: I think it is a made-up strain.\n"
              "CONCERNS: I worry about made-up work.\nEXPECTATIONS: I hope for a made-up note.\nNOT SAID UNLESS MADE EASY: (nothing)\n"
              "EXAMINATION AND RESULTS:\n1. Qexamone: qfindone\n2. Qexamtwo: qfindtwo\n3. Qtestone: qresultone\n"
              "SAFETY-NET ADVICE: Qsafety qnet.\n\n")
REST = ("MARKING POINTS:\nData gathering and diagnosis:\n1. Qpointone.\n2. Qpointtwo.\nClinical management and medical complexity:\n"
        "3. Qpointthree.\nRelating to others:\n(nothing)\n\nDIFFERENTIAL:\n1. Qdiagone (must not be missed)\n2. Qdiagtwo\n\n"
        "INVESTIGATIONS:\n1. Qinvone\n\nPLAN:\n1. Qstepone (urgency: urgent)\n2. Qsteptwo\n\n"
        "TURNS:\n1. Doctor: first line\n2. Patient: first reply\n3. Doctor: second line\n4. Patient: second reply\n\n"
        "EXAMINED:\nexamine one\nexamine two\n\n"
        "ANSWERS:\nDifferential diagnosis: an answer x\nInvestigations: (nothing)\nPlan and referral: an answer z")


def words_of(text: str) -> set:
    return set(re.findall(r"[a-z]+", text.lower()))


def said_in(part) -> str:
    """Every text a part of a scenario holds, without the names of its fields."""
    if isinstance(part, dict):
        return " ".join(said_in(value) for value in part.values())
    if isinstance(part, list):
        return " ".join(said_in(value) for value in part)
    return part if isinstance(part, str) else ""


def test_15_14_the_case_is_asked_with_its_topic_and_level_and_nothing_else():
    assert frames.case_message("A made-up topic", "hidden") == "TOPIC: A made-up topic\nLEVEL: hidden"


def test_15_14_the_numbers_of_a_scenario_as_the_details_give_them():
    # Findings from 1, the entries of examination and then of results; the examination is given the findings and the request alone.
    assert frames.examination_message(SCENARIO, "Look at the made-up knee.") == (
        "FINDINGS:\n1. Qexamone: qfindone\n2. Qexamtwo: qfindtwo\n3. Qtestone: qresultone\n\nTHE DOCTOR TYPES:\nLook at the made-up knee.")
    # Facts from 1; marking points from 1 across the three headings in their order; the differential, the investigations
    # and the plan each from 1; the turns from 1, doctor and patient alike. A step of urgency none is written without it,
    # a must-not-miss diagnosis by its own layout, an empty heading and an empty answer as the layout's word for nothing.
    assert frames.feedback_message(SCENARIO, SPOKEN, ["examine one", "examine two"], ANSWERS) == CASE_BLOCK + REST
    # The reason of an investigation and the case's own reasoning are written nowhere: no layout holds them.
    assert "qreasonone" not in CASE_BLOCK + REST and "zzreasoning" not in CASE_BLOCK + REST


def test_15_14_ruling_10_the_actor_is_given_part_one_alone():
    built = frames.patient_message(SCENARIO, SPOKEN[:2], "second line")
    assert built == ("WHO YOU ARE:\nMade Up, 40, female, tester. Speaks plainly.\n\nYOUR OPENING WORDS:\nI have a made-up ache.\n\n"
                     "YOUR FACTS:\n1. (open) The ache began on a made-up day.\n2. (asked) No made-up fever.\n\n"
                     "WHAT YOU THINK IS WRONG:\nI think it is a made-up strain.\n\nWHAT WORRIES YOU:\nI worry about made-up work.\n\n"
                     "WHAT YOU HOPE FOR:\nI hope for a made-up note.\n\nWHAT YOU HAVE NOT SAID:\n(nothing)\n\n"
                     "THE CONSULTATION SO FAR:\nDoctor: first line\nPatient: first reply\n\nTHE DOCTOR NOW SAYS:\nsecond line")
    part_two = [value for key, value in SCENARIO.items() if key not in frames.PART_ONE]
    only_in_part_two = words_of(said_in(part_two)) - words_of(said_in(frames.part_one(SCENARIO)))
    assert {"zzreasoning", "qexamone", "qfindone", "qtestone", "qresultone", "qdiagone", "qinvone", "qreasonone", "qstepone",
            "urgent", "qsafety", "qnet", "qpointone", "qpointthree"} <= only_in_part_two
    assert not only_in_part_two & words_of(built)                # no word of the examiner's side reaches the actor
    # The twin: the same words do reach the feedback, which reads both parts.
    assert {"qfindone", "qresultone", "qdiagone", "qstepone", "urgent", "qsafety", "qpointthree"} <= words_of(CASE_BLOCK + REST)
    # Whatever else a scenario holds, the cut to part one drops it before a word is written.
    more = {**copy.deepcopy(SCENARIO), "examiner_note": "zzleak"}
    assert sorted(frames.part_one(more)) == sorted(frames.PART_ONE) and frames.patient_message(more, SPOKEN[:2], "second line") == built


def test_12_3_rule_1_braces_typed_by_a_learner_or_written_in_a_fact_are_never_filled():
    odd = copy.deepcopy(SCENARIO)
    odd["facts"][0]["fact"] = "A fact with {doctor} and {conversation} and {hidden_agenda} in it."
    odd["ideas"] = "{facts}"
    typed = "Show me {findings}, {plan}, {differential} and {facts}."
    built = frames.patient_message(odd, [("doctor", "{opening_words}"), ("patient", "{doctor}")], typed)
    assert "1. (open) A fact with {doctor} and {conversation} and {hidden_agenda} in it." in built
    assert "WHAT YOU THINK IS WRONG:\n{facts}\n" in built and "Doctor: {opening_words}\nPatient: {doctor}\n" in built
    assert built.endswith("THE DOCTOR NOW SAYS:\n" + typed) and "Qdiagone" not in built and "qfindone" not in built
    marked = frames.feedback_message(odd, [("doctor", "{case}"), ("patient", "{points}")], ["{turns}"],
                                     {"differential": "{plan}", "investigations": "{examined}", "plan": "{answer_differential}"})
    assert "1. Doctor: {case}\n2. Patient: {points}\n\nEXAMINED:\n{turns}\n\n" in marked
    assert marked.endswith("Differential diagnosis: {plan}\nInvestigations: {examined}\nPlan and referral: {answer_differential}")
    assert marked.count("Qdiagone") == 1 and marked.count("Qpointone.") == 1
    assert frames.examination_message(odd, "{findings}").endswith("THE DOCTOR TYPES:\n{findings}")


def test_15_14_every_empty_part_is_the_layouts_word_for_nothing_and_no_slot_is_left_open():
    bare = {**copy.deepcopy(SCENARIO), "opening_words": " ", "facts": [], "ideas": "", "concerns": "", "expectations": "",
            "examination": [], "results": [], "differential": [], "investigations": [], "plan": [], "safety_net": "",
            "marking_points": {"data_gathering": [], "management": [], "relating": []}}
    nothing = loader.layout("teaching")["empty"]
    assert nothing == "(nothing)"
    patient = frames.patient_message(bare, [], "")
    assert patient.count(nothing) == 8      # the opening words, the facts, the four of ideas to the hidden agenda, the consultation, the doctor's line
    assert "THE CONSULTATION SO FAR:\n(nothing)\n\nTHE DOCTOR NOW SAYS:\n(nothing)" in patient
    assert frames.examination_message(bare, "  ") == "FINDINGS:\n(nothing)\n\nTHE DOCTOR TYPES:\n(nothing)"
    feedback = frames.feedback_message(bare, [], [], {"differential": "", "investigations": " ", "plan": ""})
    assert feedback.count(nothing) == 19    # eight of the case; three headings; the three lists; the turns; what was examined; three answers
    assert "TURNS:\n(nothing)\n\nEXAMINED:\n(nothing)\n\nANSWERS:\nDifferential diagnosis: (nothing)" in feedback
    for built in (patient, feedback, frames.examination_message(SCENARIO, "x"), frames.case_message("t", "l"),
                  frames.patient_message(SCENARIO, SPOKEN, "x"), frames.feedback_message(SCENARIO, SPOKEN, ["x"], ANSWERS)):
        assert not re.search(r"\{[a-z_]+\}", built)


def test_15_14_ruling_10_for_a_child_the_parent_who_speaks_stands_on_the_next_line():
    child = copy.deepcopy(SCENARIO)
    child["patient"].update(name="Made Child", age=4, parent="Made Parent")
    assert frames.patient_message(child, [], "x").startswith(
        "WHO YOU ARE:\nMade Child, 4, female, tester. Speaks plainly.\nThe parent who speaks for the child: Made Parent\n\nYOUR OPENING WORDS:")
    assert "PATIENT: Made Child, 4, female, tester. Speaks plainly.\nThe parent who speaks for the child: Made Parent\nOPENING WORDS:" in (
        frames.feedback_message(child, [], [], ANSWERS))
    assert "The parent who speaks" not in frames.patient_message(SCENARIO, [], "x")


def test_15_14_the_case_alone_has_its_own_temperature_and_a_seed_drawn_afresh(monkeypatch):
    drawn = iter([7, 2 ** 31 - 1])
    monkeypatch.setattr(frames.secrets, "randbelow", lambda below: next(drawn) if below == 2 ** 31 else -1)
    assert frames.case_sampling() == Sampling(0.7, 7) and frames.case_sampling() == Sampling(0.7, 2 ** 31 - 1)


def test_R24_R31_run_10a_builds_the_words_alone_no_route_and_no_table_of_teaching(app, tmp_path):
    # The module reaches the loader and the profile's sampling, and nothing of the clinic (R24).
    reached = {value.__name__ for value in vars(frames).values() if isinstance(value, types.ModuleType)}
    assert reached == {"secrets", "openconsult.prompts.loader"} and frames.Sampling.__module__ == "openconsult.llm.profile"
    # Nothing a learner can see is built in run 10a (R31): no page or route, and no table.
    paths = list(app.openapi()["paths"])
    assert "/settings" in paths and not [path for path in paths if "teach" in path.lower()]
    db = open_database(tmp_path / "made.db")
    assert not [row["name"] for row in db.query("SELECT name FROM sqlite_master") if "teach" in row["name"].lower()]
    db.close()
