"""The alarm harnesses carry age and sex (owner ruling 2026-10-02, Task 5b). Needs no model.

Task 5 put the patient line at the top of the assessment and urgency
messages, and the live app sends it. The harness scripts called
CDSEngine.update with no patient, so run as they were they tested the app
without the line. app.mock_scripts.SCRIPT_PATIENTS now gives the age and
sex of every script, and scripts/evaluate_urgency.py,
scripts/evaluate_cds_restraint.py (through evaluate_urgency's
evaluate_script) and scripts/simulate_cds.py pass it at every update.

Every model call is recorded at the httpx layer, so these tests see the
user messages the engine would actually send.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
from pathlib import Path

import httpx
import pytest

from app import cds
from app.mock_scripts import SCRIPT_PATIENTS, parse_script, script_patient
from scripts import evaluate_cds_restraint as ecr
from scripts import evaluate_urgency as eu
from scripts import simulate_cds

SCRIPTS_DIR = Path(__file__).parent.parent / "mock_consultations"
SCRIPT_FILES = sorted(p.name for p in SCRIPTS_DIR.glob("*.md") if p.name != "README.md")

REPLIES = {
    cds.ASSESSMENT_PROMPT: {"reasoning": "", "questions_to_ask": [], "signs_to_check": [],
                            "differentials": [{"condition": "Testicular torsion",
                                               "likelihood": "high", "rationale": "pain"}]},
    cds.URGENCY_PROMPT: {"reasoning": "", "time_critical_possible": True,
                         "already_done_or_arranged": False,
                         "urgent_actions": [{"action": "Urgent surgical review",
                                             "reason": "possible torsion"}]},
    cds.AFFECT_PROMPT: {"patient_affect": "anxious"},
}


class Recorder:
    """Stands in for httpx.AsyncClient inside app.cds: records each request
    body and answers by system prompt."""

    def __init__(self):
        self.bodies: list[dict] = []

    def __call__(self, *args, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json=None):  # noqa: A002 - httpx's own keyword
        request = httpx.Request("POST", url, json=json)
        self.bodies.append(json)
        return httpx.Response(200, request=request, json={
            "message": {"content": _dumps(REPLIES[json["messages"][0]["content"]])},
            "done_reason": "stop", "eval_count": 7, "prompt_eval_count": 11})

    def user(self, prompt: str) -> list[str]:
        """The user message of every recorded call with this system prompt."""
        return [b["messages"][1]["content"] for b in self.bodies
                if b["messages"][0]["content"] == prompt]


def _dumps(obj) -> str:
    return json.dumps(obj)


@pytest.fixture
def recorder(monkeypatch) -> Recorder:
    rec = Recorder()
    monkeypatch.setattr(cds.httpx, "AsyncClient", rec)
    return rec


def _header(name: str) -> str:
    for line in (SCRIPTS_DIR / name).read_text(encoding="utf-8").splitlines():
        if line.startswith("**Fictional patient:**"):
            return line.removeprefix("**Fictional patient:**").strip()
    raise AssertionError(f"{name} has no Fictional patient header")


def _assert_every_update_carries(rec: Recorder, line: str, n_updates: int) -> None:
    """Each assessment and urgency message opens with the line and a blank
    line, once; the affect message never carries it. The counts show the
    harness really reached the engine at every update."""
    assessment, urgency, affect = (rec.user(p) for p in (
        cds.ASSESSMENT_PROMPT, cds.URGENCY_PROMPT, cds.AFFECT_PROMPT))
    assert n_updates > 1
    assert len(assessment) == len(urgency) == len(affect) == n_updates
    for message in assessment + urgency:
        assert message.startswith(f"{line}\n\n")
        assert message.count("The patient is") == 1
    for message in urgency:
        assert message.startswith(f"{line}\n\nLIVE TRANSCRIPT SO FAR:\n")
    for message in affect:
        assert "The patient is" not in message


# ------------------------------------------------------------------ the table

def test_every_script_has_an_entry_and_nothing_else_does():
    assert len(SCRIPT_FILES) == 16
    assert sorted(SCRIPT_PATIENTS) == SCRIPT_FILES


@pytest.mark.parametrize("name", SCRIPT_FILES)
def test_each_age_is_the_one_in_the_scripts_own_header(name):
    age, sex = SCRIPT_PATIENTS[name]
    header = _header(name)
    first_age = re.search(r",\s*(\d+)\b", header)
    assert first_age and int(first_age.group(1)) == age, header
    title = header.split()[0].rstrip(".")
    want = {"Mr": "M", "Mrs": "F", "Miss": "F", "Ms": "F"}.get(title)
    if want is None:                       # 10: "Kasun Rajapakse, 15, schoolboy"
        want = "M" if "boy" in header else "F" if "girl" in header else None
    assert sex == want, header


def test_every_entry_gives_a_line():
    for name in SCRIPT_PATIENTS:
        assert cds.patient_line(**script_patient(name)), name


def test_the_line_for_script_10_is_a_15_year_old_boy():
    assert cds.patient_line(**script_patient("10_testicular_torsion_en.md")) \
        == "The patient is a 15-year-old boy."


def test_script_patient_is_none_off_the_table_and_a_fresh_dict_on_it():
    assert script_patient("99_not_a_script.md") is None
    a = script_patient("01_chest_pain_en.md")
    a["age"] = 1
    assert script_patient("01_chest_pain_en.md") == {"age": 52, "sex": "M"}


def test_the_harness_scripts_are_all_on_the_table():
    assert set(eu.EXPECTATIONS) | set(eu.UK_EXPECTATIONS) <= set(SCRIPT_PATIENTS)
    assert set(ecr.RESTRAINT_SPEC) <= set(SCRIPT_PATIENTS)


# --------------------------------------------------------------- the harnesses

@pytest.mark.parametrize("name", list(eu.EXPECTATIONS))
def test_the_urgency_harness_passes_the_patient_at_every_update(recorder, name):
    r = asyncio.run(eu.evaluate_script(name))
    line = cds.patient_line(**script_patient(name))
    _assert_every_update_carries(recorder, line, r["n_updates"])


@pytest.mark.parametrize("name", list(eu.UK_EXPECTATIONS))
def test_the_restraint_harness_passes_the_patient_at_every_update(recorder, name):
    # evaluate_cds_restraint replays through the evaluate_script it imports.
    assert ecr.evaluate_script is eu.evaluate_script
    r = asyncio.run(ecr.evaluate_script(name, expected_fire=eu.UK_EXPECTATIONS[name]))
    line = cds.patient_line(**script_patient(name))
    _assert_every_update_carries(recorder, line, r["n_updates"])


def test_script_10_goes_to_the_model_as_a_15_year_old_boy(recorder):
    asyncio.run(eu.evaluate_script("10_testicular_torsion_en.md"))
    first = recorder.user(cds.URGENCY_PROMPT)[0]
    assert first.split("\n", 1)[0] == "The patient is a 15-year-old boy."


def test_the_urgency_harness_refuses_a_script_off_the_table(recorder, monkeypatch, tmp_path):
    shutil.copy(SCRIPTS_DIR / "01_chest_pain_en.md", tmp_path / "99_off_table.md")
    monkeypatch.setattr(eu, "SCRIPTS_DIR", tmp_path)
    with pytest.raises(KeyError, match="SCRIPT_PATIENTS"):
        asyncio.run(eu.evaluate_script("99_off_table.md", expected_fire=True))
    assert recorder.bodies == []


def test_simulate_cds_passes_the_patient_at_every_update(recorder, capsys):
    path = SCRIPTS_DIR / "12_dizziness_uk.md"
    asyncio.run(simulate_cds.simulate(path, 4))
    n_updates = -(-len(parse_script(path)) // 4)
    _assert_every_update_carries(recorder, "The patient is a 45-year-old man.", n_updates)
    assert "patient: 45 M" in capsys.readouterr().out


def test_simulate_cds_off_the_table_sends_no_line_and_says_so(recorder, capsys, tmp_path):
    path = tmp_path / "99_off_table.md"
    shutil.copy(SCRIPTS_DIR / "12_dizziness_uk.md", path)
    asyncio.run(simulate_cds.simulate(path, 4))
    users = recorder.user(cds.ASSESSMENT_PROMPT) + recorder.user(cds.URGENCY_PROMPT)
    assert len(users) > 2
    assert not any("The patient is" in u for u in users)
    assert "no age or sex sent" in capsys.readouterr().out
