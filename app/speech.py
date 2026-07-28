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
    # Examination handover: the system never pretends to examine.
    "examination_handover": "Thank you — Dr {doctor} will examine you now.",
    # Sound check (spec Part 10 / D6). Deliberately not clinical and not
    # addressed to the patient — it is a check spoken in the room, and it
    # should sound like one.
    "sound_check": "Sound check. If you can hear this clearly, press yes.",
    # Silence nudge (Phase 7b session 3, owner's wording verbatim). THE
    # ONLY AUTONOMOUS UTTERANCE IN 7a/7b — the caging lives in main.py's
    # speak handler (one-shot per consultation, only after the invitation
    # has played through, any activity cancels it client-side). It must
    # stay the only one until 7c's behaviour-policy machinery exists — do
    # not generalise it into an encourager loop.
    "silence_nudge": "When you're ready, tell me what's brought you in today.",
}

ENCOURAGER_IDS = ("mm-hm", "i_see", "go_on")

# Phrases the patient must have heard the disclosure before (hard rule 4).
# The encouragers are exempt: "mm-hm" is not a clinical interaction, and
# gating them would make the lock feel like a nuisance rather than a rule.
DISCLOSURE_GATED_PHRASES = ("invitation", "examination_handover", "silence_nudge")


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
# can be set from real data later — see `scripts/calibrate_barge_in.py`
# when it is built (build order item 5).
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
        # that failed validation, and a torn file would be poison.
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = cached.with_suffix(f".{os.getpid()}.wav.tmp")
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

    def get(self, utterance_id: str) -> Utterance | None:
        return self._utterances.get(utterance_id)
