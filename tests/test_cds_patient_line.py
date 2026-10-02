"""Age and sex reach the model (owner ruling 2026-10-02, Task 5). Needs no model.

One plain line — "The patient is a 31-year-old woman." — opens the user
message of the assessment and urgency calls, then a blank line, then the
message exactly as before. It goes at every pass, and never to the affect
call or the three short auto-mode calls (officer, topic, re-ranker). With
no patient, or no usable age and sex, every request is byte for byte what
it was before.

Every model call is recorded at the httpx layer, so these tests see the
request bodies the app would actually send.
"""

from __future__ import annotations

import asyncio
import json
import re

import httpx
import pytest

from app import cds

TRANSCRIPT = "Doctor: What brings you in?\nPatient: Pain low down on the right side."

PREVIOUS = {
    "reasoning": "right-sided lower abdominal pain",
    "differentials": [
        {"condition": "Appendicitis", "likelihood": "high", "rationale": "RLQ pain"},
        {"condition": "Ovarian cyst", "likelihood": "moderate", "rationale": "pain"},
    ],
    "questions_to_ask": [], "signs_to_check": [],
    "urgency_check": {"time_critical_possible": False,
                      "already_done_or_arranged": False, "reason": ""},
    "urgent_actions": [],
    "patient_affect": "neutral",
}

WOMAN_31 = {"age": 31, "sex": "F"}
LINE_31F = "The patient is a 31-year-old woman."

REPLIES = {
    cds.ASSESSMENT_PROMPT: {"reasoning": "", "differentials": [], "questions_to_ask": [],
                            "signs_to_check": []},
    cds.URGENCY_PROMPT: {"reasoning": "", "time_critical_possible": True,
                         "already_done_or_arranged": False,
                         "urgent_actions": [{"action": "Urgent surgical review",
                                             "reason": "possible appendicitis"}]},
    cds.AFFECT_PROMPT: {"patient_affect": "anxious"},
    cds.OFFICER_PROMPT: {"finished_thought": True, "handed_back": False},
    cds.TOPIC_PROMPT: {"topic": "the pain", "lay": "Can you tell me more about the pain?"},
    cds.RERANK_PROMPT: {"order": ["q1"], "drop": []},
}


class Recorder:
    """Stands in for httpx.AsyncClient inside app.cds: records each request
    body and its bytes, and answers by system prompt. `cap` names the
    prompts whose reply comes back stopped for length (a runaway)."""

    def __init__(self, cap: tuple[str, ...] = ()):
        self.bodies: list[dict] = []
        self.raw: list[bytes] = []
        self.cap = cap

    def __call__(self, *args, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json=None):  # noqa: A002 - httpx's own keyword
        request = httpx.Request("POST", url, json=json)
        self.bodies.append(json)
        self.raw.append(request.content)
        system = json["messages"][0]["content"]
        done = "length" if system in self.cap else "stop"
        return httpx.Response(200, request=request, json={
            "message": {"content": _json(REPLIES[system])}, "done_reason": done,
            "eval_count": 7, "prompt_eval_count": 11})

    def user(self, prompt: str) -> list[str]:
        """The user message of every recorded call with this system prompt."""
        return [b["messages"][1]["content"] for b in self.bodies
                if b["messages"][0]["content"] == prompt]


def _json(obj) -> str:
    return json.dumps(obj)


def _run_update(monkeypatch, previous=None, cap=(), **kwargs) -> Recorder:
    rec = Recorder(cap)
    monkeypatch.setattr(cds.httpx, "AsyncClient", rec)
    asyncio.run(cds.CDSEngine(model="test-model").update(TRANSCRIPT, previous, **kwargs))
    return rec


# --------------------------------------------------------------- the line

@pytest.mark.parametrize("age, sex, want", [
    (31, "F", "The patient is a 31-year-old woman."),
    (46, "M", "The patient is a 46-year-old man."),
    (18, "F", "The patient is a 18-year-old woman."),
    (18, "M", "The patient is a 18-year-old man."),
    (17, "F", "The patient is a 17-year-old girl."),
    (15, "M", "The patient is a 15-year-old boy."),
    (1, "F", "The patient is a 1-year-old girl."),
    (1, "M", "The patient is a 1-year-old boy."),
    (0, "F", "The patient is a baby girl, under 1 year old."),
    (0, "M", "The patient is a baby boy, under 1 year old."),
    (120, "F", "The patient is a 120-year-old woman."),
])
def test_the_line_for_each_case(age, sex, want):
    assert cds.patient_line(age, sex) == want


@pytest.mark.parametrize("age, sex", [
    (None, "F"), (31, None), (None, None),
    (31, "X"), (31, ""), (31, "female"), (31, "U"),
    (-1, "F"), (121, "M"), (True, "F"), (31.0, "F"), ("31", "F"),
])
def test_no_line_without_a_usable_age_and_sex(age, sex):
    assert cds.patient_line(age, sex) is None


def test_with_patient_puts_the_line_first_then_a_blank_line():
    assert cds.with_patient("MESSAGE", WOMAN_31) == f"{LINE_31F}\n\nMESSAGE"
    for none in (None, {}, {"age": 31}, {"sex": "F"}, {"age": None, "sex": None},
                 {"age": 31, "sex": "X"}):
        assert cds.with_patient("MESSAGE", none) == "MESSAGE"
    # Anything beyond age and sex — a name, say — never reaches the line.
    named = cds.with_patient("MESSAGE", {**WOMAN_31, "name": "Ada Example", "id": 7})
    assert named == f"{LINE_31F}\n\nMESSAGE"


# ------------------------------------------- without a patient: unchanged

TODAY_ASSESSMENT = {
    None: f"Here is the transcript of the consultation so far:\n{TRANSCRIPT}",
    "previous": ("We have more information.\n\n"
                 "This is a stale list of possibilities, made from an earlier, shorter "
                 "transcript:\nAppendicitis\nOvarian cyst\n\n"
                 f"Here is the updated transcript of the consultation so far:\n{TRANSCRIPT}"),
}
TODAY_URGENCY = f"LIVE TRANSCRIPT SO FAR:\n{TRANSCRIPT}"


@pytest.mark.parametrize("which", [None, "previous"])
def test_without_a_patient_both_messages_are_todays_exactly(monkeypatch, which):
    previous = PREVIOUS if which else None
    omitted = _run_update(monkeypatch, previous)
    assert omitted.user(cds.ASSESSMENT_PROMPT) == [TODAY_ASSESSMENT[which]]
    assert omitted.user(cds.URGENCY_PROMPT) == [TODAY_URGENCY]
    # patient=None, or a patient row with no usable age and sex (an old
    # row from before 2026-10-02), sends the very same bytes on every call.
    for patient in (None, {"age": None, "sex": None}, {"age": 31, "sex": None},
                    {"age": None, "sex": "F"}, {"age": 31, "sex": "X"}):
        again = _run_update(monkeypatch, previous, patient=patient)
        assert again.raw == omitted.raw, patient
    assert len(omitted.raw) == 3            # assessment, urgency, affect


# ----------------------------------------------- with a patient: the line

@pytest.mark.parametrize("which", [None, "previous"])
def test_the_line_is_the_first_line_and_the_rest_is_unchanged(monkeypatch, which):
    previous = PREVIOUS if which else None
    rec = _run_update(monkeypatch, previous, patient=WOMAN_31)
    [assessment] = rec.user(cds.ASSESSMENT_PROMPT)
    [urgency] = rec.user(cds.URGENCY_PROMPT)
    for sent, today in ((assessment, TODAY_ASSESSMENT[which]), (urgency, TODAY_URGENCY)):
        assert sent.splitlines()[0] == LINE_31F
        assert sent == f"{LINE_31F}\n\n{today}"
        assert sent.count("The patient is") == 1


def test_only_the_user_messages_change(monkeypatch):
    """The system prompts, schemas, options and every other field of the
    request are untouched: only messages[1] differs, and only by the line."""
    plain = _run_update(monkeypatch, PREVIOUS)
    lined = _run_update(monkeypatch, PREVIOUS, patient=WOMAN_31)
    assert len(plain.bodies) == len(lined.bodies) == 3
    for a, b in zip(plain.bodies, lined.bodies):
        assert {k: v for k, v in a.items() if k != "messages"} == \
               {k: v for k, v in b.items() if k != "messages"}
        assert a["messages"][0] == b["messages"][0]
        assert len(a["messages"]) == len(b["messages"]) == 2
        system = a["messages"][0]["content"]
        if system == cds.AFFECT_PROMPT:
            assert a["messages"][1] == b["messages"][1]
        else:
            assert b["messages"][1]["content"] == f"{LINE_31F}\n\n{a['messages'][1]['content']}"


def test_the_affect_message_never_carries_the_line(monkeypatch):
    rec = _run_update(monkeypatch, PREVIOUS, patient=WOMAN_31)
    # Not vacuous: the line did reach this update's other two calls.
    assert rec.user(cds.ASSESSMENT_PROMPT)[0].startswith(LINE_31F)
    assert rec.user(cds.URGENCY_PROMPT)[0].startswith(LINE_31F)
    assert rec.user(cds.AFFECT_PROMPT) == [cds.affect_message(TRANSCRIPT)]
    assert "The patient is" not in rec.user(cds.AFFECT_PROMPT)[0]


def test_the_three_short_auto_mode_calls_never_carry_it(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(cds.httpx, "AsyncClient", rec)
    engine = cds.CDSEngine(model="test-model")

    async def session():
        await engine.update(TRANSCRIPT, None, patient=WOMAN_31)
        await engine.end_of_turn(TRANSCRIPT)
        await engine.topic_for("Where exactly is the pain?")
        await engine.rerank([("q1", "Where exactly is the pain?")], "Patient: on the right.")

    asyncio.run(session())
    # The same engine, in the same session, did send the line to the pass...
    assert rec.user(cds.ASSESSMENT_PROMPT)[0].startswith(LINE_31F)
    # ...and each short call was made, without it.
    for prompt in (cds.OFFICER_PROMPT, cds.TOPIC_PROMPT, cds.RERANK_PROMPT):
        [sent] = rec.user(prompt)
        assert "The patient is" not in sent
        assert "year-old" not in sent and "baby" not in sent


def test_the_runaway_path_still_sends_the_line_to_the_urgency_call(monkeypatch):
    """A runaway assessment never costs the alarm; the alarm it still runs
    is told who the patient is, as a landed pass's would be."""
    rec = Recorder(cap=(cds.ASSESSMENT_PROMPT,))
    monkeypatch.setattr(cds.httpx, "AsyncClient", rec)
    with pytest.raises(cds.CDSRunaway) as caught:
        asyncio.run(cds.CDSEngine(model="test-model").update(TRANSCRIPT, PREVIOUS,
                                                             patient=WOMAN_31))
    assert caught.value.urgency["urgent_actions"]           # the alarm still counted
    assert rec.user(cds.ASSESSMENT_PROMPT)[0].startswith(LINE_31F)
    assert rec.user(cds.URGENCY_PROMPT) == [f"{LINE_31F}\n\n{TODAY_URGENCY}"]
    assert rec.user(cds.AFFECT_PROMPT) == []                 # a runaway pass stops there


def test_the_line_names_no_country():
    """The no-country rule (owner decisions 2026-09-30) covers what this
    adds to a request too."""
    for age, sex in ((0, "F"), (15, "M"), (31, "F"), (46, "M")):
        text = cds.patient_line(age, sex).lower()
        for country in ("sri lanka", "united kingdom", "britain", "england"):
            assert country not in text
        assert not re.search(r"\buk\b", text)
