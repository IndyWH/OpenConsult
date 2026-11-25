"""Made-up teaching material and made-up replies for the tests of run 10a
(spec 15.14): a scenario in the form of teaching_case, a bench folder in
the shape of Cowork's README, and one reply that fits each of the four
forms. Nothing here is a real case, and nothing is what a model wrote."""

from __future__ import annotations

import copy
import json
from pathlib import Path

# Every word of the second part begins with q or z and stands nowhere in the first.
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
    "differential": [{"diagnosis": "Qdiagone", "must_not_miss": True}, {"diagnosis": "Qdiagtwo", "must_not_miss": False},
                     {"diagnosis": "Qdiagthree", "must_not_miss": False}],
    "investigations": [{"investigation": "Qinvone", "reason": "qreasonone"}],
    "plan": [{"step": "Qstepone", "urgency": "urgent"}, {"step": "Qsteptwo", "urgency": "none"}],
    "safety_net": "Qsafety qnet.",
    "marking_points": {"data_gathering": ["Qpointone.", "Qpointtwo.", "Qpointthree."],
                       "management": ["Qpointfour.", "Qpointfive.", "Qpointsix."],
                       "relating": ["Qpointseven.", "Qpointeight.", "Qpointnine."]},
}

# One reply that fits each form.
PATIENT_OK = {"reply": "A made-up reply.", "facts_used": [1]}
EXAMINATION_OK = {"asked": [1, 2], "not_in_case": []}
FEEDBACK_OK = {"reasoning": "made up", "points": [{"number": n, "met": True, "turns": [1]} for n in range(1, 10)],
               "differential": [{"number": 1, "named": True}, {"number": 2, "named": False}, {"number": 3, "named": False}],
               "differential_extra": [], "investigations": [{"number": 1, "named": True}], "investigations_extra": [],
               "plan": [{"number": 1, "named": True}, {"number": 2, "named": False}], "plan_extra": [],
               "most_important_missed": 0, "done_well": [1], "signposted": False, "signpost_turns": []}
CASE_OK = SCENARIO
FITS = {"teaching_case": CASE_OK, "teaching_patient": PATIENT_OK, "teaching_examination": EXAMINATION_OK, "teaching_feedback": FEEDBACK_OK}

BENCH = {
    "red_flag_points": [2],
    "points_not_asserted": [9],
    "lines": [
        {"n": 1, "kind": "open", "doctor": "Tell me about the made-up ache.", "expects_any": [1], "forbids": [2], "meets": [1],
         "reference_reply": "Reference reply one."},
        {"n": 2, "kind": "direct", "doctor": "Any made-up fever?", "expects_any": [2], "forbids": [], "meets": [2],
         "reference_reply": "Reference reply two."},
        {"n": 3, "kind": "absent", "doctor": "Any made-up rash?", "expects_any": [], "forbids": [], "meets": [],
         "reference_reply": "Reference reply three."},
        {"n": 4, "kind": "agenda_closed", "doctor": "Right, anything else?", "expects_any": [], "forbids": [], "meets": [],
         "hidden_must_stay": True, "reference_reply": "Reference reply four."},
    ],
    "examination_requests": [
        {"doctor": "Examine made-up one and two.", "expects": [1, 2], "held": True},
        {"doctor": "Examine a made-up elbow.", "expects": [], "held": False},
        {"doctor": "Send a made-up test away.", "expects": [], "held": False, "neither": True},
    ],
    "answers": [
        {"name": "good", "differential": "Made answer one.", "investigations": "Made answer two.", "plan": "Made answer three.",
         "expects_differential": [1, 2], "expects_investigations": [1], "expects_plan": [1, 2]},
        {"name": "poor", "differential": "Made answer four.", "investigations": "None.", "plan": "Made answer five.",
         "expects_differential": [3], "expects_investigations": [], "expects_plan": []},
    ],
    "transcripts": [
        {"name": "full", "lines": [1, 2, 3], "examined": [1], "answers": "good", "expects_met": [1, 2, 3, 4], "expects_most_important_missed": 0},
        {"name": "one_red_flag_missed", "lines": [1, 3], "examined": [1, 2], "answers": "good", "expects_not_met": [2],
         "expects_most_important_missed": 2},
        {"name": "poor", "lines": [1], "examined": [], "answers": "poor", "expects_not_met": [2, 3, 4], "expects_most_important_missed": None},
    ],
}
RUNS = [{"n": 1, "topic": "A made-up topic", "level": "straightforward"}, {"n": 2, "topic": "Another made-up topic", "level": "hidden"},
        {"n": 3, "topic": "A third made-up topic", "level": "noisy"}]


TOPICS = ("A made-up topic", "Another made-up topic", "A third made-up topic")


def made_bank(unread: int = 0):
    """A made bank as the app holds one after its start (run 10b): two cases, the second approved and with no
    finding at all. Nothing of a file's name or id is in it, as in the app's own."""
    from openconsult.teaching.bank import Bank, BankCase
    second = copy.deepcopy(SCENARIO)
    second.update(examination=[], results=[])
    return Bank(TOPICS, (BankCase(1, TOPICS[0], "straightforward", "script", copy.deepcopy(SCENARIO)),
                         BankCase(2, TOPICS[1], "hidden", "approved", second)), unread)


def case(case_id: str = "01_made") -> dict:
    return {"id": case_id, "source": "made up", "topic": "A made-up topic", "level": "straightforward", "label": "script",
            "not_in_script": [], "left_out": [], "scenario": copy.deepcopy(SCENARIO), "bench": copy.deepcopy(BENCH)}


def second_case() -> dict:
    """A smaller case: two lines, one request, one transcript, no finding at all."""
    made = case("02_made")
    made["scenario"].update(examination=[], results=[])
    made["bench"].update(lines=made["bench"]["lines"][:2], examination_requests=made["bench"]["examination_requests"][1:2],
                         transcripts=[{"name": "full", "lines": [1, 2], "examined": [], "answers": "good", "expects_met": [1],
                                       "expects_most_important_missed": 0}])
    del made["bench"]["points_not_asserted"]
    return made


def write_material(folder: Path, cases=None, runs=None) -> Path:
    """A bench folder in the shape of Cowork's: case_*.json and writer_runs.json."""
    folder.mkdir(parents=True, exist_ok=True)
    for made in cases if cases is not None else [case(), second_case()]:
        (folder / f"case_{made['id']}.json").write_text(json.dumps(made, indent=1), encoding="utf-8")
    listed = runs if runs is not None else RUNS
    (folder / "writer_runs.json").write_text(json.dumps({"topics": [r["topic"] for r in listed], "levels": ["straightforward", "hidden", "noisy"],
                                                         "runs": listed}, indent=1), encoding="utf-8")
    return folder
