"""Speech synthesis for Phase 7a tap-to-ask — the server's own voice.

Spec: `PHASE_7A_SPEC.md` Parts 2, 4 and 7. This module does synthesis and
reference resolution only; the speaking-window protocol and the transcript
exclusion it enforces live in `app/main.py` and `app/live.py`.

**The rule this module exists to enforce (hard rule 1, PHASE_7_SPEC.md):
the AI asks questions and acknowledges. It never advises, reassures,
interprets or hints at diagnosis to the patient.** The enforcement is
structural rather than a prompt or a filter: the client can only send a
*reference*, and the server resolves that reference against its own copy
of the CDS agenda or a fixed phrase table reviewed in advance. There is no
channel through which a client — buggy, compromised, or merely modified by
a well-meaning future contributor — can supply words. Nothing the system
says in 7a is authored at speak time.

That is why `resolve()` takes a ref and never a string, and why the
`speak` protocol message rejects a `text` field outright rather than
sanitising it. A rejected message is a bug report; a sanitised one is a
silent hole.

## Piper runs as a SUBPROCESS, at arm's length. Do not "simplify" this.

Owner's decision, 2026-07-25. There is no `import piper` anywhere in this
application and there must not be one. Synthesis goes through a
configurable command (`TTS_COMMAND`) run as a separate process, which
writes a WAV and exits. Two reasons, both of which survive whoever reads
this next:

1. **Licence.** `piper-tts` is **GPL-3.0-or-later** and links espeak-ng.
   Invoking a separate program at arm's length is a different
   relationship from linking it into our own process, and this project is
   intended for external collaboration. See `NOTICE`.
2. **The lockfile.** Adding it to `pyproject.toml` would re-resolve the
   app's dependency graph. On this machine, resolution churn corrupted the
   venv's CUDA wheels once already (HANDOVER, Troubleshooting). Piper
   lives in its own environment — `uv tool install piper-tts` — and the
   app's `uv.lock` never learns it exists.

**CPU only, structurally.** `app/finalize.py`'s VRAM sequencing assumes
sole ownership of the 24 GB card: MedGemma at ~17 GB plus WhisperX and
pyannote at 6–8 GB leaves no room for a guest. Piper's `--cuda` flag is
opt-in and `TTS_COMMAND` does not pass it — but the stronger guarantee is
that the onnxruntime installed in the tool environment is a CPU-only
build with no CUDA execution provider available at all, so the flag could
not work even if someone added it. Verified 2026-07-25.

A missing command or model degrades to `SpeechUnavailable`; a non-zero
exit or a timeout raises `SpeechFailed`, which is audited and surfaces to
the client as a visible error state. Neither ever degrades to silence:
a dead speaker must look like a fault, not like a system that chose not
to speak.
"""

from __future__ import annotations

import hashlib
import io
import logging
import math
import os
import secrets
import shlex
import shutil
import subprocess
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from app import auto_mode

load_dotenv()

logger = logging.getLogger(__name__)

# --- configuration (PHASE_7A_SPEC.md Part 7) -------------------------------

TTS_ENABLED = os.getenv("TTS_ENABLED", "true").lower() != "false"
TTS_VOICE = os.getenv("TTS_VOICE", "en_GB-alba-medium")
TTS_MODEL_PATH = os.getenv("TTS_MODEL_PATH", "")
# The command adapter. `{model}` and `{output}` are substituted; the text
# to speak goes on stdin, never on the command line — argv is world-readable
# in /proc and a consultation's questions are clinical content.
TTS_COMMAND = os.getenv("TTS_COMMAND", "piper --model {model} --output-file {output}")
TTS_TIMEOUT_S = float(os.getenv("TTS_TIMEOUT_S", "30"))
SPEECH_MAX_UTTERANCE_S = float(os.getenv("SPEECH_MAX_UTTERANCE_S", "20"))
SPEECH_EXCLUSION_TAIL_MS = int(os.getenv("SPEECH_EXCLUSION_TAIL_MS", "200"))
SPEECH_CACHE_DIR = Path(os.getenv("SPEECH_CACHE_DIR", "data/speech_cache"))

# --- barge-in (Phase 7a session 3; PHASE_7A_SPEC.md build item 5, Part 9 D5)
#
# SHIPS FALSE. Hard mute is this design with the detector off (spec §1.2),
# and the flag flips only when scripts/calibrate_barge_in.py shows BOTH
# sides of the D5 target met in the real room — false stops ≤ 1% of
# utterances AND ≥ 90% of true interruptions caught within 300 ms.
# Flipping it is the OWNER'S act, not a code change.
#
# This is a COMFORT parameter, not a safety parameter (D5): exclusion is
# structural, so no threshold here can corrupt a transcript. A false stop
# costs a re-tap; a miss behaves exactly like hard mute.
BARGE_IN_ENABLED = os.getenv("BARGE_IN_ENABLED", "false").lower() == "true"
BARGE_IN_MIN_MS = int(os.getenv("BARGE_IN_MIN_MS", "150"))
# Mic energy must exceed the PREDICTED residual echo — the measured
# loopback level scaled by the playback envelope — by this factor before
# it counts as an interruption. An uncalibrated first guess, stated as
# such like the sound-check ratios below; the calibration script reports
# what the recorded measurements actually support.
BARGE_IN_MARGIN = float(os.getenv("BARGE_IN_MARGIN", "2.0"))
# Absolute floor: below this, mic energy is never an interruption however
# quiet our playback is at that moment. The default is an UNCALIBRATED
# GUESS placed between this project's own measurements (HANDOVER,
# consultation 445): ordinary room noise read 0.008–0.011 RMS and real
# speech 0.056–0.153, so 0.02 sits above the former with headroom under
# the latter. Env-tunable so the owner sets it from his room.
_BARGE_IN_FLOOR_RAW = os.getenv("BARGE_IN_RMS_THRESHOLD", "").strip()
BARGE_IN_RMS_THRESHOLD = float(_BARGE_IN_FLOOR_RAW) if _BARGE_IN_FLOOR_RAW else 0.02

# --- the auto-mode floor comes from the room (owner decision 2026-09-09) ----
#
# Pilot 488, finding G2: one absolute floor — BARGE_IN_RMS_THRESHOLD, 0.02
# — served both the politeness abort and the client's quiet reporter, and a
# cafe sits above it (the sound check's quiet-room peak 0.0085, speech mean
# 0.0216; the enable's disclosure aborted at 0.0314; 94 s of GOLDEN in
# which quiet never reached 3 s). Now each auto session's floor is derived
# from the room: the doctor's newest sound check's noise_floor_rms (the
# quiet room's peak over 400 ms) times AUTO_FLOOR_MARGIN, clamped to
# [AUTO_FLOOR_MIN, AUTO_FLOOR_MAX]. The quiet flat (0.0031) yields exactly
# AUTO_FLOOR_MIN, so today's behaviour there is unchanged; the cafe
# (0.0085) yields 0.0255; a very loud room clamps at the max; no sound
# check falls back to AUTO_FLOOR_MIN and says so. All three are
# UNCALIBRATED GUESSES — the next runs' auto.enabled and
# speech.politeness_abort rows carry the floor chosen and inform them.
AUTO_FLOOR_MARGIN = float(os.getenv("AUTO_FLOOR_MARGIN", "3.0"))
AUTO_FLOOR_MIN = float(os.getenv("AUTO_FLOOR_MIN", "0.02"))
AUTO_FLOOR_MAX = float(os.getenv("AUTO_FLOOR_MAX", "0.08"))

# --- lay wording through the topic call (owner decision 2026-09-09) --------
#
# The D1 extension: the topic call returns, beside the topic, a plain-English
# wording of the SAME agenda question, and Alba speaks that instead of the
# clinical original ("Do you have any risk factors for heart disease? (e.g.,
# smoking, diabetes, hypertension...)" — 486's lesson). The wording is
# model text spoken to a patient, so it is admitted only through a
# code-enforced guard: it must share its subject with the original under
# the shared normaliser — token-set similarity at or above this — or the
# original is spoken verbatim and auto.lay_rejected is audited with both
# texts and the score. An UNCALIBRATED GUESS; the next runs' rows (the
# spoken wording beside the original on every auto.queue_consumed) inform
# it.
AUTO_LAY_MIN_SIMILARITY = float(os.getenv("AUTO_LAY_MIN_SIMILARITY", "0.3"))


def lay_accepted(lay: str, original: str, threshold: float | None = None) -> tuple[bool, float]:
    """The subject guard for a lay wording (owner decision 2026-09-09): the
    token-set similarity of the lay wording to the original question under
    the shared normaliser (app/auto_mode.py, action_similarity — the same
    tokens the queue's identity and the cone use), and whether it reaches
    AUTO_LAY_MIN_SIMILARITY. Pure."""
    t = AUTO_LAY_MIN_SIMILARITY if threshold is None else float(threshold)
    score = auto_mode.action_similarity(str(lay), str(original))
    return score >= t, score


def auto_floor(noise_floor_rms: float | None, *, margin: float | None = None,
               floor_min: float | None = None, floor_max: float | None = None) -> dict:
    """The per-session floor for the politeness abort and the quiet
    reporter (owner decision 2026-09-09, pilot 488 G2). Pure.

    Returns the floor and how it was arrived at: `source` is
    "sound_check" when a measured noise floor was used, "no_sound_check"
    when there was none (the floor is then AUTO_FLOOR_MIN); `clamped` is
    None, "min" or "max"; `noise_floor_rms` and `margin` travel for the
    record. Rounded to 5 places, the client's own precision for RMS.
    """
    m = AUTO_FLOOR_MARGIN if margin is None else float(margin)
    lo = AUTO_FLOOR_MIN if floor_min is None else float(floor_min)
    hi = AUTO_FLOOR_MAX if floor_max is None else float(floor_max)
    if noise_floor_rms is None:
        return {"floor": round(lo, 5), "noise_floor_rms": None, "margin": m,
                "min": lo, "max": hi, "source": "no_sound_check", "clamped": None}
    raw = float(noise_floor_rms) * m
    clamped = None
    if raw < lo:
        raw, clamped = lo, "min"
    elif raw > hi:
        raw, clamped = hi, "max"
    return {"floor": round(raw, 5), "noise_floor_rms": round(float(noise_floor_rms), 8),
            "margin": m, "min": lo, "max": hi, "source": "sound_check", "clamped": clamped}

# Pre-synthesis guard on the hard cap. Fast speech tops out around 25
# characters per second, so this refuses a pathological string before
# spending CPU on it. The real bound is the post-synthesis duration check
# below — this one only stops absurd input cheaply.
_MAX_CHARS_PER_SECOND = 25.0

# How many CDS agenda versions the server keeps resolvable. A reference to
# a question since revised off the agenda is allowed (the panel can lag by
# a turn), so old versions must stay resolvable for a while — but not
# forever, or a long consultation accumulates unbounded state.
AGENDA_HISTORY = 20


class SpeechUnavailable(RuntimeError):
    """The synthesis command or its voice model is not on this machine.

    A configuration state, not a fault: the app runs fine without speech.
    """


class SpeechFailed(RuntimeError):
    """The synthesis command ran and did not produce usable audio.

    A fault, and it must reach the doctor as one. Silence that looks like
    a choice is the failure mode being avoided here.
    """


class SpeechRefused(ValueError):
    """The request cannot be honoured: unknown reference, or over the cap.

    Distinct from SpeechUnavailable on purpose — this one is the client's
    fault and is audited as `speech.failed`.
    """


# --- the fixed phrase table ------------------------------------------------
#
# Reviewed in advance. This is half of the answer to "what can the system
# say?" — the other half is the CDS agenda, which the CDS engine already
# constrains to questions.
#
# `{doctor}` is interpolated SERVER-SIDE from the session's doctor
# account, in code and never by a model — the same convention as
# `app/letters.py`, where the salutation, the Re: line and the sign-off
# are code precisely because they are the parts that must not be invented.

PHRASES: dict[str, str] = {
    # Hard rule 4 — disclosure. Wording APPROVED BY THE OWNER 2026-07-25,
    # amended by them 2026-07-28 ("him" → "them"), verbatim; do not edit
    # without them.
    #
    # The amendment removes an assumption the original carried: the doctor
    # is not necessarily male, and the sentence is spoken to a patient about
    # a named real person. It was flagged in the first session rather than
    # changed, because the words a patient hears are the owner's to set.
    #
    # It deliberately says NOTHING about interrupting the system, so that
    # it stays true whether or not barge-in is enabled and stays constant
    # across the face study's arms. Do not add an interruption line when
    # the detector lands.
    "disclosure": (
        "Hello. I'm a computer, not a person. I'll ask you some questions "
        "about what's brought you in. Dr {doctor} is here with you and you "
        "can speak to them at any time."
    ),
    # Golden minutes: the single opening invitation (spec Part 5, and the
    # behaviour policy in PHASE_7_SPEC.md).
    "invitation": "Please, tell me what's brought you in.",
    # Minimal encouragers — the only thing the system may say during the
    # golden minutes. Ids are spelled as the build brief spells them.
    "mm-hm": "Mm-hm.",
    "i_see": "I see.",
    "go_on": "Go on.",
    # Owner decision 2026-09-09 (golden window encouragers, after
    # consultations 487–490): the second golden encourager, alternated
    # with "go_on". Owner wording, verbatim.
    "tell_me_more_short": "Please, tell me more.",
    # Owner decision 2026-09-09 ("Let me think" and the empty-queue rule):
    # spoken at most once per wait in the question phases when the
    # patient's turn has ended and no question is ready — the machine
    # covering its own thinking, not a prompt to the patient. Replaces the
    # bridge "go on" there entirely. Owner wording, verbatim.
    "let_me_think": "Let me think for a moment.",
    # Examination handover: the system never pretends to examine.
    "examination_handover": "Thank you — Dr {doctor} will examine you now.",
    # Sound check (spec Part 10 / D6). Deliberately not clinical and not
    # addressed to the patient — it is a check spoken in the room, and it
    # should sound like one.
    "sound_check": "Sound check. If you can hear this clearly, press yes.",
    # Silence nudge (Phase 7b session 3, owner's wording verbatim). THE
    # ONLY AUTONOMOUS UTTERANCE IN 7a/7b — the caging lives in main.py's
    # speak handler (one-shot per consultation, only after the invitation
    # has played through, any activity cancels it client-side). Its guard
    # against generalisation was retired in Phase 7c slice 3, when the
    # behaviour-policy machinery arrived behind AUTO_MODE_ENABLED; with
    # auto mode off, the cage holds exactly as before.
    "silence_nudge": "When you're ready, tell me what's brought you in today.",
    # Phase 7c (PHASE_7C_SPEC.md §4 item 4, owner-approved wording): the
    # invitation-class follow-up auto mode speaks once before the
    # examination handover. A fixed phrase like the others — no slot, no
    # model — and disclosure-gated because it is a question to the patient.
    "anything_else": "Is there anything else you wanted to talk about today?",
}

ENCOURAGER_IDS = ("mm-hm", "i_see", "go_on", "tell_me_more_short")
# The one the automatic flow speaks (owner decision 2026-09-01, after the
# solo pilot: "we need to get rid of the mm-hm"): "go on" only. "mm-hm" and
# "i_see" stay registered, tappable and pre-synthesised — unused, not
# deleted, like the affecting_you template.
ENCOURAGER_ID = "go_on"
# The golden window's two phrasings, alternated (owner decision 2026-09-09,
# reversing the 1 Sept one-per-window rule): an encourager may be spoken
# every time the patient has been quiet for AUTO_ENCOURAGER_MIN_QUIET_S,
# go_on then tell_me_more_short then go_on…
GOLDEN_ENCOURAGER_IDS = ("go_on", "tell_me_more_short")
# The thinking phrase (owner decision 2026-09-09): not an encourager, not a
# question — it does not count as asked, does not touch the queue, and the
# client does not restart its quiet span at its end.
THINKING_ID = "let_me_think"

# Phrases the patient must have heard the disclosure before (hard rule 4).
# The encouragers are exempt: "mm-hm" is not a clinical interaction, and
# gating them would make the lock feel like a nuisance rather than a rule.
DISCLOSURE_GATED_PHRASES = ("invitation", "examination_handover", "silence_nudge",
                            "anything_else")


# --- the open-question templates (Phase 7c, PHASE_7C_SPEC.md §4 item 3) ----
#
# Owner-approved wording, instantiated SERVER-SIDE ONLY with a short topic
# noun phrase ("the chest pain") — the {doctor} precedent above, applied to
# a second slot. There is no client reference kind for these: `resolve()`
# below does not know them, so a tap cannot reach them, and the auto path
# reaches them only through `TemplateUtterance` (app/auto_mode.py), which
# names the template by id and carries the topic string and nothing else.
# The words around the slot are never authored at speak time.

TEMPLATES: dict[str, str] = {
    "tell_me_more": "Can you tell me more about {topic}?",
    "affecting_you": "How has {topic} been affecting you?",
}


def render_template(template_id: str, topic: str) -> str:
    """An owner-approved template with its topic slot filled, server-side.

    The topic is the ONLY variable part and it is a noun phrase, not a
    sentence: it must be non-empty and a single line. Anything longer than
    the utterance cap is refused downstream by `synthesise()`.
    """
    if template_id not in TEMPLATES:
        raise SpeechRefused(f"unknown template id: {template_id!r}")
    return TEMPLATES[template_id].format(topic=clean_topic(topic))


def clean_topic(topic: str) -> str:
    """The topic slot, whitespace-collapsed to one line; empty is refused."""
    if not isinstance(topic, str):
        raise SpeechRefused("template topic must be a string")
    cleaned = " ".join(topic.split())
    if not cleaned:
        raise SpeechRefused("template topic is empty")
    return cleaned


# --- sound check (spec Part 10) --------------------------------------------
#
# WHY THIS EXISTS, and it is not a convenience: a dead speaker fails
# SILENTLY. Playback succeeds, nothing errors, and the patient simply
# hears nothing — the doctor reads the silence as a patient who is not
# answering. Worse, the exclusion window opens anyway, so for the length
# of that inaudible utterance the microphone feeds nothing to the
# transcript and whatever the patient says is dropped BY CONSTRUCTION.
#
# A dead speaker therefore converts quietly into missing transcript, with
# nothing on screen to say so. That is the same shape as every other
# failure this project has had to design against: not visibly broken,
# just wrong. The mic cluster answers "is the room being heard"; this
# answers the other half — "is the room hearing us".

RESULT_HEARD_GOOD = "heard_good"
RESULT_HEARD_FAINT = "heard_faint"
RESULT_NOT_HEARD = "not_heard"
RESULT_UNVERIFIED = "unverified"

# Absolute silence floor. NOT a new number: this is the same RMS the live
# page's mic cluster already treats as "no signal" for its dead-mic pill
# (`app/static/live.html`). Reusing it means the two surfaces cannot
# disagree about what silence is.
SOUND_CHECK_SILENT_RMS = float(os.getenv("SOUND_CHECK_SILENT_RMS", "1e-4"))

# ---------------------------------------------------------------------------
# THESE TWO ARE UNCALIBRATED GUESSES. They are stated as such rather than
# dressed up: nobody has measured this room, this speaker or this
# microphone. 4.0x is roughly +12 dB over the noise floor and 1.8x roughly
# +5 dB, chosen so that "faint" covers the band where a patient would
# strain and the barge-in detector would be unreliable. Every measurement
# is stored raw in the `speech.sound_check` audit row precisely so these
# can be set from real data later — `scripts/calibrate_barge_in.py`
# (built, 7a session 3) reads those rows and RECOMMENDS values when the
# data supports them; setting them stays the owner's.
# ---------------------------------------------------------------------------
SOUND_CHECK_GOOD_RATIO = float(os.getenv("SOUND_CHECK_GOOD_RATIO", "4.0"))
SOUND_CHECK_FAINT_RATIO = float(os.getenv("SOUND_CHECK_FAINT_RATIO", "1.8"))


def classify_sound_check(*, noise_floor_rms: float, peak_rms: float,
                         mean_rms: float | None = None,
                         answer: str | None) -> dict:
    """Turn a loopback measurement plus the doctor's answer into a result.

    **The human answer is authoritative.** The only true test of whether
    the room heard it is a person in the room saying so; the acoustic
    measurement corroborates that and is the part that produces a number.

    Headphones are a known confound: they defeat the acoustic path
    entirely, so energy reads as absent while the doctor says yes. That is
    NOT a warning — the answer is accepted, the discrepancy is recorded,
    and nothing is flagged. The same courtesy runs the other way: energy
    present but the doctor says no is still `not_heard`.

    Pure and side-effect free, so the four classes are testable without a
    browser, a speaker or a room.
    """
    floor = max(float(noise_floor_rms or 0.0), SOUND_CHECK_SILENT_RMS)
    peak = max(float(peak_rms or 0.0), 0.0)
    ratio = peak / floor if floor > 0 else 0.0
    audible = peak >= SOUND_CHECK_SILENT_RMS and ratio >= SOUND_CHECK_FAINT_RATIO

    level = {
        "noise_floor_rms": round(float(noise_floor_rms or 0.0), 8),
        "peak_rms": round(peak, 8),
        "mean_rms": round(float(mean_rms), 8) if mean_rms is not None else None,
        "ratio": round(ratio, 3),
        "ratio_db": round(20 * math.log10(ratio), 1) if ratio > 0 else None,
        "good_ratio": SOUND_CHECK_GOOD_RATIO,
        "faint_ratio": SOUND_CHECK_FAINT_RATIO,
        "silent_rms": SOUND_CHECK_SILENT_RMS,
    }

    if answer not in ("yes", "no"):
        # Declined to answer. Recorded as unverified rather than as a pass —
        # the doctor may have good reason to skip and the system does not
        # get to overrule that, but it also does not get to call it a pass.
        return {"result": RESULT_UNVERIFIED, "level": level, "discrepancy": None,
                "answer": answer or "skip"}

    if answer == "no":
        return {"result": RESULT_NOT_HEARD, "level": level,
                "discrepancy": "energy_present_but_doctor_says_no" if audible else None,
                "answer": answer}

    if not audible:
        # Doctor heard it, the microphone did not. Almost always headphones.
        return {"result": RESULT_HEARD_GOOD, "level": level,
                "discrepancy": "no_acoustic_path_headphones_likely",
                "answer": answer}

    return {"result": RESULT_HEARD_GOOD if ratio >= SOUND_CHECK_GOOD_RATIO
                      else RESULT_HEARD_FAINT,
            "level": level, "discrepancy": None, "answer": answer}


def doctor_name_for(user: dict | None) -> str:
    """The name to speak, from the session's doctor account.

    Fallback order is display name, then username. **No title is ever
    invented**: every phrase that needs one carries "Dr " in its own
    template, so this returns the name exactly as the account records it.
    If an account's display name already began "Dr", the spoken line would
    read "Dr Dr ..." — no active account does today, and correcting that
    is a data decision for the owner rather than a transform to apply
    silently here.
    """
    if not user:
        return "the doctor"
    return (user.get("display_name") or "").strip() or user.get("username", "the doctor")


def render_phrase(phrase_id: str, doctor: str | None = None) -> str:
    """A phrase with its server-side fields filled in."""
    if phrase_id not in PHRASES:
        raise SpeechRefused(f"unknown phrase id: {phrase_id!r}")
    return PHRASES[phrase_id].format(doctor=doctor or "the doctor")


# --- the server's own copy of the CDS agenda -------------------------------

@dataclass(frozen=True)
class AgendaVersion:
    """One snapshot of the question agenda, as the CDS engine left it.

    `reasoning` is the assessment's own reasoning field. It stands in for
    the per-question rationale that spec §3.1 asks to record: the CDS
    schema gives questions as bare strings with no rationale of their own
    (`app/cds.py`, ASSESSMENT_SCHEMA), so the assessment's reasoning at
    that version is the honest answer to "why was this question on the
    agenda". Recorded as-is rather than invented per question.
    """

    version: int
    questions: tuple[str, ...]
    reasoning: str


class AgendaLog:
    """Versioned history of the question agenda for one live session.

    Exists so a `cds_question` reference resolves to the text the doctor
    actually tapped, not to whatever the agenda says by the time the
    message arrives. The CDS panel can lag a revision behind, and re-asking
    an answered question is redundant rather than unsafe.
    """

    def __init__(self, history: int = AGENDA_HISTORY) -> None:
        self._versions: dict[int, AgendaVersion] = {}
        self._history = history
        self.current_version = 0

    def record(self, assessment: dict | None) -> int:
        """Snapshot a new assessment; returns its version number."""
        questions = tuple(str(q) for q in (assessment or {}).get("questions_to_ask", []))
        reasoning = str((assessment or {}).get("reasoning", ""))
        self.current_version += 1
        self._versions[self.current_version] = AgendaVersion(
            version=self.current_version, questions=questions, reasoning=reasoning)
        for old in sorted(self._versions)[:-self._history]:
            del self._versions[old]
        return self.current_version

    def get(self, version: int) -> AgendaVersion | None:
        return self._versions.get(version)

    @property
    def current(self) -> AgendaVersion | None:
        return self._versions.get(self.current_version)


# --- reference resolution --------------------------------------------------

@dataclass(frozen=True)
class Resolution:
    """What the server decided it will say, and why. Never client-supplied."""

    text: str
    ref_kind: str
    ref_detail: dict
    cds_rationale: str = ""
    stale: bool = False   # the question has since left the agenda


def resolve(ref: dict, agenda: AgendaLog | None = None,
            doctor: str | None = None) -> Resolution:
    """Turn a client reference into server-authored text.

    Raises SpeechRefused for anything unrecognised. It never falls back to
    a client-supplied string, because there is no client-supplied string:
    that is the whole design. `doctor` is likewise server-side — the
    client cannot choose whose name the machine says.
    """
    if not isinstance(ref, dict):
        raise SpeechRefused("speak.ref must be an object")

    kind = ref.get("kind")

    if kind == "phrase":
        phrase_id = ref.get("id")
        if phrase_id not in PHRASES:
            raise SpeechRefused(f"unknown phrase id: {phrase_id!r}")
        return Resolution(text=render_phrase(phrase_id, doctor), ref_kind="phrase",
                          ref_detail={"id": phrase_id})

    if kind == "cds_question":
        if agenda is None:
            raise SpeechRefused("no CDS agenda in this session")
        try:
            version = int(ref["assessment_version"])
            index = int(ref["index"])
        except (KeyError, TypeError, ValueError):
            raise SpeechRefused(
                "cds_question needs integer assessment_version and index") from None
        snapshot = agenda.get(version)
        if snapshot is None:
            # Never guess at another version's wording — that would be the
            # server authoring a question the doctor did not tap.
            raise SpeechRefused(f"assessment version {version} is not resolvable")
        if not 0 <= index < len(snapshot.questions):
            raise SpeechRefused(
                f"question index {index} out of range for version {version}")
        text = snapshot.questions[index]
        current = agenda.current
        stale = current is not None and text not in current.questions
        if stale:
            # Allowed and logged (spec §2.1): the panel lags by a turn, and
            # re-asking an answered question is redundant, not unsafe.
            logger.info(
                "Speaking a CDS question revised off the agenda "
                "(version %d index %d, current version %d)",
                version, index, agenda.current_version)
        return Resolution(text=text, ref_kind="cds_question",
                          ref_detail={"assessment_version": version, "index": index},
                          cds_rationale=snapshot.reasoning, stale=stale)

    raise SpeechRefused(f"unknown speak.ref kind: {kind!r}")


# --- the auto path's resolution (Phase 7c, PHASE_7C_SPEC.md §4) -----------
#
# The server-initiated path never sees a client message at all: it is
# handed one of the three whitelist TYPES from app/auto_mode.py and nothing
# else. There is no free-text type to hand it, so hard rule 1 holds by
# construction one layer up; this function then refuses anything that is
# not one of the three (a bare string, a dict, a client-style ref), so a
# caller cannot smuggle words past the type either.

def resolve_utterance(utterance: auto_mode.Utterance,
                      agenda: AgendaLog | None = None,
                      doctor: str | None = None) -> Resolution:
    """Turn a whitelist utterance into server-authored text.

    - `PhraseUtterance` → the fixed phrase table, `{doctor}` filled from the
      session's own doctor account exactly as a tapped phrase is.
    - `TemplateUtterance` → an owner-approved template with its topic slot
      filled server-side; recorded as ref_kind "template" with the id and
      the topic, so the review page can show what was said and why.
    - `AgendaUtterance` → the versioned AgendaLog, by assessment version and
      index, exactly as a doctor's tap resolves — same stale rule, same
      rationale, same refusal to guess at another version's wording.
    - `LayUtterance` (owner decision 2026-09-09) → the same agenda
      resolution for the question's identity, rationale and stale rule;
      the spoken text is the lay wording, admitted only through the
      subject guard (lay_accepted) — a wording that drifts from the
      original's subject is REFUSED here, whatever the caller checked —
      and recorded as ref_kind "cds_question" with `lay: true` and the
      original `question` beside the reference.

    Anything else raises SpeechRefused. Not TypeError: a wrong type here is
    the same class of event as a `speak` carrying text, and it is audited
    the same way by the caller.
    """
    if isinstance(utterance, auto_mode.PhraseUtterance):
        return resolve({"kind": "phrase", "id": utterance.phrase_id}, agenda, doctor)
    if isinstance(utterance, auto_mode.AgendaUtterance):
        return resolve({"kind": "cds_question",
                        "assessment_version": utterance.assessment_version,
                        "index": utterance.index}, agenda, doctor)
    if isinstance(utterance, auto_mode.TemplateUtterance):
        text = render_template(utterance.template_id, utterance.topic)
        return Resolution(text=text, ref_kind="template",
                          ref_detail={"template_id": utterance.template_id,
                                      "topic": clean_topic(utterance.topic)})
    if isinstance(utterance, auto_mode.LayUtterance):
        base = resolve({"kind": "cds_question",
                        "assessment_version": utterance.assessment_version,
                        "index": utterance.index}, agenda, doctor)
        lay = " ".join(str(utterance.lay).split()).strip()
        if not lay:
            raise SpeechRefused("a lay wording must not be empty")
        ok, score = lay_accepted(lay, base.text)
        if not ok:
            raise SpeechRefused(
                f"the lay wording does not share its subject with the question "
                f"(similarity {score} < {AUTO_LAY_MIN_SIMILARITY}): {lay!r} for {base.text!r}")
        return Resolution(text=lay, ref_kind="cds_question",
                          ref_detail={**base.ref_detail, "lay": True, "question": base.text,
                                      "lay_similarity": score},
                          cds_rationale=base.cds_rationale, stale=base.stale)
    raise SpeechRefused(
        "the auto path speaks only a PhraseUtterance, TemplateUtterance, "
        f"AgendaUtterance or LayUtterance, not {type(utterance).__name__}")


# --- synthesis -------------------------------------------------------------

@dataclass
class Utterance:
    """One thing the system has been asked to say.

    `user_id` is the doctor who requested it; the audio route checks it, so
    an utterance is not fetchable by anyone who happens to guess an id.
    """

    utterance_id: str
    text: str
    voice: str
    wav: bytes = field(repr=False)
    duration_ms: int
    synth_ms: int
    ref_kind: str
    ref_detail: dict
    cds_rationale: str = ""
    stale: bool = False
    user_id: int | None = None
    consultation_id: int | None = None


def cache_key(text: str, voice: str) -> str:
    """hash(text) + voice, per spec Part 4. The voice is part of the key
    because the same words in a different voice are different audio."""
    digest = hashlib.sha256(f"{voice}\x00{text}".encode()).hexdigest()
    return f"{voice}-{digest[:32]}"


def wav_duration_ms(wav_bytes: bytes) -> int:
    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        return round(1000 * w.getnframes() / w.getframerate())


# --- barge-in threshold scale (Part 10 amendment, 2026-07-30) ---------------

# How far the detector-stream residual PEAK may exceed the main-stream raw
# PEAK before that is treated as an anomaly rather than the expected
# window-length effect: the main analyser's fftSize 2048 (~43 ms) against
# the residual analyser's 512 (~11 ms) bounds the ratio of same-signal
# peaks at sqrt(4) = 2 (see barge_in_scale). Observed 2026-08-18: x1.3–1.9.
RESIDUAL_EXCESS_MAX = 2.0


def barge_in_scale(detail: dict | None) -> dict:
    """The threshold scale for the client, from the newest sound-check row.

    The threshold is envelope-proportional to the DETECTOR-STREAM RESIDUAL
    when the row carries one (spec Part 10 amendment): the detector
    listens through its echo canceller, so the echo it must ignore is the
    residual, not the raw loopback — measured on this room, raw loopback
    (0.30–0.58 RMS) towers over quiet speech (0.056), a gap no raw-derived
    threshold can bridge. The raw loopback is retained as a SANITY UPPER
    BOUND and the value is always clamped to it. Rows without a residual
    fall back to the raw figure — conservative, since its failure
    direction is a miss, which is hard mute.

    A residual peak ABOVE the raw peak is NOT, by itself, physically
    wrong (revised 2026-08-18 after the read-only analysis of that day's
    batches). The two peaks are not on one scale: the main stream's
    analyser reads ~43 ms RMS windows (fftSize 2048) with AGC on, the
    detector stream's ~11 ms windows (fftSize 512) with AGC off, so for
    the same signal the shorter window's peak can exceed the longer's by
    up to sqrt(2048/512) = x2, and the un-AGC'd stream keeps a loud
    onset the main stream compressed — the observed case on most MacBook
    Air readings (0.24 vs 0.14). Within that bound the excess is the
    EXPECTED consequence of the measurement, clamped and logged, not
    audited. Beyond it (RESIDUAL_EXCESS_MAX) it may still be an anomaly —
    a gain difference or a stream mix-up — and keeps the anomaly audit.

    Returns raw_peak_rms, residual_peak_rms (clamped), `clamped` (the
    expected excess, or None) and `anomaly` (the unexplained excess, or
    None); the two are exclusive.
    """
    detail = detail or {}
    raw = detail.get("peak_rms")
    residual = (detail.get("residual") or {}).get("peak_rms")
    anomaly = None
    clamped = None
    if residual is not None and raw is not None and residual > raw:
        excess = {"residual_peak_rms": residual, "raw_peak_rms": raw,
                  "ratio": round(residual / raw, 3) if raw > 0 else None}
        if raw > 0 and residual <= raw * RESIDUAL_EXCESS_MAX:
            clamped = excess
        else:
            anomaly = excess
        residual = raw
    return {"raw_peak_rms": raw, "residual_peak_rms": residual,
            "clamped": clamped, "anomaly": anomaly}


# --- playback envelope (Phase 7a session 3, barge-in) -----------------------

ENVELOPE_WINDOW_MS = 100


def playback_envelope(wav_bytes: bytes,
                      window_ms: int = ENVELOPE_WINDOW_MS) -> list[float]:
    """Normalised RMS envelope of a synthesised utterance: one value per
    window, 0..1 against the utterance's own loudest window.

    The barge-in threshold is ENVELOPE-PROPORTIONAL (spec Part 9, D5): the
    client knows exactly what waveform it is rendering, so the residual
    echo it should expect at any moment is proportional to how loud the
    playback is at that moment. The client scales the measured loopback
    level — read from the `speech.sound_check` audit rows, never
    re-measured — by this envelope and requires mic energy to exceed that
    prediction by a margin, which attacks the dominant false-trigger cause
    (our own voice) directly.

    Computed server-side from the same bytes the client will play, so
    there is no second envelope implementation in JavaScript to drift.
    Pure; raises `wave.Error`/`ValueError` on malformed audio — the caller
    degrades to no envelope (absolute-floor detection), never to silence.
    """
    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        if w.getsampwidth() != 2:
            raise ValueError(f"expected 16-bit PCM, got {w.getsampwidth() * 8}-bit")
        channels = w.getnchannels()
        rate = w.getframerate()
        frames = w.readframes(w.getnframes())
    samples = memoryview(frames).cast("h")
    if channels > 1:                     # Piper is mono; be safe anyway
        samples = samples[::channels]
    per_window = max(1, int(rate * window_ms / 1000))
    windows: list[float] = []
    for start in range(0, len(samples), per_window):
        chunk = samples[start:start + per_window]
        acc = 0
        for value in chunk:
            acc += value * value
        windows.append(math.sqrt(acc / len(chunk)) / 32768.0)
    peak = max(windows, default=0.0)
    if peak <= 0:
        return [0.0] * len(windows)
    return [round(v / peak, 4) for v in windows]


class SpeechService:
    """Piper wrapper with an on-disk synthesis cache.

    The voice model is loaded lazily on the first synthesis, not at
    construction, so importing the app on a machine without Piper is fine.
    """

    def __init__(self, voice: str | None = None, model_path: str | None = None,
                 cache_dir: Path | None = None, command: str | None = None) -> None:
        self.voice = voice or TTS_VOICE
        self.model_path = model_path if model_path is not None else TTS_MODEL_PATH
        self.cache_dir = Path(cache_dir) if cache_dir else SPEECH_CACHE_DIR
        self.command = command if command is not None else TTS_COMMAND
        self._utterances: dict[str, Utterance] = {}

    # -- availability --------------------------------------------------

    def unavailable_reason(self) -> str | None:
        """Why synthesis cannot happen, or None if it can. One place, so
        the reason the doctor sees is the reason the code acted on."""
        if not TTS_ENABLED:
            return "TTS_ENABLED=false"
        if not self.command.strip():
            return "TTS_COMMAND is not set"
        if not self.model_path:
            return "TTS_MODEL_PATH is not set"
        if not Path(self.model_path).exists():
            return f"voice model not found: {self.model_path}"
        executable = shlex.split(self.command)[0]
        if shutil.which(executable) is None and not Path(executable).exists():
            return (f"synthesis command not found: {executable} "
                    f"(install it outside the app environment, e.g. "
                    f"`uv tool install piper-tts`)")
        return None

    @property
    def available(self) -> bool:
        """True when synthesis could actually happen right now."""
        return self.unavailable_reason() is None

    def _run_command(self, text: str, output: Path) -> None:
        """Run the synthesis command as a separate process.

        The text goes on **stdin**, deliberately: argv is world-readable in
        /proc, and the questions in a consultation are clinical content.
        No shell — the template is split with shlex and executed directly,
        so nothing in a path or a question can become a shell metacharacter.
        """
        reason = self.unavailable_reason()
        if reason is not None:
            raise SpeechUnavailable(reason)

        argv = [part.format(model=self.model_path, output=str(output))
                for part in shlex.split(self.command)]
        try:
            result = subprocess.run(
                argv, input=text.encode(), capture_output=True,
                timeout=TTS_TIMEOUT_S, check=False)
        except subprocess.TimeoutExpired as exc:
            raise SpeechFailed(
                f"synthesis timed out after {TTS_TIMEOUT_S:.0f}s") from exc
        except OSError as exc:
            raise SpeechFailed(f"synthesis command failed to start: {exc}") from exc

        if result.returncode != 0:
            detail = result.stderr.decode(errors="replace").strip()[-300:]
            raise SpeechFailed(
                f"synthesis exited {result.returncode}: {detail or 'no output'}")
        if not output.exists() or output.stat().st_size == 0:
            raise SpeechFailed("synthesis produced no audio")

    # -- synthesis -----------------------------------------------------

    def _cache_path(self, text: str) -> Path:
        return self.cache_dir / f"{cache_key(text, self.voice)}.wav"

    def synthesise(self, text: str) -> tuple[bytes, int, int]:
        """(wav bytes, duration ms, synthesis ms). Cached by hash(text)+voice.

        Blocking CPU work — async callers must go through asyncio.to_thread.
        """
        text = text.strip()
        if not text:
            raise SpeechRefused("nothing to say")

        # Cheap pre-check so a pathological agenda string never reaches the
        # synthesiser. The hard bound is the duration check below.
        if len(text) > SPEECH_MAX_UTTERANCE_S * _MAX_CHARS_PER_SECOND:
            raise SpeechRefused(
                f"utterance of {len(text)} characters cannot fit "
                f"{SPEECH_MAX_UTTERANCE_S:.0f}s (SPEECH_MAX_UTTERANCE_S)")

        cached = self._cache_path(text)
        if cached.exists():
            wav_bytes = cached.read_bytes()
            return wav_bytes, wav_duration_ms(wav_bytes), 0

        # Synthesise to a temp file first: the cache must never hold audio
        # that failed validation, and a torn file would be poison. The temp
        # name is unique PER CALL, not per process: since 7c pre-synthesis
        # warms the cache in a background thread, two synthesisers can be
        # working on the same text at once (a warm and a tap), and a shared
        # temp path had one of them installing the other's file and then
        # finding nothing to read (found 2026-08-16). Both produce the same
        # audio; the last atomic replace wins.
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = cached.with_suffix(f".{os.getpid()}.{secrets.token_hex(4)}.wav.tmp")
        started = time.perf_counter()
        try:
            self._run_command(text, tmp)
            synth_ms = round(1000 * (time.perf_counter() - started))
            wav_bytes = tmp.read_bytes()
            duration_ms = wav_duration_ms(wav_bytes)
            # The hard cap. Bounds the exclusion window as well as the
            # utterance: a window is only as trustworthy as its length is
            # known.
            if duration_ms > SPEECH_MAX_UTTERANCE_S * 1000:
                raise SpeechRefused(
                    f"synthesised {duration_ms / 1000:.1f}s exceeds "
                    f"SPEECH_MAX_UTTERANCE_S={SPEECH_MAX_UTTERANCE_S:.0f}")
            tmp.replace(cached)              # atomic install
        finally:
            tmp.unlink(missing_ok=True)

        logger.info("Synthesised %d ms in %d ms: %r", duration_ms, synth_ms, text)
        return wav_bytes, duration_ms, synth_ms

    # -- utterances ----------------------------------------------------

    def prepare(self, ref: dict, agenda: AgendaLog | None = None, *,
                user_id: int | None = None, consultation_id: int | None = None,
                doctor: str | None = None) -> Utterance:
        """Resolve a reference, synthesise it, and register the result."""
        resolution = resolve(ref, agenda, doctor)
        wav_bytes, duration_ms, synth_ms = self.synthesise(resolution.text)
        utterance = Utterance(
            utterance_id=secrets.token_hex(8),
            text=resolution.text, voice=self.voice, wav=wav_bytes,
            duration_ms=duration_ms, synth_ms=synth_ms,
            ref_kind=resolution.ref_kind, ref_detail=resolution.ref_detail,
            cds_rationale=resolution.cds_rationale, stale=resolution.stale,
            user_id=user_id, consultation_id=consultation_id)
        self._utterances[utterance.utterance_id] = utterance
        return utterance

    def prepare_auto(self, utterance: auto_mode.Utterance,
                     agenda: AgendaLog | None = None, *,
                     phase: str, trigger: dict | None = None,
                     detail: dict | None = None,
                     user_id: int | None = None, consultation_id: int | None = None,
                     doctor: str | None = None) -> Utterance:
        """Resolve a WHITELIST utterance for the auto path, synthesise it
        through the same cache and cap as a tap, and register the result.

        Phase 7c (PHASE_7C_SPEC.md §4, §11). The registered utterance's
        `ref_detail` carries the resolution's own detail plus
        `{"via": "auto", "phase": ..., "trigger": ...}`, so the
        system_utterance row written at session end and the review page's
        grey channel can tell an auto utterance from a tap without a new
        column; `cds_rationale` comes from the agenda version exactly as
        for a tap. `phase` is the controller's phase value; `trigger` is
        the caller's account of what prompted it (quiet seconds, a
        hand-back) and is stored as given; `detail` (slice 4) adds the
        question record — topic and open_form — beside them.
        """
        resolution = resolve_utterance(utterance, agenda, doctor)
        wav_bytes, duration_ms, synth_ms = self.synthesise(resolution.text)
        phase_value = getattr(phase, "value", phase)
        registered = Utterance(
            utterance_id=secrets.token_hex(8),
            text=resolution.text, voice=self.voice, wav=wav_bytes,
            duration_ms=duration_ms, synth_ms=synth_ms,
            ref_kind=resolution.ref_kind,
            ref_detail={**resolution.ref_detail, "via": "auto",
                        "phase": str(phase_value), "trigger": dict(trigger or {}),
                        **dict(detail or {})},
            cds_rationale=resolution.cds_rationale, stale=resolution.stale,
            user_id=user_id, consultation_id=consultation_id)
        self._utterances[registered.utterance_id] = registered
        return registered

    def presynthesise_phrases(self, doctor: str | None = None) -> dict[str, str]:
        """Warm the disk cache with every fixed phrase (PHASE_7C_SPEC.md §9).

        So that an encourager in the golden minutes is a cache hit — 0 ms
        synthesis, the play command is a WebSocket message and a cached
        fetch. Runs at service start, off the event loop, and NEVER raises:
        a machine without Piper, or a phrase that fails, is logged and the
        service carries on exactly as before — pre-synthesis is a latency
        courtesy, not a condition of speaking.

        Phrases with a `{doctor}` slot are skipped at service start: the
        name is filled per session from the doctor's account, so there is
        no one text to warm then. Neither of them is an encourager. Called
        again with `doctor` when a session starts under auto mode (7c slice
        3), it warms those two for that doctor's name — the others are
        then cache hits. Returns a per-phrase outcome map ("cached",
        "synthesised", "skipped: …", "failed: …") for the log and for tests.
        """
        outcomes: dict[str, str] = {}
        reason = self.unavailable_reason()
        if reason is not None:
            logger.info("Speech pre-synthesis skipped: %s", reason)
            return {phrase_id: f"skipped: {reason}" for phrase_id in PHRASES}
        for phrase_id, template in PHRASES.items():
            if "{doctor}" in template and doctor is None:
                outcomes[phrase_id] = "skipped: doctor-named, filled per session"
                continue
            text = render_phrase(phrase_id, doctor)
            try:
                if self._cache_path(text).exists():
                    outcomes[phrase_id] = "cached"
                    continue
                self.synthesise(text)
                outcomes[phrase_id] = "synthesised"
            except Exception as exc:  # noqa: BLE001 - never fatal, by contract
                outcomes[phrase_id] = f"failed: {exc}"
                logger.warning("Pre-synthesis of phrase %r failed: %s", phrase_id, exc)
        logger.info("Speech pre-synthesis: %s",
                    ", ".join(f"{k}={v.split(':')[0]}" for k, v in outcomes.items()))
        return outcomes

    def get(self, utterance_id: str) -> Utterance | None:
        return self._utterances.get(utterance_id)
