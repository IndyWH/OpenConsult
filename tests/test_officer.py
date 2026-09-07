"""The end-of-turn officer (Phase 7c slice 3, PHASE_7C_SPEC.md §5), with
the model stubbed.

What is evidence here: the call's SHAPE (own prompt, two-boolean schema,
the recent committed turns at the end of the user message, temperature 0
seed 42, CDS_NUM_CTX so MedGemma is never reloaded, its own timeout) and
its FAIL-SOFT contract (a connection error, a bad status, a malformed
reply or a timeout come back as a failed verdict; nothing raises into a
session; the silence-based fallback then decides). Officer QUALITY —
whether MedGemma judges a real pause well — belongs to evals/ and the
mock-patient round, not here.

The HTTP layer is stubbed at httpx's transport, so the JSON the engine
would send to Ollama is what is asserted on, not a fake at the method
boundary.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app import cds
from app.cds import CDSEngine, OfficerVerdict

_REAL_CLIENT = httpx.AsyncClient      # captured before any monkeypatch


def _capture(monkeypatch, reply=None, *, status=200, sleep_s: float = 0.0,
             body: str | None = None):
    """Route the engine's httpx client through a MockTransport that records
    the request and answers with `reply` (an Ollama-shaped envelope)."""
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


TRANSCRIPT = ("It started on Tuesday.\nA tight feeling across here.\n"
              "It comes on when I climb the stairs.\nAnd it goes when I sit down.\n"
              "My father had his heart.\nSo I thought I'd better come in.")


# --- the call's shape ------------------------------------------------------

def test_the_officer_asks_its_own_two_questions_with_the_two_boolean_schema(monkeypatch):
    seen = _capture(monkeypatch, {"finished_thought": True, "handed_back": False})
    verdict = asyncio.run(CDSEngine().end_of_turn(TRANSCRIPT))

    assert verdict == OfficerVerdict(True, False, failed=None, elapsed_ms=verdict.elapsed_ms)
    sent = seen["json"]
    assert sent["messages"][0] == {"role": "system", "content": cds.OFFICER_PROMPT}
    assert sent["format"] == cds.OFFICER_SCHEMA
    assert cds.OFFICER_SCHEMA["required"] == ["finished_thought", "handed_back"]
    assert set(cds.OFFICER_SCHEMA["properties"]) == {"finished_thought", "handed_back"}
    assert all(p["type"] == "boolean" for p in cds.OFFICER_SCHEMA["properties"].values())
    assert seen["url"].endswith("/api/chat")


def test_the_officer_reuses_the_engines_decoding_and_context_so_the_model_is_never_reloaded(monkeypatch):
    """Temperature 0, seed 42, CDS_NUM_CTX — the same options as every other
    MedGemma call in the app (Ollama reloads the model when num_ctx
    changes between calls; the officer must never cost that stall)."""
    seen = _capture(monkeypatch, {"finished_thought": False, "handed_back": False})
    asyncio.run(CDSEngine().end_of_turn(TRANSCRIPT))
    options = seen["json"]["options"]
    assert options["temperature"] == 0.0
    assert options["seed"] == 42
    assert options["num_ctx"] == cds.CDS_NUM_CTX
    assert seen["json"]["model"] == cds.CDS_MODEL
    assert seen["json"]["stream"] is False


def test_the_officer_has_its_own_timeout_not_the_cds_calls(monkeypatch):
    """AUTO_OFFICER_TIMEOUT_S bounds the HTTP client; the 180 s the clinical
    calls tolerate would let the officer answer long after the pause it
    was judging had passed."""
    monkeypatch.setattr(cds, "AUTO_OFFICER_TIMEOUT_S", 1.5)
    seen = _capture(monkeypatch, {"finished_thought": True, "handed_back": True})
    asyncio.run(CDSEngine().end_of_turn(TRANSCRIPT))
    assert seen["client_kwargs"]["timeout"] == 1.5


def test_the_user_message_puts_the_recent_committed_turns_last():
    """The affect call's construction (consultation 467): the whole
    transcript for context, then the most recent turns in a labelled block
    at the END, where the model attends most — the pause is judged on what
    was just said."""
    message = cds.officer_message(TRANSCRIPT)
    assert message.startswith("LIVE TRANSCRIPT SO FAR:\n" + TRANSCRIPT)
    block = message.split("THE MOST RECENT TURNS")[1]
    recent = TRANSCRIPT.splitlines()[-cds.OFFICER_RECENT_TURNS:]
    assert block.strip().endswith("\n".join(recent))
    assert "It started on Tuesday." not in block
    # A short transcript is the recent turns and is sent once.
    short = "It started on Tuesday.\nA tight feeling."
    assert cds.officer_message(short) == "LIVE TRANSCRIPT SO FAR:\n" + short


def test_the_prompt_carries_the_tie_break_and_the_explicitness_rule():
    """The parent spec's tie-break — err toward waiting — is in the prompt,
    not only in the code around it; and a hand-back must be explicit,
    because silence is what the officer is being asked about."""
    prompt = cds.OFFICER_PROMPT
    assert "When in doubt, answer false" in prompt
    assert "EXPLICITLY handed the conversation back" in prompt
    assert "silence is not one" in prompt
    assert "finished_thought" in prompt and "handed_back" in prompt
    # It judges the pause, not the illness: nothing clinical is asked.
    for clinical in ("diagnos", "urgent", "differential", "red flag"):
        assert clinical not in prompt.lower()


# --- fail-soft -------------------------------------------------------------

def test_a_connection_error_is_a_failed_verdict_not_an_exception(monkeypatch):
    engine = CDSEngine(base_url="http://127.0.0.1:9")   # nothing listens here
    verdict = asyncio.run(engine.end_of_turn(TRANSCRIPT))
    assert verdict.failed is not None and "ConnectError" in verdict.failed
    assert (verdict.finished_thought, verdict.handed_back) == (False, False), (
        "a failed officer never claims a turn ended or a hand-back")


def test_a_bad_status_is_a_failed_verdict(monkeypatch):
    _capture(monkeypatch, status=503, body="loading")
    verdict = asyncio.run(CDSEngine().end_of_turn(TRANSCRIPT))
    assert verdict.failed is not None and "HTTPStatusError" in verdict.failed
    assert (verdict.finished_thought, verdict.handed_back) == (False, False)


def test_a_malformed_reply_is_a_failed_verdict(monkeypatch):
    _capture(monkeypatch, body='{"message": {"content": "not json at all"}}')
    verdict = asyncio.run(CDSEngine().end_of_turn(TRANSCRIPT))
    assert verdict.failed is not None
    assert (verdict.finished_thought, verdict.handed_back) == (False, False)


def test_a_reply_missing_a_field_is_a_failed_verdict(monkeypatch):
    _capture(monkeypatch, {"finished_thought": True})
    verdict = asyncio.run(CDSEngine().end_of_turn(TRANSCRIPT))
    assert verdict.failed is not None and "KeyError" in verdict.failed


def test_a_timeout_is_a_failed_verdict_named_timeout(monkeypatch):
    """Bounded end to end: a model that does not answer inside
    AUTO_OFFICER_TIMEOUT_S returns a failed verdict, and the caller falls
    back to silence — the pause is not held hostage to the model."""
    monkeypatch.setattr(cds, "AUTO_OFFICER_TIMEOUT_S", 0.05)
    _capture(monkeypatch, {"finished_thought": True, "handed_back": True}, sleep_s=1.0)
    verdict = asyncio.run(CDSEngine().end_of_turn(TRANSCRIPT))
    assert verdict.failed == "timeout"
    assert (verdict.finished_thought, verdict.handed_back) == (False, False)
    assert verdict.elapsed_ms < 900


def test_the_officer_carries_its_output_cap_and_a_cap_hit_is_a_failed_verdict(monkeypatch):
    """Owner decision 2026-09-07 (pilot 486 F3): every model call carries
    num_predict. The officer's is AUTO_OFFICER_MAX_TOKENS (its answer is
    ~24 tokens); a reply Ollama stopped for length is a CDSRunaway inside
    the engine and a failed verdict at the boundary — fail-soft, as every
    officer failure is."""
    seen = _capture(monkeypatch, {"finished_thought": True, "handed_back": False})
    asyncio.run(CDSEngine().end_of_turn(TRANSCRIPT))
    assert seen["json"]["options"]["num_predict"] == cds.AUTO_OFFICER_MAX_TOKENS == 64
    # A length stop: the transport answers with done_reason "length".
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": "{\"finished_thought\": tr"},
                                         "done_reason": "length", "eval_count": 64})
    monkeypatch.setattr(cds.httpx, "AsyncClient",
                        lambda **kw: _REAL_CLIENT(transport=httpx.MockTransport(handler), **kw))
    verdict = asyncio.run(CDSEngine().end_of_turn(TRANSCRIPT))
    assert verdict.failed is not None and verdict.failed.startswith("CDSRunaway")
    assert (verdict.finished_thought, verdict.handed_back) == (False, False)


def test_a_callers_bound_stretches_the_officer_past_its_own_timeout(monkeypatch):
    """Owner decision 2026-09-07 (pilot 485 E4): while a CDS pass is in
    flight the wiring passes AUTO_OFFICER_MAX_WAIT_S as the bound, and the
    call that would have timed out at AUTO_OFFICER_TIMEOUT_S waits for the
    model instead — the HTTP client and the wait_for both take the caller's
    bound. Without a bound the 2 s default and the timeout verdict are
    unchanged (the tests above)."""
    monkeypatch.setattr(cds, "AUTO_OFFICER_TIMEOUT_S", 0.05)
    seen = _capture(monkeypatch, {"finished_thought": True, "handed_back": False}, sleep_s=0.3)
    verdict = asyncio.run(CDSEngine().end_of_turn(TRANSCRIPT, timeout_s=2.0))
    assert verdict.failed is None and verdict.finished_thought is True
    assert seen["client_kwargs"]["timeout"] == 2.0
    assert verdict.elapsed_ms >= 250
    late = asyncio.run(CDSEngine().end_of_turn(TRANSCRIPT))           # no bound: the default
    assert late.failed == "timeout"
    assert cds.AUTO_OFFICER_MAX_WAIT_S == 30.0, "the shipped default"


def test_end_of_turn_never_raises_whatever_chat_does(monkeypatch):
    """Belt and braces at the method boundary: any exception class from the
    call layer is absorbed into a failed verdict."""
    async def exploding(self, system, user, schema, *, timeout=180.0, **kwargs):
        raise RuntimeError("model process died")
    monkeypatch.setattr(CDSEngine, "_chat", exploding)
    verdict = asyncio.run(CDSEngine().end_of_turn(TRANSCRIPT))
    assert verdict.failed == "RuntimeError: model process died"


# --- the silence-based fallback (pure) --------------------------------------

def test_the_officers_word_decides_when_it_answered():
    assert cds.turn_finished(OfficerVerdict(True, False), quiet_s=0.5, fallback_s=5.0) is True
    assert cds.turn_finished(OfficerVerdict(False, False), quiet_s=60.0, fallback_s=5.0) is False


def test_the_fallback_is_silence_of_at_least_the_fallback_span():
    failed = OfficerVerdict(False, False, failed="timeout")
    assert cds.turn_finished(failed, quiet_s=4.9, fallback_s=5.0) is False
    assert cds.turn_finished(failed, quiet_s=5.0, fallback_s=5.0) is True
    assert cds.turn_finished(failed, quiet_s=12.0, fallback_s=5.0) is True


def test_the_fallback_span_is_longer_than_the_officers_trigger_by_default():
    """Err toward waiting: with the officer down, the system waits LONGER
    than it would have asked the officer, not shorter."""
    from app import main as appmain
    assert appmain.AUTO_EOT_FALLBACK_S > appmain.AUTO_EOT_QUIET_S


def test_a_hand_back_is_logged_when_detected(monkeypatch, caplog):
    """The prereg's metric-3 scoring needs hand-backs on the record; the
    officer logs one the moment it sees it (the wiring audits it too)."""
    _capture(monkeypatch, {"finished_thought": True, "handed_back": True})
    with caplog.at_level("INFO", logger="app.cds"):
        verdict = asyncio.run(CDSEngine().end_of_turn(TRANSCRIPT + "\nThat's all really."))
    assert verdict.handed_back is True
    assert any("hand-back detected" in r.getMessage() for r in caplog.records)


def test_the_officer_verdict_is_a_frozen_value():
    import dataclasses
    v = OfficerVerdict(True, False)
    with pytest.raises(dataclasses.FrozenInstanceError):
        v.finished_thought = False  # type: ignore[misc]
    assert v.failed is None and v.elapsed_ms == 0
