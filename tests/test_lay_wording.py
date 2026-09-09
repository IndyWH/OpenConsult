"""Lay wording through the topic call (owner decision 2026-09-09, the D1
extension of PHASE_7C_SPEC.md §4, after consultation 486's "risk factors
like hypertension" lesson).

The topic call returns two fields for the planned question: `topic` (as
before) and `lay`, the SAME question in plain spoken English. Alba speaks
the lay wording for a verbatim ask; the queue item, the panel and the
never-twice guarantee keep the original text as the question's identity.
Code-enforced guard: the lay wording must share its subject with the
original under the shared normaliser (token-set similarity at or above
AUTO_LAY_MIN_SIMILARITY) or the original is spoken verbatim and
auto.lay_rejected is audited; on timeout or failure, verbatim as today.
The spoken text goes on the queue_consumed row beside the original.

The pure halves (the cleaner, the guard, the resolver) need no database;
the wiring half uses the auto harness. Lay QUALITY — whether MedGemma's
wording is good plain English — belongs to evals/, not here.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app import auto_mode, cds, speech
from app.auto_mode import LayUtterance
from app.cds import CDSEngine, OfficerVerdict
from auto_harness import (  # noqa: F401 - the fixture is used by name
    Q_ONSET, Q_RADIATE, Q_SLEEP, _audit, _rows, _stop, gate, live, needs_db)

_REAL_CLIENT = httpx.AsyncClient

LAY_RADIATE = "Does the pain spread to your jaw or your arm?"
Q_RISK = ("Do you have any risk factors for heart disease? "
          "(e.g., smoking, diabetes, hypertension, high cholesterol, family history)")


def _capture(monkeypatch, reply):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": json.dumps(reply)}})

    def client_factory(**kwargs):
        return _REAL_CLIENT(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(cds.httpx, "AsyncClient", client_factory)


# --- the call and the cleaner ------------------------------------------------

def test_the_prompt_states_the_four_rules_of_the_lay_wording():
    prompt = cds.TOPIC_PROMPT
    assert '"lay": the SAME question in plain spoken English' in prompt
    assert "one sentence, ending in a question mark" in prompt
    assert "no medical terms" in prompt
    assert "no examples in brackets" in prompt
    assert "nothing the question did not ask" in prompt
    assert "do not name examples the question did not name" in prompt, "the 486 lesson"


@pytest.mark.parametrize("raw, expected", [
    ("Does the pain spread to your jaw or your arm?", "Does the pain spread to your jaw or your arm?"),
    ("  Does the pain   spread to your arm  ", "Does the pain spread to your arm?"),   # a missing mark appended
    ('"Do you smoke?"', "Do you smoke?"),
    ("Do you smoke? How much?", None),                    # two sentences
    ("Do you have any risks (like smoking) for your heart?", None),   # brackets: the 486 lesson
    ("You should stop smoking.", None),                   # a statement
    ("Smoke?", None),                                     # too short to be a sentence
    ("x" * 210 + "?", None),                              # over-long
    ("Does it hurt?\nAnd when?", None),
    (None, None), (42, None), ("", None),
])
def test_clean_lay_wording_admits_one_plain_question_and_refuses_the_rest(raw, expected):
    assert cds.clean_lay_wording(raw) == expected


def test_the_verdict_carries_the_lay_wording_and_an_unusable_one_is_named(monkeypatch):
    _capture(monkeypatch, {"topic": "the chest pain", "lay": LAY_RADIATE})
    verdict = asyncio.run(CDSEngine().topic_for(Q_RADIATE))
    assert verdict.lay == LAY_RADIATE and verdict.lay_failed is None
    _capture(monkeypatch, {"topic": "the chest pain", "lay": "Any risks (like smoking)?"})
    verdict = asyncio.run(CDSEngine().topic_for(Q_RADIATE))
    assert verdict.topic == "the chest pain" and verdict.lay is None
    assert verdict.lay_failed.startswith("unusable")
    _capture(monkeypatch, {"topic": "", "lay": LAY_RADIATE})      # the topic fails, the lay survives
    verdict = asyncio.run(CDSEngine().topic_for(Q_RADIATE))
    assert verdict.failed is not None and verdict.lay == LAY_RADIATE


# --- the guard ---------------------------------------------------------------

def test_the_guard_is_the_shared_normalisers_token_set_similarity_at_the_threshold():
    assert speech.AUTO_LAY_MIN_SIMILARITY == 0.3
    ok, score = speech.lay_accepted(LAY_RADIATE, Q_RADIATE)
    assert ok and score >= 0.3
    ok, score = speech.lay_accepted("Do you sleep well at night?", Q_RADIATE)   # another subject
    assert not ok and score < 0.3
    ok, score = speech.lay_accepted("Do you smoke?", "Do you smoke?")
    assert ok and score == 1.0
    assert score == auto_mode.action_similarity("Do you smoke?", "Do you smoke?")
    # The threshold is a parameter, so a calibration script can try others.
    radiate_score = speech.lay_accepted(LAY_RADIATE, Q_RADIATE)[1]
    assert speech.lay_accepted(LAY_RADIATE, Q_RADIATE, threshold=0.99) == (False, radiate_score)


def test_the_resolver_speaks_the_lay_wording_keeps_the_identity_and_refuses_drift():
    agenda = speech.AgendaLog()
    agenda.record({"questions_to_ask": [Q_RADIATE], "reasoning": "cardiac"})
    resolution = speech.resolve_utterance(LayUtterance(1, 0, LAY_RADIATE), agenda)
    assert resolution.text == LAY_RADIATE
    assert resolution.ref_kind == "cds_question" and resolution.cds_rationale == "cardiac"
    assert resolution.ref_detail["assessment_version"] == 1 and resolution.ref_detail["index"] == 0
    assert resolution.ref_detail["lay"] is True and resolution.ref_detail["question"] == Q_RADIATE
    assert 0.3 <= resolution.ref_detail["lay_similarity"] <= 1.0
    # The last line of the guard: a wording that drifts is REFUSED here,
    # whatever the caller checked — the type cannot smuggle free text.
    with pytest.raises(speech.SpeechRefused, match="does not share its subject"):
        speech.resolve_utterance(LayUtterance(1, 0, "Do you sleep well at night?"), agenda)
    with pytest.raises(speech.SpeechRefused):
        speech.resolve_utterance(LayUtterance(1, 0, "   "), agenda)
    with pytest.raises(speech.SpeechRefused):
        speech.resolve_utterance(LayUtterance(7, 0, LAY_RADIATE), agenda)   # no such version
    # And the type is a question to the machine: allowed in OPEN/CLOSED,
    # a coding error in GOLDEN like any question.
    ctl = auto_mode.AutoModeController()
    ctl.enable(); ctl.disclosure_completed(); ctl.invitation_completed()
    with pytest.raises(auto_mode.AutoModeError):
        ctl.request_question(LayUtterance(1, 0, LAY_RADIATE))


# --- the wiring --------------------------------------------------------------

pytestmark = needs_db


def test_a_lay_wording_is_spoken_and_the_original_stays_the_items_identity(gate):
    """The cone's second ask (same topic → verbatim) is spoken in lay
    wording: the auto_speak text is the lay sentence; the queue item's
    text, last_asked_text and the queue_consumed row's text are the
    original, with the spoken wording beside it; the utterance row is
    ref_kind cds_question with lay=true and the original question. And
    the never-twice guarantee matches on the original: a later pass
    re-proposing it is discarded at the merge."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET], [Q_RADIATE], [Q_RADIATE, Q_SLEEP]]
    engine.lays[Q_RADIATE] = LAY_RADIATE
    with live(gate) as s:
        queue = s.auto["queue"]
        s.to_golden()
        s.to_open()
        first = s.wait_for_auto_speak()
        assert first["text"] == "Can you tell me more about the chest pain?"
        s.play(first["utterance_id"])
        s.turn_end("It started on Tuesday night.")
        second = s.wait_for_auto_speak()
        assert second["text"] == LAY_RADIATE, "Alba speaks the lay wording"
        item = queue.find(Q_RADIATE)
        assert item is not None and item.text == Q_RADIATE, "the item's identity is the original"
        assert s.auto["last_asked_text"] == Q_RADIATE
        s.play(second["utterance_id"])
        s.turn_end("No, it stays in the middle of my chest.")   # pass 3 re-proposes Q_RADIATE
        third = s.wait_for_auto_speak()
        assert third["text"] == "Can you tell me more about your sleep?"
        assert queue.find(Q_RADIATE).status.value == "answered"
        cid = _stop(s)
    consumed = [c for c in _audit("auto.queue_consumed", s.session_id) if c["text"] == Q_RADIATE]
    assert len(consumed) == 1
    assert consumed[0]["spoken"] == LAY_RADIATE and consumed[0]["lay"] is True
    merges = _audit("auto.queue_merged", s.session_id)
    assert merges[-1]["discarded"] >= 1, "the original, proposed again, is discarded — never asked twice"
    assert _audit("auto.lay_rejected", s.session_id) == []
    row = next(r for r in _rows(cid) if r["text"] == LAY_RADIATE)
    assert row["ref_kind"] == "cds_question"
    assert row["ref_detail"]["lay"] is True and row["ref_detail"]["question"] == Q_RADIATE
    assert row["ref_detail"]["open_form"] is False


def test_a_wording_that_drifts_subject_is_rejected_and_the_original_spoken_verbatim(gate):
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET], [Q_RADIATE]]
    engine.lays[Q_RADIATE] = "Do you sleep well at night?"          # another subject entirely
    with live(gate) as s:
        s.to_golden()
        s.to_open()
        first = s.wait_for_auto_speak()
        s.play(first["utterance_id"])
        s.turn_end("It started on Tuesday night.")
        second = s.wait_for_auto_speak()
        assert second["text"] == Q_RADIATE, "verbatim: the drifting wording was refused"
        s.play(second["utterance_id"])
        cid = _stop(s)
    rejected = _audit("auto.lay_rejected", s.session_id)
    assert len(rejected) == 1
    assert rejected[0]["question"] == Q_RADIATE and rejected[0]["lay"] == "Do you sleep well at night?"
    assert rejected[0]["score"] < 0.3 and rejected[0]["threshold"] == 0.3
    consumed = next(c for c in _audit("auto.queue_consumed", s.session_id) if c["text"] == Q_RADIATE)
    assert consumed["spoken"] == Q_RADIATE and consumed["lay"] is False
    row = next(r for r in _rows(cid) if r["text"] == Q_RADIATE)
    assert "lay" not in row["ref_detail"]


def test_a_topic_call_timeout_gives_verbatim_as_today(gate):
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True)]
    engine.agendas = [["Is the pain there now?"]]                 # nothing scripted → a failed call
    with live(gate) as s:
        s.to_golden()
        s.to_open()
        ask = s.wait_for_auto_speak()
        assert ask["text"] == "Is the pain there now?"
        s.play(ask["utterance_id"])
        _stop(s)
    assert _audit("auto.lay_rejected", s.session_id) == []
    assert len(_audit("auto.topic_failed", s.session_id)) == 1
    consumed = _audit("auto.queue_consumed", s.session_id)[0]
    assert consumed["spoken"] == "Is the pain there now?" and consumed["lay"] is False
