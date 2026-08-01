"""Clinical decision support engine (Phase 3).

Feeds the growing consultation transcript to a locally served medical LLM
(MedGemma via Ollama) and maintains a working assessment: differential
diagnoses, questions still worth asking, signs to examine for, and an
urgency alarm for time-critical presentations.

Architecture: THREE model calls per update, one job each.

1. Assessment call — differentials / questions / signs. Receives its own
   previous output and revises it under stability rules (don't churn the
   list; rationales accumulate evidence).
2. Urgency call — a stateless "safety officer" that sees only the current
   transcript, fresh every update. Evaluation showed the combined call
   failed in both directions: the previous assessment anchored the alarm
   (empty stayed empty), and the alarm competed with the revision task
   (the model wrote "immediate ECG demanded" while emitting an empty
   actions array). Isolated, the same model answers correctly.
3. Affect call (2026-08-01) — the same lesson, learned twice. The
   patient_affect hint rode the assessment call from 2026-07-28 and
   returned "neutral" on every pass of consultations 464, 465 and 466,
   including one where the pain radiated to the jaw. It was not anchoring
   (it is never passed back) and not short of transcript (it sees all of
   it from zero seconds); it was item 4 of a six-hundred-word prompt that
   spends most of its words asking for conservatism. Now stateless, with
   one plain question, seeing the transcript and nothing clinical. It runs
   LAST and FAIL-SOFT: a failure logs a warning and falls back to
   "neutral", because the face must never cost the doctor the
   differentials, the questions or the alarm.

Code, not the model, does the bookkeeping: the alarm is cleared
deterministically when the urgency call reports the step already arranged,
and "arranged" latches for the rest of the session once seen.

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

# ONE context length for every MedGemma call in the app — CDS, RAG and
# the note (app/rag.py and app/notes.py import this). Session 5, owner
# decision: Ollama RELOADS the model whenever num_ctx changes between
# calls, and the live path (8192) and note path (16384) used to differ —
# a reload measured at 3.9 s warm in the VRAM investigation and ~10 s on
# consultation 454's first live assessment. One shared constant so the
# paths cannot drift apart again. VRAM cost of 16384 over 8192 is only
# ~679 MiB of KV cache; the worst measured total in exactly this
# configuration (MedGemma @16384 + embeddinggemma) was 22309 MiB with
# 2255 MiB free — it fits (HANDOVER, "VRAM baseline — MEASURED").
CDS_NUM_CTX = int(os.getenv("CDS_NUM_CTX", "16384"))

ASR_CAVEAT = """\
You receive a rough LIVE TRANSCRIPT produced by speech recognition: it has \
no speaker labels and may garble words, especially medication names — \
interpret plausible mis-transcriptions charitably (e.g. "nucleoside 80 in \
the morning" in a diabetes review most likely means gliclazide 80 mg).\
"""

# ---------------------------------------------------------------- assessment

ASSESSMENT_SCHEMA = {
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
        # patient_affect is NOT here. It rode this call from 2026-07-28
        # until 2026-08-01, when it moved to its own call and schema for
        # the same reason the urgency check has one — see the module
        # docstring, and AFFECT_PROMPT below. This assessment call must not
        # mention affect anywhere: the clinical reasoning around it is what
        # corrupted the judgement.
    },
    "required": ["reasoning", "differentials", "questions_to_ask",
                 "signs_to_check"],
}

ASSESSMENT_PROMPT = f"""\
You are a clinical decision support assistant quietly observing a live GP \
consultation in Sri Lanka. {ASR_CAVEAT}

Fill the `reasoning` field FIRST: think through what is new in the \
transcript since your previous assessment and what it changes. Keep it \
under 120 words. Then produce the assessment:
1. differentials — up to 5 diagnoses, MOST LIKELY FIRST, each with a short \
rationale grounded in what was actually said.
2. questions_to_ask — up to 4 questions the doctor has NOT yet asked that \
would best narrow the differential, ORDERED BY CLINICAL PRIORITY: the most \
clinically appropriate next question FIRST. Re-rank freely as new \
information changes what matters most — the order is living, not pinned. \
Remove a question once the transcript shows it was asked or answered.
3. signs_to_check — up to 4 focused examination findings worth checking. \
Remove one once the transcript shows it was examined.

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

# ------------------------------------------------------------------- urgency

URGENCY_SCHEMA = {
    "type": "object",
    "properties": {
        "reasoning": {"type": "string"},
        "time_critical_possible": {"type": "boolean"},
        "already_done_or_arranged": {"type": "boolean"},
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
        "time_critical_possible",
        "already_done_or_arranged",
        "urgent_actions",
    ],
}

URGENCY_PROMPT = f"""\
You are the urgency safety-check for a live GP consultation in Sri Lanka. \
You have ONE job: decide whether anything in this consultation is \
time-critical. {ASR_CAVEAT}

Time-critical means exactly this: if the immediate step does not happen \
TODAY, there is a real risk of death or major irreversible harm within \
hours to days. In `reasoning` (under 80 words), answer: could ANY \
plausible cause of this presentation, even an unconfirmed one, meet that \
bar? Examples that DO: possible ACS or NEW cardiac-sounding chest pain \
(new angina needs an ECG at this visit even if currently stable); a \
resolved episode of focal weakness or slurred speech (TIA until proven \
otherwise); GI bleeding (melaena counts); pulmonary embolism; sepsis or a \
shocked/drowsy/mottled child; severe asthma; meningitis; dengue WITH \
warning signs (severe abdominal pain, persistent vomiting, bleeding, \
drowsiness, not drinking, no urine, cold peripheries) — suspected dengue \
in an alert, drinking child is handled with same-day testing and review, \
which is routine care, not an alarm. Judge on reasonable SUSPICION, not \
confirmation — this alarm exists to prompt action before the picture is \
complete.

Examples that do NOT meet the bar, however much they deserve proactive \
care: chronic complications needing better management (diabetic neuropathy \
without acute infection or ulcer), suboptimal control of diabetes, \
hypertension, or asthma, overdue screening, routine specialist referrals; \
an uncomplicated febrile illness in an alert child without warning signs \
(drowsiness, shock, bleeding, not drinking, no urine). Medication \
optimisation and routine referrals are NEVER urgent_actions. Taking the \
history, examining the patient, and ordering routine same-visit tests are \
the consultation itself — never urgent_actions. "Could cause harm over \
months if unmanaged" is false for time_critical_possible; only "could \
cause serious harm within hours to days" is true.

Then set:
- time_critical_possible: your conclusion as a boolean.
- already_done_or_arranged: true if the transcript shows the needed \
step done, in progress, or COMMITTED TO by the doctor — "let's do that \
ECG now", "I'm calling the ambulance", "I'm writing the urgent referral", \
"you're going to hospital today" all count as arranged.
- urgent_actions: if time_critical_possible is true, the immediate \
step(s) — bedside ECG, same-day specialist referral, hospital admission, \
emergency treatment — each with a one-line reason. Fill this whenever \
time_critical_possible is true, even if already arranged (the caller \
handles that case). Empty only when nothing is time-critical.

Routine and stable chronic-disease presentations are NOT time-critical: \
for them return time_critical_possible false and an empty list. \
Output JSON only.\
"""

# -------------------------------------------------------------------- affect

AFFECT_SCHEMA = {
    "type": "object",
    "properties": {
        "patient_affect": {
            "type": "string",
            "enum": ["happy", "positive", "neutral", "low", "anxious",
                     "distressed", "angry"],
        },
    },
    "required": ["patient_affect"],
}

# THE LAST LINE IS LOAD-BEARING AND MUST SURVIVE ANY LATER EDIT: judge the
# person, not how serious their illness is. Without it patient_affect
# becomes a proxy for clinical urgency, which would put the alarm on the
# face by a back door — and the urgency alarm is deliberately kept OFF the
# face (see the module docstring in app/face.py). Do not remove it as
# redundant.
#
# Its own call since 2026-08-01 (owner decision), for the reason the
# urgency check has one: 464, 465 and 466 all returned neutral on every
# pass, including one where the pain radiated to the jaw. The field was
# item 4 of a six-hundred-word clinical prompt that spends most of its
# words asking for conservatism. This prompt asks one plain question.
#
# It asks a NOW question, and it says so twice over, after consultation
# 467: a patient who opened with an all-clear after cancer surgery and
# turned sad about his wife's illness was still read as "happy" on a
# transcript that contained "I'm sad about that". The call sees the whole
# consultation, so without this it summarises a document instead of
# reporting a moment — and the sadness being about someone else was the
# second half of the miss.
AFFECT_PROMPT = """\
You are reading the transcript of a doctor's consultation.
Decide how the PATIENT is feeling RIGHT NOW, in what they have just \
said — not across the consultation as a whole.
Earlier parts of the transcript are context only. A patient can arrive \
delighted and turn sad, or arrive frightened and be reassured: report the \
present moment, not the balance of the conversation.
Feelings about other people count. A patient who is sad about a family \
member's illness is sad.
Answer with exactly one of: happy, positive, neutral, low, anxious, \
distressed, angry.
  happy       delight or relief: an all-clear, a worry lifted, laughter, \
enjoying the visit
  positive    pleased, in good spirits
  neutral     settled, taking things in their stride
  low         flat, sad, downhearted
  anxious     worried, frightened, uneasy
  distressed  badly upset, or in real difficulty
  angry       angry at the wait, at not being believed, at being in pain
Judge the person, not how serious their illness is.\
"""


class CDSEngine:
    """Stateless client: callers hold the assessment and pass it back in."""

    def __init__(self, model: str | None = None, base_url: str | None = None) -> None:
        self.model = model or CDS_MODEL
        self.base_url = (base_url or OLLAMA_URL).rstrip("/")

    async def _chat(self, system: str, user: str, schema: dict) -> dict:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "format": schema,
                    "stream": False,
                    "keep_alive": "30m",  # avoid a 30 s reload stall mid-consultation
                    "options": {
                        # Greedy + fixed seed: an alarm must not be a coin flip,
                        # and evaluations must be reproducible.
                        "temperature": float(os.getenv("CDS_TEMPERATURE", "0.0")),
                        "seed": int(os.getenv("CDS_SEED", "42")),
                        "num_ctx": CDS_NUM_CTX,
                    },
                },
            )
            response.raise_for_status()
        return json.loads(response.json()["message"]["content"])

    async def update(self, transcript: str, previous: dict | None = None) -> dict:
        """One CDS pass: transcript so far + previous assessment → new assessment.

        Returns the assessment fields plus `urgency_check` (the safety
        officer's booleans and reasoning), `urgent_actions` (already
        bookkept: empty when nothing is due or everything is arranged) and
        `patient_affect` (its own stateless call since 2026-08-01 — see
        the module docstring; it is fail-soft and never fails the pass).
        The returned shape is unchanged by that split: `patient_affect`
        sits at the top level exactly where it always has.
        """
        if previous:
            stable_fields = {
                k: previous[k]
                for k in ("differentials", "questions_to_ask", "signs_to_check")
                if k in previous
            }
            prev_text = (
                "YOUR PREVIOUS ASSESSMENT (revise this, keeping it stable):\n"
                + json.dumps(stable_fields, indent=1)
            )
        else:
            prev_text = "This is your FIRST assessment of this consultation."

        transcript_text = f"LIVE TRANSCRIPT SO FAR:\n{transcript}"

        assessment = await self._chat(
            ASSESSMENT_PROMPT, f"{prev_text}\n\n{transcript_text}", ASSESSMENT_SCHEMA
        )
        urgency = await self._chat(URGENCY_PROMPT, transcript_text, URGENCY_SCHEMA)

        # Third call, LAST and FAIL-SOFT. It sees the transcript and
        # nothing else — no previous answer to anchor on, no differentials,
        # no urgency verdict; a fresh judgement of the whole consultation
        # every pass, with nothing clinical in its context.
        #
        # An affect failure must NEVER cost the doctor the differentials,
        # the questions or the alarm: the face is a comfort feature and the
        # rest of this pass is the clinical output. So it is wrapped, and a
        # failure falls back to neutral with a warning.
        try:
            affect = await self._chat(AFFECT_PROMPT, transcript_text, AFFECT_SCHEMA)
            assessment["patient_affect"] = affect["patient_affect"]
        except Exception as exc:  # noqa: BLE001 - the clinical pass survives
            logger.warning("Affect call failed, falling back to neutral: %s", exc)
            assessment["patient_affect"] = "neutral"

        # Deterministic bookkeeping. "Arranged" latches for the session: once
        # the doctor has committed to the urgent step, the alarm stays
        # cleared (the model can flap this boolean on later passes).
        arranged = urgency["already_done_or_arranged"] or bool(
            previous and previous.get("urgency_check", {}).get("already_done_or_arranged")
        )
        assessment["urgency_check"] = {
            "time_critical_possible": urgency["time_critical_possible"],
            "already_done_or_arranged": arranged,
            "reason": urgency["reasoning"],
        }
        assessment["urgent_actions"] = (
            urgency["urgent_actions"]
            if urgency["time_critical_possible"] and not arranged
            else []
        )
        return assessment
