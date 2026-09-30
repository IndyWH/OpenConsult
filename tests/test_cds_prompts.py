"""Properties of the CDS prompt text itself. Needs no model.

Owner decisions of 2026-09-30 (HANDOVER.md, CDS prompt: weigh a stale
list): OpenConsult v1.1 is for UK GPs, so no prompt names a country, and
the dengue examples left the urgency prompt with Sri Lanka.
"""

from __future__ import annotations

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
