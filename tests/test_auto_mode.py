"""app/auto_mode.py — the pure auto-mode phase machine holds its properties.

Phase 7c slice 1 (PHASE_7C_SPEC.md §3, §4, §7; the machine-level subset of
§13). The module is unwired and dark: nothing here touches a session, a
socket or the database. Time is a counter the tests advance, so nothing
sleeps and every timing assertion is exact.

What these tests pin, and why each matters:

- The phase is code-owned and every edge is explicit. Every legal edge
  in the transition table is walked, and illegal edges RAISE rather than
  no-op — a silent no-op would let the wiring believe it is in a phase
  the machine has left, which is exactly how an unsupervised question
  gets asked at the wrong moment.
- Zero questions in GOLDEN is a coding-error guard, not a filter (§5):
  a question request in the golden minutes raises.
- The whitelist is TYPES (§4, hard rule 1 by construction): the three
  utterance shapes construct, none carries free text, and the module's
  public surface exposes no free-text utterance type. The assertion is
  on the public surface itself, not a search of the source.
- The pause protocol (§7): an alarm from each listening phase pauses,
  resume returns to exactly that phase, take-over is terminal.
- The ratchet (§7): acknowledging an action never makes its re-fire
  quieter — the same text pauses again after a resume and needs a fresh
  acknowledgement; there is no automatic ack-resume loop.
- Auto off is legal and immediate from every state (hard rule 3).
- Every transition returns a record carrying (from, to, trigger) for the
  audit trail (§11, `auto.phase`).
"""

from __future__ import annotations

import dataclasses
import types
import typing

import pytest

from app import auto_mode
from app.auto_mode import (LEGAL_TRANSITIONS, LISTENING_PHASES,
                           QUESTION_PHASES, RESUMES_PRIOR_PHASE,
                           Acknowledgement, AgendaUtterance, AutoEvent,
                           AutoModeController, AutoModeError, AutoPhase,
                           PhraseUtterance, QuestionUtterance,
                           TemplateUtterance, Transition, Utterance)


class Clock:
    """A monotonic clock the test advances by hand."""

    def __init__(self, start: float = 1000.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


# The event method that fires each event — the API under test is the
# named methods, not _fire(); the table is walked through them.
EVENT_METHODS: dict[AutoEvent, str] = {
    AutoEvent.ENABLE: "enable",
    AutoEvent.DISCLOSURE_COMPLETED: "disclosure_completed",
    AutoEvent.INVITATION_COMPLETED: "invitation_completed",
    AutoEvent.GOLDEN_TIMER_ELAPSED: "golden_timer_elapsed",
    AutoEvent.HAND_BACK: "hand_back",
    AutoEvent.NARRATIVE_EXHAUSTED: "narrative_exhausted",
    AutoEvent.AGENDA_EXHAUSTED: "agenda_exhausted",
    AutoEvent.HANDOVER_REQUESTED: "handover_requested",
    AutoEvent.URGENT_ALARM: "urgent_alarm",
    AutoEvent.ACKNOWLEDGE_RESUME: "acknowledge_and_resume",
    AutoEvent.ACKNOWLEDGE_TAKE_OVER: "acknowledge_and_take_over",
    AutoEvent.AUTO_OFF: "auto_off",
}

ALARM = ("Arrange immediate transfer to the emergency department",)


def fire(controller: AutoModeController, event: AutoEvent) -> Transition:
    method = getattr(controller, EVENT_METHODS[event])
    if event is AutoEvent.URGENT_ALARM:
        return method(ALARM)
    return method()


def drive_to(phase: AutoPhase, clock: Clock | None = None) -> AutoModeController:
    """A controller placed in `phase` by legal events only — no state is
    poked, so reaching a phase is itself evidence the path to it works."""
    c = AutoModeController(clock=clock or Clock())
    if phase is AutoPhase.OFF:
        return c
    c.enable()
    if phase is AutoPhase.DISCLOSURE:
        return c
    c.disclosure_completed()
    if phase is AutoPhase.INVITATION:
        return c
    c.invitation_completed()
    if phase is AutoPhase.GOLDEN:
        return c
    c.golden_timer_elapsed()
    if phase is AutoPhase.OPEN:
        return c
    if phase is AutoPhase.PAUSED_URGENT:
        c.urgent_alarm(ALARM)
        return c
    if phase is AutoPhase.TAKEN_OVER:
        c.urgent_alarm(ALARM)
        c.acknowledge_and_take_over()
        return c
    c.narrative_exhausted()
    if phase is AutoPhase.CLOSED:
        return c
    c.agenda_exhausted()
    assert phase is AutoPhase.HANDOVER
    return c


def test_every_phase_is_reachable_by_legal_events_alone():
    """drive_to() is the harness for everything below; if it could not
    reach a phase legally the tests that use it would be testing nothing."""
    for phase in AutoPhase:
        assert drive_to(phase).phase is phase


# --- the transition table --------------------------------------------------

def test_every_event_has_a_named_method_and_nothing_else_is_an_event():
    """The API is the event methods; the table is keyed by the enum. Both
    must agree, or an edge could exist in the table with no way to fire it."""
    assert set(EVENT_METHODS) == set(AutoEvent)
    events_in_table = {event for _, event in LEGAL_TRANSITIONS}
    assert events_in_table == set(AutoEvent)


@pytest.mark.parametrize("edge", sorted(LEGAL_TRANSITIONS, key=lambda e: (e[0].value, e[1].value)))
def test_every_legal_edge_transitions_to_its_table_target(edge):
    """Walk every (from, event) in the table from a legally reached `from`
    and check the machine lands on the table's target. Parametrised over
    the table itself, so a new edge is exercised the moment it is added
    and a removed edge is noticed the moment it goes."""
    from_phase, event = edge
    c = drive_to(from_phase)
    expected = LEGAL_TRANSITIONS[edge]
    if expected is RESUMES_PRIOR_PHASE:
        expected = c.paused_from
        assert expected in LISTENING_PHASES
    record = fire(c, event)
    assert c.phase is expected
    assert record == Transition(from_phase=from_phase, to_phase=expected,
                                trigger=event, at=record.at)


@pytest.mark.parametrize("phase", list(AutoPhase))
def test_illegal_edges_raise_and_leave_the_phase_untouched(phase):
    """Every event NOT in the table for this phase raises AutoModeError,
    and the phase is unchanged afterwards. Nothing is silently ignored:
    a swallowed event is how the wiring and the machine drift apart."""
    illegal = [e for e in AutoEvent if (phase, e) not in LEGAL_TRANSITIONS]
    assert illegal, f"{phase} has no illegal edges — the table is too permissive to test"
    for event in illegal:
        c = drive_to(phase)
        with pytest.raises(AutoModeError):
            fire(c, event)
        assert c.phase is phase
        assert not [t for t in c.history if t.trigger is event and t.from_phase is phase]


def test_representative_illegal_edges_by_name():
    """The cases a reader would ask about, spelled out: enabling twice,
    skipping the disclosure, a golden timer landing after the golden
    minutes are over, resuming when nothing is paused, and anything
    but auto-off after a take-over."""
    with pytest.raises(AutoModeError):
        drive_to(AutoPhase.DISCLOSURE).enable()
    with pytest.raises(AutoModeError):
        drive_to(AutoPhase.OFF).invitation_completed()
    with pytest.raises(AutoModeError):
        drive_to(AutoPhase.OPEN).golden_timer_elapsed()
    with pytest.raises(AutoModeError):
        drive_to(AutoPhase.OPEN).acknowledge_and_resume()
    taken = drive_to(AutoPhase.TAKEN_OVER)
    for event in AutoEvent:
        if event is AutoEvent.AUTO_OFF:
            continue
        with pytest.raises(AutoModeError):
            fire(taken, event)
    assert taken.phase is AutoPhase.TAKEN_OVER


def test_the_main_line_runs_disclosure_to_handover_in_order():
    """The spine of §3: OFF → DISCLOSURE → INVITATION → GOLDEN → OPEN →
    CLOSED → HANDOVER, each step by its own event, recorded in order."""
    c = AutoModeController(clock=Clock())
    c.enable()
    c.disclosure_completed()
    c.invitation_completed()
    c.golden_timer_elapsed()
    c.narrative_exhausted()
    c.agenda_exhausted()
    assert [t.to_phase for t in c.history] == [
        AutoPhase.DISCLOSURE, AutoPhase.INVITATION, AutoPhase.GOLDEN,
        AutoPhase.OPEN, AutoPhase.CLOSED, AutoPhase.HANDOVER]
    assert c.phase is AutoPhase.HANDOVER


def test_hand_back_ends_golden_early_and_the_late_timer_then_raises():
    """§6: an explicit hand-back exits GOLDEN before the window is up. A
    golden-timer event arriving afterwards is illegal — the wiring must
    check the phase, because the machine will not guess for it."""
    c = drive_to(AutoPhase.GOLDEN)
    assert c.hand_back().to_phase is AutoPhase.OPEN
    with pytest.raises(AutoModeError):
        c.golden_timer_elapsed()


def test_handover_is_reachable_from_every_listening_phase_by_the_doctors_tap():
    """§6: the doctor's Handover tap works in GOLDEN, OPEN and CLOSED; the
    agenda-empty route only exists once questions have begun."""
    for phase in LISTENING_PHASES:
        assert drive_to(phase).handover_requested().to_phase is AutoPhase.HANDOVER
    for phase in QUESTION_PHASES:
        assert drive_to(phase).agenda_exhausted().to_phase is AutoPhase.HANDOVER
    with pytest.raises(AutoModeError):
        drive_to(AutoPhase.GOLDEN).agenda_exhausted()


def test_is_legal_reports_the_table_for_the_current_phase():
    c = drive_to(AutoPhase.GOLDEN)
    assert c.is_legal(AutoEvent.HAND_BACK)
    assert c.is_legal(AutoEvent.URGENT_ALARM)
    assert not c.is_legal(AutoEvent.NARRATIVE_EXHAUSTED)


# --- zero questions in GOLDEN --------------------------------------------

def test_a_question_request_in_golden_raises():
    """§5: zero questions in the golden minutes is enforced as a raise, not
    a filtered request. Both question shapes are refused."""
    c = drive_to(AutoPhase.GOLDEN)
    with pytest.raises(AutoModeError, match="GOLDEN"):
        c.request_question(AgendaUtterance(assessment_version=1, index=0))
    with pytest.raises(AutoModeError, match="GOLDEN"):
        c.request_question(TemplateUtterance(template_id="tell_me_more", topic="the chest pain"))
    assert c.phase is AutoPhase.GOLDEN


@pytest.mark.parametrize("phase", sorted(set(AutoPhase) - QUESTION_PHASES, key=lambda p: p.value))
def test_a_question_request_outside_the_question_phases_raises(phase):
    """A question during disclosure, invitation, a pause, after handover or
    with auto off is the same class of wiring fault as one in GOLDEN."""
    with pytest.raises(AutoModeError):
        drive_to(phase).request_question(AgendaUtterance(assessment_version=1, index=0))


@pytest.mark.parametrize("phase", sorted(QUESTION_PHASES, key=lambda p: p.value))
def test_a_question_request_in_open_or_closed_is_returned_unchanged(phase):
    q = AgendaUtterance(assessment_version=3, index=1)
    assert drive_to(phase).request_question(q) is q


def test_request_question_refuses_a_phrase_and_refuses_free_text():
    """A fixed phrase is not a question, and a bare string is not an
    utterance at all — neither passes the guard even in OPEN."""
    c = drive_to(AutoPhase.OPEN)
    with pytest.raises(AutoModeError):
        c.request_question(PhraseUtterance(phrase_id="encourager_1"))  # type: ignore[arg-type]
    with pytest.raises(AutoModeError):
        c.request_question("Can you tell me more about the pain?")  # type: ignore[arg-type]


# --- the whitelist as types ----------------------------------------------

def test_the_three_utterance_types_construct_and_are_frozen():
    p = PhraseUtterance(phrase_id="invitation")
    t = TemplateUtterance(template_id="tell_me_more", topic="the chest pain")
    a = AgendaUtterance(assessment_version=2, index=0)
    assert (p.phrase_id, t.template_id, t.topic, a.assessment_version, a.index) == (
        "invitation", "tell_me_more", "the chest pain", 2, 0)
    for u in (p, t, a):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(u, next(iter(dataclasses.fields(u))).name, "changed")


def public_types() -> set[type]:
    """The classes the module publishes: `__all__` is the surface."""
    return {getattr(auto_mode, name) for name in auto_mode.__all__
            if isinstance(getattr(auto_mode, name), type)}


def test_the_public_surface_exposes_exactly_three_utterance_types_and_no_free_text_one():
    """Hard rule 1 by construction (§4). Asserted on the public surface:
    the `Utterance` union is exactly the three whitelist types, they are
    the only public types whose name says utterance, and no field of any
    of them is a free-text field — the only str slots are an id, an id
    plus a topic noun phrase for an owner-approved template. There is no
    type a caller could use to hand auto mode a sentence."""
    whitelist = {PhraseUtterance, TemplateUtterance, AgendaUtterance}
    assert set(typing.get_args(Utterance)) == whitelist
    assert set(typing.get_args(QuestionUtterance)) == {TemplateUtterance, AgendaUtterance}
    published_utterances = {t for t in public_types() if t.__name__.endswith("Utterance")}
    assert published_utterances == whitelist
    # No whitelist type accepts free text under any name.
    for cls in whitelist:
        for forbidden in ("text", "wording", "sentence", "content"):
            assert forbidden not in {f.name for f in dataclasses.fields(cls)}
            with pytest.raises(TypeError):
                cls(**{forbidden: "You will be fine."})  # type: ignore[arg-type]
    # The exact field surface, so an added free-text slot fails here.
    assert [f.name for f in dataclasses.fields(PhraseUtterance)] == ["phrase_id"]
    assert [f.name for f in dataclasses.fields(TemplateUtterance)] == ["template_id", "topic"]
    assert [f.name for f in dataclasses.fields(AgendaUtterance)] == ["assessment_version", "index"]


def test_the_module_is_pure_stdlib():
    """§3: no FastAPI, no DB, no other app module, no threads, no timers.
    Checked from the module's own globals, not by reading the source.
    (2026-09-07: the action matcher, owner decision E3, brought `re` and
    difflib's SequenceMatcher — stdlib both, no new dependency; the
    property is unchanged.)"""
    imported_modules = {v.__name__ for v in vars(auto_mode).values()
                        if isinstance(v, types.ModuleType)}
    assert imported_modules <= {"time", "re"}
    for value in vars(auto_mode).values():
        module = getattr(value, "__module__", "") or ""
        assert not module.startswith("app.") or module == "app.auto_mode", value
        assert not module.startswith(("fastapi", "psycopg", "starlette", "threading", "asyncio")), value


# --- the pause protocol ---------------------------------------------------

@pytest.mark.parametrize("phase", sorted(LISTENING_PHASES, key=lambda p: p.value))
def test_an_alarm_pauses_from_each_listening_phase_and_resume_returns_exactly_there(phase):
    """§7: pause from GOLDEN, OPEN and CLOSED; the prior phase is stored;
    RESUME AUTO returns to exactly that phase, not to the start of the
    run and not to the next phase."""
    clock = Clock()
    c = drive_to(phase, clock)
    clock.advance(4.0)
    paused = c.urgent_alarm(ALARM)
    assert paused == Transition(phase, AutoPhase.PAUSED_URGENT, AutoEvent.URGENT_ALARM, clock.t)
    assert c.phase is AutoPhase.PAUSED_URGENT
    assert c.paused_from is phase
    assert c.pending_actions == frozenset(ALARM)
    clock.advance(11.0)
    resumed = c.acknowledge_and_resume()
    assert resumed == Transition(AutoPhase.PAUSED_URGENT, phase, AutoEvent.ACKNOWLEDGE_RESUME, clock.t)
    assert c.phase is phase
    assert c.paused_from is None
    assert c.pending_actions == frozenset()
    assert c.acknowledgements == (Acknowledgement(
        actions=frozenset(ALARM), resolution="resume", paused_from=phase,
        paused_at=clock.t - 11.0, acknowledged_at=clock.t),)


@pytest.mark.parametrize("phase", sorted(LISTENING_PHASES, key=lambda p: p.value))
def test_take_over_from_a_pause_is_terminal_for_the_auto_run(phase):
    """§7: TAKE OVER acknowledges and drops to TAKEN_OVER; from there no
    event but auto-off is legal — the doctor has the room."""
    c = drive_to(phase)
    c.urgent_alarm(ALARM)
    record = c.acknowledge_and_take_over()
    assert record.to_phase is AutoPhase.TAKEN_OVER
    assert c.phase is AutoPhase.TAKEN_OVER
    assert c.acknowledged_actions == frozenset(ALARM)
    assert c.acknowledgements[-1].resolution == "take_over"
    for event in AutoEvent:
        if event is AutoEvent.AUTO_OFF:
            continue
        with pytest.raises(AutoModeError):
            fire(c, event)
    assert c.phase is AutoPhase.TAKEN_OVER


def test_an_alarm_outside_the_listening_phases_is_illegal():
    """§7 scopes the pause to GOLDEN/OPEN/CLOSED. Anywhere else the alarm
    belongs to the CDS panel as today and the machine refuses it, so the
    wiring must consult the phase rather than fire blindly."""
    for phase in (AutoPhase.OFF, AutoPhase.DISCLOSURE, AutoPhase.INVITATION,
                  AutoPhase.HANDOVER, AutoPhase.TAKEN_OVER):
        with pytest.raises(AutoModeError):
            drive_to(phase).urgent_alarm(ALARM)


def test_a_refire_while_paused_stays_paused_and_widens_the_pending_set():
    """The session keeps listening while paused, so the CDS can re-fire
    before the doctor answers the banner. That is a recorded self-edge,
    the prior phase is kept, and the acknowledgement then covers every
    action text that fired."""
    clock = Clock()
    c = drive_to(AutoPhase.CLOSED, clock)
    c.urgent_alarm(ALARM)
    clock.advance(6.0)
    refire = c.urgent_alarm(ALARM + ("Give aspirin 300 mg now",))
    assert refire.from_phase is AutoPhase.PAUSED_URGENT
    assert refire.to_phase is AutoPhase.PAUSED_URGENT
    assert c.paused_from is AutoPhase.CLOSED
    assert c.pending_actions == frozenset(ALARM + ("Give aspirin 300 mg now",))
    c.acknowledge_and_resume()
    assert c.phase is AutoPhase.CLOSED
    assert c.acknowledged_actions == frozenset(ALARM + ("Give aspirin 300 mg now",))
    assert c.acknowledgements[-1].paused_at == clock.t - 6.0


def test_an_alarm_with_no_action_text_is_refused():
    """A pause must be attributable: an empty alarm has nothing for the
    doctor to acknowledge and nothing for the ratchet to remember."""
    c = drive_to(AutoPhase.OPEN)
    with pytest.raises(AutoModeError):
        c.urgent_alarm([])
    assert c.phase is AutoPhase.OPEN


# --- the ratchet -----------------------------------------------------------

def test_the_same_action_refiring_after_a_resume_pauses_again_and_needs_a_fresh_ack():
    """§7, the ratchet. Acknowledging an action does not make its re-fire
    quieter: after RESUME AUTO the identical text pauses again, the
    machine stays paused until the doctor acknowledges AGAIN, and both
    acknowledgements are on the record. No automatic ack-resume loop."""
    c = drive_to(AutoPhase.OPEN)
    c.urgent_alarm(ALARM)
    c.acknowledge_and_resume()
    assert c.acknowledged_actions == frozenset(ALARM)   # already acknowledged once
    second = c.urgent_alarm(ALARM)                       # the same text, verbatim
    assert second.to_phase is AutoPhase.PAUSED_URGENT
    assert c.phase is AutoPhase.PAUSED_URGENT
    assert c.pending_actions == frozenset(ALARM)
    with pytest.raises(AutoModeError):                   # a question does not slip through the pause
        c.request_question(AgendaUtterance(assessment_version=1, index=0))
    c.acknowledge_and_resume()
    assert c.phase is AutoPhase.OPEN
    assert [a.actions for a in c.acknowledgements] == [frozenset(ALARM), frozenset(ALARM)]


def test_a_different_action_after_a_resume_also_pauses():
    """The ratchet is not the only pause path — a new action text pauses
    like any first alarm, and the acknowledged set grows to include it."""
    c = drive_to(AutoPhase.CLOSED)
    c.urgent_alarm(ALARM)
    c.acknowledge_and_resume()
    other = ("Check blood glucose now",)
    assert c.urgent_alarm(other).to_phase is AutoPhase.PAUSED_URGENT
    assert c.pending_actions == frozenset(other)
    c.acknowledge_and_resume()
    assert c.acknowledged_actions == frozenset(ALARM + other)
    assert c.phase is AutoPhase.CLOSED


def test_the_acknowledged_set_survives_auto_off_within_the_session():
    """The ratchet's memory is per session, not per auto run: the review
    page shows who acknowledged what regardless of later toggling."""
    c = drive_to(AutoPhase.OPEN)
    c.urgent_alarm(ALARM)
    c.acknowledge_and_resume()
    c.auto_off()
    assert c.acknowledged_actions == frozenset(ALARM)


# --- auto off from everywhere ---------------------------------------------

@pytest.mark.parametrize("phase", list(AutoPhase))
def test_auto_off_is_legal_and_immediate_from_every_state(phase):
    """Hard rule 3: the doctor's tap can never be the thing that raises.
    From every phase — OFF itself, a live pause, the terminal states —
    auto off lands on OFF in one transition, drops any pending pause, and
    is recorded with the phase it left."""
    clock = Clock()
    c = drive_to(phase, clock)
    before = len(c.history)
    record = c.auto_off()
    assert record == Transition(phase, AutoPhase.OFF, AutoEvent.AUTO_OFF, clock.t)
    assert c.phase is AutoPhase.OFF
    assert len(c.history) == before + 1
    assert c.paused_from is None
    assert c.pending_actions == frozenset()


def test_auto_off_from_a_pause_drops_the_pause_without_recording_an_acknowledgement():
    """Turning auto off is not an acknowledgement: the alarm still stands
    in the CDS panel and the review banner, and the record must not say
    the doctor acknowledged what they only switched away from."""
    c = drive_to(AutoPhase.PAUSED_URGENT)
    c.auto_off()
    assert c.acknowledgements == ()
    assert c.acknowledged_actions == frozenset()


def test_after_auto_off_a_fresh_run_starts_from_disclosure():
    """OFF is a real state, not a dead end: enable() from it begins a new
    run at DISCLOSURE (the speech layer's disclosure lock decides whether
    the phrase is spoken again — that is not this machine's business)."""
    c = drive_to(AutoPhase.HANDOVER)
    c.auto_off()
    assert c.enable().to_phase is AutoPhase.DISCLOSURE


# --- transition records ----------------------------------------------------

def test_transition_records_carry_from_to_trigger_and_the_clock_reading():
    """§11: `auto.phase` is audited with from/to/trigger. The record is a
    frozen value carrying exactly those plus the monotonic time, and the
    trigger is the event enum whose value is the audit string."""
    clock = Clock(start=50.0)
    c = AutoModeController(clock=clock)
    clock.advance(2.5)
    record = c.enable()
    assert dataclasses.is_dataclass(record)
    assert [f.name for f in dataclasses.fields(record)] == ["from_phase", "to_phase", "trigger", "at"]
    assert (record.from_phase, record.to_phase, record.trigger, record.at) == (
        AutoPhase.OFF, AutoPhase.DISCLOSURE, AutoEvent.ENABLE, 52.5)
    assert record.trigger.value == "enable"
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.to_phase = AutoPhase.GOLDEN  # type: ignore[misc]


def test_history_keeps_every_transition_in_order_and_seconds_in_phase_follows_the_clock():
    """The controller's own history is the audit trail the wiring writes
    out; the injected clock is the only time source it reads."""
    clock = Clock()
    c = AutoModeController(clock=clock)
    c.enable()
    clock.advance(3.0)
    c.disclosure_completed()
    clock.advance(1.5)
    assert c.seconds_in_phase() == 1.5
    c.invitation_completed()
    clock.advance(90.0)
    assert c.seconds_in_phase() == 90.0
    c.golden_timer_elapsed()
    assert [(t.from_phase, t.to_phase, t.trigger) for t in c.history] == [
        (AutoPhase.OFF, AutoPhase.DISCLOSURE, AutoEvent.ENABLE),
        (AutoPhase.DISCLOSURE, AutoPhase.INVITATION, AutoEvent.DISCLOSURE_COMPLETED),
        (AutoPhase.INVITATION, AutoPhase.GOLDEN, AutoEvent.INVITATION_COMPLETED),
        (AutoPhase.GOLDEN, AutoPhase.OPEN, AutoEvent.GOLDEN_TIMER_ELAPSED),
    ]
    assert [t.at for t in c.history] == [1000.0, 1003.0, 1004.5, 1094.5]
    assert c.seconds_in_phase() == 0.0


# --------------------------------------------------------------------------
# The ratchet's notion of "the same action" (owner decision 2026-09-07, E3)

ADMIT = "Consider hospital admission"
REFER = "Immediate referral to hospital"
SPECIALIST = "Same-day specialist referral"


def test_normalisation_strips_case_punctuation_whitespace_and_the_stop_words():
    assert auto_mode.normalise_action("  Bedside ECG, now!  ") == frozenset({"ecg"})
    assert auto_mode.normalise_action("Consider hospital admission") == frozenset({"hospital", "admission"})
    assert auto_mode.normalise_action("Same-day specialist referral") == frozenset({"specialist", "referral"})
    assert auto_mode.normalise_action("") == frozenset()


def test_the_485_rewordings_of_the_hospital_action_match_at_the_default_threshold():
    """The three wordings the CDS produced in 485, each against the one
    before it: the same decision in new words scores at or above 0.6."""
    assert auto_mode.action_similarity(ADMIT, REFER) >= 0.6
    assert auto_mode.action_similarity(REFER, SPECIALIST) >= 0.6
    assert auto_mode.match_action(REFER, [ADMIT, "Bedside ECG"], 0.6) == (ADMIT, auto_mode.action_similarity(ADMIT, REFER))


def test_an_exact_text_scores_one_and_wins_outright():
    assert auto_mode.action_similarity("Bedside ECG", "Bedside ECG") == 1.0
    assert auto_mode.match_action("Bedside ECG", [ADMIT, "Bedside ECG"], 0.6) == ("Bedside ECG", 1.0)
    assert auto_mode.action_similarity("Bedside ECG now", "12-lead ECG") == 1.0, "same tokens after the stop words"


def test_a_genuinely_new_action_matches_nothing():
    """No shared token, no match — letters alone never make two actions the
    same: "Bedside ECG" then "IV access", and the pilot's pairs that are
    different decisions."""
    assert auto_mode.action_similarity("Bedside ECG", "IV access") == 0.0
    assert auto_mode.match_action("IV access", ["Bedside ECG", ADMIT], 0.6) is None
    assert auto_mode.action_similarity("Bedside ECG", "Bedside glucose") == 0.0, "'bedside' is a place, not the action"
    assert auto_mode.action_similarity("Bedside ECG now", "Call 999") == 0.0
    assert auto_mode.action_similarity("", "Bedside ECG") == 0.0


def test_the_threshold_is_the_callers_and_bounds_the_match():
    score = auto_mode.action_similarity(ADMIT, REFER)
    assert 0.6 <= score < 1.0
    assert auto_mode.match_action(REFER, [ADMIT], score) == (ADMIT, score)
    assert auto_mode.match_action(REFER, [ADMIT], round(score + 0.01, 3)) is None


def test_the_matcher_is_pure_and_symmetric():
    assert auto_mode.action_similarity(ADMIT, REFER) == auto_mode.action_similarity(REFER, ADMIT)
    assert auto_mode.action_similarity(ADMIT, REFER) == auto_mode.action_similarity(ADMIT, REFER)
