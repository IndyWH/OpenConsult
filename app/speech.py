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

**CPU only, deliberately.** `app/finalize.py`'s VRAM sequencing assumes
sole ownership of the 24 GB card — MedGemma at ~17 GB plus
WhisperX+pyannote at 6–8 GB leaves no room for a guest. `PiperVoice.load`
is called with an explicit `use_cuda=False` rather than relying on its
default, so the intent is visible at the call site.

Piper is an optional dependency, absent from `pyproject.toml` as of
2026-07-25 pending the owner's decision (it is GPL-3.0-or-later, and
adding it re-resolves the lockfile on a machine where resolution churn has
corrupted the CUDA wheels before — see HANDOVER). Everything here that
does not need Piper works without it; synthesis raises
`SpeechUnavailable`, and the tests that need real audio self-skip, exactly
as the Ollama/corpus-dependent tests already do.
"""

from __future__ import annotations

import hashlib
import io
import logging
import os
import secrets
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
    """Piper or its voice model is not installed on this machine."""


class SpeechRefused(ValueError):
    """The request cannot be honoured: unknown reference, or over the cap.

    Distinct from SpeechUnavailable on purpose — this one is the client's
    fault and is audited as `speech.failed`.
    """


# --- the fixed phrase table ------------------------------------------------
#
# Reviewed in advance, wording from PHASE_7A_SPEC.md Part 5. This is half
# of the answer to "what can the system say?" — the other half is the CDS
# agenda, which the CDS engine already constrains to questions.
#
# NOTE FOR THE OWNER: the four spec-quoted phrases are verbatim. The
# `disclosure` wording is NOT in the spec — hard rule 4 requires only that
# the patient is told they are talking to a machine, so the sentence below
# is a first draft written by the implementer and needs the owner's
# sign-off as a clinical-communication decision, like the marking schemes.

PHRASES: dict[str, str] = {
    # Hard rule 4 — disclosure. DRAFT WORDING, awaiting the owner.
    "disclosure": (
        "Before we begin — I am a computer, not a person. "
        "I will ask you some questions about what has brought you in. "
        "Doctor Herath is here with you and will examine you."
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
    "examination_handover": "Thank you — Doctor Herath will examine you now.",
}

ENCOURAGER_IDS = ("mm-hm", "i_see", "go_on")


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


def resolve(ref: dict, agenda: AgendaLog | None = None) -> Resolution:
    """Turn a client reference into server-authored text.

    Raises SpeechRefused for anything unrecognised. It never falls back to
    a client-supplied string, because there is no client-supplied string:
    that is the whole design.
    """
    if not isinstance(ref, dict):
        raise SpeechRefused("speak.ref must be an object")

    kind = ref.get("kind")

    if kind == "phrase":
        phrase_id = ref.get("id")
        if phrase_id not in PHRASES:
            raise SpeechRefused(f"unknown phrase id: {phrase_id!r}")
        return Resolution(text=PHRASES[phrase_id], ref_kind="phrase",
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
                 cache_dir: Path | None = None) -> None:
        self.voice = voice or TTS_VOICE
        self.model_path = model_path if model_path is not None else TTS_MODEL_PATH
        self.cache_dir = Path(cache_dir) if cache_dir else SPEECH_CACHE_DIR
        self._piper = None
        self._utterances: dict[str, Utterance] = {}

    # -- availability --------------------------------------------------

    @property
    def available(self) -> bool:
        """True when synthesis could actually happen right now."""
        if not TTS_ENABLED or not self.model_path:
            return False
        if not Path(self.model_path).exists():
            return False
        try:
            import piper  # noqa: F401
        except ImportError:
            return False
        return True

    def _load(self):
        if self._piper is not None:
            return self._piper
        if not TTS_ENABLED:
            raise SpeechUnavailable("TTS_ENABLED=false")
        if not self.model_path:
            raise SpeechUnavailable("TTS_MODEL_PATH is not set")
        if not Path(self.model_path).exists():
            raise SpeechUnavailable(f"voice model not found: {self.model_path}")
        try:
            from piper import PiperVoice
        except ImportError as exc:
            raise SpeechUnavailable(
                "piper-tts is not installed (optional dependency)") from exc
        started = time.perf_counter()
        # use_cuda=False is Piper's default; passed explicitly because the
        # GPU rule is load-bearing here, not incidental (see module docstring).
        self._piper = PiperVoice.load(self.model_path, use_cuda=False)
        logger.info("Piper voice %s loaded in %.2fs (CPU)",
                    self.voice, time.perf_counter() - started)
        return self._piper

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

        piper = self._load()
        started = time.perf_counter()
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            piper.synthesize_wav(text, wav_file)
        wav_bytes = buffer.getvalue()
        synth_ms = round(1000 * (time.perf_counter() - started))

        duration_ms = wav_duration_ms(wav_bytes)
        # The hard cap. Bounds the exclusion window as well as the
        # utterance: a window is only as trustworthy as its length is known.
        if duration_ms > SPEECH_MAX_UTTERANCE_S * 1000:
            raise SpeechRefused(
                f"synthesised {duration_ms / 1000:.1f}s exceeds "
                f"SPEECH_MAX_UTTERANCE_S={SPEECH_MAX_UTTERANCE_S:.0f}")

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = cached.with_suffix(".wav.tmp")
        tmp.write_bytes(wav_bytes)
        tmp.replace(cached)   # atomic: a torn cache file would be poison
        logger.info("Synthesised %d ms in %d ms: %r", duration_ms, synth_ms, text)
        return wav_bytes, duration_ms, synth_ms

    # -- utterances ----------------------------------------------------

    def prepare(self, ref: dict, agenda: AgendaLog | None = None, *,
                user_id: int | None = None,
                consultation_id: int | None = None) -> Utterance:
        """Resolve a reference, synthesise it, and register the result."""
        resolution = resolve(ref, agenda)
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
