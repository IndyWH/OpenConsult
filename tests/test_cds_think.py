"""CDS_THINK (Task 3j, 2026-10-02): the think field on every chat request
to CDS_MODEL, with the HTTP layer stubbed at httpx's transport so the JSON
each call site sends to Ollama is what is asserted on.

Gemma 4 can think before it answers; every Gemma 4 request in the Task 3i
benchmark carried think false. MedGemma's requests must stay exactly as
they were. What is pinned, at each of the four call sites (the CDS engine's
_chat_raw, draft_note, the letters' _chat and the guideline summary):
unset or empty sends no think key and the body keys the app has always
sent; false sends the boolean false; low sends the word; an unknown value
sends no key and logs one warning. Every test asserts that the request
reached the stub, so none can pass by sending nothing. Needs no model.
"""

from __future__ import annotations

import asyncio
import json
import logging

import httpx
import pytest

from app import cds, letters, notes, rag
from app.cds import CDSEngine

_REAL_CLIENT = httpx.AsyncClient

# The body keys every chat request to CDS_MODEL carried before CDS_THINK.
BODY_KEYS = {"model", "messages", "format", "stream", "keep_alive", "options"}

ASSESSMENT = {"reasoning": "", "differentials": [], "questions_to_ask": [],
              "signs_to_check": []}
URGENCY = {"reasoning": "", "time_critical_possible": False,
           "already_done_or_arranged": False, "urgent_actions": []}
AFFECT = {"patient_affect": "neutral"}
NOTE = {"reasoning": "", "subjective": [{"text": "Chest pain on stairs.", "turns": [0]}],
        "objective": [], "assessment": [], "plan": []}
SUMMARY = {"covered": True, "summary": "Offer an ECG.", "passages_cited": [1]}
TURNS = [{"idx": 0, "role": "Patient", "start": 0.0, "end": 2.0,
          "text": "I get chest pain on stairs.", "confidence": 0.9}]
PASSAGES = [{"source": "Chest pain", "publisher": "NICE", "section": "1.1",
             "url": "https://example.org", "text": "Offer a resting ECG.", "similarity": 0.9}]


def _stub(monkeypatch) -> list[dict]:
    """Answer each chat request with a reply its call site can parse;
    record every request body."""
    seen: list[dict] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        system = body["messages"][0]["content"]
        reply = {cds.ASSESSMENT_PROMPT: ASSESSMENT, cds.URGENCY_PROMPT: URGENCY,
                 cds.AFFECT_PROMPT: AFFECT, notes.NOTE_PROMPT: NOTE,
                 rag.SUMMARY_PROMPT: SUMMARY}.get(system, {"ok": True})
        return httpx.Response(200, json={"message": {"content": json.dumps(reply)},
                                         "done_reason": "stop", "eval_count": 10})

    monkeypatch.setattr(cds.httpx, "AsyncClient",
                        lambda **kw: _REAL_CLIENT(transport=httpx.MockTransport(handler), **kw))
    return seen


async def _no_db_provenance(self) -> dict:
    return {"corpus_name": "test", "corpus_version": "1", "n_sources": 1, "n_chunks": 1,
            "date_ingested": "-"}


def _call_site(name: str, monkeypatch) -> None:
    """Drive one call site through to its chat request."""
    if name == "cds":
        asyncio.run(CDSEngine().update("I get chest pain on stairs."))
    elif name == "note":
        asyncio.run(notes.draft_note(TURNS))
    elif name == "letters":
        asyncio.run(letters._chat("system", "user", {"type": "object"}))
    elif name == "rag":
        monkeypatch.setattr(rag.RAGService, "provenance", _no_db_provenance)
        asyncio.run(rag.RAGService()._summarise("chest pain", PASSAGES))
    else:
        raise AssertionError(name)


SITES = ("cds", "note", "letters", "rag")
SITE_MODEL = {"cds": lambda: cds.CDS_MODEL, "note": lambda: notes.NOTE_MODEL,
              "letters": lambda: letters.LETTER_MODEL, "rag": lambda: rag.RAG_MODEL}


def _requests(name: str, monkeypatch) -> list[dict]:
    seen = _stub(monkeypatch)
    _call_site(name, monkeypatch)
    assert seen, f"{name}: no request reached the stub"
    assert all(body["model"] == SITE_MODEL[name]() for body in seen), name
    if name == "cds":
        prompts = {body["messages"][0]["content"] for body in seen}
        assert prompts == {cds.ASSESSMENT_PROMPT, cds.URGENCY_PROMPT, cds.AFFECT_PROMPT}
    return seen


@pytest.mark.parametrize("site", SITES)
@pytest.mark.parametrize("value", [None, "", "  "])
def test_unset_or_empty_sends_no_think_and_the_body_is_unchanged(site, value, monkeypatch):
    if value is None:
        monkeypatch.delenv("CDS_THINK", raising=False)
    else:
        monkeypatch.setenv("CDS_THINK", value)
    for body in _requests(site, monkeypatch):
        assert "think" not in body, f"{site}: think sent with CDS_THINK={value!r}"
        assert set(body) == BODY_KEYS, f"{site}: body keys changed: {sorted(body)}"


@pytest.mark.parametrize("site", SITES)
def test_false_sends_think_false(site, monkeypatch):
    monkeypatch.setenv("CDS_THINK", "false")
    for body in _requests(site, monkeypatch):
        assert body["think"] is False, site
        assert set(body) == BODY_KEYS | {"think"}, site


@pytest.mark.parametrize("site", SITES)
def test_true_sends_think_true(site, monkeypatch):
    monkeypatch.setenv("CDS_THINK", "true")
    for body in _requests(site, monkeypatch):
        assert body["think"] is True, site


@pytest.mark.parametrize("site", SITES)
def test_low_sends_the_word_low(site, monkeypatch):
    monkeypatch.setenv("CDS_THINK", "low")
    for body in _requests(site, monkeypatch):
        assert body["think"] == "low", site


@pytest.mark.parametrize("site", SITES)
def test_an_unknown_value_sends_no_think(site, monkeypatch):
    monkeypatch.setenv("CDS_THINK", "off")
    monkeypatch.setattr(cds, "_THINK_WARNED", set())
    for body in _requests(site, monkeypatch):
        assert "think" not in body, site
        assert set(body) == BODY_KEYS, site


def test_every_valid_value_maps_as_documented(monkeypatch):
    for raw, field in [("false", {"think": False}), ("FALSE", {"think": False}),
                       ("true", {"think": True}), ("low", {"think": "low"}),
                       ("medium", {"think": "medium"}), ("High", {"think": "high"})]:
        monkeypatch.setenv("CDS_THINK", raw)
        assert cds.think_field() == field, raw


def test_an_unknown_value_logs_one_warning_however_many_calls(monkeypatch, caplog):
    monkeypatch.setenv("CDS_THINK", "maybe")
    monkeypatch.setattr(cds, "_THINK_WARNED", set())
    with caplog.at_level(logging.WARNING, logger="app.cds"):
        for _ in range(3):
            assert cds.think_field() == {}
    warnings = [r for r in caplog.records if "CDS_THINK" in r.getMessage()]
    assert len(warnings) == 1, [r.getMessage() for r in warnings]
    assert "'maybe'" in warnings[0].getMessage()


def test_think_is_read_at_call_time(monkeypatch):
    monkeypatch.delenv("CDS_THINK", raising=False)
    assert cds.think_field() == {}
    monkeypatch.setenv("CDS_THINK", "false")
    assert cds.think_field() == {"think": False}
