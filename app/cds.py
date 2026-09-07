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

A fourth call lives here too, outside `update()`: the END-OF-TURN OFFICER
(Phase 7c slice 3, PHASE_7C_SPEC.md §5) — a tiny stateless call in the
affect call's shape that auto mode asks, when the patient has been quiet
for a while, whether they have finished the thought and whether they have
explicitly handed the conversation back. It never raises: a failure or a
timeout is returned as a failed verdict, and the caller falls back to a
silence rule (`turn_finished`). Officer QUALITY is an evals question, not
a unit-test one.

And a fifth, the same shape (Phase 7c slice 4, spec §4 decision D1): the
TOPIC CALL, which names what one agenda question is about as a short noun
phrase ("the chest pain") so auto mode can ask it open-form through an
owner-approved template. Stateless, its own prompt and timeout, never
raises; on failure, timeout, or an unusable phrase the caller asks the
agenda question verbatim — still correct, just less open. The CDS
assessment prompt is untouched by it (the alternative, a topic field in
the assessment schema, was declined for exactly that reason).

Everything is a draft for the doctor. Nothing here is medical advice.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass

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

# Phase 7c (PHASE_7C_SPEC.md §5, §12): the end-of-turn officer's own
# timeout, in seconds — a tiny call that must answer inside the pause it is
# judging, then fall back (silence-based, in app/main.py's wiring). An
# UNCALIBRATED GUESS; the mock-patient round is the run that informs it.
AUTO_OFFICER_TIMEOUT_S = float(os.getenv("AUTO_OFFICER_TIMEOUT_S", "2.0"))
# A busy model is a wait, not a failure (owner decision 2026-09-07, pilot
# 485 E4): while a CDS pass is in flight the officer's call is bounded by
# this instead — the model serves one request at a time, and in 485 every
# one of the seven officer timeouts fell inside a pass's call windows.
AUTO_OFFICER_MAX_WAIT_S = float(os.getenv("AUTO_OFFICER_MAX_WAIT_S", "30.0"))
# Phase 7c (PHASE_7C_SPEC.md §4, decision D1): the topic call's own
# timeout — the tiny call that names what an agenda question is about so
# it can be asked open-form; on timeout the question is asked verbatim.
# An UNCALIBRATED GUESS; the mock-patient round is the run that informs it.
AUTO_TOPIC_TIMEOUT_S = float(os.getenv("AUTO_TOPIC_TIMEOUT_S", "2.0"))

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

# How many turns at the end of the transcript count as "right now".
# A FIRST GUESS, NOT A TUNED VALUE: four is a plausible present moment for
# a live transcript that commits roughly sentence-sized turns, and nothing
# has been measured. It wants calibrating against real consultations —
# against the PATIENT_AFFECT log of a consultation whose emotional turn is
# known, which is what 467 provided for the first time.
AFFECT_RECENT_TURNS = 4


def affect_message(transcript: str) -> str:
    """The affect call's user message.

    The whole transcript first, for context, and then the most recent
    turns in a labelled block at the END — the end of the message is what
    the model attends to most, so the thing being judged goes last. This
    is the second half of the consultation-467 fix: the prompt asks a NOW
    question (see AFFECT_PROMPT) and this puts the now in front of it.

    A transcript shorter than AFFECT_RECENT_TURNS turns IS the recent
    turns, so it is sent once rather than repeated twice.
    """
    turns = [line for line in transcript.splitlines() if line.strip()]
    full = f"LIVE TRANSCRIPT SO FAR:\n{transcript}"
    if len(turns) <= AFFECT_RECENT_TURNS:
        return full
    recent = "\n".join(turns[-AFFECT_RECENT_TURNS:])
    return (f"{full}\n\n"
            f"THE MOST RECENT TURNS (this is the moment you are judging):\n"
            f"{recent}")


# ------------------------------------------- end-of-turn officer (Phase 7c)
#
# PHASE_7C_SPEC.md §5. Auto mode must decide, from a pause, whether the
# patient has finished speaking or is merely drawing breath — and whether
# they have handed the conversation back outright ("that's all", "what do
# you think?"). Two booleans, one plain question each, in the affect call's
# shape: stateless, sees the transcript and nothing clinical, the recent
# turns repeated at the END where the model attends most. It reuses the
# engine's `_chat` — same model, temperature 0, seed 42, CDS_NUM_CTX — so
# MedGemma is never reloaded for it; only the timeout is its own.
#
# The tie-break is written into the prompt: when in doubt, NOT finished.
# A slow system is polite; an interrupting one fails the eval.

OFFICER_SCHEMA = {
    "type": "object",
    "properties": {
        "finished_thought": {"type": "boolean"},
        "handed_back": {"type": "boolean"},
    },
    "required": ["finished_thought", "handed_back"],
}

OFFICER_PROMPT = """\
You are listening to a patient telling a doctor what has brought them in. \
The patient has just gone quiet. Judge ONLY the most recent turns; earlier \
transcript is context.
Answer two questions, and nothing else.
finished_thought: has the patient come to the end of what they were \
saying — a complete thought, a natural stopping point — or have they \
paused mid-thought? A trailing "and", "so", "because", "but", an unfinished \
list, or a sentence that stops before its point means NOT finished. When \
in doubt, answer false: waiting is polite, interrupting is not.
handed_back: has the patient EXPLICITLY handed the conversation back to \
the doctor — "that's all", "that's it really", "that's everything", \
"what do you think?", "so what should I do?", a direct question to the \
doctor — rather than merely stopped? Only an explicit hand-back counts; \
silence is not one.\
"""

# How many turns at the end of the transcript count as "just now" — the
# affect call's window, reused unmeasured (AFFECT_RECENT_TURNS is itself
# a first guess). The mock-patient round is the run that informs it.
OFFICER_RECENT_TURNS = AFFECT_RECENT_TURNS


def officer_message(transcript: str) -> str:
    """The officer's user message: the whole transcript for context, then
    the most recent turns in a labelled block at the END — the affect
    call's construction (affect_message), for the same reason: the thing
    being judged goes where the model attends most. A transcript no longer
    than the window is sent once."""
    turns = [line for line in transcript.splitlines() if line.strip()]
    full = f"LIVE TRANSCRIPT SO FAR:\n{transcript}"
    if len(turns) <= OFFICER_RECENT_TURNS:
        return full
    recent = "\n".join(turns[-OFFICER_RECENT_TURNS:])
    return (f"{full}\n\n"
            f"THE MOST RECENT TURNS (the patient went quiet after these):\n"
            f"{recent}")


@dataclass(frozen=True)
class OfficerVerdict:
    """What the officer said — or that it did not answer.

    `failed` is None when the model answered; otherwise it names the
    failure (error class and message, or "timeout") and BOTH booleans are
    False: a failed officer never claims a turn ended or a hand-back. The
    caller applies the silence-based fallback (`turn_finished`) and audits
    the failure; nothing here raises into a live session.
    """

    finished_thought: bool
    handed_back: bool
    failed: str | None = None
    elapsed_ms: int = 0


def turn_finished(verdict: OfficerVerdict, quiet_s: float, fallback_s: float) -> bool:
    """Has the patient's turn ended? The officer's word when it answered;
    when it did not, a quiet span of at least `fallback_s`
    (AUTO_EOT_FALLBACK_S — longer than the officer's own trigger, so the
    fallback errs toward waiting). Pure, so the fallback rule is testable
    without a model."""
    if verdict.failed is None:
        return verdict.finished_thought
    return float(quiet_s) >= float(fallback_s)


# --------------------------------------------------- topic call (Phase 7c)
#
# PHASE_7C_SPEC.md §4, D1. One question in, one noun phrase out, in the
# affect call's shape. The phrase goes into a slot in an owner-approved
# template ("Can you tell me more about {topic}?"), so the prompt asks for
# exactly the thing that fits that slot and nothing else — no verb, no
# question, no diagnosis, no advice — and `clean_topic_phrase` refuses
# anything that does not look like a slot filler. Refusal is fail-soft:
# the caller asks the agenda question verbatim.

TOPIC_SCHEMA = {
    "type": "object",
    "properties": {"topic": {"type": "string"}},
    "required": ["topic"],
}

TOPIC_PROMPT = """\
You are helping a doctor ask a question in an open way. You are given ONE \
question from the doctor's list. Name what it is ABOUT — the thing the \
patient would talk about — as a short noun phrase, the way a doctor \
would say it to the patient: "the chest pain", "your sleep", "the tablets \
you started last week", "the falls".
Rules: two to six words; lower case; no verb; not a question; no \
diagnosis; no advice; nothing the patient has not already mentioned. The \
phrase must fit the sentence "Can you tell me more about ___?" exactly.
Answer with the phrase only.\
"""

# Bounds on a usable slot filler, stated as such: a phrase longer than
# this is a sentence, not a topic, and would read oddly in the template.
TOPIC_MAX_WORDS = 8
TOPIC_MAX_CHARS = 60


def topic_message(question: str) -> str:
    """The topic call's user message: the one question, labelled."""
    return f"THE QUESTION:\n{question.strip()}"


def clean_topic_phrase(raw) -> str | None:
    """A usable slot filler, or None.

    Whitespace collapsed; surrounding quotes and a trailing full stop
    stripped; anything empty, longer than the bounds, carrying a question
    mark or a line break, or that is not a string, is unusable — the
    caller then asks verbatim rather than speak a broken sentence.
    """
    if not isinstance(raw, str):
        return None
    phrase = " ".join(raw.split()).strip().strip('"\'“”‘’').strip()
    phrase = phrase.rstrip(".").strip()
    if not phrase or "?" in phrase or "\n" in raw.strip("\n"):
        return None
    if len(phrase.split()) > TOPIC_MAX_WORDS or len(phrase) > TOPIC_MAX_CHARS:
        return None
    return phrase


@dataclass(frozen=True)
class TopicVerdict:
    """What the topic call named — or that it did not.

    `topic` is a usable slot filler when `failed` is None; otherwise
    `failed` names the failure (error, "timeout", or "unusable: …") and
    `topic` is None. The caller asks the agenda question verbatim.
    """

    topic: str | None
    failed: str | None = None
    elapsed_ms: int = 0


class CDSEngine:
    """Stateless client: callers hold the assessment and pass it back in."""

    async def topic_for(self, question: str) -> TopicVerdict:
        """The topic call (Phase 7c, spec §4 D1). NEVER RAISES.

        Bounded by AUTO_TOPIC_TIMEOUT_S end to end (asyncio.wait_for and
        the HTTP timeout beneath it). A failure, a timeout, or a phrase
        `clean_topic_phrase` refuses comes back as a failed verdict; the
        caller asks the question verbatim and audits (auto.topic_failed).
        """
        started = time.perf_counter()
        try:
            reply = await asyncio.wait_for(
                self._chat(TOPIC_PROMPT, topic_message(question), TOPIC_SCHEMA,
                           timeout=AUTO_TOPIC_TIMEOUT_S),
                timeout=AUTO_TOPIC_TIMEOUT_S)
            raw = reply["topic"]
        except asyncio.TimeoutError:
            elapsed = round(1000 * (time.perf_counter() - started))
            logger.warning("Topic call timed out after %d ms (AUTO_TOPIC_TIMEOUT_S=%.1f); "
                           "asking verbatim", elapsed, AUTO_TOPIC_TIMEOUT_S)
            return TopicVerdict(None, failed="timeout", elapsed_ms=elapsed)
        except Exception as exc:  # noqa: BLE001 - fail-soft by contract
            elapsed = round(1000 * (time.perf_counter() - started))
            logger.warning("Topic call failed (%s: %s); asking verbatim",
                           type(exc).__name__, exc)
            return TopicVerdict(None, failed=f"{type(exc).__name__}: {exc}",
                                elapsed_ms=elapsed)
        elapsed = round(1000 * (time.perf_counter() - started))
        topic = clean_topic_phrase(raw)
        if topic is None:
            logger.info("Topic call returned an unusable phrase %r; asking verbatim", raw)
            return TopicVerdict(None, failed=f"unusable: {raw!r}", elapsed_ms=elapsed)
        return TopicVerdict(topic, elapsed_ms=elapsed)

    def __init__(self, model: str | None = None, base_url: str | None = None) -> None:
        self.model = model or CDS_MODEL
        self.base_url = (base_url or OLLAMA_URL).rstrip("/")

    async def end_of_turn(self, transcript: str, *,
                          timeout_s: float | None = None) -> OfficerVerdict:
        """The end-of-turn officer (Phase 7c, spec §5). NEVER RAISES.

        Bounded end to end (asyncio.wait_for around the call, and the same
        value as the HTTP timeout beneath it) by AUTO_OFFICER_TIMEOUT_S —
        or by `timeout_s` when the caller passes one: the wiring stretches
        the bound to AUTO_OFFICER_MAX_WAIT_S while a CDS pass is in flight
        (owner decision 2026-09-07, pilot 485 E4: a busy model is a wait,
        not a failure). Any failure — connection, HTTP status, malformed
        reply, timeout — comes back as a failed verdict with both booleans
        False, for the caller to fall back on silence and audit
        (auto.officer_failed). A detected hand-back is logged here, as the
        prereg requires for scoring, and again by the caller in its
        transition record.
        """
        bound = float(timeout_s) if timeout_s is not None else AUTO_OFFICER_TIMEOUT_S
        started = time.perf_counter()
        try:
            reply = await asyncio.wait_for(
                self._chat(OFFICER_PROMPT, officer_message(transcript), OFFICER_SCHEMA,
                           timeout=bound),
                timeout=bound)
            finished = bool(reply["finished_thought"])
            handed_back = bool(reply["handed_back"])
        except asyncio.TimeoutError:
            elapsed = round(1000 * (time.perf_counter() - started))
            logger.warning("End-of-turn officer timed out after %d ms (bound %.1f s%s); "
                           "falling back to silence", elapsed, bound,
                           "" if timeout_s is None else ", stretched for a CDS pass in flight")
            return OfficerVerdict(False, False, failed="timeout", elapsed_ms=elapsed)
        except Exception as exc:  # noqa: BLE001 - fail-soft by contract
            elapsed = round(1000 * (time.perf_counter() - started))
            logger.warning("End-of-turn officer failed (%s: %s); falling back to silence",
                           type(exc).__name__, exc)
            return OfficerVerdict(False, False, failed=f"{type(exc).__name__}: {exc}",
                                  elapsed_ms=elapsed)
        elapsed = round(1000 * (time.perf_counter() - started))
        if handed_back:
            logger.info("End-of-turn officer: hand-back detected (%d ms)", elapsed)
        return OfficerVerdict(finished, handed_back, elapsed_ms=elapsed)

    async def _chat(self, system: str, user: str, schema: dict, *,
                    timeout: float = 180.0) -> dict:
        async with httpx.AsyncClient(timeout=timeout) as client:
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
        # no urgency verdict; a fresh judgement every pass, with nothing
        # clinical in its context. Since 2026-08-01 the transcript arrives
        # with the most recent turns repeated in a labelled block at the
        # end (affect_message): the question is about the present moment,
        # so the present moment goes where the model attends most.
        #
        # An affect failure must NEVER cost the doctor the differentials,
        # the questions or the alarm: the face is a comfort feature and the
        # rest of this pass is the clinical output. So it is wrapped, and a
        # failure falls back to neutral with a warning.
        try:
            affect = await self._chat(
                AFFECT_PROMPT, affect_message(transcript), AFFECT_SCHEMA)
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
