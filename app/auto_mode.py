"""Phase 7c: the auto-mode phase machine — pure, unwired, dark.

PHASE_7C_SPEC.md §3 (architecture), §4 (the utterance whitelist) and §7
(the urgency pause protocol). Slice 1 of the build: this module lands
UNUSED. Nothing in the running app imports it yet, and everything in
7c ships behind AUTO_MODE_ENABLED=false — enabling it is the owner's
act, after the frozen gate is met.

WHAT THIS MODULE IS
-------------------
A plain state machine. Stdlib and typing only: no FastAPI, no database,
no imports from other app modules, no threads, no timers of its own.
The LiveSession will own one and drive it with the events the session
already produces; the clock is an injected callable returning monotonic
seconds, so tests control time and the machine never sleeps.

The phase is CODE-OWNED. The LLM chooses content only within the
current phase and never advances it (PHASE_7_SPEC.md, staged build:
"the LLM choosing content WITHIN the current phase, never the phase
itself"). Every transition goes through one explicit legal-transition
table, returns a `Transition` record for the caller to audit
(`auto.phase` with from/to/trigger, spec §11), and an illegal
transition raises `AutoModeError` — never silently ignored, because a
silent no-op would let the wiring drift out of step with the phase it
believes it is in.

HARD RULE 1 BY CONSTRUCTION
---------------------------
Hard rule 1 (questions and acknowledgements only — no advice, no
diagnosis, no reassurance to the patient) is met here by the TYPE
SYSTEM, not by a check. The three utterance types below are the whole
whitelist a caller can ask auto mode to say: a fixed phrase by id, an
owner-approved template by id plus a topic string, or an agenda
question by assessment version and index. There is deliberately NO type
that carries free text, so a caller cannot construct an utterance the
design forbids; the speech layer's existing refusal of a `speak` that
carries raw text is the second line, downstream, unchanged.

ZERO QUESTIONS IN GOLDEN
------------------------
`request_question()` raises in GOLDEN. That is a coding-error guard,
not a filter (spec §5): a question request during the golden minutes
means the wiring is wrong, and the right response is a loud failure in
tests, not a quietly dropped utterance in a room.

THE PAUSE PROTOCOL AND THE RATCHET (§7)
---------------------------------------
An urgent alarm in GOLDEN, OPEN or CLOSED moves to PAUSED_URGENT and
remembers the phase it left. Resume returns to exactly that phase; take
over moves to TAKEN_OVER, terminal for the session's auto run. The
controller keeps the set of acknowledged urgent action texts for the
session — but that set never suppresses a pause: a re-fire of an
already-acknowledged action after a resume pauses again and needs a
fresh acknowledgement. There is no automatic ack-resume loop, and the
set exists so the review page can show who acknowledged what, not so
the machine can decide an alarm is old news.

Auto off is legal and immediate from every state (hard rule 3: the
doctor always wins), including OFF itself, so the doctor's tap can
never be the thing that raises.

Thresholds (the golden window, quiet timings) are NOT here — they arrive
with the wiring in slice 3, as owner-tunable settings. This machine has
no numbers in it.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import Enum

__all__ = [
    "AutoPhase",
    "AutoEvent",
    "AutoModeError",
    "PhraseUtterance",
    "TemplateUtterance",
    "AgendaUtterance",
    "Utterance",
    "QuestionUtterance",
    "Transition",
    "Acknowledgement",
    "AutoModeController",
    "LEGAL_TRANSITIONS",
    "RESUMES_PRIOR_PHASE",
    "LISTENING_PHASES",
    "QUESTION_PHASES",
]


class AutoModeError(RuntimeError):
    """A transition or request the phase machine does not permit.

    Raised, never swallowed: every one of these is a wiring or coding
    error, and the place to learn about it is a failing test.
    """


class AutoPhase(str, Enum):
    """The phases of a supervised auto history-taking run (spec §3)."""

    OFF = "off"
    DISCLOSURE = "disclosure"
    INVITATION = "invitation"
    GOLDEN = "golden"
    OPEN = "open"
    CLOSED = "closed"
    HANDOVER = "handover"
    PAUSED_URGENT = "paused_urgent"
    TAKEN_OVER = "taken_over"


class AutoEvent(str, Enum):
    """The events that drive the machine — named for what happened, not
    for where the machine goes. The value is the trigger string written
    into every `Transition` record and hence into the audit trail."""

    ENABLE = "enable"
    DISCLOSURE_COMPLETED = "disclosure_completed"
    INVITATION_COMPLETED = "invitation_completed"
    GOLDEN_TIMER_ELAPSED = "golden_timer_elapsed"
    HAND_BACK = "hand_back"
    NARRATIVE_EXHAUSTED = "narrative_exhausted"
    AGENDA_EXHAUSTED = "agenda_exhausted"
    HANDOVER_REQUESTED = "handover_requested"
    URGENT_ALARM = "urgent_alarm"
    ACKNOWLEDGE_RESUME = "acknowledge_resume"
    ACKNOWLEDGE_TAKE_OVER = "acknowledge_take_over"
    AUTO_OFF = "auto_off"


# --- the utterance whitelist, as types (spec §4) ---------------------------

@dataclass(frozen=True, slots=True)
class PhraseUtterance:
    """A fixed, owner-verbatim phrase (disclosure, invitation, the
    encouragers, silence nudge, examination handover, the anything-else
    follow-up), named by its id in the speech layer's phrase table."""

    phrase_id: str


@dataclass(frozen=True, slots=True)
class TemplateUtterance:
    """An owner-approved open-question template, named by id, instantiated
    with a short topic noun phrase ("the chest pain"). The template
    wording lives in the speech layer; only the topic slot varies."""

    template_id: str
    topic: str


@dataclass(frozen=True, slots=True)
class AgendaUtterance:
    """A CDS agenda question, verbatim, addressed by assessment version and
    index into that version's `questions_to_ask` — the same reference the
    doctor's tap already uses, so the text is resolved server-side from
    the versioned AgendaLog and never carried by the caller."""

    assessment_version: int
    index: int


# The whole whitelist. Nothing else is an utterance; there is no free-text
# member and none may be added.
Utterance = PhraseUtterance | TemplateUtterance | AgendaUtterance

# The two utterance shapes that are questions, and hence forbidden in GOLDEN.
QuestionUtterance = TemplateUtterance | AgendaUtterance


# --- audit records ---------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Transition:
    """One audited phase change: where from, where to, what caused it, and
    the monotonic clock reading when it happened."""

    from_phase: AutoPhase
    to_phase: AutoPhase
    trigger: AutoEvent
    at: float


@dataclass(frozen=True, slots=True)
class Acknowledgement:
    """One doctor acknowledgement of a pause: the action texts it covered,
    how it was resolved (`resume` or `take_over`), the phase the pause
    interrupted, and the clock readings of the pause and the ack."""

    actions: frozenset[str]
    resolution: str
    paused_from: AutoPhase
    paused_at: float
    acknowledged_at: float


# --- the legal-transition table (spec §3, §6, §7) --------------------------

class _ResumesPriorPhase:
    """Marker for the one edge whose target is not fixed: acknowledge-and-
    resume returns to whichever of GOLDEN/OPEN/CLOSED the pause left."""

    def __repr__(self) -> str:  # pragma: no cover - repr only
        return "RESUMES_PRIOR_PHASE"


RESUMES_PRIOR_PHASE = _ResumesPriorPhase()

_P = AutoPhase
_E = AutoEvent

# (from, event) -> to. Absent means illegal, and illegal raises.
LEGAL_TRANSITIONS: dict[tuple[AutoPhase, AutoEvent], AutoPhase | _ResumesPriorPhase] = {
    # The main line: OFF → DISCLOSURE → INVITATION → GOLDEN → OPEN → CLOSED → HANDOVER
    (_P.OFF, _E.ENABLE): _P.DISCLOSURE,
    (_P.DISCLOSURE, _E.DISCLOSURE_COMPLETED): _P.INVITATION,
    (_P.INVITATION, _E.INVITATION_COMPLETED): _P.GOLDEN,
    # GOLDEN ends when the window has elapsed (the wiring fires this only
    # once the current turn has also ended — never at a bare timer
    # boundary, spec §6) or early on an explicit hand-back.
    (_P.GOLDEN, _E.GOLDEN_TIMER_ELAPSED): _P.OPEN,
    (_P.GOLDEN, _E.HAND_BACK): _P.OPEN,
    # OPEN narrows to CLOSED when the open narrative is dry; either
    # question phase ends in HANDOVER when a post-answer revision leaves
    # the agenda empty (spec §6).
    (_P.OPEN, _E.NARRATIVE_EXHAUSTED): _P.CLOSED,
    (_P.OPEN, _E.AGENDA_EXHAUSTED): _P.HANDOVER,
    (_P.CLOSED, _E.AGENDA_EXHAUSTED): _P.HANDOVER,
    # The doctor's Handover tap, from any listening phase.
    (_P.GOLDEN, _E.HANDOVER_REQUESTED): _P.HANDOVER,
    (_P.OPEN, _E.HANDOVER_REQUESTED): _P.HANDOVER,
    (_P.CLOSED, _E.HANDOVER_REQUESTED): _P.HANDOVER,
    # The pause protocol (spec §7). While paused the session keeps
    # listening and the CDS keeps revising, so an alarm can re-fire before
    # the doctor has answered the banner: that stays paused (a recorded
    # self-edge) and widens the pending set the acknowledgement covers.
    (_P.GOLDEN, _E.URGENT_ALARM): _P.PAUSED_URGENT,
    (_P.OPEN, _E.URGENT_ALARM): _P.PAUSED_URGENT,
    (_P.CLOSED, _E.URGENT_ALARM): _P.PAUSED_URGENT,
    (_P.PAUSED_URGENT, _E.URGENT_ALARM): _P.PAUSED_URGENT,
    (_P.PAUSED_URGENT, _E.ACKNOWLEDGE_RESUME): RESUMES_PRIOR_PHASE,
    (_P.PAUSED_URGENT, _E.ACKNOWLEDGE_TAKE_OVER): _P.TAKEN_OVER,
    # The doctor always wins: auto off from every state, OFF included.
    **{(phase, _E.AUTO_OFF): _P.OFF for phase in AutoPhase},
}

# The phases in which the system is listening to the patient under auto
# mode; the only phases an urgent alarm can interrupt.
LISTENING_PHASES = frozenset({_P.GOLDEN, _P.OPEN, _P.CLOSED})

# The only phases in which a question may be requested (spec §5, §6).
QUESTION_PHASES = frozenset({_P.OPEN, _P.CLOSED})


# --- the controller --------------------------------------------------------

class AutoModeController:
    """The auto-mode phase machine for one live session.

    Construct with a clock — any zero-argument callable returning
    monotonic seconds; `time.monotonic` by default, a counter in tests.
    Every event method returns the `Transition` it made; every illegal
    event raises `AutoModeError`. The controller keeps its own history of
    transitions and acknowledgements so the caller can audit them, and
    exposes the pause bookkeeping the banner needs.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._phase = AutoPhase.OFF
        self._entered_at = clock()
        self._history: list[Transition] = []
        # Pause bookkeeping (spec §7).
        self._paused_from: AutoPhase | None = None
        self._paused_at: float | None = None
        self._pending_actions: frozenset[str] = frozenset()
        # The ratchet's memory: every action text the doctor has
        # acknowledged this session. Consulted by the review page, never
        # by the machine to decide whether to pause.
        self._acknowledged: set[str] = set()
        self._acknowledgements: list[Acknowledgement] = []

    # -- state the wiring reads --------------------------------------------

    @property
    def phase(self) -> AutoPhase:
        return self._phase

    @property
    def history(self) -> tuple[Transition, ...]:
        """Every transition made so far, oldest first."""
        return tuple(self._history)

    @property
    def paused_from(self) -> AutoPhase | None:
        """The phase a live pause interrupted; None unless PAUSED_URGENT."""
        return self._paused_from

    @property
    def pending_actions(self) -> frozenset[str]:
        """Urgent action texts awaiting the doctor's acknowledgement."""
        return self._pending_actions

    @property
    def acknowledged_actions(self) -> frozenset[str]:
        """Every urgent action text acknowledged this session (the ratchet's
        record — it never suppresses a pause)."""
        return frozenset(self._acknowledged)

    @property
    def acknowledgements(self) -> tuple[Acknowledgement, ...]:
        return tuple(self._acknowledgements)

    def seconds_in_phase(self) -> float:
        """Monotonic seconds since the current phase was entered."""
        return self._clock() - self._entered_at

    def is_legal(self, event: AutoEvent) -> bool:
        """Whether `event` is a legal transition from the current phase."""
        return (self._phase, event) in LEGAL_TRANSITIONS

    # -- the guards ---------------------------------------------------------

    def request_question(self, utterance: QuestionUtterance) -> QuestionUtterance:
        """Permit a question utterance in the current phase, or raise.

        Raises `AutoModeError` in GOLDEN — the zero-questions rule, enforced
        as a coding-error guard rather than a filter (spec §5) — and in
        every other phase that is not OPEN or CLOSED, since a question
        during disclosure, invitation, a pause or after handover is
        equally a wiring fault. Also refuses anything that is not a
        `TemplateUtterance` or `AgendaUtterance`: a fixed phrase is not a
        question, and free text is not an utterance at all.
        """
        if not isinstance(utterance, (TemplateUtterance, AgendaUtterance)):
            raise AutoModeError(
                f"a question must be a TemplateUtterance or AgendaUtterance, "
                f"not {type(utterance).__name__}")
        if self._phase is AutoPhase.GOLDEN:
            raise AutoModeError(
                "zero questions in GOLDEN: a question was requested during the "
                "golden minutes — this is a coding error, not a filtered request")
        if self._phase not in QUESTION_PHASES:
            raise AutoModeError(
                f"a question was requested in phase {self._phase.value!r}; "
                f"questions are permitted only in OPEN and CLOSED")
        return utterance

    # -- the events ---------------------------------------------------------

    def enable(self) -> Transition:
        """The doctor turns auto mode on: OFF → DISCLOSURE."""
        return self._fire(AutoEvent.ENABLE)

    def disclosure_completed(self) -> Transition:
        """The disclosure phrase's playback ended: DISCLOSURE → INVITATION."""
        return self._fire(AutoEvent.DISCLOSURE_COMPLETED)

    def invitation_completed(self) -> Transition:
        """The invitation's `speak_ended` arrived — the prereg's metric-3
        zero point: INVITATION → GOLDEN."""
        return self._fire(AutoEvent.INVITATION_COMPLETED)

    def golden_timer_elapsed(self) -> Transition:
        """The golden window has run its course AND the current turn has
        ended (the caller owns the timer and the turn; spec §6): GOLDEN → OPEN."""
        return self._fire(AutoEvent.GOLDEN_TIMER_ELAPSED)

    def hand_back(self) -> Transition:
        """An explicit hand-back ("that's all", "what do you think?") during
        the golden minutes ends them early: GOLDEN → OPEN."""
        return self._fire(AutoEvent.HAND_BACK)

    def narrative_exhausted(self) -> Transition:
        """The open narrative has dried up; questions narrow: OPEN → CLOSED."""
        return self._fire(AutoEvent.NARRATIVE_EXHAUSTED)

    def agenda_exhausted(self) -> Transition:
        """A post-answer revision left the agenda empty: OPEN/CLOSED → HANDOVER."""
        return self._fire(AutoEvent.AGENDA_EXHAUSTED)

    def handover_requested(self) -> Transition:
        """The doctor tapped Handover: GOLDEN/OPEN/CLOSED → HANDOVER."""
        return self._fire(AutoEvent.HANDOVER_REQUESTED)

    def urgent_alarm(self, action_texts: Iterable[str]) -> Transition:
        """The CDS produced non-empty urgent actions while auto mode was
        listening: → PAUSED_URGENT, remembering the phase it left. A re-fire
        while already paused stays paused and widens the pending set.
        Acknowledged-before is no defence — the ratchet (spec §7): every
        alarm pauses and needs a fresh acknowledgement.
        """
        actions = frozenset(str(a) for a in action_texts)
        if not actions:
            raise AutoModeError("an urgent alarm must carry at least one action text")
        transition = self._fire(AutoEvent.URGENT_ALARM)
        if transition.from_phase is not AutoPhase.PAUSED_URGENT:
            self._paused_from = transition.from_phase
            self._paused_at = transition.at
        self._pending_actions = self._pending_actions | actions
        return transition

    def acknowledge_and_resume(self) -> Transition:
        """RESUME AUTO on the pause banner: acknowledge the pending actions
        and return to exactly the phase the pause interrupted."""
        transition = self._fire(AutoEvent.ACKNOWLEDGE_RESUME)
        self._record_ack("resume", transition.at)
        return transition

    def acknowledge_and_take_over(self) -> Transition:
        """TAKE OVER on the pause banner: acknowledge the pending actions
        and drop to standard mode: PAUSED_URGENT → TAKEN_OVER, terminal for
        this auto run."""
        transition = self._fire(AutoEvent.ACKNOWLEDGE_TAKE_OVER)
        self._record_ack("take_over", transition.at)
        return transition

    def auto_off(self) -> Transition:
        """The doctor turns auto mode off. Legal and immediate from every
        state, OFF included; a live pause is dropped unacknowledged (the
        alarm itself lives in the CDS panel and the review banner, not
        here, so nothing is lost)."""
        transition = self._fire(AutoEvent.AUTO_OFF)
        self._clear_pause()
        return transition

    # -- internals ----------------------------------------------------------

    def _fire(self, event: AutoEvent) -> Transition:
        target = LEGAL_TRANSITIONS.get((self._phase, event))
        if target is None:
            raise AutoModeError(
                f"illegal transition: {event.value!r} in phase {self._phase.value!r}")
        if target is RESUMES_PRIOR_PHASE:
            if self._paused_from is None:  # pragma: no cover - table guarantees a pause
                raise AutoModeError("resume with no paused-from phase recorded")
            target = self._paused_from
        now = self._clock()
        transition = Transition(from_phase=self._phase, to_phase=target,
                                trigger=event, at=now)
        self._phase = target
        self._entered_at = now
        self._history.append(transition)
        return transition

    def _record_ack(self, resolution: str, at: float) -> None:
        assert self._paused_from is not None and self._paused_at is not None
        self._acknowledgements.append(Acknowledgement(
            actions=self._pending_actions, resolution=resolution,
            paused_from=self._paused_from, paused_at=self._paused_at,
            acknowledged_at=at))
        self._acknowledged |= self._pending_actions
        self._clear_pause()

    def _clear_pause(self) -> None:
        self._paused_from = None
        self._paused_at = None
        self._pending_actions = frozenset()


# --- the ratchet's notion of "the same action" (owner decision 2026-09-07) --
#
# Pilot 485, defect E3: the CDS re-worded the hospital action on every
# pass — "Consider hospital admission", "Immediate referral to hospital",
# "Same-day specialist referral" — and the ratchet, keyed on exact text,
# read each as genuinely new and re-paused three times, once 8 s after a
# RESUME on a pass that was in flight at the resume, once cutting the
# doctor's own tapped question. The ratchet now matches actions by
# meaning, not wording: lower-cased, punctuation and whitespace stripped,
# a small stop-word list removed, and a token-set similarity at or above
# AUTO_ACTION_MATCH_THRESHOLD (the wiring's setting; default 0.6). Pure,
# stdlib only (difflib) — no new dependency — so the rule is testable
# without a session, and every match the wiring acts on is audited
# (auto.action_matched) with both texts and the score.

# Words that carry urgency, hedging, place or verb but not WHICH action:
# stripping them is what lets "Consider hospital admission" meet
# "Immediate referral to hospital". Small on purpose; the owner tunes it.
ACTION_STOP_WORDS = frozenset({
    # articles, prepositions, conjunctions
    "a", "an", "the", "to", "for", "of", "and", "or", "with", "in", "at", "on", "by",
    # urgency and hedging
    "consider", "immediate", "immediately", "urgent", "urgently", "now", "today",
    "same", "day", "sameday", "asap", "prompt", "promptly", "early",
    # verbs that say "do it", not what
    "arrange", "obtain", "perform", "do", "give", "start", "check", "order",
    "request", "refer", "send", "get", "carry", "out",
    # place words
    "bedside",
    # possessives (owner decision 2026-09-08): the normaliser is shared by
    # the ratchet, the queue's exact match and the cone's topic identity,
    # and with "your" counted as a token "your tablets" and "your sleep"
    # scored 0.636 — one topic at the 0.6 threshold, so the tablets were
    # asked verbatim once sleep had been opened. Whose thing it is never
    # says WHICH action or topic. The articles were already here.
    "your", "my", "his", "her", "their", "our", "its",
})

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def normalise_action(text: str) -> frozenset[str]:
    """The tokens an action text is compared by: lower-case, punctuation and
    whitespace stripped, the stop words removed."""
    tokens = _TOKEN_RE.findall(str(text).casefold())
    return frozenset(t for t in tokens if t not in ACTION_STOP_WORDS)


def action_similarity(a: str, b: str) -> float:
    """Token-set similarity in [0, 1]: 1.0 for the same token set, 0.0 when
    the two share no token at all (so nothing matches on letters alone),
    otherwise the token-set ratio — the shared tokens against each side's
    shared-plus-own tokens, the best of the three pairings — computed
    with difflib.SequenceMatcher on the sorted, space-joined tokens."""
    ta, tb = normalise_action(a), normalise_action(b)
    if not ta or not tb:
        return 0.0
    if ta == tb:
        return 1.0
    shared = ta & tb
    if not shared:
        return 0.0
    sect = " ".join(sorted(shared))
    only_a = " ".join(sorted(ta - tb))
    only_b = " ".join(sorted(tb - ta))
    t1 = sect
    t2 = (sect + " " + only_a).strip()
    t3 = (sect + " " + only_b).strip()

    def ratio(x: str, y: str) -> float:
        return SequenceMatcher(None, x, y).ratio()

    return round(max(ratio(t1, t2), ratio(t1, t3), ratio(t2, t3)), 3)


def match_action(candidate: str, known: Iterable[str],
                 threshold: float) -> tuple[str, float] | None:
    """The known action `candidate` is the same as, if any: the best-scoring
    known text at or above `threshold` (an exact text scores 1.0 and wins
    outright). None when nothing known is close enough — a genuinely new
    action."""
    best: tuple[str, float] | None = None
    for text in known:
        score = 1.0 if str(text) == str(candidate) else action_similarity(candidate, text)
        if score >= threshold and (best is None or score > best[1]):
            best = (str(text), score)
            if score >= 1.0:
                break
    return best
