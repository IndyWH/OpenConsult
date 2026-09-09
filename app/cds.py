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
from collections.abc import Mapping
from dataclasses import dataclass, field

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

# Cap runaway generation (owner decision 2026-09-07, pilot 486 F3). In 486
# an assessment call generated 7,211+ tokens at 40 t/s for the full 180 s
# of the client timeout (a normal pass produces 500–620), holding Ollama's
# single slot while five deferred officer calls died behind it and the
# patient waited 3 min 18 s. Every model call now carries a maximum
# output (num_predict) — about three times the recorded normal for the
# long calls, small caps for the short ones — and the assessment call's
# own timeout is 60 s, not 180. A call that hits its cap or timeout is a
# CDSRunaway: the pass fails, the previous assessment is kept, and the
# urgency check still runs on its own call (the alarm is never lost).
CDS_ASSESSMENT_MAX_TOKENS = int(os.getenv("CDS_ASSESSMENT_MAX_TOKENS", "1500"))
CDS_URGENCY_MAX_TOKENS = int(os.getenv("CDS_URGENCY_MAX_TOKENS", "1000"))
CDS_AFFECT_MAX_TOKENS = int(os.getenv("CDS_AFFECT_MAX_TOKENS", "800"))
AUTO_OFFICER_MAX_TOKENS = int(os.getenv("AUTO_OFFICER_MAX_TOKENS", "64"))
AUTO_TOPIC_MAX_TOKENS = int(os.getenv("AUTO_TOPIC_MAX_TOKENS", "48"))
CDS_ASSESSMENT_TIMEOUT_S = float(os.getenv("CDS_ASSESSMENT_TIMEOUT_S", "60.0"))

# The standing question queue's re-ranker (AGENDA_QUEUE_SPEC.md §3, slice
# 3): the short call after each answered turn that re-orders the pending
# questions and drops the ones the patient has just addressed. Its own
# timeout — on timeout the current order stands (auto.rerank_failed) — and
# its output cap: the reply is at most eight ids and a one-word reason per
# drop, so 200 tokens is about three times a full reply. Both UNCALIBRATED
# GUESSES; the next solo run informs them.
AUTO_RERANK_TIMEOUT_S = float(os.getenv("AUTO_RERANK_TIMEOUT_S", "2.0"))
AUTO_RERANK_MAX_TOKENS = int(os.getenv("AUTO_RERANK_MAX_TOKENS", "200"))


class CDSRunaway(Exception):
    """A model call hit its output cap or its timeout (pilot 486 F3). For
    the assessment call, `urgency` carries the urgency check's own
    result — bookkept exactly as a landed pass would have it — so the
    caller can keep the previous assessment and still act on an alarm."""

    def __init__(self, call: str, *, reason: str, tokens: int | None,
                 elapsed_ms: int, cap: int | None = None, timeout_s: float | None = None) -> None:
        super().__init__(f"{call} call {reason}: {tokens} tokens in {elapsed_ms} ms")
        self.call, self.reason, self.tokens = call, reason, tokens
        self.elapsed_ms, self.cap, self.timeout_s = elapsed_ms, cap, timeout_s
        self.urgency: dict | None = None

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
    "properties": {"topic": {"type": "string"}, "lay": {"type": "string"}},
    "required": ["topic", "lay"],
}

# Two fields since 2026-09-09 (owner decision, the D1 extension after
# consultation 486's "risk factors like hypertension" lesson): `topic`, as
# before, for the open-form template; and `lay`, the SAME question in plain
# spoken English for the verbatim ask — one sentence, no medical terms, no
# examples in brackets, nothing the question did not ask. Alba speaks the
# lay wording; the queue item, the panel and the never-twice guarantee keep
# the original text as the question's identity. The lay wording must pass
# the code-enforced subject guard (app/speech.py, lay_accepted) or the
# original is spoken verbatim.
TOPIC_PROMPT = """\
You are helping a doctor ask a question in an open, plain way. You are \
given ONE question from the doctor's list. Answer with two fields.
"topic": what the question is ABOUT — the thing the patient would talk \
about — as a short noun phrase, the way a doctor would say it to the \
patient: "the chest pain", "your sleep", "the tablets you started last \
week", "the falls". Rules: two to six words; lower case; no verb; not a \
question; no diagnosis; no advice; nothing the patient has not already \
mentioned. The phrase must fit the sentence "Can you tell me more about \
___?" exactly.
"lay": the SAME question in plain spoken English that a patient with no \
medical knowledge understands. Rules: one sentence, ending in a question \
mark; no medical terms; no examples in brackets; nothing the question did \
not ask — do not add, narrow or widen what is asked, and do not name \
examples the question did not name.
Answer with JSON only.\
"""

# Bounds on a usable lay wording, stated as such: one spoken sentence.
LAY_MAX_CHARS = 200
LAY_MIN_WORDS = 3

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


def clean_lay_wording(raw) -> str | None:
    """A usable lay wording, or None (owner decision 2026-09-09, D1
    extension).

    Whitespace collapsed; surrounding quotes stripped; a missing question
    mark appended. Unusable — the caller then speaks the original verbatim
    — is anything that is not a string, is empty or under LAY_MIN_WORDS
    words, exceeds LAY_MAX_CHARS, carries a line break, a bracket (the 486
    lesson: no examples in brackets), or more than one sentence, or ends
    as a statement rather than a question.
    """
    if not isinstance(raw, str):
        return None
    text = " ".join(raw.split()).strip().strip('"\'“”‘’').strip()
    if not text or "\n" in raw.strip("\n"):
        return None
    if any(ch in text for ch in "()[]{}"):
        return None
    if text.endswith((".", "!")):
        return None
    if not text.endswith("?"):
        text += "?"
    body = text[:-1]
    if any(ch in body for ch in ".?!;"):
        return None                              # more than one sentence
    if len(text) > LAY_MAX_CHARS or len(body.split()) < LAY_MIN_WORDS:
        return None
    return text


@dataclass(frozen=True)
class TopicVerdict:
    """What the topic call named — or that it did not.

    `topic` is a usable slot filler when `failed` is None; otherwise
    `failed` names the failure (error, "timeout", or "unusable: …") and
    `topic` is None. The caller asks the agenda question verbatim.

    `lay` (owner decision 2026-09-09, D1 extension) is the same call's
    plain-English wording of the question, cleaned, or None when the
    call failed or the wording was unusable (`lay_failed` says why). The
    caller still applies the subject guard before speaking it.
    """

    topic: str | None
    failed: str | None = None
    elapsed_ms: int = 0
    lay: str | None = None
    lay_failed: str | None = None


# ----------------------------------------- the re-ranker (standing queue)
#
# AGENDA_QUEUE_SPEC.md §3. A stateless call in the topic call's shape: the
# pending questions with their ids and the transcript since the last full
# pass landed (D-B: at most AUTO_RERANK_CONTEXT_TURNS turns, capped by
# characters — both the wiring's settings, applied by rerank_excerpt) in;
# the ids still worth asking, best first, and the ids to drop with a
# one-word reason each, out. It never writes a question: the whitelist
# (PHASE_7C_SPEC.md §4) is untouched because nothing it returns is text
# that could be spoken, only ids — and the queue's apply_rerank ignores
# any id that is not a known pending item, so it cannot invent, resurrect
# or touch an asked question either. Fail-soft: a timeout, an error or a
# malformed reply is a failed verdict and the current order stands.

RERANK_SCHEMA = {
    "type": "object",
    "properties": {
        "order": {"type": "array", "items": {"type": "string"}},
        "drop": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "string"}, "reason": {"type": "string"}},
                "required": ["id", "reason"],
            },
        },
    },
    "required": ["order", "drop"],
}

RERANK_PROMPT = """\
You are helping a doctor keep a short list of questions still worth asking \
a patient, part-way through a consultation. You are given the list — each \
question with an id — and what the patient has said since the list was last \
revised.
Return the ids still worth asking, in the best order for this moment: the \
question that follows most naturally from what the patient has just said \
comes first.
Drop any question the patient has already addressed in the excerpt. A \
question counts as answered when its SUBJECT was addressed, even if not every \
example in it was named — "any other risk factors (e.g. diabetes, high \
cholesterol)?" is answered once the patient has spoken about their risk \
factors, whether or not diabetes came up. Give each dropped id a one-word \
reason (for example: answered, addressed, volunteered).
Never write a new question. Use only the ids you were given — an id you were \
not given is ignored — and name each id at most once, in the order or in the \
drops. Answer with JSON only.\
"""


def rerank_excerpt(turns, *, max_turns: int, max_chars: int) -> str:
    """The re-ranker's excerpt (D-B): the last `max_turns` non-empty turns
    of `turns` — the committed transcript lines since the last full pass
    landed — joined one per line, and if still longer than `max_chars`
    cut from the FRONT so the most recent words survive (the thing being
    judged is what the patient has just said). Pure."""
    lines = [str(t).strip() for t in turns if str(t).strip()]
    if max_turns > 0:
        lines = lines[-max_turns:]
    text = "\n".join(lines)
    if max_chars > 0 and len(text) > max_chars:
        text = "…" + text[-max_chars:]
    return text


def rerank_message(pending, excerpt: str) -> str:
    """The user message: the pending questions with their ids, then the
    excerpt in a labelled block at the END, where the model attends most
    (the officer's and affect call's construction)."""
    listed = "\n".join(f"{item_id}: {str(text).strip()}" for item_id, text in pending)
    return (f"THE QUESTIONS STILL ON THE LIST (id: question):\n{listed}\n\n"
            f"WHAT THE PATIENT HAS SAID SINCE THE LIST WAS LAST REVISED:\n"
            f"{excerpt.strip() or '(nothing new)'}")


def one_word(reason) -> str:
    """The re-ranker's reason, held to one word for the audit row: the
    first alphabetic word, lower case; "addressed" when there is none."""
    if isinstance(reason, str):
        for token in reason.replace("_", " ").split():
            word = "".join(ch for ch in token if ch.isalpha())
            if word:
                return word.casefold()
    return "addressed"


@dataclass(frozen=True)
class RerankVerdict:
    """What the re-ranker said — or that it did not answer.

    `order_ids` are the ids still worth asking, best first; `drop_ids`
    maps each id to drop to its one-word reason. When `failed` names a
    failure (a timeout, an error, a runaway cap, a malformed reply) both
    are empty and the caller leaves the current order standing and audits
    (auto.rerank_failed). `outcome` is the model.call vocabulary — ok |
    timeout | cap | malformed | error; `run_ms` is the server's own total
    for the call when it reported one, and `tokens` its prompt and output
    counts — the shape slice 6's model.call audit extends to every call.
    Nothing here raises into a live session.
    """

    order_ids: tuple[str, ...] = ()
    drop_ids: Mapping[str, str] = field(default_factory=dict)
    failed: str | None = None
    elapsed_ms: int = 0
    outcome: str = "ok"
    run_ms: int | None = None
    tokens: Mapping[str, int | None] | None = None


def parse_rerank_reply(reply) -> tuple[tuple[str, ...], dict[str, str]]:
    """The reply's shape, checked: `order` a list of strings, `drop` a list
    of {id, reason} objects. Anything else raises ValueError (a malformed
    reply is a failed verdict). Ids are de-duplicated in first-seen order;
    whether an id is a real pending item is the queue's business."""
    if not isinstance(reply, dict):
        raise ValueError(f"reply is not an object: {type(reply).__name__}")
    order_raw, drop_raw = reply.get("order"), reply.get("drop")
    if not isinstance(order_raw, list) or not isinstance(drop_raw, list):
        raise ValueError("order and drop must both be lists")
    order: list[str] = []
    for item_id in order_raw:
        if not isinstance(item_id, str):
            raise ValueError(f"order holds a non-string id: {item_id!r}")
        if item_id.strip() and item_id.strip() not in order:
            order.append(item_id.strip())
    drops: dict[str, str] = {}
    for entry in drop_raw:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            raise ValueError(f"drop entry is not {{id, reason}}: {entry!r}")
        item_id = entry["id"].strip()
        if item_id and item_id not in drops:
            drops[item_id] = one_word(entry.get("reason"))
    return tuple(order), drops


class CDSEngine:
    """Stateless client: callers hold the assessment and pass it back in."""

    async def rerank(self, pending, excerpt: str) -> RerankVerdict:
        """The re-ranker (AGENDA_QUEUE_SPEC.md §3). NEVER RAISES.

        `pending` is the queue's pending items as (id, text) pairs, head
        first; `excerpt` the transcript since the last full pass landed,
        already bounded by rerank_excerpt. Bounded by AUTO_RERANK_TIMEOUT_S
        end to end (asyncio.wait_for and the HTTP timeout beneath it) with
        AUTO_RERANK_MAX_TOKENS as the output cap. A timeout, an error, a
        cap hit or a malformed reply comes back as a failed verdict; the
        caller leaves the order standing and audits auto.rerank_failed.
        """
        started = time.perf_counter()
        pairs = [(str(item_id), str(text)) for item_id, text in pending]
        try:
            reply, meta = await asyncio.wait_for(
                self._chat_raw(RERANK_PROMPT, rerank_message(pairs, excerpt), RERANK_SCHEMA,
                               timeout=AUTO_RERANK_TIMEOUT_S, num_predict=AUTO_RERANK_MAX_TOKENS,
                               call="rerank"),
                timeout=AUTO_RERANK_TIMEOUT_S)
        except asyncio.TimeoutError:
            elapsed = round(1000 * (time.perf_counter() - started))
            logger.warning("Re-ranker timed out after %d ms (AUTO_RERANK_TIMEOUT_S=%.1f); "
                           "the current order stands", elapsed, AUTO_RERANK_TIMEOUT_S)
            return RerankVerdict(failed="timeout", elapsed_ms=elapsed, outcome="timeout")
        except CDSRunaway as exc:
            return RerankVerdict(failed=f"CDSRunaway: {exc}", elapsed_ms=exc.elapsed_ms,
                                 outcome="cap", tokens={"prompt": None, "output": exc.tokens})
        except Exception as exc:  # noqa: BLE001 - fail-soft by contract
            elapsed = round(1000 * (time.perf_counter() - started))
            malformed = isinstance(exc, (json.JSONDecodeError, KeyError, TypeError, ValueError))
            logger.warning("Re-ranker failed (%s: %s); the current order stands",
                           type(exc).__name__, exc)
            return RerankVerdict(failed=f"{type(exc).__name__}: {exc}", elapsed_ms=elapsed,
                                 outcome="malformed" if malformed else "error")
        elapsed = round(1000 * (time.perf_counter() - started))
        try:
            order, drops = parse_rerank_reply(reply)
        except ValueError as exc:
            logger.info("Re-ranker reply malformed (%s); the current order stands", exc)
            return RerankVerdict(failed=f"malformed: {exc}", elapsed_ms=elapsed,
                                 outcome="malformed", run_ms=meta.get("run_ms"),
                                 tokens=meta.get("tokens"))
        return RerankVerdict(order, drops, elapsed_ms=elapsed, run_ms=meta.get("run_ms"),
                             tokens=meta.get("tokens"))

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
                           timeout=AUTO_TOPIC_TIMEOUT_S, num_predict=AUTO_TOPIC_MAX_TOKENS,
                           call="topic"),
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
        raw_lay = reply.get("lay") if isinstance(reply, dict) else None
        lay = clean_lay_wording(raw_lay)
        lay_failed = None if lay is not None else f"unusable: {raw_lay!r}"
        topic = clean_topic_phrase(raw)
        if topic is None:
            logger.info("Topic call returned an unusable phrase %r; asking verbatim", raw)
            return TopicVerdict(None, failed=f"unusable: {raw!r}", elapsed_ms=elapsed,
                                lay=lay, lay_failed=lay_failed)
        return TopicVerdict(topic, elapsed_ms=elapsed, lay=lay, lay_failed=lay_failed)

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
                           timeout=bound, num_predict=AUTO_OFFICER_MAX_TOKENS, call="officer"),
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
                    timeout: float = 180.0, num_predict: int | None = None,
                    call: str = "chat") -> dict:
        """One model call, parsed. `num_predict` caps the output (owner
        decision 2026-09-07, pilot 486 F3); a reply Ollama stopped for
        length (`done_reason: "length"`) is a CDSRunaway, never a parsed
        answer — truncated JSON would not parse anyway, and a cap hit is a
        fault to record, not a value to use."""
        reply, _meta = await self._chat_raw(system, user, schema, timeout=timeout,
                                            num_predict=num_predict, call=call)
        return reply

    async def _chat_raw(self, system: str, user: str, schema: dict, *,
                        timeout: float = 180.0, num_predict: int | None = None,
                        call: str = "chat") -> tuple[dict, dict]:
        """One model call: the parsed reply AND what the server said about
        the call — `tokens` {prompt, output} and `run_ms` (Ollama's own
        total_duration, when reported) — the numbers the model.call audit
        wants (AGENDA_QUEUE_SPEC.md §7a; the re-ranker first, every call
        in slice 6)."""
        started = time.perf_counter()
        options = {
            # Greedy + fixed seed: an alarm must not be a coin flip,
            # and evaluations must be reproducible.
            "temperature": float(os.getenv("CDS_TEMPERATURE", "0.0")),
            "seed": int(os.getenv("CDS_SEED", "42")),
            "num_ctx": CDS_NUM_CTX,
        }
        if num_predict is not None:
            options["num_predict"] = int(num_predict)
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
                    "options": options,
                },
            )
            response.raise_for_status()
        body = response.json()
        if num_predict is not None and body.get("done_reason") == "length":
            elapsed = round(1000 * (time.perf_counter() - started))
            tokens = body.get("eval_count")
            logger.warning("%s call hit its output cap (%s tokens, num_predict=%d) after %d ms",
                           call, tokens, num_predict, elapsed)
            raise CDSRunaway(call, reason="cap", tokens=tokens, elapsed_ms=elapsed,
                             cap=num_predict)
        total_ns = body.get("total_duration")
        meta = {"tokens": {"prompt": body.get("prompt_eval_count"), "output": body.get("eval_count")},
                "run_ms": (round(total_ns / 1_000_000) if isinstance(total_ns, (int, float))
                           else None)}
        return json.loads(body["message"]["content"]), meta

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

        runaway: CDSRunaway | None = None
        started = time.perf_counter()
        try:
            # Bounded end to end, like the officer: asyncio.wait_for around
            # the call and the same value as the HTTP timeout beneath it.
            assessment = await asyncio.wait_for(
                self._chat(
                    ASSESSMENT_PROMPT, f"{prev_text}\n\n{transcript_text}", ASSESSMENT_SCHEMA,
                    timeout=CDS_ASSESSMENT_TIMEOUT_S, num_predict=CDS_ASSESSMENT_MAX_TOKENS,
                    call="assessment"),
                timeout=CDS_ASSESSMENT_TIMEOUT_S)
        except CDSRunaway as exc:
            runaway = exc
        except (httpx.TimeoutException, asyncio.TimeoutError):
            elapsed = round(1000 * (time.perf_counter() - started))
            logger.warning("Assessment call timed out after %d ms (CDS_ASSESSMENT_TIMEOUT_S=%.0f)",
                           elapsed, CDS_ASSESSMENT_TIMEOUT_S)
            runaway = CDSRunaway("assessment", reason="timeout", tokens=None,
                                 elapsed_ms=elapsed, timeout_s=CDS_ASSESSMENT_TIMEOUT_S)
        # The urgency check runs on its own call whatever became of the
        # assessment: a runaway must never cost the doctor the alarm.
        urgency = await self._chat(URGENCY_PROMPT, transcript_text, URGENCY_SCHEMA,
                                   num_predict=CDS_URGENCY_MAX_TOKENS, call="urgency")
        if runaway is not None:
            arranged = urgency["already_done_or_arranged"] or bool(
                previous and previous.get("urgency_check", {}).get("already_done_or_arranged")
            )
            runaway.urgency = {
                "urgency_check": {
                    "time_critical_possible": urgency["time_critical_possible"],
                    "already_done_or_arranged": arranged,
                    "reason": urgency["reasoning"],
                },
                "urgent_actions": (urgency["urgent_actions"]
                                   if urgency["time_critical_possible"] and not arranged
                                   else []),
            }
            raise runaway

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
                AFFECT_PROMPT, affect_message(transcript), AFFECT_SCHEMA,
                num_predict=CDS_AFFECT_MAX_TOKENS, call="affect")
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
