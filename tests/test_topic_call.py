"""The topic call (Phase 7c slice 4, PHASE_7C_SPEC.md §4 decision D1),
with the model stubbed.

What is evidence here: the call's SHAPE (own prompt, the {"topic":
string} schema, the one question as the user message, temperature 0
seed 42, CDS_NUM_CTX so MedGemma is never reloaded, its own timeout
AUTO_TOPIC_TIMEOUT_S) and its FAIL-SOFT contract (error, timeout, or an
unusable phrase come back as a failed verdict; nothing raises; the
caller asks the agenda question verbatim). `clean_topic_phrase` is the
pure gate on what may fill the template's slot. Topic QUALITY — whether
MedGemma names a real question's subject well — belongs to evals/ and
the mock-patient round, not here.

The HTTP layer is stubbed at httpx's transport, as tests/test_officer.py
does, so the JSON the engine would send is what is asserted on.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app import cds
from app.cds import CDSEngine, TopicVerdict

_REAL_CLIENT = httpx.AsyncClient      # captured before any monkeypatch


def _capture(monkeypatch, reply=None, *, status=200, sleep_s: float = 0.0,
             body: str | None = None):
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["json"] = json.loads(request.content)
        if sleep_s:
            await asyncio.sleep(sleep_s)
        if body is not None:
            return httpx.Response(status, text=body)
        content = json.dumps(reply if reply is not None else {})
        return httpx.Response(status, json={"message": {"content": content}})

    def client_factory(**kwargs):
        seen["client_kwargs"] = kwargs
        return _REAL_CLIENT(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(cds.httpx, "AsyncClient", client_factory)
    return seen


QUESTION = "Does the pain radiate to your jaw or arm?"


# --- the call's shape ------------------------------------------------------

def test_the_topic_call_asks_its_own_question_with_the_one_string_schema(monkeypatch):
    seen = _capture(monkeypatch, {"topic": "the chest pain"})
    verdict = asyncio.run(CDSEngine().topic_for(QUESTION))
    assert verdict.topic == "the chest pain" and verdict.failed is None
    sent = seen["json"]
    assert sent["messages"][0] == {"role": "system", "content": cds.TOPIC_PROMPT}
    assert sent["messages"][1] == {"role": "user", "content": cds.topic_message(QUESTION)}
    assert cds.topic_message(QUESTION) == "THE QUESTION:\nDoes the pain radiate to your jaw or arm?"
    assert sent["format"] == cds.TOPIC_SCHEMA
    assert cds.TOPIC_SCHEMA == {"type": "object", "properties": {"topic": {"type": "string"}},
                                "required": ["topic"]}
    assert seen["url"].endswith("/api/chat")


def test_the_topic_call_reuses_the_engines_decoding_and_context(monkeypatch):
    seen = _capture(monkeypatch, {"topic": "the chest pain"})
    asyncio.run(CDSEngine().topic_for(QUESTION))
    options = seen["json"]["options"]
    assert options["temperature"] == 0.0 and options["seed"] == 42
    assert options["num_ctx"] == cds.CDS_NUM_CTX
    assert seen["json"]["model"] == cds.CDS_MODEL


def test_the_topic_call_has_its_own_timeout(monkeypatch):
    monkeypatch.setattr(cds, "AUTO_TOPIC_TIMEOUT_S", 1.25)
    seen = _capture(monkeypatch, {"topic": "the chest pain"})
    asyncio.run(CDSEngine().topic_for(QUESTION))
    assert seen["client_kwargs"]["timeout"] == 1.25


def test_the_prompt_asks_for_a_slot_filler_and_nothing_clinical():
    prompt = cds.TOPIC_PROMPT
    assert 'must fit the sentence "Can you tell me more about ___?"' in prompt
    assert "no diagnosis" in prompt and "no advice" in prompt
    assert "Answer with the phrase only" in prompt
    # The slot sentence in the prompt IS the registered template.
    from app import speech
    assert speech.TEMPLATES["tell_me_more"] == "Can you tell me more about {topic}?"


# --- fail-soft -------------------------------------------------------------

def test_a_connection_error_is_a_failed_verdict_not_an_exception():
    verdict = asyncio.run(CDSEngine(base_url="http://127.0.0.1:9").topic_for(QUESTION))
    assert verdict.topic is None and "ConnectError" in verdict.failed


def test_a_bad_status_and_a_malformed_reply_are_failed_verdicts(monkeypatch):
    _capture(monkeypatch, status=503, body="loading")
    assert asyncio.run(CDSEngine().topic_for(QUESTION)).failed is not None
    _capture(monkeypatch, body='{"message": {"content": "not json"}}')
    assert asyncio.run(CDSEngine().topic_for(QUESTION)).failed is not None
    _capture(monkeypatch, {"subject": "the chest pain"})       # wrong key
    verdict = asyncio.run(CDSEngine().topic_for(QUESTION))
    assert verdict.topic is None and "KeyError" in verdict.failed


def test_a_timeout_is_a_failed_verdict_named_timeout(monkeypatch):
    monkeypatch.setattr(cds, "AUTO_TOPIC_TIMEOUT_S", 0.05)
    _capture(monkeypatch, {"topic": "the chest pain"}, sleep_s=1.0)
    verdict = asyncio.run(CDSEngine().topic_for(QUESTION))
    assert verdict == TopicVerdict(None, failed="timeout", elapsed_ms=verdict.elapsed_ms)
    assert verdict.elapsed_ms < 900


@pytest.mark.parametrize("raw", ["", "   ", "Can you tell me more about the pain?",
                                 "the pain in the chest that comes on with exertion and settles",
                                 12, None, "line one\nline two"])
def test_an_unusable_phrase_is_a_failed_verdict_so_the_caller_asks_verbatim(monkeypatch, raw):
    """Empty, a question, a sentence, a non-string, a line break: none may
    fill the slot. The failure names the phrase for the audit row."""
    _capture(monkeypatch, {"topic": raw})
    verdict = asyncio.run(CDSEngine().topic_for(QUESTION))
    assert verdict.topic is None
    assert verdict.failed is not None and verdict.failed.startswith("unusable:")


def test_topic_for_never_raises_whatever_chat_does(monkeypatch):
    async def exploding(self, system, user, schema, *, timeout=180.0, **kwargs):
        raise RuntimeError("model process died")
    monkeypatch.setattr(CDSEngine, "_chat", exploding)
    verdict = asyncio.run(CDSEngine().topic_for(QUESTION))
    assert verdict.failed == "RuntimeError: model process died"


# --- the pure slot gate ----------------------------------------------------

def test_clean_topic_phrase_normalises_what_a_model_typically_returns():
    assert cds.clean_topic_phrase("the chest pain") == "the chest pain"
    assert cds.clean_topic_phrase('"the chest pain."') == "the chest pain"
    assert cds.clean_topic_phrase("  your   sleep \n") == "your sleep"
    assert cds.clean_topic_phrase("the tablets you started last week") == \
        "the tablets you started last week"


def test_clean_topic_phrase_bounds_are_stated_and_enforced():
    assert cds.TOPIC_MAX_WORDS == 8 and cds.TOPIC_MAX_CHARS == 60
    assert cds.clean_topic_phrase(" ".join(["w"] * 8)) == " ".join(["w"] * 8)
    assert cds.clean_topic_phrase(" ".join(["w"] * 9)) is None
    assert cds.clean_topic_phrase("a" * 60) == "a" * 60
    assert cds.clean_topic_phrase("a" * 61) is None
    assert cds.clean_topic_phrase("is it worse?") is None


def test_the_timeout_is_configured_in_the_house_pattern():
    from pathlib import Path
    assert "AUTO_TOPIC_TIMEOUT_S=2.0" in Path(".env.example").read_text()
    assert cds.AUTO_TOPIC_TIMEOUT_S == 2.0
