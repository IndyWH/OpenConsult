"""What code checks of a scenario a model has just written (spec 15.14,
rulings 10, 14 and 23, and the details of run 10b: A fresh scenario; the
owner's okay of 25 Nov 2026 for the third check). The app and the bench
count a dose in a plan by one function. Every scenario here is made up
or is the bank's own; no model is asked."""

import copy
import types

import pytest

from openconsult.bench import teaching_marks
from openconsult.teaching import checks
from openconsult.teaching.bank import read_bank
from tests import made_teaching

SCENARIO = made_teaching.SCENARIO


def with_plan(*steps: str) -> dict:
    return {**copy.deepcopy(SCENARIO), "plan": [{"step": step, "urgency": "none"} for step in steps]}


def test_15_14_mark_six_the_app_and_the_bench_count_a_dose_in_a_plan_by_one_function():
    assert teaching_marks.plan_doses is checks.plan_doses and teaching_marks.DOSE is checks.DOSE
    made = with_plan("A made-up step", "Give 40 mg of a made-up medicine", "Give 2 units", "Review in 2 weeks", "Give 250 micrograms")
    assert checks.plan_doses(made) == [2, 3]                                           # a near form is not the mark, as in run 10a
    row = {"ok": True, "answer": made, "failure": None}
    assert teaching_marks.writer_marks(row)["HARD_MARK_SIX_a_dose_in_the_plan"] == checks.plan_doses(made)
    assert checks.plan_doses(SCENARIO) == [] and checks.plan_doses(with_plan()) == []
    # The teaching package reaches no bench: the bench reads the app's function, never the other way (R31).
    reached = {value.__name__ for value in vars(checks).values() if isinstance(value, types.ModuleType)}
    assert reached == {"re", "openconsult.teaching.frames"}


@pytest.mark.parametrize("change, is_incomplete", [
    ({}, False),
    ({"facts": []}, True),                                                             # no fact: nothing for the patient to say
    ({"differential": []}, True),                                                      # no diagnosis: nothing to set an answer against
    ({"marking_points": {"data_gathering": [], "management": [], "relating": []}}, True),      # no marking point under any heading
    ({"marking_points": {"data_gathering": [], "management": ["Qpoint."], "relating": []}}, False),      # one heading holds a point
    ({"examination": [], "results": [], "investigations": [], "plan": []}, False),     # a case may hold no finding and no plan
], ids=["whole", "no fact", "no diagnosis", "no marking point", "one marking point", "no finding and no plan"])
def test_15_14_a_scenario_with_no_fact_no_marking_point_or_no_diagnosis_is_incomplete(change, is_incomplete):
    assert checks.incomplete({**copy.deepcopy(SCENARIO), **change}) is is_incomplete


def test_15_14_ruling_23_a_scenario_made_from_a_clinicians_script_keeps_its_dose_and_is_offered():
    # The giant cell arteritis scenario holds the clinician's own dose in its plan; the bank is not put through the check.
    bank = read_bank()
    with_dose = [case.number for case in bank.cases if checks.plan_doses(case.scenario)]
    assert with_dose == [4] and bank.unread == 0 and len(bank.cases) == 8
    assert not [case.number for case in bank.cases if checks.incomplete(case.scenario)]
