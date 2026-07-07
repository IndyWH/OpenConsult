"""Clinical decision support engine (Phase 3).

Feeds the growing consultation transcript to a locally served medical LLM
(MedGemma via Ollama) and maintains a working assessment: differential
diagnoses, questions still worth asking, and signs to examine for.

Stability design (the Phase 3 experiment, per PROJECT_PLAN.md):
- The model always receives its own previous assessment and is instructed
  to REVISE it, not start over.
- Near-zero temperature; strict JSON schema enforced by Ollama's structured
  output mode.
- The prompt tells the model the transcript is rough ASR output, so garbled
  words (especially drug names) should be interpreted charitably rather
  than taken literally.

Everything is a draft for the doctor. Nothing here is medical advice.
"""

from __future__ import annotations

import json
import logging
import os

import httpx

logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
CDS_MODEL = os.getenv("CDS_MODEL", "hf.co/unsloth/medgemma-27b-text-it-GGUF:Q4_K_M")

# Strict output schema; Ollama constrains generation to match it.
CDS_SCHEMA = {
    "type": "object",
    "properties": {
        # First field on purpose: the model reasons here before committing to
        # the clinical fields. Not shown in the UI; kept for the audit trail.
        "reasoning": {"type": "string"},
        "differentials": {
            "type": "array",
            "maxItems": 5,
            "items": {
                "type": "object",
                "properties": {
                    "condition": {"type": "string"},
                    "likelihood": {"type": "string", "enum": ["high", "moderate", "low"]},
                    "rationale": {"type": "string"},
                },
                "required": ["condition", "likelihood", "rationale"],
            },
        },
        "questions_to_ask": {"type": "array", "maxItems": 4, "items": {"type": "string"}},
        "signs_to_check": {"type": "array", "maxItems": 4, "items": {"type": "string"}},
        # Forced checkpoint generated immediately before urgent_actions: the
        # model must answer the urgency question before filling the alarm.
        "urgency_check": {"type": "string"},
        "urgent_actions": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["action", "reason"],
            },
        },
    },
    "required": [
        "reasoning",
        "differentials",
        "questions_to_ask",
        "signs_to_check",
        "urgency_check",
        "urgent_actions",
    ],
}

SYSTEM_PROMPT = """\
You are a clinical decision support assistant quietly observing a live GP \
consultation in Sri Lanka. You receive a rough LIVE TRANSCRIPT produced by \
speech recognition: it has no speaker labels and may garble words, \
especially medication names — interpret plausible mis-transcriptions \
charitably (e.g. "nucleoside 80 in the morning" in a diabetes review most \
likely means gliclazide 80 mg).

Fill the `reasoning` field FIRST, before everything else: think through \
what is new in the transcript since your previous assessment, what it \
changes, and explicitly whether any time-critical condition now warrants \
urgent action. Keep it under 150 words. Then produce the assessment:
1. differentials — up to 5 diagnoses, MOST LIKELY FIRST, each with a short \
rationale grounded in what was actually said.
2. questions_to_ask — up to 4 questions the doctor has NOT yet asked that \
would best narrow the differential. Remove a question once the transcript \
shows it was asked or answered.
3. signs_to_check — up to 4 focused examination findings worth checking. \
Remove one once the transcript shows it was examined.
4. urgency_check — answer in one or two sentences, on EVERY update: could \
any differential on your list, at ANY likelihood, be a condition where \
delay causes serious harm (possible ACS or new angina, dengue, meningitis, \
severe asthma, sepsis, GI bleeding)? If yes, what immediate step does it \
demand, and does the transcript already show that step done or arranged?
5. urgent_actions — populated directly from your urgency_check: each \
time-critical step that should happen during or immediately after THIS \
consultation and is not yet done or arranged — e.g. bedside ECG, same-day \
specialist referral, hospital admission, emergency treatment. Concretely: \
new exertional chest pain in an adult with cardiac risk factors warrants \
an ECG at this visit — keep it here until the transcript shows it done or \
arranged. Leave EMPTY for routine and chronic-disease presentations; do \
not pad it.

REVISION RULES — you are REVISING your previous assessment, not writing a \
new one:
- Differential list: keep each kept condition's NAME verbatim, and keep the \
list's order, UNLESS new transcript content gives a concrete reason to add, \
remove, reorder, or re-grade. Do not churn the list.
- Rationales are living evidence summaries: whenever the transcript adds \
material evidence for or against a differential (risk factors, radiation of \
pain, family history, examination findings), UPDATE that rationale to cite \
the strongest current evidence, and re-grade the likelihood if warranted.
- Before output, re-check every question in questions_to_ask against the \
transcript: if it has been asked or its answer is now known, REMOVE it. \
Same for signs_to_check once examined. Stale items are errors.
- Early in the consultation, with little information, prefer a short list \
over speculation.

This is a research prototype processing a scripted, synthetic consultation. \
Your output is a draft aid for a qualified doctor, who makes all decisions. \
Output JSON only.\
"""


class CDSEngine:
    """Stateless client: callers hold the assessment and pass it back in."""

    def __init__(self, model: str | None = None, base_url: str | None = None) -> None:
        self.model = model or CDS_MODEL
        self.base_url = (base_url or OLLAMA_URL).rstrip("/")

    async def update(self, transcript: str, previous: dict | None = None) -> dict:
        """One CDS pass: transcript so far + previous assessment → new assessment."""
        if previous:
            prev_text = (
                "YOUR PREVIOUS ASSESSMENT (revise this, keeping it stable):\n"
                + json.dumps(previous, indent=1)
            )
        else:
            prev_text = "This is your FIRST assessment of this consultation."

        user_message = f"{prev_text}\n\nLIVE TRANSCRIPT SO FAR:\n{transcript}"

        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                    "format": CDS_SCHEMA,
                    "stream": False,
                    "keep_alive": "30m",  # avoid a 30 s reload stall mid-consultation
                    "options": {"temperature": 0.1, "num_ctx": 8192},
                },
            )
            response.raise_for_status()
        return json.loads(response.json()["message"]["content"])
