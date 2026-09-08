"""The standing question queue's re-ranker call (AGENDA_QUEUE_SPEC.md §3,
slice 3 of 7), with the model stubbed.

What is evidence here: the call's SHAPE (own prompt, the {order, drop}
schema, the pending ids and the excerpt in the user message with the
excerpt last, temperature 0 seed 42, CDS_NUM_CTX so MedGemma is never
reloaded, its own timeout AUTO_RERANK_TIMEOUT_S and output cap
AUTO_RERANK_MAX_TOKENS), its FAIL-SOFT contract (a connection error, a
bad status, a malformed reply, a cap hit or a timeout come back as a
failed verdict with nothing to apply; nothing raises; the caller leaves
the current order standing), the instruction the prompt carries (never
write a new question; a subject addressed counts as answered even if not
every example was named — the 486 parenthetical), and the D-B excerpt
builder. The no-invention GUARD is the queue module's (apply_rerank,
tests/test_agenda_queue.py) — the engine passes ids through. Re-ranker
QUALITY belongs to evals/ and the next solo run, not here.

The HTTP layer is stubbed at httpx's transport, as tests/test_officer.py
and tests/test_topic_call.py do, so the JSON the engine would send is
what is asserted on.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from app import cds
from app.cds import CDSEngine, RerankVerdict

_REAL_CLIENT = httpx.AsyncClient      # captured before any monkeypatch


def _capture(monkeypatch, reply=None, *, status=200, sleep_s: float = 0.0,
             body: str | None = None, envelope: dict | None = None):
    """Route the engine's httpx client through a MockTransport that records
    the request and answers with `reply` inside an Ollama-shaped envelope
    (`envelope` adds fields such as eval_count or done_reason)."""
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["json"] = json.loads(request.content)
        if sleep_s:
            await asyncio.sleep(sleep_s)
        if body is not None:
            return httpx.Response(status, text=body)
        content = json.dumps(reply if reply is not None else {})
        return httpx.Response(status, json={"message": {"content": content}, **(envelope or {})})

    def client_factory(**kwargs):
        seen["client_kwargs"] = kwargs
        return _REAL_CLIENT(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(cds.httpx, "AsyncClient", client_factory)
    return seen


PENDING = [("q1", "Do you have any other risk factors for heart disease? (e.g., diabetes, high cholesterol)"),
           ("q2", "When did the chest pain first start?"),
           ("q3", "How have you been sleeping?")]
EXCERPT = "I smoke, and my blood pressure was high once.\nMy father had his heart at sixty."
WELL_FORMED = {"order": ["q2", "q3"], "drop": [{"id": "q1", "reason": "answered"}]}


# --- the call's shape ------------------------------------------------------

def test_a_well_formed_reply_parses_into_the_order_and_the_drops_with_their_reasons(monkeypatch):
    seen = _capture(monkeypatch, WELL_FORMED)
    verdict = asyncio.run(CDSEngine().rerank(PENDING, EXCERPT))
    assert verdict.failed is None and verdict.outcome == "ok"
    assert verdict.order_ids == ("q2", "q3")
    assert dict(verdict.drop_ids) == {"q1": "answered"}
    sent = seen["json"]
    assert sent["messages"][0] == {"role": "system", "content": cds.RERANK_PROMPT}
    assert sent["format"] == cds.RERANK_SCHEMA
    assert cds.RERANK_SCHEMA["required"] == ["order", "drop"]
    assert cds.RERANK_SCHEMA["properties"]["drop"]["items"]["required"] == ["id", "reason"]
    assert seen["url"].endswith("/api/chat")


def test_the_user_message_lists_every_pending_id_with_its_text_and_puts_the_excerpt_last():
    message = cds.rerank_message(PENDING, EXCERPT)
    for item_id, text in PENDING:
        assert f"{item_id}: {text}" in message
    assert message.index("q1:") < message.index("q2:") < message.index("q3:") < message.index(EXCERPT)
    assert message.rstrip().endswith(EXCERPT)
    assert cds.rerank_message(PENDING, "   ").rstrip().endswith("(nothing new)")


def test_the_re_ranker_reuses_the_engines_decoding_and_context_with_its_own_timeout_and_cap(monkeypatch):
    """Temperature 0, seed 42, CDS_NUM_CTX (no reload), the HTTP client
    bounded by AUTO_RERANK_TIMEOUT_S — not the clinical calls' 180 s — and
    num_predict = AUTO_RERANK_MAX_TOKENS, like the topic and officer calls."""
    monkeypatch.setattr(cds, "AUTO_RERANK_TIMEOUT_S", 1.5)
    monkeypatch.setattr(cds, "AUTO_RERANK_MAX_TOKENS", 123)
    seen = _capture(monkeypatch, WELL_FORMED)
    asyncio.run(CDSEngine().rerank(PENDING, EXCERPT))
    options = seen["json"]["options"]
    assert options["temperature"] == 0.0 and options["seed"] == 42
    assert options["num_ctx"] == cds.CDS_NUM_CTX
    assert options["num_predict"] == 123
    assert seen["client_kwargs"]["timeout"] == 1.5
    assert seen["json"]["model"] == cds.CDS_MODEL and seen["json"]["stream"] is False


def test_the_prompt_carries_the_three_instructions_of_spec_section_3():
    prompt = cds.RERANK_PROMPT.lower()
    assert "never write a new question" in prompt
    assert "best order" in prompt and "still worth asking" in prompt
    assert "even if not every example" in prompt, "the 486 parenthetical lesson"
    assert "one-word reason" in prompt
    assert "use only the ids you were given" in prompt


def test_the_verdict_carries_the_servers_numbers_for_the_model_call_audit(monkeypatch):
    """Ollama's own prompt_eval_count, eval_count and total_duration travel
    on the verdict as tokens {prompt, output} and run_ms — the model.call
    shape slice 6 extends to every call."""
    _capture(monkeypatch, WELL_FORMED,
             envelope={"prompt_eval_count": 410, "eval_count": 27, "total_duration": 812_000_000})
    verdict = asyncio.run(CDSEngine().rerank(PENDING, EXCERPT))
    assert dict(verdict.tokens) == {"prompt": 410, "output": 27}
    assert verdict.run_ms == 812
    assert verdict.elapsed_ms >= 0


# --- the fail-soft contract ------------------------------------------------

def _nothing_to_apply(verdict: RerankVerdict) -> bool:
    return verdict.order_ids == () and dict(verdict.drop_ids) == {} and verdict.failed is not None


def test_a_timeout_is_a_failed_verdict_named_timeout(monkeypatch):
    monkeypatch.setattr(cds, "AUTO_RERANK_TIMEOUT_S", 0.2)
    _capture(monkeypatch, WELL_FORMED, sleep_s=2.0)
    verdict = asyncio.run(CDSEngine().rerank(PENDING, EXCERPT))
    assert _nothing_to_apply(verdict)
    assert verdict.failed == "timeout" and verdict.outcome == "timeout"
    assert verdict.elapsed_ms < 900


@pytest.mark.parametrize("reply", [
    {"order": "q2", "drop": []},                       # order not a list
    {"order": ["q2", 3], "drop": []},                  # a non-string id
    {"order": ["q2"], "drop": ["q1"]},                 # a drop without {id, reason}
    {"order": ["q2"]},                                 # drop missing
    ["q2", "q1"],                                      # not an object
])
def test_a_malformed_reply_is_a_failed_verdict_so_the_order_stands(monkeypatch, reply):
    _capture(monkeypatch, reply)
    verdict = asyncio.run(CDSEngine().rerank(PENDING, EXCERPT))
    assert _nothing_to_apply(verdict)
    assert verdict.outcome == "malformed" and verdict.failed.startswith("malformed:")


def test_a_non_json_body_and_a_bad_status_are_failed_verdicts(monkeypatch):
    _capture(monkeypatch, body="not json at all")
    verdict = asyncio.run(CDSEngine().rerank(PENDING, EXCERPT))
    assert _nothing_to_apply(verdict) and verdict.outcome == "malformed"
    _capture(monkeypatch, WELL_FORMED, status=503)
    verdict = asyncio.run(CDSEngine().rerank(PENDING, EXCERPT))
    assert _nothing_to_apply(verdict) and verdict.outcome == "error"
    assert verdict.failed.startswith("HTTPStatusError")


def test_a_connection_error_is_a_failed_verdict_not_an_exception():
    verdict = asyncio.run(CDSEngine(base_url="http://127.0.0.1:9").rerank(PENDING, EXCERPT))
    assert _nothing_to_apply(verdict) and verdict.outcome == "error"


def test_a_cap_hit_is_a_failed_verdict_with_the_runaway_named(monkeypatch):
    """A reply Ollama stopped for length is a CDSRunaway inside _chat (pilot
    486 F3); for the re-ranker that is a failed call — never a parsed,
    truncated answer — with outcome cap and the tokens it produced."""
    _capture(monkeypatch, WELL_FORMED, envelope={"done_reason": "length", "eval_count": 200})
    verdict = asyncio.run(CDSEngine().rerank(PENDING, EXCERPT))
    assert _nothing_to_apply(verdict)
    assert verdict.outcome == "cap" and verdict.failed.startswith("CDSRunaway")
    assert dict(verdict.tokens)["output"] == 200


def test_rerank_never_raises_whatever_the_call_does(monkeypatch):
    async def exploding(self, system, user, schema, *, timeout=180.0, **kwargs):
        raise RuntimeError("model process died")
    monkeypatch.setattr(CDSEngine, "_chat_raw", exploding)
    verdict = asyncio.run(CDSEngine().rerank(PENDING, EXCERPT))
    assert verdict.failed == "RuntimeError: model process died" and verdict.outcome == "error"


# --- the pure parts ------------------------------------------------------------

def test_reasons_are_held_to_one_word_and_ids_are_deduplicated_in_first_seen_order():
    order, drops = cds.parse_rerank_reply(
        {"order": ["q2", " q3 ", "q2", ""],
         "drop": [{"id": "q1", "reason": "Already ANSWERED in detail."},
                  {"id": "q1", "reason": "again"}, {"id": "q9", "reason": ""}]})
    assert order == ("q2", "q3")
    assert drops == {"q1": "already", "q9": "addressed"}
    assert cds.one_word(None) == "addressed" and cds.one_word("volunteered_it") == "volunteered"


def test_the_engine_passes_unknown_ids_through_for_the_queues_guard_to_ignore(monkeypatch):
    """The no-invention guard is code in the queue module, not a filter
    here: an id the model made up reaches apply_rerank, which ignores it
    and lists it in the audit row (tests/test_agenda_queue.py)."""
    _capture(monkeypatch, {"order": ["q7", "q2"], "drop": [{"id": "q8", "reason": "done"}]})
    verdict = asyncio.run(CDSEngine().rerank(PENDING, EXCERPT))
    assert verdict.order_ids == ("q7", "q2") and dict(verdict.drop_ids) == {"q8": "done"}


def test_the_excerpt_is_the_last_n_turns_cut_from_the_front_by_characters():
    """D-B: at most max_turns turns since the last full pass, and if still
    longer than max_chars the FRONT is cut, so the most recent words — the
    thing being judged — survive."""
    turns = ["one", "", "  ", "two", "three", "four"]
    assert cds.rerank_excerpt(turns, max_turns=2, max_chars=1000) == "three\nfour"
    assert cds.rerank_excerpt(turns, max_turns=10, max_chars=1000) == "one\ntwo\nthree\nfour"
    cut = cds.rerank_excerpt(turns, max_turns=10, max_chars=9)
    assert cut == "…hree\nfour" and cut.endswith("four")
    assert cds.rerank_excerpt([], max_turns=6, max_chars=100) == ""


def test_the_settings_are_configured_in_the_house_pattern():
    env = Path(".env.example").read_text()
    assert "AUTO_RERANK_TIMEOUT_S=2.0" in env and cds.AUTO_RERANK_TIMEOUT_S == 2.0
    assert "AUTO_RERANK_MAX_TOKENS=200" in env and cds.AUTO_RERANK_MAX_TOKENS == 200
    assert "AUTO_RERANK_MAX_CHARS=1500" in env
    assert "AUTO_RERANK_CONTEXT_TURNS=6" in env
    block = env[env.index("AUTO_RERANK_MAX_TOKENS") - 400: env.index("AUTO_RERANK_MAX_CHARS") + 200]
    assert block.count("UNCALIBRATED GUESS") >= 2
