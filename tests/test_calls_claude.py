"""What the model saw, for a call to Claude (spec 15.13, ruling 16; 15.8
ruling 1; the details of run 9b): the one plain sentence that the service
adds an instruction of its own, the reply read from the Messages API's
own shape, and the test of a connection shown with its few words. Made-up
everything; no model's words asserted."""

from __future__ import annotations

import json

from openconsult import words
from openconsult.consult import seen
from openconsult.llm import claude
from openconsult.llm.record import CallRow
from openconsult.prompts import loader
from tests.conftest import text_of
from tests.fakes import ALARM_QUIET
from tests.test_review_page import reviewed


def claude_row(job: str, request: dict, text: str, consultation_id: int = 1) -> CallRow:
    reply = {"id": "msg_made_up", "type": "message", "role": "assistant", "model": "claude-haiku-5-5",
             "content": [{"type": "text", "text": text}], "stop_reason": "end_turn", "usage": {"input_tokens": 9, "output_tokens": 3}}
    return CallRow(job=job, engine="claude", engine_version=claude.ENGINE_VERSION, model_tag="claude-haiku-5-5",
                   model_digest=claude.NO_DIGEST, prompt_sha256=loader.sha256("made up"), request=json.dumps(request),
                   reply=json.dumps(reply), prompt_tokens=9, output_tokens=3, wall_ms=900, total_ms=900, load_ms=0, read_ms=None,
                   write_ms=None, outcome="ok", detail=None, consultation_id=consultation_id)


def test_15_13_ruling_16_a_call_to_claude_carries_the_one_sentence_and_its_reply_is_read_word_for_word(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine)
    p = app.state.parts
    record = p.door._record
    alarm = {"model": "claude-haiku-5-5", "max_tokens": 1000, "system": "MADE-UP SYSTEM WORDS",
             "messages": [{"role": "user", "content": "made-up user words"}],
             "output_config": {"format": {"type": "json_schema", "schema": {"type": "object"}}}, "thinking": {"type": "disabled"}}
    asked = record.add(claude_row("alarm", alarm, json.dumps(ALARM_QUIET)))
    tested = record.add(claude_row("connection_test", claude.test_request("claude-haiku-5-5"), "made-up reply"))
    raw = client.get("/consultations/1/calls").text
    page = text_of(client.get("/consultations/1/calls"))
    local = [row["id"] for row in p.consultations.model_calls(1) if row["engine"] != "claude"]
    assert local and page.count(words.CALL_CLAUDE_ADDS) == 1                              # on the call to Claude that carries a form
    assert f'id="service-adds-{asked}"' in raw and f'id="service-adds-{tested}"' not in raw
    assert not any(f'id="service-adds-{call_id}"' in raw for call_id in local)             # and on no call of this computer's model
    assert "Language model: claude-haiku-5-5 on Claude anthropic-version 2026-10-21, effort default." in page
    # The test of the connection made at Start: named, its few words shown as what was sent, and no row asked of it.
    assert "the test of the connection to Claude, at Start" in page
    block = raw.split(f'id="call-{tested}"', 1)[1].split("</details>", 1)[0]
    assert words.SOURCE_LABELS["test_words"] in block and "Connection test. Reply with OK." in block
    assert words.CALL_NO_ROW not in text_of_block(block) and "made-up reply" in block
    # The reply of the Messages API is read as its text, word for word, not shown as the service's whole body.
    assert seen.answer_of(json.dumps({"content": [{"type": "text", "text": "one "}, {"type": "text", "text": "two"}]})) == "one two"
    assert "msg_made_up" not in page and "MADE-UP SYSTEM WORDS" not in page               # 15.8 ruling 1: a prompt's words are never shown


def text_of_block(block: str) -> str:
    import html
    return html.unescape(block)
