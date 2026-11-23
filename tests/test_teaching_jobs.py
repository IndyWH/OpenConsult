"""The four jobs of teaching in the door (spec 15.14, the details of run
10a: The four jobs, Sampling; R20, R30; 15.13 rulings 16 and 19): their
limits, the door's own check of each form, what each engine is sent.
Made engines and a made service; what a model writes is never asserted."""

import copy
import json

import pytest

from openconsult.db import open_database
from openconsult.llm import claude
from openconsult.llm.door import Door
from openconsult.llm.jobs import job
from openconsult.llm.record import ModelCalls
from openconsult.prompts import loader
from tests.fakes import FakeEngine
from tests.made_teaching import FITS

LIMITS = {"teaching_case": (4000, 180.0), "teaching_patient": (300, 30.0),
          "teaching_examination": (300, 30.0), "teaching_feedback": (2500, 120.0)}


@pytest.fixture
def record(tmp_path, clock):
    db = open_database(tmp_path / "calls.db")
    yield ModelCalls(db, clock)
    db.close()


def test_R30_15_14_the_four_jobs_carry_their_own_prompt_form_frame_limits_and_what_happens_when_one_fails(record):
    engine = FakeEngine({name: [fits] for name, fits in FITS.items()})
    door = Door(engine, record)
    for name, (max_tokens, timeout_s) in LIMITS.items():
        found = job(name)
        assert (found.prompt, found.form, found.frames) == (name, name, (name,))
        assert (found.max_tokens, found.timeout_s) == (max_tokens, timeout_s)
        assert found.on_failure.startswith("The page says that ") and found.on_failure.endswith(".")
        assert loader.frame(name) and loader.form(found.form)["required"]
        result = door.ask(name, "made-up words")
        call = engine.calls[-1]
        assert result.ok and result.answer == FITS[name]
        assert call.system == loader.prompt(name) and call.form == loader.form(name) and call.user == "made-up words"
        assert (call.max_tokens, call.timeout_s) == (max_tokens, timeout_s)
    assert len({job(name).on_failure for name in LIMITS}) == 4


def without(answer: dict, *path):
    """A copy of a made reply with one field taken out, or set when the last step is a pair."""
    changed = copy.deepcopy(answer)
    at = changed
    for step in path[:-1]:
        at = at[step]
    if isinstance(path[-1], tuple):
        at[path[-1][0]] = path[-1][1]
    else:
        del at[path[-1]]
    return changed


@pytest.mark.parametrize("name, path, reason", [
    ("teaching_patient", ("facts_used",), "answer lacks facts_used"),
    ("teaching_patient", (("facts_used", ["one"]),), "answer.facts_used[0] is not a integer"),
    ("teaching_examination", (("asked", "1 and 2"),), "answer.asked is not a array"),
    ("teaching_examination", ("not_in_case",), "answer lacks not_in_case"),
    ("teaching_feedback", ("points", 0, "turns"), "answer.points[0] lacks turns"),
    ("teaching_feedback", (("most_important_missed", True),), "answer.most_important_missed is a boolean, not a integer"),
    ("teaching_case", ("plan", 0, ("urgency", "soon")), "answer.plan[0].urgency is not one of ['emergency today', 'urgent', 'routine', 'none']"),
    ("teaching_case", ("facts", 1, ("tells", "never")), "answer.facts[1].tells is not one of ['open', 'asked']"),
    ("teaching_case", ("patient", "parent"), "answer.patient lacks parent"),
    ("teaching_case", ("marking_points", "relating"), "answer.marking_points lacks relating"),
])
def test_R30_the_door_refuses_a_reply_that_is_not_the_form_with_its_reason(record, name, path, reason):
    door = Door(FakeEngine({name: [without(FITS[name], *path)]}), record)
    result = door.ask(name, "made-up words")
    assert not result.ok and result.failure == "bad_form" and result.detail == reason
    assert record.rows()[0]["outcome"] == "bad_form" and record.rows()[0]["job"] == name


def objects(form):
    if form.get("type") == "object":
        yield form
    for sub in form.get("properties", {}).values():
        yield from objects(sub)
    if "items" in form:
        yield from objects(form["items"])


def test_15_13_rulings_16_and_19_claudes_copy_of_the_four_forms_closes_every_object_and_changes_nothing_else():
    counted = {}
    for name in LIMITS:
        form, sent = loader.form(name), claude.sent_form(loader.form(name))
        counted[name] = len(list(objects(sent)))
        assert all(node["additionalProperties"] is False for node in objects(sent))
        for node in objects(sent):
            del node["additionalProperties"]
        assert sent == form                       # nothing else was touched: no form of teaching holds a maxItems to take off
        assert "maxItems" not in json.dumps(form) and "minItems" not in json.dumps(form) and "description" not in json.dumps(form)
    assert counted == {"teaching_case": 9, "teaching_patient": 1, "teaching_examination": 1, "teaching_feedback": 5}
