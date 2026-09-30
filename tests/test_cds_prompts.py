"""Properties of the CDS prompt text itself. Needs no model.

Owner decisions of 2026-09-30 (HANDOVER.md, CDS prompt: weigh a stale
list): OpenConsult v1.1 is for UK GPs, so no prompt names a country, and
the dengue examples left the urgency prompt with Sri Lanka.
"""

from __future__ import annotations

import asyncio
import re

import pytest

from app import cds


def _prompts() -> dict[str, str]:
    return {name: value for name, value in vars(cds).items()
            if name.endswith("_PROMPT") and isinstance(value, str)}


def test_the_check_sees_the_clinical_prompts():
    # Not vacuous: the scan below must reach the two prompts that named
    # a country before 2026-09-30.
    prompts = _prompts()
    assert {"ASSESSMENT_PROMPT", "URGENCY_PROMPT"} <= set(prompts)
    assert all(prompts.values())


def test_no_prompt_names_sri_lanka():
    for name, text in _prompts().items():
        assert "sri lanka" not in text.lower(), name


def test_urgency_prompt_has_no_dengue_example():
    assert "dengue" not in cds.URGENCY_PROMPT.lower()


# ------------------------------------------ assessment: weigh a stale list
# Owner decisions 2026-09-30: no rule to keep the list's names or order;
# the earlier list goes to the model as a stale list, names only, before
# the transcript.

TRANSCRIPT = "Doctor: What brings you in?\nPatient: Pain in the left side of my tummy."

PREVIOUS = {
    "reasoning": "left-sided lower abdominal pain",
    "differentials": [
        {"condition": "Diverticulitis", "likelihood": "high",
         "rationale": "RATIONALE-ONE left iliac fossa pain"},
        {"condition": "Ovarian cyst", "likelihood": "moderate",
         "rationale": "RATIONALE-TWO woman of reproductive age"},
        {"condition": "Ectopic pregnancy", "likelihood": "low",
         "rationale": "RATIONALE-THREE pain and possible missed period"},
    ],
    "questions_to_ask": ["QUESTION-ONE When was your last period?"],
    "signs_to_check": ["SIGN-ONE Abdominal guarding"],
    "urgency_check": {"time_critical_possible": False,
                      "already_done_or_arranged": False, "reason": ""},
    "urgent_actions": [],
    "patient_affect": "neutral",
}


def _sent_messages(previous):
    """Run one update() with every model call stubbed; return the user
    message each call received, by prompt."""
    seen: dict[str, str] = {}

    async def fake_chat(self, system, user, schema, **kwargs):
        if system is cds.ASSESSMENT_PROMPT:
            seen["assessment"] = user
            return {"reasoning": "", "differentials": [], "questions_to_ask": [],
                    "signs_to_check": []}
        if system is cds.URGENCY_PROMPT:
            seen["urgency"] = user
            return {"reasoning": "", "time_critical_possible": False,
                    "already_done_or_arranged": False, "urgent_actions": []}
        seen["affect"] = user
        return {"patient_affect": "neutral"}

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(cds.CDSEngine, "_chat", fake_chat)
        asyncio.run(cds.CDSEngine().update(TRANSCRIPT, previous))
    assert set(seen) == {"assessment", "urgency", "affect"}
    return seen


def test_first_pass_message_is_the_transcript_alone():
    want = f"Here is the transcript of the consultation so far:\n{TRANSCRIPT}"
    assert cds.assessment_message(TRANSCRIPT, None) == want
    assert _sent_messages(None)["assessment"] == want
    # A previous with no differentials (a runaway's bookkeeping) is a first pass.
    empty = {**PREVIOUS, "differentials": []}
    assert _sent_messages(empty)["assessment"] == want


def test_later_pass_message_puts_the_stale_list_before_the_transcript():
    sent = _sent_messages(PREVIOUS)["assessment"]
    assert sent == (
        "We have more information.\n\n"
        "This is a stale list of possibilities, made from an earlier, shorter transcript:\n"
        "Diverticulitis\nOvarian cyst\nEctopic pregnancy\n\n"
        f"Here is the updated transcript of the consultation so far:\n{TRANSCRIPT}")
    # Stale list first, evidence last, previous order kept.
    positions = [sent.index(n) for n in ("Diverticulitis", "Ovarian cyst", "Ectopic pregnancy")]
    assert positions == sorted(positions)
    assert positions[-1] < sent.index(TRANSCRIPT)
    assert sent.endswith(TRANSCRIPT)


def test_later_pass_message_carries_names_only():
    sent = _sent_messages(PREVIOUS)["assessment"]
    assert "Diverticulitis" in sent          # the list did reach the message
    for absent in ("RATIONALE-", "QUESTION-ONE", "SIGN-ONE", "likelihood", "rationale",
                   "high", "moderate", "low", "{", "PREVIOUS ASSESSMENT", "stable"):
        assert absent not in sent, absent


def test_urgency_and_affect_messages_do_not_carry_the_list():
    for previous in (None, PREVIOUS):
        seen = _sent_messages(previous)
        assert seen["urgency"] == f"LIVE TRANSCRIPT SO FAR:\n{TRANSCRIPT}"
        assert seen["affect"] == cds.affect_message(TRANSCRIPT)


def test_assessment_prompt_has_no_revise_and_keep_stable_rules():
    text = cds.ASSESSMENT_PROMPT.lower()
    for phrase in ("revision rules", "verbatim", "churn", "keeping it stable",
                   "previous assessment"):
        assert phrase not in text, phrase


def test_assessment_prompt_names_no_country():
    text = cds.ASSESSMENT_PROMPT.lower()
    for country in ("sri lanka", "united kingdom", "britain", "england", "scotland",
                    "wales", "ireland", "india"):
        assert country not in text, country
    assert not re.search(r"\buk\b", text)
