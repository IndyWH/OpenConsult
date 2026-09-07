"""Cap runaway generation (owner decision 2026-09-07, pilot 486 F3), with
the HTTP layer stubbed at httpx's transport so the JSON the engine sends
to Ollama is what is asserted on.

In 486 an assessment call generated 7,211+ tokens for the full 180 s of
the client timeout on Ollama's single slot. What is pinned here: every
call of a pass carries its cap (num_predict); the assessment call's own
timeout is CDS_ASSESSMENT_TIMEOUT_S; a length stop or a timeout on the
assessment call is a CDSRunaway carrying the urgency check's own result
(bookkept as a landed pass would have it), so the caller keeps the
previous assessment and still acts on an alarm; the urgency call is
unaffected. Needs no model.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app import cds
from app.cds import CDSEngine, CDSRunaway

_REAL_CLIENT = httpx.AsyncClient

ASSESSMENT = {"reasoning": "exertional chest pain", "differentials": [],
              "questions_to_ask": ["Does it radiate?"], "signs_to_check": []}
URGENCY = {"reasoning": "new cardiac-sounding chest pain", "time_critical_possible": True,
           "already_done_or_arranged": False,
           "urgent_actions": [{"action": "Bedside ECG", "reason": "exclude ACS"}]}
AFFECT = {"patient_affect": "anxious"}


def _engine(monkeypatch, *, assessment_done="stop", assessment_sleep=0.0):
    """Answer each call by its system prompt; record every request."""
    seen: list[dict] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        system = body["messages"][0]["content"]
        if system == cds.ASSESSMENT_PROMPT:
            if assessment_sleep:
                await asyncio.sleep(assessment_sleep)
            return httpx.Response(200, json={"message": {"content": json.dumps(ASSESSMENT)},
                                             "done_reason": assessment_done, "eval_count": 1500})
        if system == cds.URGENCY_PROMPT:
            return httpx.Response(200, json={"message": {"content": json.dumps(URGENCY)},
                                             "done_reason": "stop", "eval_count": 320})
        return httpx.Response(200, json={"message": {"content": json.dumps(AFFECT)},
                                         "done_reason": "stop", "eval_count": 260})

    monkeypatch.setattr(cds.httpx, "AsyncClient",
                        lambda **kw: _REAL_CLIENT(transport=httpx.MockTransport(handler), **kw))
    return seen


def _caps(seen):
    return {body["messages"][0]["content"][:20]: body["options"].get("num_predict") for body in seen}


def test_every_call_of_a_pass_carries_its_cap_and_a_normal_pass_is_unchanged(monkeypatch):
    seen = _engine(monkeypatch)
    assessment = asyncio.run(CDSEngine().update("I get chest pain on stairs."))
    assert assessment["questions_to_ask"] == ["Does it radiate?"]
    assert assessment["urgent_actions"] == URGENCY["urgent_actions"]
    assert assessment["patient_affect"] == "anxious"
    by_prompt = {body["messages"][0]["content"]: body["options"]["num_predict"] for body in seen}
    assert by_prompt[cds.ASSESSMENT_PROMPT] == cds.CDS_ASSESSMENT_MAX_TOKENS == 1500
    assert by_prompt[cds.URGENCY_PROMPT] == cds.CDS_URGENCY_MAX_TOKENS == 1000
    assert by_prompt[cds.AFFECT_PROMPT] == cds.CDS_AFFECT_MAX_TOKENS == 800
    assert cds.CDS_ASSESSMENT_TIMEOUT_S == 60.0, "the assessment call's own timeout, not 180"


def test_an_assessment_that_hits_its_cap_is_a_runaway_that_still_carries_the_alarm(monkeypatch):
    seen = _engine(monkeypatch, assessment_done="length")
    with pytest.raises(CDSRunaway) as caught:
        asyncio.run(CDSEngine().update("I get chest pain on stairs.", {"questions_to_ask": ["old"]}))
    exc = caught.value
    assert exc.call == "assessment" and exc.reason == "cap"
    assert exc.tokens == 1500 and exc.cap == 1500 and exc.elapsed_ms >= 0
    # The urgency check ran on its own call, after the runaway, bookkept.
    prompts = [body["messages"][0]["content"] for body in seen]
    assert prompts == [cds.ASSESSMENT_PROMPT, cds.URGENCY_PROMPT], "no affect call on a failed pass"
    assert exc.urgency == {
        "urgency_check": {"time_critical_possible": True, "already_done_or_arranged": False,
                          "reason": "new cardiac-sounding chest pain"},
        "urgent_actions": [{"action": "Bedside ECG", "reason": "exclude ACS"}]}


def test_an_assessment_timeout_is_a_runaway_too_and_arranged_latches_from_the_previous(monkeypatch):
    monkeypatch.setattr(cds, "CDS_ASSESSMENT_TIMEOUT_S", 0.05)
    seen = _engine(monkeypatch, assessment_sleep=0.5)
    previous = {"questions_to_ask": ["old"],
                "urgency_check": {"already_done_or_arranged": True}}
    with pytest.raises(CDSRunaway) as caught:
        asyncio.run(CDSEngine().update("I get chest pain on stairs.", previous))
    exc = caught.value
    assert exc.reason == "timeout" and exc.tokens is None and exc.timeout_s == 0.05
    assert exc.elapsed_ms < 400
    assert [b["messages"][0]["content"] for b in seen][-1] == cds.URGENCY_PROMPT
    assert exc.urgency["urgency_check"]["already_done_or_arranged"] is True, "the latch holds"
    assert exc.urgency["urgent_actions"] == [], "arranged: no alarm"


def test_the_runaway_names_itself():
    exc = CDSRunaway("assessment", reason="cap", tokens=1500, elapsed_ms=37000, cap=1500)
    assert "assessment call cap: 1500 tokens in 37000 ms" in str(exc)
