"""The standing question queue, wired (AGENDA_QUEUE_SPEC.md §5, §6, §9
item 2; slice 2 of 7). Slice 1 pinned the pure module in
tests/test_agenda_queue.py; these tests pin what the live flow does with
it: passes merge, the ask comes from the head, the asked-memory is the
queue's status, the empty rules, the doctor's tap, and the latency
numbers. Same harness as the question-phase tests (tests/auto_harness.py):
a live session on a real socket, a real SpeechService on a fake command,
a scripted engine standing in for MedGemma.

Every test here runs with AUTO_MODE_ENABLED forced on for the session
(the `gate` fixture); the shipped flag stays false.
"""

from __future__ import annotations

import json
import time

import pytest  # noqa: F401

from app import main as appmain
from app.agenda_queue import ItemStatus
from app.cds import OfficerVerdict
from auto_harness import (  # noqa: F401 - the fixture is used by name
    Q_ONSET, Q_RADIATE, Q_SLEEP, Q_TABLETS, _audit, _collect_until, _stop, _until, gate, live, needs_db)

pytestmark = needs_db

Q_RISK = "Do you have any other risk factors for heart disease? (e.g., diabetes, high cholesterol)"
Q_NAUSEA = "Have you felt sick or been vomiting?"

def wait_for_pass(s, count: int, tries: int = 60):
    engine = s.state.cds_engine
    for _ in range(tries):
        s.probe()
        if len(engine.updates) >= count and s.entry["agenda"].current_version >= count:
            return
        time.sleep(0.03)
    raise AssertionError(f"pass {count} did not land; {len(engine.updates)} ran")


def pending_texts(s):
    return [i.text for i in s.auto["queue"].pending]


def _toggle_on_through_the_invitation(s):
    """The tap's half of to_golden(): auto on after the disclosure was given
    by hand, the invitation played through, the machine in GOLDEN."""
    from auto_harness import _collect_until
    s.toggle(True)
    seen = _collect_until(s.ws, {"auto_toggled"})
    invitation = next(m for m in seen if m.get("type") == "auto_speak")
    s.play(invitation["utterance_id"])
    s.probe()
    assert s.phase.value == "golden"


# ==========================================================================
# Item 1: one queue per session; every pass that lands while auto mode is on merges

def test_a_pass_that_lands_while_auto_mode_is_on_merges_into_the_sessions_queue(gate):
    """Spec §2, §5: the queue is built with the session (behind the gate)
    from AUTO_QUEUE_MAX and AUTO_QUEUE_ABSENT_PASSES, and a pass landing
    while the machine is on — here in GOLDEN, on transcript growth, not
    one auto mode asked for — merges its questions in the pass's order,
    audited auto.queue_merged with the counts and the version."""
    engine = gate.cds_engine
    engine.agendas = [[Q_ONSET, Q_RADIATE]]
    with live(gate) as s:
        queue = s.auto["queue"]
        assert queue.max_pending == appmain.AUTO_QUEUE_MAX == 8
        assert queue.absent_passes == appmain.AUTO_QUEUE_ABSENT_PASSES == 3
        assert queue.topic_threshold == appmain.AUTO_TOPIC_MATCH_THRESHOLD
        s.to_golden()
        version = s.land_pass()
        assert s.phase.value == "golden", "a pass in the golden minutes: nothing asked"
        assert pending_texts(s) == [Q_ONSET, Q_RADIATE]
        assert queue.last_version == version
        _stop(s)
    rows = _audit("auto.queue_merged", s.session_id)
    assert len(rows) == 1
    assert rows[0]["version"] == version
    assert (rows[0]["added"], rows[0]["refreshed"], rows[0]["discarded"],
            rows[0]["dropped_absent"], rows[0]["capped"]) == (2, 0, 0, 0, 0)
    assert rows[0]["pending"] == 2
    enabled = _audit("auto.enabled", s.session_id)[0]
    assert enabled["thresholds"]["queue_max"] == 8
    assert enabled["thresholds"]["queue_absent_passes"] == 3


def test_a_pass_that_lands_while_auto_mode_is_off_does_not_touch_the_queue(gate):
    """With the gate up but the machine never switched on, passes land as
    they always have — the doctor's panel — and the queue is untouched:
    no items, no audit row. The queue belongs to the machine's run."""
    engine = gate.cds_engine
    engine.agendas = [[Q_ONSET, Q_RADIATE]]
    with live(gate) as s:
        s.disclose()
        assert s.phase.value == "off"
        s.land_pass()
        assert s.entry["assessment"]["questions_to_ask"] == [Q_ONSET, Q_RADIATE], "the pass landed"
        assert s.auto["queue"].items == ()
        assert s.auto["queue"].last_version is None
        _stop(s)
    assert _audit("auto.queue_merged", s.session_id) == []


def test_the_merge_row_carries_the_counts_of_a_second_pass(gate):
    """A second pass that keeps one question, drops one and adds two:
    refreshed 1, added 2, the unmentioned one counted absent (kept — D-A
    needs three), and the queue in the pass's order then the survivor."""
    engine = gate.cds_engine
    engine.agendas = [[Q_ONSET, Q_RADIATE], [Q_SLEEP, Q_ONSET, Q_TABLETS]]
    with live(gate) as s:
        s.to_golden()
        s.land_pass()
        v2 = s.land_pass()
        assert pending_texts(s) == [Q_SLEEP, Q_ONSET, Q_TABLETS, Q_RADIATE]
        radiate = s.auto["queue"].find(Q_RADIATE)
        assert radiate.absent_count == 1 and radiate.status is ItemStatus.PENDING
        _stop(s)
    rows = _audit("auto.queue_merged", s.session_id)
    assert [r["version"] for r in rows] == [v2 - 1, v2]
    assert (rows[1]["added"], rows[1]["refreshed"], rows[1]["discarded"],
            rows[1]["dropped_absent"], rows[1]["capped"]) == (2, 1, 0, 0, 0)
    assert rows[1]["pending"] == 4


# ==========================================================================
# Item 2: Alba asks from the queue, not from the agenda snapshot

def test_the_486_case_end_to_end_an_answered_question_proposed_again_is_never_planned_again(gate):
    """The 486 defect through the wiring: Q asked from the queue head and
    answered; the next pass proposes it again at the top (the model's
    literal reading of its own parenthetical); the merge discards it and
    the plan takes the new head. Consumed by id, answered at the turn
    end, the whole life on the audit trail."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.topics[Q_RISK] = "heart disease risk factors"
    engine.topics[Q_NAUSEA] = "nausea"
    engine.agendas = [[Q_RISK, Q_ONSET], [Q_RISK, Q_NAUSEA, Q_ONSET], [Q_RISK, Q_ONSET]]
    with live(gate) as s:
        queue = s.auto["queue"]
        s.to_golden()
        s.to_open()
        first = s.wait_for_auto_speak()
        assert first["text"] == "Can you tell me more about heart disease risk factors?"
        risk = queue.find(Q_RISK)
        assert risk.status is ItemStatus.ASKED and pending_texts(s) == [Q_ONSET]
        s.play(first["utterance_id"])
        s.turn_end("I smoke, and my blood pressure was high once.")
        assert risk.status is ItemStatus.ANSWERED
        second = s.wait_for_auto_speak()          # the head in hand, asked without waiting for pass 2
        assert second["text"] == "Can you tell me more about the chest pain?"
        s.play(second["utterance_id"])
        wait_for_pass(s, 2)                       # pass 2 merges mid-answer: Q_RISK discarded, Q_NAUSEA added
        assert pending_texts(s) == [Q_NAUSEA]
        assert risk.status is ItemStatus.ANSWERED
        s.turn_end("Tuesday, quite suddenly.")
        third = s.wait_for_auto_speak()
        assert third["text"] == "Can you tell me more about nausea?"
        s.play(third["utterance_id"])
        s.turn_end("No, not sick.")               # pass 3 proposes Q_RISK a third time: discarded again
        fourth = s.wait_for_auto_speak()
        assert fourth["ref_id"] == "anything_else", "nothing left that has not been asked: spent"
        assert risk.status is ItemStatus.ANSWERED
        assert "asked_answered" not in s.auto and "asked_open" not in s.auto, "retired"
        _stop(s)
    consumed = _audit("auto.queue_consumed", s.session_id)
    assert [c["text"] for c in consumed] == [Q_RISK, Q_ONSET, Q_NAUSEA]
    assert all(c["by"] == "auto" for c in consumed)
    assert [c["id"] for c in consumed] == [risk.id, "q2", "q3"], "consumed by id: the planned item"
    answered = _audit("auto.queue_answered", s.session_id)
    assert [a["text"] for a in answered] == [Q_RISK, Q_ONSET, Q_NAUSEA]
    merges = _audit("auto.queue_merged", s.session_id)
    # v4 is the nausea answer's own pass (the scripted engine repeats its
    # last agenda): both proposals already answered, discarded again.
    assert [(m["version"], m["discarded"]) for m in merges] == [(1, 0), (2, 2), (3, 2), (4, 2)]
    assert all(Q_RISK in [d["text"] for d in m["discarded_items"]] for m in merges[1:])
    assert _audit("auto.reask_suppressed", s.session_id) == [], "retired with the asked-answered list"


def test_the_f5_deliberate_re_ask_is_exempt_and_the_answer_still_marks_the_item_answered(gate, monkeypatch):
    """A question with no patient speech inside AUTO_NO_ANSWER_GRACE_S is
    re-asked once (slice 3, F5) — the same item, still ASKED, not a plan
    and not a consume; when the answer finally comes the item is
    answered once and a later pass's copy is discarded."""
    monkeypatch.setattr(appmain, "AUTO_NO_ANSWER_GRACE_S", 4.0)
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET], [Q_ONSET, Q_SLEEP]]
    with live(gate) as s:
        queue = s.auto["queue"]
        s.to_golden()
        s.to_open()
        ask = s.wait_for_auto_speak()
        s.play(ask["utterance_id"])
        item = queue.find(Q_ONSET)
        assert item.status is ItemStatus.ASKED
        s.quiet(4.2)                                   # no speech since the question: the one re-ask
        seen = s.probe()
        again = next(m for m in seen if m.get("type") == "auto_speak")
        assert again["text"] == ask["text"] and again["utterance_id"] != ask["utterance_id"]
        assert item.status is ItemStatus.ASKED, "the re-ask is not a consume"
        s.play(again["utterance_id"])
        s.turn_end("Tuesday, I think.")
        assert item.status is ItemStatus.ANSWERED
        nxt = s.wait_for_auto_speak()
        assert nxt["text"] == "Can you tell me more about your sleep?"
        _stop(s)
    assert len(_audit("auto.reask_no_answer", s.session_id)) == 1
    assert [c["text"] for c in _audit("auto.queue_consumed", s.session_id)] == [Q_ONSET, Q_SLEEP]
    assert [a["text"] for a in _audit("auto.queue_answered", s.session_id)] == [Q_ONSET]
    assert _audit("auto.queue_merged", s.session_id)[1]["discarded"] == 1


def test_a_politeness_aborted_question_goes_back_to_pending_at_its_rank_and_is_asked_again(gate):
    """The abort declined to play the question: the item is requeued at
    its rank (auto.queue_requeued), the prepared plan is kept, and at the
    next permitting quiet the same question is asked — consumed again —
    and its answer marks it answered. Asked but not heard is not asked."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET, Q_RADIATE], [Q_SLEEP]]
    with live(gate) as s:
        queue = s.auto["queue"]
        s.to_golden()
        s.to_open()
        ask = s.wait_for_auto_speak()
        item = queue.find(Q_ONSET)
        assert item.status is ItemStatus.ASKED and pending_texts(s) == [Q_RADIATE]
        s.abort(ask["utterance_id"])
        s.probe()
        assert item.status is ItemStatus.PENDING and pending_texts(s) == [Q_ONSET, Q_RADIATE], \
            "back to pending at its rank — the head"
        assert s.auto["queued"] is not None and s.auto["queued"]["item_id"] == item.id
        assert s.auto["asked_item_id"] is None
        s.turn_end("Sorry — it woke me up.")        # the resumed turn ends; no answer was awaited
        again = s.wait_for_auto_speak()
        assert again["text"] == ask["text"]
        assert item.status is ItemStatus.ASKED
        s.play(again["utterance_id"])
        s.turn_end("Tuesday night.")
        assert item.status is ItemStatus.ANSWERED
        _stop(s)
    requeued = _audit("auto.queue_requeued", s.session_id)
    assert len(requeued) == 1 and requeued[0]["id"] == item.id and requeued[0]["rank"] == 0
    assert requeued[0]["utterance_id"] == ask["utterance_id"]
    consumed = _audit("auto.queue_consumed", s.session_id)
    assert [c["id"] for c in consumed] == [item.id, item.id], "consumed twice: once per issue"
    assert [a["id"] for a in _audit("auto.queue_answered", s.session_id)] == [item.id]


# ==========================================================================
# Item 3: asking does not wait for the pass (spec §5); the empty rules; D-C (a)

def test_with_a_pending_item_the_next_ask_is_planned_at_the_turn_end_before_the_pass_lands(gate):
    """The point of the queue. The answer's turn end requests the pass
    (strict) AND plans the next ask from the head in the same call — the
    plan exists the moment the turn end has been judged, while the pass
    is still held — and the question is issued with the pass still in
    flight. 486: 27.7 s of that gap was the pass."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET, Q_SLEEP, Q_TABLETS], [Q_NAUSEA]]
    with live(gate) as s:
        s.to_golden()
        s.to_open()
        first = s.wait_for_auto_speak()
        assert first["text"] == "Can you tell me more about the chest pain?"
        s.play(first["utterance_id"])
        gate_event = s.ws.portal.call(lambda: __import__("asyncio").Event())
        engine.gate_event = gate_event                  # hold every pass from here
        topic_calls_before = len(engine.topic_calls)
        passes_before = len(engine.updates)
        s.turn_end("Tuesday night, quite suddenly.")   # the answer's turn end, in this probe
        # Same event-loop turn as the turn end: the ask is under way — since
        # slice 3 its first step is the re-rank task, the plan following its
        # verdict — and the pass has been requested but has not landed.
        assert s.auto["turn_ended"] is True
        assert s.auto["plan_task"] is not None or s.auto["rerank_task"] is not None, \
            "under way in _end_turn, not after on_fresh_agenda"
        assert s.auto["revision"] in ("requested", "running"), "the full pass is still requested (D-C a)"
        assert len(engine.updates) == passes_before, "the pass has not landed"
        nxt = s.wait_for_auto_speak()
        assert nxt["text"] == "Can you tell me more about your sleep?", "the head, asked with the pass in flight"
        assert len(engine.updates) == passes_before, "still in flight"
        assert len(engine.topic_calls) == topic_calls_before + 1
        assert s.auto["revision"] == "running"
        s.play(nxt["utterance_id"])
        s.ws.portal.call(gate_event.set)               # the pass lands now, mid-answer
        wait_for_pass(s, passes_before + 1)
        assert pending_texts(s) == [Q_NAUSEA, Q_TABLETS], "merged: the new pass first, the survivor after"
        assert s.auto["queued"] is None, "nothing planned mid-answer: the turn end plans from the head"
        s.turn_end("Badly.")
        third = s.wait_for_auto_speak()
        assert third["text"] == "Can you tell me more about nausea?" or third["text"] == Q_NAUSEA
        _stop(s)
    consumed = _audit("auto.queue_consumed", s.session_id)
    merges = _audit("auto.queue_merged", s.session_id)
    assert [c["text"] for c in consumed][:2] == [Q_ONSET, Q_SLEEP]
    assert len(merges) == 3 and merges[1]["version"] == 2


def test_under_the_queue_exactly_one_full_pass_runs_per_answer(gate):
    """D-C option (a), pinned: with AUTO_STRICT_REVISE=true a full pass is
    requested on every answered turn end even though the ask never waits
    for it — so the urgency check (its own call inside the pass) runs
    exactly as often as before the queue. Three answers → three passes
    after the golden exit's one. Extended in slice 3: the re-ranker runs
    once per answer beside it and changes neither count. Extended
    2026-09-09 (owner decision, pilot 489/490 G4: short calls before the
    pass): at every answer the re-ranker and then the topic call reach the
    engine BEFORE the pass is launched, and the urgency check still runs
    exactly once per answer — the hold delays the pass, it never drops it."""
    assert appmain.AUTO_STRICT_REVISE is True
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET, Q_SLEEP, Q_TABLETS, Q_RADIATE, Q_NAUSEA]]
    with live(gate) as s:
        s.to_golden()
        s.to_open()
        ask = s.wait_for_auto_speak()
        wait_for_pass(s, 1)
        for answer in ("Tuesday.", "Badly.", "Sometimes."):
            passes_before = len(engine.updates)
            s.play(ask["utterance_id"])
            s.turn_end(answer)
            ask = s.wait_for_auto_speak()
            wait_for_pass(s, passes_before + 1)
            assert len(engine.updates) == passes_before + 1, "one full pass per answer, no more, no fewer"
        _stop(s)
    turn_ends = [t for t in _audit("auto.turn_ended", s.session_id) if t["answer"]]
    assert len(turn_ends) == 3
    assert len(engine.updates) == 4
    assert len(engine.rerank_calls) == 3, "one re-rank per answer, none at the golden exit"
    assert engine.rerank_during_pass == [False, False, False]
    # The order at the slot (G4): the exit's pass first (nothing pending
    # at the exit, so no short call held it) and its merge's topic call,
    # then every answer is re-rank → topic → topic back → pass, three times.
    assert engine.order == (["pass", "topic", "topic_done"]
                            + ["rerank", "topic", "topic_done", "pass"] * 3), engine.order
    calls = _audit("model.call", s.session_id)
    assert [c["kind"] for c in calls if c["kind"] == "rerank"] == ["rerank"] * 3
    assert [c["kind"] for c in calls if c["kind"] == "pass"] == ["pass"] * 4, "every pass is a row too"
    assert all(c["pass_in_flight"] is False and c["outcome"] == "ok" for c in calls)
    # (The scripted short calls return inside one yield, so no pass was
    # actually held here — auto.pass_held is written only for a real hold;
    # the held case is pinned by test_the_topic_call_returns_before_the_pass_is_launched.)


def test_empty_rule_one_nothing_pending_and_a_pass_running_says_let_me_think_once_and_a_non_empty_merge_asks(gate):
    """Spec §5, as the owner restated it 2026-09-09: the queue is empty
    after the answer (its one item was just answered) and the post-answer
    pass is running → "Let me think for a moment." once and no question
    until the merge lands; the merge adds a pending item → ask from the
    head. REPINNED 2026-09-09 (owner decision): the bridge "go on" this
    test pinned is replaced by the thinking phrase, which never resets the
    quiet clock — the question issues on the same span's next report,
    with no fresh span needed."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET], [Q_SLEEP]]
    with live(gate) as s:
        s.to_golden()
        s.to_open()
        first = s.wait_for_auto_speak()
        s.play(first["utterance_id"])
        gate_event = s.ws.portal.call(lambda: __import__("asyncio").Event())
        engine.gate_event = gate_event
        s.turn_end("Tuesday night.")
        assert not s.auto["queue"].has_pending
        assert s.auto["plan_task"] is None or s.auto["plan_task"].done(), "nothing being prepared"
        assert s.auto["revision"] in ("requested", "running")
        heard = []
        q = 3.3
        for _ in range(5):
            q += 0.8
            s.quiet(q)
            heard += [m for m in s.probe() if m.get("type") == "auto_speak"]   # probe plays it through
        assert [m["ref_id"] for m in heard] == ["let_me_think"], "once, no question, while the pass runs"
        s.ws.portal.call(gate_event.set)               # the merge adds Q_SLEEP
        nxt = s.wait_for_auto_speak(skip_thinking=False)
        assert nxt["text"] == "Can you tell me more about your sleep?", "asked from the head, same span"
        _stop(s)
    thinking = _audit("auto.thinking", s.session_id)
    # Two empty waits: the golden exit's (the first pass had not landed yet)
    # and the answer's — one phrase each, no more.
    assert [t["reason"] for t in thinking] == ["empty_queue", "empty_queue"]
    assert [t["pending"] for t in thinking] == [0, 0]


def test_let_me_think_is_not_spoken_when_a_question_is_ready(gate):
    """Owner decision 2026-09-09: the thinking phrase covers a wait with no
    question ready, never a question in preparation that is quick. With an
    item pending and the plan back inside the threshold, the next ask
    issues with no "Let me think" before it — the thing the bridge used
    to get wrong ("Go on." a second before a question)."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET, Q_SLEEP, Q_TABLETS]]
    with live(gate) as s:
        s.to_golden()
        s.land_pass()                                  # the queue holds items at the exit
        s.to_open()
        first = s.wait_for_auto_speak(skip_thinking=False)
        assert first["ref_id"] is None and first["text"] == "Can you tell me more about the chest pain?"
        s.play(first["utterance_id"])
        s.turn_end("Tuesday night.")
        second = s.wait_for_auto_speak(skip_thinking=False)
        assert second["ref_id"] is None and second["text"] == "Can you tell me more about your sleep?"
        _stop(s)
    assert _audit("auto.thinking", s.session_id) == []
    assert s.thinking_heard == []


def test_a_slow_preparation_speaks_let_me_think_once_and_it_neither_counts_as_asked_nor_resets_the_clock(gate, monkeypatch):
    """Owner decision 2026-09-09: when the planned question's preparation
    runs past AUTO_THINK_THRESHOLD_S after the turn end with nothing ready
    (here the topic call is held), "Let me think for a moment." is spoken
    once (reason slow_preparation), and only once however long the wait
    goes on. It is not a question: the queue is untouched (no consume, the
    planned item still pending), nothing is awaited, last_asked_text is
    the last real question, and the judged turn end stands — the question
    issues on the same span's next report once the preparation is back."""
    import asyncio
    monkeypatch.setattr(appmain, "AUTO_THINK_THRESHOLD_S", 0.2)
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET, Q_SLEEP, Q_TABLETS]]
    with live(gate) as s:
        queue = s.auto["queue"]
        _first_answer_setup(s, engine)
        topic_gate = s.ws.portal.call(asyncio.Event)
        engine.topic_gate = topic_gate                 # the preparation stalls here
        s.turn_end("Tuesday night.")
        time.sleep(0.25)                               # past the threshold with nothing ready
        heard = []
        q = 3.3
        for _ in range(4):
            q += 0.8
            s.quiet(q)
            heard += [m for m in s.probe() if m.get("type") == "auto_speak"]   # probe plays it through
            time.sleep(0.03)
        assert [m["ref_id"] for m in heard] == ["let_me_think"], "once per wait"
        assert s.auto["turn_ended"] is True, "the turn end stands: the phrase never resets the clock"
        assert s.auto["awaiting_answer"] is False and s.auto["asked_item_id"] is None
        assert s.auto["last_asked_text"] == Q_ONSET, "not a question: the last real question stands"
        assert [i.text for i in queue.pending] == [Q_SLEEP, Q_TABLETS], "the queue is untouched"
        consumed_before = len(_audit("auto.queue_consumed", s.session_id))
        s.ws.portal.call(topic_gate.set)               # the preparation returns
        nxt = s.wait_for_auto_speak(skip_thinking=False)
        assert nxt["text"] == "Can you tell me more about your sleep?", "issued on the same span"
        _stop(s)
    thinking = _audit("auto.thinking", s.session_id)
    slow = [t for t in thinking if t["reason"] == "slow_preparation"]
    assert len(slow) == 1, "once — the other row is the golden exit's empty wait"
    assert slow[0]["since_turn_end_ms"] >= 200 and slow[0]["pending"] == 2
    assert [t["reason"] for t in thinking if t["reason"] != "slow_preparation"] == ["empty_queue"]
    consumed = _audit("auto.queue_consumed", s.session_id)
    assert len(consumed) == consumed_before + 1 and consumed[-1]["text"] == Q_SLEEP
    assert all(c["text"] != "Let me think for a moment." for c in consumed)


def test_empty_rule_two_nothing_pending_and_no_pass_running_requests_a_pass(gate, monkeypatch):
    """Spec §5, discriminated with AUTO_STRICT_REVISE=false so no pass is
    requested on the answer itself: the answer empties the queue and no
    pass is running → one is requested; its merge supplies the next ask.
    And, the flag's new meaning: with an item pending, the earlier answer
    requested NO pass."""
    monkeypatch.setattr(appmain, "AUTO_STRICT_REVISE", False)
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET, Q_SLEEP], [Q_TABLETS]]
    # "your tablets" would match the opened "your sleep" at 0.636 under the
    # cone's threshold (a slice-3 matcher property, flagged in HANDOVER);
    # the topic here is chosen so this test is about the empty rule only.
    engine.topics[Q_TABLETS] = "the tablets"
    with live(gate) as s:
        s.to_golden()
        s.land_pass()                                  # pass 1 merged in the golden minutes
        s.to_open()                                    # the exit: pending → no pass requested
        first = s.wait_for_auto_speak()
        assert first["text"] == "Can you tell me more about the chest pain?"
        assert len(engine.updates) == 1 and s.auto["revision"] is None
        s.play(first["utterance_id"])
        s.turn_end("Tuesday.")                         # pending (Q_SLEEP) → planned, still no pass
        second = s.wait_for_auto_speak()
        assert second["text"] == "Can you tell me more about your sleep?"
        assert len(engine.updates) == 1, "strict off: no pass on an answer while something is pending"
        s.play(second["utterance_id"])
        s.turn_end("Badly.")                           # empties the queue, no pass running → request one
        assert s.auto["revision"] in ("requested", "running")
        third = s.wait_for_auto_speak()
        assert third["text"] == "Can you tell me more about the tablets?"
        assert len(engine.updates) == 2, "exactly the one pass the empty rule asked for"
        _stop(s)
    assert _audit("auto.enabled", s.session_id)[0]["thresholds"]["strict_revise"] is False


def test_empty_rule_three_still_empty_after_the_post_answer_merge_hands_over_with_the_refill_return(gate):
    """Spec §5, §6 as amended: the post-answer pass proposes only questions
    already asked and answered → the merge discards them all → nothing
    pending → the anything-else phrase; its answer's pass refills → back
    to the questions; the next pass empties again → the examination
    handover, and anything-else is not spoken twice. Extended 2026-09-09
    (owner decision, the empty-queue rule restated): "Let me think for a
    moment." is said once while the pass is awaited, before the anything-
    else phrase — the harness steps over it and records it."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET], [Q_ONSET], [Q_ONSET, Q_TABLETS], [Q_ONSET, Q_TABLETS]]
    with live(gate) as s:
        queue = s.auto["queue"]
        s.to_golden()
        s.to_open()
        first = s.wait_for_auto_speak()
        s.play(first["utterance_id"])
        s.turn_end("Tuesday night.")                  # pass 2: only the answered one → spent
        anything = s.wait_for_auto_speak()
        assert anything["ref_id"] == "anything_else"
        assert not queue.has_pending and queue.find(Q_ONSET).status is ItemStatus.ANSWERED
        s.play(anything["utterance_id"])
        s.turn_end("My tablets — I keep forgetting them.")   # pass 3 refills
        back = s.wait_for_auto_speak()
        assert back["text"] == "Can you tell me more about your tablets?"
        s.play(back["utterance_id"])
        s.turn_end("Most mornings.")                  # pass 4: both answered → spent again
        final = s.wait_for_auto_speak()
        assert final["ref_id"] == "examination_handover"
        s.play(final["utterance_id"])
        s.probe()
        assert s.phase.value == "handover"
        assert [t["ref_id"] for t in s.thinking_heard] == ["let_me_think"] * len(s.thinking_heard)
        assert len(s.thinking_heard) >= 1, "the machine said it was thinking before the empty merge handed over"
        _stop(s)
    merges = _audit("auto.queue_merged", s.session_id)
    assert [(m["version"], m["discarded"], m["pending"]) for m in merges] == [
        (1, 0, 1), (2, 1, 0), (3, 1, 1), (4, 2, 0)]
    assert len(_audit("auto.handover", s.session_id)) == 1
    thinking = _audit("auto.thinking", s.session_id)
    assert len(thinking) == len(s.thinking_heard) and all(t["reason"] == "empty_queue" for t in thinking)


# ==========================================================================
# Item 4: the doctor's tap and the queue (the minimum for D-E; the panel is slice 4)

def test_a_tap_on_a_pending_item_consumes_it_by_tap_and_alba_continues_from_the_new_head(gate):
    """D-E: the doctor taps a question the queue holds pending — the item
    is consumed (auto.queue_consumed by=tap), its answer marks it
    answered, and the machine's next ask is the new head. Here the tap
    displaces the machine's own queued question (the guarded tap,
    confirmed), which stays pending and is asked after."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET, Q_SLEEP, Q_TABLETS]]
    with live(gate) as s:
        queue = s.auto["queue"]
        s.to_golden()
        s.to_open()
        for _ in range(40):                          # let the machine queue its ask (Q_ONSET)
            s.probe()
            if s.auto["queued"] is not None:
                break
            time.sleep(0.03)
        assert s.auto["queued"]["question"] == Q_ONSET
        version = s.entry["agenda"].current_version
        import json
        s.ws.send_text(json.dumps({"type": "speak", "confirm_displace": True, "ref": {
            "kind": "cds_question", "assessment_version": version, "index": 2}}))   # Q_TABLETS
        from auto_harness import _until
        ready = _until(s.ws, {"speak_ready"})
        tablets = queue.find(Q_TABLETS)
        assert tablets.status is ItemStatus.ASKED, "consumed by the tap"
        assert pending_texts(s) == [Q_ONSET, Q_SLEEP], "the displaced question stays pending"
        assert s.auto["asked_item_id"] == tablets.id
        s.play(ready["utterance_id"])
        s.turn_end("Most mornings I forget.")
        nxt = s.wait_for_auto_speak()                # the answer's turn ends as the quiet grows
        assert tablets.status is ItemStatus.ANSWERED
        assert nxt["text"] == "Can you tell me more about the chest pain?", "the new head"
        _stop(s)
    consumed = _audit("auto.queue_consumed", s.session_id)
    assert [(c["text"], c["by"]) for c in consumed] == [(Q_TABLETS, "tap"), (Q_ONSET, "auto")]
    assert consumed[0]["utterance_id"] == ready["utterance_id"]
    assert [a["text"] for a in _audit("auto.queue_answered", s.session_id)] == [Q_TABLETS]
    assert _audit("auto.queue_asked_externally", s.session_id) == []


def test_a_tap_on_a_novel_question_is_recorded_asked_and_a_later_pass_proposing_it_is_discarded(gate):
    """D-E, the other half: the doctor taps a question from a panel version
    the queue never held. Since the toggle-on seed (owner decision
    2026-09-08) the CURRENT agenda is in the queue from the toggle, so the
    never-held question comes from an older version the seed did not
    take. It is recorded asked (auto.queue_asked_externally, by=tap), its
    answer marks it answered, and when the next pass proposes the same
    words they are discarded at the merge — never asked by Alba."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_NAUSEA], [Q_ONSET], [Q_SLEEP], [Q_NAUSEA, Q_SLEEP]]
    with live(gate) as s:
        queue = s.auto["queue"]
        s.disclose()
        stale = s.land_pass()                          # v1 [Q_NAUSEA], machine OFF: not merged
        current = s.land_pass()                        # v2 [Q_ONSET], OFF: the agenda the toggle seeds from
        assert queue.items == ()
        _toggle_on_through_the_invitation(s)
        assert pending_texts(s) == [Q_ONSET] and queue.find(Q_NAUSEA) is None, "v1's question was never held"
        s.to_open()
        first = s.wait_for_auto_speak()                # the seeded head, planned at the exit
        assert first["text"] == "Can you tell me more about the chest pain?"
        s.play(first["utterance_id"])
        wait_for_pass(s, 3)                            # v3 [Q_SLEEP] has landed: nothing in preparation
        import json
        from auto_harness import _until
        s.ws.send_text(json.dumps({"type": "speak", "ref": {
            "kind": "cds_question", "assessment_version": stale, "index": 0}}))   # Q_NAUSEA, never held
        ready = _until(s.ws, {"speak_ready"})
        recorded = queue.find(Q_NAUSEA)
        assert recorded is not None and recorded.status is ItemStatus.ASKED
        assert recorded.rank == -1 and pending_texts(s) == [Q_SLEEP]
        s.play(ready["utterance_id"])
        s.turn_end("No, not sick at all.")
        assert recorded.status is ItemStatus.ANSWERED
        nxt = s.wait_for_auto_speak()
        assert nxt["text"] == "Can you tell me more about your sleep?"
        wait_for_pass(s, 4)                            # v4 proposes Q_NAUSEA again: discarded
        assert recorded.status is ItemStatus.ANSWERED and queue.find(Q_NAUSEA) is recorded
        _stop(s)
    ext = _audit("auto.queue_asked_externally", s.session_id)
    assert len(ext) == 1 and ext[0]["text"] == Q_NAUSEA and ext[0]["by"] == "tap"
    assert ext[0]["version"] == stale and ext[0]["utterance_id"] == ready["utterance_id"]
    merges = _audit("auto.queue_merged", s.session_id)
    assert merges[0]["version"] == current and merges[0]["seeded"] is True
    v4 = next(m for m in merges if m["version"] == 4)
    nausea = next(d for d in v4["discarded_items"] if d["text"] == Q_NAUSEA)
    assert nausea["id"] == recorded.id and nausea["status"] == "answered"
    assert Q_NAUSEA not in [c["text"] for c in _audit("auto.queue_consumed", s.session_id)]


def test_resume_after_an_urgency_pause_asks_from_the_queue_head_the_alarm_bearing_pass_merged(gate, monkeypatch):
    """The one answer's chance, unchanged (owner decision 2026-08-17): at
    RESUME AUTO no revision is requested; the ask is the queue's head,
    which the alarm-bearing pass has already merged (it landed while the
    machine was paused — paused is on)."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET], [Q_NAUSEA, Q_SLEEP]]
    engine.topics[Q_NAUSEA] = "nausea"
    async def update(transcript, previous=None):
        engine.updates.append(transcript)
        questions = engine.agendas.pop(0) if len(engine.agendas) > 1 else engine.agendas[0]
        from auto_harness import _assessment
        assessment = _assessment(questions, reasoning=f"pass {len(engine.updates)}")
        if len(engine.updates) == 2:
            assessment["urgent_actions"] = [{"action": "Bedside ECG now", "reason": "exclude ACS"}]
        return assessment
    engine.update = update
    with live(gate) as s:
        queue = s.auto["queue"]
        s.to_golden()
        s.to_open()
        first = s.wait_for_auto_speak()
        s.play(first["utterance_id"])
        s.turn_end("Tuesday night.")                  # pass 2: the alarm
        for _ in range(40):
            if s.phase.value == "paused_urgent":
                break
            s.probe()
            time.sleep(0.02)
        assert s.phase.value == "paused_urgent"
        assert pending_texts(s) == [Q_NAUSEA, Q_SLEEP], "the alarm-bearing pass merged while paused"
        assert queue.last_version == 2
        passes = len(engine.updates)
        import json
        s.ws.send_text(json.dumps({"type": "auto_ack", "resolution": "resume"}))
        from auto_harness import _collect_until
        _collect_until(s.ws, {"auto_acknowledged"})
        assert s.auto["revision"] is None, "no revision at resume"
        assert s.auto["plan_task"] is not None, "planned from the head at once"
        s.commit_transcript("okay")
        s.quiet(3.2)
        s.probe()
        ask = s.wait_for_auto_speak()
        assert ask["text"] == "Can you tell me more about nausea?"
        assert len(engine.updates) == passes, "asked from the merged head, no new pass"
        _stop(s)
    consumed = _audit("auto.queue_consumed", s.session_id)
    assert [c["text"] for c in consumed] == [Q_ONSET, Q_NAUSEA]
    assert consumed[1]["version"] == 2


# ==========================================================================
# Item 5: the number to beat, per question, on the record

def test_every_auto_question_carries_its_turn_end_to_issue_and_turn_end_to_speech_latency(gate):
    """AGENDA_QUEUE_SPEC.md §7: on a question issued after an answered turn
    the issue's detail carries turn_end_to_issue_ms measured from the
    auto.turn_ended that permitted it, and the client's speak_started
    writes auto.question_latency with turn_end_to_speech_ms ≥ the issue
    number. Correct = non-negative, bounded by the test's own clock
    around the same interval, and consistent between the two rows."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET, Q_SLEEP]]
    with live(gate) as s:
        s.to_golden()
        s.to_open()
        first = s.wait_for_auto_speak()
        s.play(first["utterance_id"])
        t0 = time.monotonic()
        s.turn_end("Tuesday night.")
        second = s.wait_for_auto_speak()
        issued_bound_ms = (time.monotonic() - t0) * 1000
        s.play(second["utterance_id"])
        spoken_bound_ms = (time.monotonic() - t0) * 1000
        s.probe()
        cid = _stop(s)
    from auto_harness import _rows
    row = next(r for r in _rows(cid) if r["text"] == "Can you tell me more about your sleep?")
    issue_ms = row["ref_detail"]["turn_end_to_issue_ms"]
    assert 0 <= issue_ms <= issued_bound_ms
    import os, psycopg
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:     # speech.requested rows carry no session_id
        requested = conn.execute(
            "SELECT detail FROM audit_event WHERE action = 'speech.requested'"
            " AND detail->>'utterance_id' = %s", (second["utterance_id"],)).fetchall()
    assert len(requested) == 1 and requested[0][0]["ref_detail"]["turn_end_to_issue_ms"] == issue_ms
    latency = _audit("auto.question_latency", s.session_id)
    ours = [l for l in latency if l["utterance_id"] == second["utterance_id"]]
    assert len(ours) == 1
    assert ours[0]["turn_end_to_issue_ms"] == issue_ms
    assert issue_ms <= ours[0]["turn_end_to_speech_ms"] <= spoken_bound_ms
    assert ours[0]["turn_end_to_speech_ms"] == pytest.approx(
        issue_ms + ours[0]["issue_to_speech_ms"], abs=2)
    assert ours[0]["queue_item"] == "q2" and ours[0]["text"] == row["text"]
    # The first question followed the golden exit's turn end and has its own row too.
    assert any(l["utterance_id"] == first["utterance_id"] for l in latency)


# ==========================================================================
# Slice 3, item 1: the queue is seeded at toggle-on (owner decision 2026-09-08)

def test_toggle_on_with_a_non_empty_agenda_seeds_the_queue_and_the_first_ask_needs_no_pass(gate):
    """Owner decision 2026-09-08: a pass that landed while the machine was
    OFF is the doctor's panel and never merged — but at toggle-on the
    current agenda's questions are merged at once as a pass with the
    current version (auto.queue_merged, seeded=true). With every later
    pass held, the golden exit's ask comes from the seeded head: the
    first question no longer waits for the exit's own pass."""
    import asyncio
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET, Q_SLEEP]]
    with live(gate) as s:
        s.disclose()
        version = s.land_pass()                        # machine OFF: the panel only
        assert s.auto["queue"].items == ()
        gate_event = s.ws.portal.call(asyncio.Event)
        engine.gate_event = gate_event                 # hold every pass from here
        passes_before = len(engine.updates)
        _toggle_on_through_the_invitation(s)
        assert pending_texts(s) == [Q_ONSET, Q_SLEEP], "seeded at the toggle"
        assert s.auto["queue"].last_version == version
        s.to_open()                                    # the hand-back: the exit's turn end
        first = s.wait_for_auto_speak()
        assert first["text"] == "Can you tell me more about the chest pain?"
        assert len(engine.updates) == passes_before, "asked with no pass landed since the toggle"
        assert s.auto["queue"].find(Q_ONSET).status is ItemStatus.ASKED
        s.ws.portal.call(gate_event.set)
        _stop(s)
    rows = _audit("auto.queue_merged", s.session_id)
    assert rows[0]["seeded"] is True
    assert rows[0]["version"] == version and rows[0]["added"] == 2 and rows[0]["pending"] == 2
    consumed = _audit("auto.queue_consumed", s.session_id)
    assert consumed[0]["text"] == Q_ONSET and consumed[0]["version"] == version


def test_toggle_on_with_an_empty_agenda_seeds_nothing_and_the_golden_window_is_unchanged(gate):
    """Auto pressed at the very start: no agenda yet, so the seed is a
    no-op — no items, no auto.queue_merged row — and the golden window
    begins exactly as before, at the invitation's speak_ended, with
    nothing spent and the window not run."""
    with live(gate) as s:
        s.to_golden()
        assert s.auto["queue"].items == () and s.auto["queue"].last_version is None
        assert s.auto["golden_spent"] == 0.0 and s.auto["golden_window_ran"] is False
        assert s.auto["queued"] is None and s.auto["plan_task"] is None
        _stop(s)
    assert _audit("auto.queue_merged", s.session_id) == []
    phases = _audit("auto.phase", s.session_id)
    golden = [p for p in phases if p["to"] == "golden"]
    assert len(golden) == 1 and golden[0]["from"] == "invitation"
    assert golden[0]["trigger"] == "invitation_completed"


def test_toggle_off_and_on_keeps_asked_items_asked_and_the_seed_discards_them(gate):
    """The queue survives a toggle off and on as the asked-memory (slice-2
    decision, kept): the seed at the second toggle-on is a merge like any
    other, so the current agenda's copy of a question asked in the first
    run is DISCARDED, not re-added, and only the unasked question is
    pending for the new run."""
    from auto_harness import _until
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET, Q_SLEEP]]
    with live(gate) as s:
        queue = s.auto["queue"]
        s.to_golden()
        s.to_open()
        first = s.wait_for_auto_speak()
        s.play(first["utterance_id"])
        item = queue.find(Q_ONSET)
        assert item.status is ItemStatus.ASKED
        wait_for_pass(s, 1)                            # the exit's pass: v1 is [Q_ONSET, Q_SLEEP]
        s.toggle(False)
        assert _until(s.ws, {"auto_toggled"})["on"] is False
        assert s.phase.value == "off" and item.status is ItemStatus.ASKED
        s.toggle(True)                                 # disclosure given, invitation done: GOLDEN at the toggle
        assert _until(s.ws, {"auto_toggled"})["on"] is True
        assert s.phase.value == "golden"
        assert item.status is ItemStatus.ASKED, "asked stays asked across the toggle"
        assert pending_texts(s) == [Q_SLEEP]
        _stop(s)
    merges = _audit("auto.queue_merged", s.session_id)
    seeded = [m for m in merges if m.get("seeded")]
    assert len(seeded) == 1
    assert seeded[0]["version"] == 1 and seeded[0]["discarded"] == 1 and seeded[0]["refreshed"] == 1
    assert seeded[0]["discarded_items"] == [{"id": item.id, "text": Q_ONSET, "status": "asked"}]
    assert all("seeded" not in m for m in merges if m is not seeded[0])


# ==========================================================================
# Slice 3, item 4: the re-ranker wired — after each answered turn, fail-soft,
# the no-invention guard, the race with a planned item (spec §3, D-B, D-F)

from app.cds import RerankVerdict  # noqa: E402


def _first_answer_setup(s, engine):
    """GOLDEN → OPEN by a hand-back; the exit's ask (Q_ONSET, the head)
    issued and played; the exit's pass landed. The next turn end is the
    first ANSWER's — the first moment the re-ranker runs."""
    s.to_golden()
    s.to_open()
    first = s.wait_for_auto_speak()
    assert first["text"] == "Can you tell me more about the chest pain?"
    wait_for_pass(s, 1)
    s.play(first["utterance_id"])
    return first


def _probe_until(s, predicate, tries=60):
    for _ in range(tries):
        s.probe()
        if predicate():
            return
        time.sleep(0.03)
    raise AssertionError("condition not reached")


def test_a_verdict_reorders_the_pending_items_and_drops_one_with_its_reason(gate, monkeypatch):
    """Spec §3, D-B: at the answer's turn end, with no pass in flight and
    three items pending, the re-ranker is called with the pending (id,
    text) pairs and the turns since the last landed pass — here exactly
    the answer — and its verdict is applied: the named order first, the
    drop marked with the re-ranker's one-word reason, and the next ask
    planned from the NEW head. Audited auto.queue_reranked (order, drops
    with reasons, ignored, ms) and model.call (kind=rerank).

    RE-POINTED 2026-09-10 (owner decision after consultation 491: the
    re-ranker re-orders only, never drops — 0 for 7 wrong drops on the
    record): the drop path this test pins now lives behind
    AUTO_RERANK_DROPS_ENABLED, off by default, kept for evals/ and never
    deleted. The flag is turned on here; the flag-off behaviour is pinned
    by the two tests that follow the single-stale-item one."""
    monkeypatch.setattr(appmain, "AUTO_RERANK_DROPS_ENABLED", True)
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET, Q_SLEEP, Q_TABLETS, Q_RADIATE]]
    engine.rerank_verdicts = [RerankVerdict(("q4", "q2"), {"q3": "volunteered"}, elapsed_ms=41)]
    with live(gate) as s:
        queue = s.auto["queue"]
        _first_answer_setup(s, engine)
        assert pending_texts(s) == [Q_SLEEP, Q_TABLETS, Q_RADIATE]
        s.turn_end("Tuesday night, quite suddenly.")
        nxt = s.wait_for_auto_speak()
        assert nxt["text"] == Q_RADIATE, "the new head; its topic is already open, so verbatim"
        tablets = queue.get("q3")
        assert tablets.status is ItemStatus.DROPPED and tablets.drop_reason == "volunteered"
        assert queue.pending[0].id == "q2", "the verdict's order, after the consumed head"
        # The answer's own pass (the same list) may already have landed and
        # re-proposed the tablets afresh — a NEW item, the slice-1 rule.
        assert all(i.id != "q3" for i in queue.pending)
        assert len(engine.rerank_calls) == 1
        pairs, excerpt = engine.rerank_calls[0]
        assert pairs == [("q2", Q_SLEEP), ("q3", Q_TABLETS), ("q4", Q_RADIATE)]
        assert excerpt == "Tuesday night, quite suddenly.", "the turns since the last landed pass"
        _stop(s)
    rows = _audit("auto.queue_reranked", s.session_id)
    assert len(rows) == 1
    row = rows[0]
    assert row["before"] == ["q2", "q3", "q4"] and row["order"] == ["q4", "q2"]
    assert row["drops"] == [{"id": "q3", "text": Q_TABLETS, "reason": "volunteered"}]
    assert row["drops_advised"] == row["drops"] and row["drops_enabled"] is True
    assert row["ignored"] == [] and row["ms"] == 41 and row["protected"] is None
    assert row["excerpt_turns"] == 1 and row["excerpt_chars"] == len("Tuesday night, quite suddenly.")
    calls = [c for c in _audit("model.call", s.session_id) if c["kind"] == "rerank"]
    assert len(calls) == 1 and calls[0]["kind"] == "rerank" and calls[0]["outcome"] == "ok"
    assert calls[0]["pass_in_flight"] is False and calls[0]["elapsed_ms"] == 41
    assert set(calls[0]) >= {"queued_ms", "run_ms", "tokens", "outcome", "model"}
    assert _audit("auto.rerank_failed", s.session_id) == []
    assert _audit("auto.rerank_skipped", s.session_id) == []


def test_an_unknown_id_in_the_verdict_is_ignored_and_appears_in_the_row(gate):
    """The no-invention guard, through the wiring: ids the model made up
    (q8 to drop, q9 to ask) touch nothing — no item is added, resurrected
    or dropped for them — and the auto.queue_reranked row lists them as
    ignored. The known ids it named are applied as usual."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET, Q_SLEEP, Q_TABLETS, Q_RADIATE]]
    engine.rerank_verdicts = [RerankVerdict(("q9", "q3", "q2"), {"q8": "done"}, elapsed_ms=30)]
    with live(gate) as s:
        queue = s.auto["queue"]
        _first_answer_setup(s, engine)
        items_before = [i.id for i in queue.items]
        s.turn_end("Tuesday night.")
        nxt = s.wait_for_auto_speak()
        assert nxt["text"] == "Can you tell me more about your tablets?"
        assert [i.id for i in queue.items] == items_before, "nothing invented"
        assert queue.get("q8") is None and queue.get("q9") is None
        assert pending_texts(s) == [Q_SLEEP, Q_RADIATE]
        assert all(i.status is not ItemStatus.DROPPED for i in queue.items)
        _stop(s)
    row = _audit("auto.queue_reranked", s.session_id)[0]
    assert sorted(row["ignored"]) == ["q8", "q9"]
    assert row["order"] == ["q3", "q2", "q4"] and row["drops"] == []
    assert row["unmentioned"] == ["q4"]


def test_the_re_ranker_runs_with_a_pass_in_flight_and_its_row_says_so(gate, monkeypatch):
    """REPINNED 2026-09-09 (owner decision, pilot 490 G5). Slice 3 pinned
    D-F: with a full pass in flight at the answer's turn end the re-ranker
    was skipped and the ask planned from the head at once. That property
    is deliberately replaced, not weakened: under cadence (a) a pass is in
    flight at most answered turn ends, so the skip switched the re-ranker
    off exactly when it was needed — 490 asked "Do you smoke?" to a
    patient who had just said so, with the pass that knew still in flight.
    Now the re-ranker runs with the pass in flight, the plan follows its
    verdict, model.call says pass_in_flight=true, and no skip row is
    written. The attack reaches its target: the pass IS running when the
    answer ends.

    RE-POINTED 2026-09-10 (owner decision after consultation 491, re-order
    only): the verdict's drop, which this test reads as proof that the
    verdict was applied, is applied only with AUTO_RERANK_DROPS_ENABLED
    on — turned on here; what the test is about (the re-ranker running
    with a pass in flight) is unchanged."""
    import asyncio
    monkeypatch.setattr(appmain, "AUTO_RERANK_DROPS_ENABLED", True)
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET, Q_SLEEP, Q_TABLETS, Q_RADIATE]]
    engine.rerank_verdicts = [RerankVerdict(("q4", "q3"), {"q2": "volunteered"}, elapsed_ms=30)]
    with live(gate) as s:
        s.to_golden()
        s.land_pass()                                  # v1 merges in the golden minutes
        gate_event = s.ws.portal.call(asyncio.Event)
        engine.gate_event = gate_event                 # the exit's pass (v2) is held from here
        s.to_open()
        first = s.wait_for_auto_speak()
        s.play(first["utterance_id"])
        _probe_until(s, lambda: engine.pass_in_flight)
        assert len(engine.updates) == 1 and engine.pass_in_flight, "the exit's pass is in flight"
        s.turn_end("Tuesday night.")
        assert len(engine.rerank_calls) == 1, "the re-ranker runs, pass or no pass"
        nxt = s.wait_for_auto_speak()
        assert nxt["text"] == Q_RADIATE or nxt["text"].endswith("the chest pain?"), \
            "planned after the verdict: q4 first, q2 dropped — not the unreordered head"
        assert len(engine.rerank_calls) == 1 and engine.rerank_during_pass == [True]
        sleep = next(i for i in s.auto["queue"].items if i.text == Q_SLEEP)
        assert sleep.status is ItemStatus.DROPPED, "the verdict was applied with the pass in flight"
        s.ws.portal.call(gate_event.set)
        wait_for_pass(s, 2)
        _stop(s)
    assert _audit("auto.rerank_skipped", s.session_id) == [], "a pass in flight is no longer a skip"
    calls = [c for c in _audit("model.call", s.session_id) if c["kind"] == "rerank"]
    assert len(calls) == 1 and calls[0]["pass_in_flight"] is True and calls[0]["outcome"] == "ok"
    assert len(_audit("auto.queue_reranked", s.session_id)) == 1


def test_the_topic_call_returns_before_the_pass_is_launched(gate):
    """Owner decision 2026-09-09 (pilot 489/490 G4: short calls before the
    pass). On Ollama's single slot the topic call issued in the same tick
    as the pass lost to it on 9 of 10 questions. Now the pass requested at
    the answer's turn end is not launched until the re-ranker and the
    topic call have returned: with the topic call HELD the engine sees no
    pass however many ticks go by; released, the pass launches at once,
    auto.pass_held records the hold and its release, and the pass's
    model.call row carries the hold as queued_ms."""
    import asyncio
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET, Q_SLEEP, Q_TABLETS, Q_RADIATE]]
    with live(gate) as s:
        _first_answer_setup(s, engine)                 # the exit's pass (v1) has landed
        topic_gate = s.ws.portal.call(asyncio.Event)
        engine.topic_gate = topic_gate                 # hold every topic call from here
        engine.order.clear()
        passes_before = len(engine.updates)
        s.turn_end("Tuesday night.")
        assert s.auto["revision"] == "requested", "the pass is asked for at the turn end"
        for _ in range(8):                             # ticks go by: the pass waits
            s.probe()
            time.sleep(0.03)
        assert engine.order == ["rerank", "topic"], engine.order
        assert len(engine.updates) == passes_before and not engine.pass_in_flight
        assert s.auto["revision"] == "requested" and s.auto["topic_pending"] is True
        s.ws.portal.call(topic_gate.set)               # the topic call returns
        wait_for_pass(s, passes_before + 1)
        assert engine.order[:4] == ["rerank", "topic", "topic_done", "pass"], engine.order
        s.wait_for_auto_speak()
        _stop(s)
    held = _audit("auto.pass_held", s.session_id)
    assert len(held) >= 1
    row = held[-1]
    assert row["released"] == "short_calls_done" and row["hold_ms"] >= 200
    assert row["bound_s"] == appmain.AUTO_SHORT_CALLS_HOLD_S and row["pass_version"] == 2
    pass_rows = [c for c in _audit("model.call", s.session_id) if c["kind"] == "pass"]
    assert pass_rows[-1]["queued_ms"] == row["hold_ms"] and pass_rows[-1]["outcome"] == "ok"
    assert pass_rows[-1]["version"] == 2


def test_the_hold_is_bounded_a_topic_call_that_never_returns_does_not_hold_the_pass_forever(gate, monkeypatch):
    """The bound (AUTO_SHORT_CALLS_HOLD_S): the pass — and the urgency
    check inside it — is never held hostage by a short call. With the
    topic call held past the bound the pass launches anyway, and the row
    says the hold was released by the bound."""
    import asyncio
    monkeypatch.setattr(appmain, "AUTO_SHORT_CALLS_HOLD_S", 0.3)
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET, Q_SLEEP, Q_TABLETS]]
    with live(gate) as s:
        _first_answer_setup(s, engine)
        topic_gate = s.ws.portal.call(asyncio.Event)
        engine.topic_gate = topic_gate
        engine.order.clear()
        passes_before = len(engine.updates)
        s.turn_end("Tuesday night.")
        wait_for_pass(s, passes_before + 1)            # launches despite the held topic call
        assert engine.order[:3] == ["rerank", "topic", "pass"], engine.order
        assert s.auto["topic_pending"] is True, "the topic call is still out when the pass launches"
        s.ws.portal.call(topic_gate.set)
        s.wait_for_auto_speak()
        _stop(s)
    row = _audit("auto.pass_held", s.session_id)[-1]
    # hold_ms counts from the moment the due pass was first held, which is
    # a tick after the short calls began (the bound's zero), so it is a
    # little under the bound, never over it by more than a tick.
    assert row["released"] == "bound" and 0 < row["hold_ms"] <= 300 + 250 and row["bound_s"] == 0.3


def test_a_failed_call_leaves_the_order_standing_and_is_audited_with_reason_and_elapsed(gate):
    """Fail-soft (spec §3): a timed-out re-ranker changes nothing — the
    next ask is the head in the baseline order — and auto.rerank_failed
    carries the reason and elapsed_ms; model.call records the timeout."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET, Q_SLEEP, Q_TABLETS, Q_RADIATE]]
    engine.rerank_verdicts = [RerankVerdict(failed="timeout", elapsed_ms=2003, outcome="timeout")]
    with live(gate) as s:
        _first_answer_setup(s, engine)
        before = pending_texts(s)
        s.turn_end("Tuesday night.")
        nxt = s.wait_for_auto_speak()
        assert nxt["text"] == "Can you tell me more about your sleep?", "the head, order untouched"
        assert pending_texts(s) == before[1:]
        assert all(i.status is not ItemStatus.DROPPED for i in s.auto["queue"].items)
        _stop(s)
    failed = _audit("auto.rerank_failed", s.session_id)
    assert len(failed) == 1
    assert failed[0]["reason"] == "timeout" and failed[0]["elapsed_ms"] == 2003
    assert failed[0]["outcome"] == "timeout" and failed[0]["pending"] == 3
    assert _audit("auto.queue_reranked", s.session_id) == []
    calls = [c for c in _audit("model.call", s.session_id) if c["kind"] == "rerank"]
    assert len(calls) == 1 and calls[0]["outcome"] == "timeout" and calls[0]["failed"] == "timeout"


def test_a_verdict_landing_after_the_next_ask_is_planned_leaves_the_planned_item_alone(gate, monkeypatch):
    """The race (spec §3 as built): the pass requested at the same turn end
    lands while the re-ranker is still out — the merge supersedes it and
    the ask is planned from the merged head at once. When the late verdict
    arrives — reordering, and dropping the very item now planned — the
    planned item is protected: not dropped, kept first; the verdict shapes
    the rest of the queue; the row says what was protected and that the
    verdict had dropped it. The planned question is the one asked.

    REPINNED 2026-09-09 (owner decision, G4: short calls before the pass):
    the pass is now held behind the re-ranker, so it can only land
    mid-re-rank once the hold's bound has expired — the bound is shortened
    here so the race still occurs; the protection it exercises is unchanged."""
    import asyncio
    monkeypatch.setattr(appmain, "AUTO_SHORT_CALLS_HOLD_S", 0.2)
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET, Q_SLEEP, Q_TABLETS, Q_RADIATE]]
    engine.rerank_verdicts = [RerankVerdict(("q4", "q3"), {"q2": "volunteered"}, elapsed_ms=900)]
    with live(gate) as s:
        queue = s.auto["queue"]
        _first_answer_setup(s, engine)
        pass_gate = s.ws.portal.call(asyncio.Event)
        rerank_gate = s.ws.portal.call(asyncio.Event)
        engine.gate_event, engine.rerank_gate = pass_gate, rerank_gate
        s.turn_end("Tuesday night.")
        assert s.auto["rerank_task"] is not None
        assert s.auto["plan_task"] is None or s.auto["plan_task"].done()
        assert s.auto["queued"] is None, "the plan waits for the verdict"
        s.ws.portal.call(pass_gate.set)                # the pass lands first, mid-re-rank
        wait_for_pass(s, 2)
        _probe_until(s, lambda: s.auto["queued"] is not None)
        sleep = queue.find(Q_SLEEP)
        assert s.auto["queued"]["item_id"] == sleep.id, "planned from the merged head"
        assert s.auto["rerank_task"] is not None, "the verdict is still out"
        s.ws.portal.call(rerank_gate.set)              # the late verdict lands now
        _probe_until(s, lambda: s.auto["rerank_task"] is None)
        assert s.auto["queued"]["item_id"] == sleep.id and sleep.status is ItemStatus.PENDING
        assert pending_texts(s) == [Q_SLEEP, Q_RADIATE, Q_TABLETS], "protected first, the rest re-ordered"
        nxt = s.wait_for_auto_speak()
        assert nxt["text"] == "Can you tell me more about your sleep?"
        _stop(s)
    row = _audit("auto.queue_reranked", s.session_id)[0]
    assert row["protected"] == sleep.id and row["protected_dropped_by_verdict"] is True
    assert row["order"] == [sleep.id, "q4", "q3"] and row["drops"] == []
    assert _audit("auto.rerank_skipped", s.session_id) == [], "it was not in flight when the re-rank started"


def test_a_single_stale_pending_item_is_dropped_by_a_verdict_and_a_dropped_item_may_re_enter_on_a_later_pass(gate, monkeypatch):
    """REPINNED 2026-09-09 (owner decision, pilot 490 G5). Slice 3 pinned
    "one pending item: nothing to order, no call, no row". Replaced: the
    re-ranker is consulted with one pending item too, so a lone stale
    head can be dropped by a verdict — in 489/490 a single item was never
    checked six times. Here the second answer leaves one item pending;
    the verdict drops it; nothing is asked from it; the empty rule waits
    for the pass, whose merge supplies the next ask. And a re-ranker drop
    is still not the never-re-enter guarantee (slice-1 decision): a later
    pass that raises the dropped question again adds it afresh, with a
    new id.

    RE-POINTED 2026-09-10 (owner decision after consultation 491: the
    re-ranker re-orders only, never drops — in 491 exactly this drop of
    the lone head, wrong every time, emptied the queue twice at 23-27 s a
    time): the behaviour pinned here is the flag-on case,
    AUTO_RERANK_DROPS_ENABLED, kept for evals/. The flag-off case — the
    same verdict removes nothing — is pinned by the next test."""
    monkeypatch.setattr(appmain, "AUTO_RERANK_DROPS_ENABLED", True)
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET, Q_SLEEP, Q_TABLETS], [Q_SLEEP, Q_TABLETS], [Q_RADIATE],
                      [Q_RADIATE, Q_TABLETS]]
    engine.rerank_verdicts = [RerankVerdict(("q2", "q3"), {}, elapsed_ms=20),
                              RerankVerdict((), {"q3": "volunteered"}, elapsed_ms=20),
                              RerankVerdict((), {}, elapsed_ms=20)]
    with live(gate) as s:
        queue = s.auto["queue"]
        _first_answer_setup(s, engine)
        s.turn_end("Tuesday night.")                   # re-rank 1: the order kept; pass 2 refreshes both
        nxt = s.wait_for_auto_speak()
        assert nxt["text"] == "Can you tell me more about your sleep?"
        wait_for_pass(s, 2)
        s.play(nxt["utterance_id"])
        assert [i.text for i in queue.pending] == [Q_TABLETS], "one item left pending"
        s.turn_end("Badly — and my tablets, I keep forgetting them.")   # one pending: re-rank 2 drops it
        assert len(engine.rerank_calls) == 2, "consulted with a single pending item"
        assert engine.rerank_calls[1][0] == [("q3", Q_TABLETS)]
        _probe_until(s, lambda: s.auto["rerank_task"] is None)
        dropped = next(i for i in queue.items if i.text == Q_TABLETS)
        assert dropped.status is ItemStatus.DROPPED and dropped.drop_reason == "volunteered"
        assert Q_TABLETS not in [i.text for i in queue.pending], \
            "the lone stale head was dropped; nothing is asked from it (pass 3 may already have merged)"
        third = s.wait_for_auto_speak()                # the empty rule: pass 3's merge supplies it
        assert third["text"] in (Q_RADIATE, "Can you tell me more about the chest pain?")
        wait_for_pass(s, 3)
        s.play(third["utterance_id"])
        s.turn_end("No.")                              # pass 4 re-proposes Q_TABLETS
        wait_for_pass(s, 4)
        again = queue.find(Q_TABLETS)
        assert again is not None and again.id != dropped.id and again.status is ItemStatus.PENDING
        assert dropped.status is ItemStatus.DROPPED
        _stop(s)
    reranked = _audit("auto.queue_reranked", s.session_id)
    assert len(reranked) >= 2
    assert reranked[1]["before"] == ["q3"] and reranked[1]["drops"][0]["reason"] == "volunteered"
    consumed = [c["text"] for c in _audit("auto.queue_consumed", s.session_id)]
    assert Q_TABLETS not in consumed, "the stale head was never put to the patient"


def test_with_drops_off_a_single_pending_item_is_never_removed_by_a_verdict_and_is_asked(gate):
    """Owner decision 2026-09-10 (after consultation 491, the re-ranker
    0 for 7): the verdict that drops the lone pending item removes
    nothing — the item stays PENDING, is asked next, and the empty rule
    is never reached by a re-rank. The drop is on the record as
    drops_advised with its reason text; drops is empty and drops_enabled
    false. Same script as the flag-on test above: the attack reaches its
    target (the verdict names the only item, and the wiring receives
    it)."""
    assert appmain.AUTO_RERANK_DROPS_ENABLED is False, "the default"
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET, Q_SLEEP, Q_TABLETS], [Q_SLEEP, Q_TABLETS], []]   # pass 3 adds nothing
    engine.rerank_verdicts = [RerankVerdict(("q2", "q3"), {}, elapsed_ms=20),
                              RerankVerdict((), {"q3": "volunteered"}, elapsed_ms=20),
                              RerankVerdict((), {}, elapsed_ms=20)]
    with live(gate) as s:
        queue = s.auto["queue"]
        _first_answer_setup(s, engine)
        s.turn_end("Tuesday night.")
        nxt = s.wait_for_auto_speak()
        assert nxt["text"] == "Can you tell me more about your sleep?"
        wait_for_pass(s, 2)
        s.play(nxt["utterance_id"])
        assert [i.text for i in queue.pending] == [Q_TABLETS], "one item left pending"
        s.turn_end("Badly — and my tablets, I keep forgetting them.")   # re-rank 2 advises the drop
        assert len(engine.rerank_calls) == 2 and engine.rerank_calls[1][0] == [("q3", Q_TABLETS)]
        _probe_until(s, lambda: s.auto["rerank_task"] is None)
        tablets = queue.get("q3")
        assert tablets.status is ItemStatus.PENDING, "advised, not applied: still pending"
        assert tablets.drop_reason is None
        assert Q_TABLETS in [i.text for i in queue.pending], "the queue was not emptied"
        third = s.wait_for_auto_speak()
        assert third["text"] == "Can you tell me more about your tablets?", "asked from the head"
        _stop(s)
    reranked = _audit("auto.queue_reranked", s.session_id)
    assert len(reranked) >= 2
    row = reranked[1]
    assert row["before"] == ["q3"] and row["order"] == ["q3"], "unmentioned by the order: it follows"
    assert row["drops"] == [] and row["drops_enabled"] is False
    assert row["drops_advised"] == [{"id": "q3", "text": Q_TABLETS, "reason": "volunteered"}]
    assert all(i.status is not ItemStatus.DROPPED for i in queue.items)
    assert [c["text"] for c in _audit("auto.queue_consumed", s.session_id)].count(Q_TABLETS) == 1


def test_with_drops_off_a_verdict_that_drops_everything_re_orders_and_empties_nothing(gate):
    """Owner decision 2026-09-10: a re-rank can never empty the queue.
    Three pending; the verdict names one and drops the other two — the
    named one leads, the two it would drop follow in their previous
    order, every item stays pending, all three are still asked in turn,
    and the row records the two as drops_advised with no drop applied."""
    assert appmain.AUTO_RERANK_DROPS_ENABLED is False, "the default"
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET, Q_SLEEP, Q_TABLETS, Q_RADIATE]]
    engine.rerank_verdicts = [RerankVerdict(("q3",), {"q2": "addressed", "q4": "answered"},
                                            elapsed_ms=33)]
    with live(gate) as s:
        queue = s.auto["queue"]
        _first_answer_setup(s, engine)
        assert pending_texts(s) == [Q_SLEEP, Q_TABLETS, Q_RADIATE]
        s.turn_end("Tuesday night, quite suddenly.")
        nxt = s.wait_for_auto_speak()
        assert nxt["text"] == "Can you tell me more about your tablets?", "the verdict's order leads"
        _probe_until(s, lambda: s.auto["rerank_task"] is None)
        assert pending_texts(s) == [Q_SLEEP, Q_RADIATE], "nothing removed; the queue is not empty"
        assert all(i.status is not ItemStatus.DROPPED for i in queue.items)
        assert queue.get("q2").status is ItemStatus.PENDING and queue.get("q4").status is ItemStatus.PENDING
        _stop(s)
    row = _audit("auto.queue_reranked", s.session_id)[0]
    assert row["before"] == ["q2", "q3", "q4"] and row["order"] == ["q3", "q2", "q4"]
    assert row["unmentioned"] == ["q2", "q4"] and row["drops"] == [] and row["drops_enabled"] is False
    assert row["drops_advised"] == [{"id": "q2", "text": Q_SLEEP, "reason": "addressed"},
                                    {"id": "q4", "text": Q_RADIATE, "reason": "answered"}]
    assert _audit("auto.queue_dropped", s.session_id) == [], "no drop row of any kind"


# ==========================================================================
# Slice 3, item 5: GPU priority, the minimum the re-ranker needs (§7a; D-G is
# slice 6) — a re-ranker call is never issued while a full pass holds Ollama's
# single slot, and every call is on the record as model.call

MODEL_CALL_KEYS = {"session_id", "kind", "model", "queued_ms", "run_ms", "elapsed_ms",
                   "tokens", "outcome", "pass_in_flight", "at_audio_s"}


def test_every_call_is_a_model_call_row_and_a_re_rank_behind_a_held_pass_says_pass_in_flight(gate):
    """REPINNED 2026-09-09 (owner decision, pilot 490 G5). Slice 3's item 5
    pinned "a re-ranker call is never issued while a pass holds the slot"
    (by construction, through D-F's skip). Replaced: the re-ranker IS
    issued with a pass in flight — that is the moment it is needed — and
    its model.call row says so (pass_in_flight=true). What stands from
    item 5: every call is a model.call row in the §7a shape — each
    re-ranker call one row (kind=rerank), and now each full pass one row
    too (kind=pass, queued_ms = the hold behind the short calls, G4). The
    attack reaches its target: the pass was in flight when the second
    answer ended."""
    import asyncio
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET, Q_SLEEP, Q_TABLETS, Q_RADIATE, Q_NAUSEA]]
    with live(gate) as s:
        _first_answer_setup(s, engine)                 # the exit's pass (v1) has landed
        hold = s.ws.portal.call(asyncio.Event)         # unset: every pass from here is held
        engine.gate_event = hold
        s.turn_end("Tuesday.")                         # no pass in flight: re-rank 1; v2 requested
        first = s.wait_for_auto_speak()
        assert len(engine.rerank_calls) == 1
        s.play(first["utterance_id"])
        _probe_until(s, lambda: engine.pass_in_flight)
        assert engine.pass_in_flight is True, "v2 is running when the second answer ends"
        s.turn_end("Badly.")                           # a pass in flight: re-rank 2 runs anyway
        second = s.wait_for_auto_speak()
        assert len(engine.rerank_calls) == 2, "issued with the pass running (G5)"
        assert engine.pass_in_flight is True
        s.play(second["utterance_id"])
        s.ws.portal.call(hold.set)                     # the held passes land
        wait_for_pass(s, 3)
        _probe_until(s, lambda: not engine.pass_in_flight and s.auto["revision"] is None)
        s.turn_end("Sometimes.")                       # free again: re-rank 3
        s.wait_for_auto_speak()
        assert len(engine.rerank_calls) == 3
        _stop(s)
    assert engine.rerank_during_pass == [False, True, False]
    assert _audit("auto.rerank_skipped", s.session_id) == []
    calls = _audit("model.call", s.session_id)
    reranks = [c for c in calls if c["kind"] == "rerank"]
    assert len(reranks) == 3 == len(engine.rerank_calls)
    for call in reranks:
        assert set(call) == MODEL_CALL_KEYS, sorted(call)
        assert call["outcome"] == "ok"
        assert call["queued_ms"] >= 0 and call["run_ms"] == call["elapsed_ms"] == 5
        assert call["tokens"] is None, "the scripted engine reports none; Ollama's counts travel here"
    assert [c["pass_in_flight"] for c in reranks] == [False, True, False]
    passes = [c for c in calls if c["kind"] == "pass"]
    assert len(passes) == len(engine.updates) == 4
    for call in passes:
        assert set(call) == MODEL_CALL_KEYS | {"version"}, sorted(call)
        assert call["outcome"] == "ok" and call["queued_ms"] >= 0 and call["elapsed_ms"] >= 0
        assert call["run_ms"] is None and call["tokens"] is None, "the pass's own numbers are slice 6's"
    assert [c["version"] for c in passes] == [1, 2, 3, 4]


# ==========================================================================
# Pilot fix slice 4, item 7 (owner decision 2026-09-09, pilot 489/490 G6):
# the turn-end quiet rule to 3.5 s, with the evidence recorded

def test_the_fallback_fires_at_3_5_s_and_the_officer_is_asked_at_2_s(gate):
    """AUTO_EOT_FALLBACK_S 5.0 → 3.5 and AUTO_EOT_QUIET_S 3.0 → 2.0: after
    an answered question, a report at 2.1 s asks the officer (here "not
    finished"), 3.4 s ends nothing, and 3.6 s ends the turn by the quiet
    fallback with fallback_s 3.5 on the row."""
    assert (appmain.AUTO_EOT_FALLBACK_S, appmain.AUTO_EOT_QUIET_S) == (3.5, 2.0)
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(False, False)]
    engine.agendas = [[Q_ONSET, Q_SLEEP]]
    with live(gate) as s:
        s.to_golden()
        s.to_open()
        first = s.wait_for_auto_speak()
        s.play(first["utterance_id"])
        asked = len(engine.asked)
        s.commit_transcript("Tuesday night, quite suddenly.")
        s.quiet(1.9)
        s.probe()
        assert len(engine.asked) == asked, "under the officer's 2 s"
        s.quiet(2.1)
        s.probe()
        assert len(engine.asked) == asked + 1, "the officer is asked at 2 s"
        s.quiet(3.4)
        s.probe()
        assert s.auto["turn_ended"] is False, "under the 3.5 s rule"
        s.quiet(3.6)
        s.probe()
        assert s.auto["turn_ended"] is True
        _stop(s)
    ended = [t for t in _audit("auto.turn_ended", s.session_id) if t["answer"]]
    assert len(ended) == 1
    assert ended[0]["by"] == "quiet_fallback" and ended[0]["quiet_s"] == 3.6
    assert ended[0]["fallback_s"] == 3.5 and ended[0]["finished_thought"] is False


def test_the_turn_ended_row_carries_the_clients_rms_trace(gate):
    """G6: every quiet report carries the client's RMS trace (the last
    AUTO_TRACE_S seconds at ~100 ms), and the auto.turn_ended row carries
    the latest one — newest sample last — with its step, the report it
    came with and its age, so the next run can say what the ≈ 3 s of
    trailing energy after an answer is. A report without a trace leaves
    the last one standing; a session that never sent one records null."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(False, False)]
    engine.agendas = [[Q_ONSET, Q_SLEEP]]
    trace = [0.0412, 0.0388, 0.021, 0.0093, 0.0041, 0.0032, 0.0031, 0.003]
    with live(gate) as s:
        config = next(m for m in _collect_until(s.ws, {"auto_toggled"}) if m["type"] == "speech_config")
        assert config["auto"]["trace_s"] == appmain.AUTO_TRACE_S and config["auto"]["trace_step_ms"] == 100
        s.to_golden()
        s.to_open()
        first = s.wait_for_auto_speak()
        s.play(first["utterance_id"])
        s.commit_transcript("Tuesday night.")
        s.quiet(2.0, rms=0.0041, floor=0.02, trace=trace, trace_step_ms=100)
        s.probe()
        s.quiet(3.6, rms=0.003, floor=0.02)               # no trace on this one: the last stands
        s.probe()
        assert s.auto["turn_ended"] is True
        _stop(s)
    ended = [t for t in _audit("auto.turn_ended", s.session_id) if t["answer"]][0]
    assert ended["trace"] == trace and ended["trace_step_ms"] == 100
    assert ended["trace_s"] == appmain.AUTO_TRACE_S and ended["trace_quiet_s"] == 2.0
    assert ended["trace_age_ms"] >= 0 and ended["floor"] == 0.02
    exit_end = [t for t in _audit("auto.turn_ended", s.session_id) if not t["answer"]]
    assert all(t["trace"] is None for t in exit_end), "no trace was ever sent before the exit"


def test_quiet_reports_are_audited_and_rate_bounded(gate, monkeypatch):
    """G11: the client's quiet reports are on the record — quiet_s, span,
    since, rms, floor, whether the report began a span — the first of
    every span always, then at most one per AUTO_QUIET_REPORT_AUDIT_S.
    Eight reports across two spans inside a fraction of a second → two
    rows (the two span starts); with the bound at zero every report is a
    row."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(False, False)]
    engine.agendas = [[Q_ONSET]]
    with live(gate) as s:
        s.to_golden()
        s.commit_transcript("It started last week.")
        for q in (1.0, 1.5, 2.0, 2.5):                 # one span, four reports
            s.quiet(q, rms=0.004, floor=0.02, span=7)
            s.probe()
        s.commit_transcript("And then it stopped.")     # the patient speaks: a fresh span
        for q in (1.0, 1.5, 2.0, 2.5):
            s.quiet(q, rms=0.005, floor=0.02, span=8)
            s.probe()
        rows = _audit("auto.quiet_report", s.session_id)
        assert [r["fresh"] for r in rows] == [True, True], "the two span starts, nothing else inside the bound"
        assert [r["span"] for r in rows] == [7, 8] and [r["since"] for r in rows] == ["speech", "speech"]
        assert rows[0]["rms"] == 0.004 and rows[0]["floor"] == 0.02 and rows[0]["phase"] == "golden"
        monkeypatch.setattr(appmain, "AUTO_QUIET_REPORT_AUDIT_S", 0.0)
        for q in (3.0, 3.2):
            s.quiet(q, rms=0.005, floor=0.02, span=8)
            s.probe()
        rows = _audit("auto.quiet_report", s.session_id)
        assert len(rows) == 4 and [r["quiet_s"] for r in rows[-2:]] == [3.0, 3.2]
        assert rows[-1]["fresh"] is False
        _stop(s)


# ==========================================================================
# Pilot fix slice 4, item 8 (owner decision 2026-09-09, pilot 489 G3):
# a fresh quiet span is never invisible

def test_the_489_q3_shape_a_new_span_whose_first_report_equals_the_last_is_seen_and_the_answer_ends_the_turn(gate):
    """489 Q3: the question's playback ended; the reporter's span (since
    playback) reported 2.0; the patient began answering ~2 s later, so
    the NEW span's first report was 2.0 too, and the server — keying a
    fresh span on quiet_s falling — never saw it: awaiting_speech stayed
    set, no turn end came, and at 12 s the grace re-asked an answered
    question. Now the client numbers its spans and the server keys on
    the number: the equal report on a new span is seen, awaiting_speech
    clears, span_seq bumps, and the 3.5 s fallback ends the turn; the
    grace re-ask does not fire. The attack reaches its target: the two
    reports carry the same quiet_s and differ only by span."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(False, False)]
    engine.agendas = [[Q_ONSET, Q_SLEEP]]
    with live(gate) as s:
        s.to_golden()
        s.to_open()
        first = s.wait_for_auto_speak()
        s.play(first["utterance_id"])                  # the span restarts at our playback's end
        assert s.since == "playback"
        s.quiet(2.0)                                   # the playback span's report: 2.0
        s.probe()
        assert s.auto["awaiting_speech"] is True, "no patient speech yet (F5)"
        seq_before = s.auto["span_seq"]
        # The patient begins ~2 s after the playback span began: a NEW span
        # whose first report is 2.0 again. The harness plays the client:
        # activity → span + 1, since=speech; no transcript is committed yet
        # (the words are still in flight) — exactly the 489 shape.
        s.since = "speech"
        s.span += 1
        s.quiet(2.0)
        s.probe()
        assert s.auto["awaiting_speech"] is False, "the fresh span was seen: the patient has spoken"
        assert s.auto["span_seq"] == seq_before + 1
        assert s.auto["turn_ended"] is False
        s.quiet(3.6)                                   # the 3.5 s fallback ends the answer's turn
        s.probe()
        assert s.auto["turn_ended"] is True
        _stop(s)
    ended = [t for t in _audit("auto.turn_ended", s.session_id) if t["answer"]]
    assert len(ended) == 1 and ended[0]["by"] == "quiet_fallback" and ended[0]["quiet_s"] == 3.6
    assert _audit("auto.reask_no_answer", s.session_id) == [], "no grace re-ask of an answered question"
    reports = _audit("auto.quiet_report", s.session_id)
    equal = [r for r in reports if r["quiet_s"] == 2.0]
    assert len(equal) >= 2 and equal[-1]["span"] == equal[-2]["span"] + 1 and equal[-1]["fresh"] is True


def test_a_report_without_a_span_number_keeps_the_old_fresh_span_test(gate):
    """An older page sends no span: the server falls back to quiet_s
    falling below the last report — the pre-G3 rule — so nothing breaks
    and the two rules never mix within one session's reports of a kind."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(False, False)]
    engine.agendas = [[Q_ONSET, Q_SLEEP]]
    with live(gate) as s:
        s.to_golden()
        s.to_open()
        first = s.wait_for_auto_speak()
        s.play(first["utterance_id"])
        s.ws.send_text(json.dumps({"type": "quiet", "quiet_s": 2.0, "since": "playback"}))
        s.probe()
        assert s.auto["awaiting_speech"] is True
        s.ws.send_text(json.dumps({"type": "quiet", "quiet_s": 1.0, "since": "speech"}))   # falls: fresh
        s.probe()
        assert s.auto["awaiting_speech"] is False
        _stop(s)


# ==========================================================================
# Pilot fix slice 4, item 9 (owner decision 2026-09-09, pilot 489/490 G7 and G8):
# no plan is issued before its pre-synthesis has finished; the re-ask's own row

def _slow_speech(tmp_path, seconds: float):
    """A SpeechService whose synthesiser takes `seconds` to answer."""
    import secrets as _secrets
    import sys as _sys
    script = tmp_path / f"slow_tts_{_secrets.token_hex(4)}.py"
    script.write_text(
        "import sys, time, wave\n"
        "sys.stdin.buffer.read()\n"
        f"time.sleep({seconds})\n"
        "with wave.open(sys.argv[sys.argv.index('--output-file') + 1], 'wb') as w:\n"
        "    w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)\n"
        "    w.writeframes(b'\\x00\\x00' * 11025)\n")
    (tmp_path / "voice.onnx").write_bytes(b"never read")
    from app import speech as _speech
    return _speech.SpeechService(voice="test", model_path=str(tmp_path / "voice.onnx"),
                                 cache_dir=tmp_path / "slow_cache",
                                 command=f"{_sys.executable} {script} --model {{model}} --output-file {{output}}")


def test_the_issue_waits_for_the_plans_presynthesis_so_the_ask_is_a_cache_hit(gate, tmp_path):
    """G7: in 489/490 the plan was issued the moment the turn had ended
    while its pre-synthesis was still running, so the same text was
    synthesised twice and issue_to_speech_ms read 0.9–1.4 s against 24 ms
    on a cache hit. Now the issue waits for the synthesis task (bounded):
    with a 0.6 s synthesiser the question still goes out synth_ms 0 — a
    cache hit — and no fallback is audited."""
    gate.speech = _slow_speech(tmp_path, 0.6)
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET, Q_SLEEP]]
    with live(gate) as s:
        s.to_golden()
        s.to_open()
        first = s.wait_for_auto_speak()
        s.play(first["utterance_id"])
        s.turn_end("Tuesday night.")                   # the plan's synthesis starts now (0.6 s)
        nxt = s.wait_for_auto_speak()                  # the first report finds it still running
        assert nxt["text"] == "Can you tell me more about your sleep?"
        assert s.entry["pending_utterance"].synth_ms == 0, "waited for the pre-synthesis: a cache hit"
        s.play(nxt["utterance_id"])
        _stop(s)
    assert _audit("auto.presynth_fallback", s.session_id) == []
    latency = [r for r in _audit("auto.question_latency", s.session_id) if r["text"].endswith("sleep?")]
    assert latency and latency[0]["turn_end_to_issue_ms"] >= 500, "the issue instant is after the wait"


def test_past_the_bound_the_issue_falls_back_to_synthesis_at_issue_and_says_so(gate, tmp_path, monkeypatch):
    """The bound (AUTO_PRESYNTH_WAIT_S): a synthesiser slower than it does
    not hold the ask — the issue proceeds, synthesises at issue, and
    auto.presynth_fallback records the wait."""
    monkeypatch.setattr(appmain, "AUTO_PRESYNTH_WAIT_S", 0.15)
    gate.speech = _slow_speech(tmp_path, 0.8)
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET, Q_SLEEP]]
    with live(gate) as s:
        s.to_golden()
        s.to_open()
        first = s.wait_for_auto_speak()
        s.play(first["utterance_id"])
        s.turn_end("Tuesday night.")
        nxt = s.wait_for_auto_speak()
        assert nxt["text"] == "Can you tell me more about your sleep?"
        s.play(nxt["utterance_id"])
        _stop(s)
    fallback = _audit("auto.presynth_fallback", s.session_id)
    assert len(fallback) >= 1
    row = fallback[-1]
    assert row["text"] == "Can you tell me more about your sleep?" and row["kind"] == "question"
    assert 150 <= row["waited_ms"] < 800 and row["bound_s"] == 0.15


def test_the_f5_re_asks_latency_row_is_marked_reask_and_carries_no_turn_end_numbers(gate, monkeypatch):
    """G8: 489's re-ask wrote auto.question_latency against the ORIGINAL
    turn end — 43,627 ms, an artefact. Now the re-ask's row is marked
    reask=true, carries only issue_to_speech_ms (measured from the
    re-ask's own issue), and its turn-end numbers are null, so it is
    excluded from the mean by its mark; the original's row is unchanged."""
    monkeypatch.setattr(appmain, "AUTO_NO_ANSWER_GRACE_S", 6.0)
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET]]
    with live(gate) as s:
        s.to_golden()
        s.to_open()
        first = s.wait_for_auto_speak()
        s.play(first["utterance_id"])
        s.quiet(4.0)                                   # no speech since the question
        s.probe()
        s.quiet(6.2)                                   # the grace: re-asked once
        again = _until(s.ws, {"auto_speak"})
        assert again["text"] == first["text"] and again["utterance_id"] != first["utterance_id"]
        s.play(again["utterance_id"])                  # speak_started writes the row
        _stop(s)
    rows = _audit("auto.question_latency", s.session_id)
    original = next(r for r in rows if r["utterance_id"] == first["utterance_id"])
    reask = next(r for r in rows if r["utterance_id"] == again["utterance_id"])
    assert original["reask"] is False and original["turn_end_to_speech_ms"] is not None
    assert reask["reask"] is True
    assert reask["turn_end_to_issue_ms"] is None and reask["turn_end_to_speech_ms"] is None
    assert 0 <= reask["issue_to_speech_ms"] < 5000, "measured from the re-ask's own issue"
    assert len(_audit("auto.reask_no_answer", s.session_id)) == 1


# ==========================================================================
# Pilot fix slice 4, item 10 (owner decision 2026-09-09, pilot 488 G9 and G10)

def test_a_doctors_tap_in_golden_is_recorded_in_the_queue_and_answered_at_the_exit(gate):
    """G9: 488's two tapped questions in the golden minutes left the queue
    untouched (the bookkeeping ran only in the question phases), so Alba
    could have asked them again. Now a tap in GOLDEN consumes a pending
    match (by=tap) exactly as in the question phases, the golden exit
    marks it answered, and a later pass proposing it is discarded at the
    merge — never asked by the machine. A novel tapped question is
    recorded asked (add_asked) the same way. No answer is awaited in the
    golden minutes: the flow flags stay the question phases'."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET, Q_SLEEP, Q_TABLETS], [Q_ONSET, Q_SLEEP, Q_TABLETS, Q_RADIATE]]
    with live(gate) as s:
        queue = s.auto["queue"]
        s.to_golden()
        s.land_pass()                                  # v1 merges in the golden minutes
        version = s.entry["agenda"].current_version
        s.seed_agenda("Have you had this before?")     # a panel the queue never held (v2)
        s.ws.send_text(json.dumps({"type": "speak", "ref": {
            "kind": "cds_question", "assessment_version": version, "index": 1}}))   # Q_SLEEP, in GOLDEN
        ready = _until(s.ws, {"speak_ready"})
        sleep = queue.find(Q_SLEEP)
        assert sleep.status is ItemStatus.ASKED, "consumed by the tap, in GOLDEN"
        assert s.auto["awaiting_answer"] is False, "no answer is awaited in the golden minutes"
        assert s.phase.value == "golden"
        s.play(ready["utterance_id"])
        s.ws.send_text(json.dumps({"type": "speak", "ref": {
            "kind": "cds_question", "assessment_version": version + 1, "index": 0}}))   # the novel one
        ready2 = _until(s.ws, {"speak_ready"})
        novel = queue.find("Have you had this before?")
        assert novel is not None and novel.status is ItemStatus.ASKED
        s.play(ready2["utterance_id"])
        s.to_open()                                    # the exit: the tapped items' answers have ended
        assert queue.get(sleep.id).status is ItemStatus.ANSWERED
        assert queue.get(novel.id).status is ItemStatus.ANSWERED
        first = s.wait_for_auto_speak()
        assert first["text"] == "Can you tell me more about the chest pain?", "Q_ONSET, the head"
        s.play(first["utterance_id"])
        s.turn_end("Tuesday.")                         # pass 2 re-proposes Q_SLEEP: discarded
        nxt = s.wait_for_auto_speak()
        assert Q_SLEEP not in nxt["text"] and "sleep" not in nxt["text"]
        _stop(s)
    consumed = _audit("auto.queue_consumed", s.session_id)
    assert (consumed[0]["text"], consumed[0]["by"]) == (Q_SLEEP, "tap")
    assert consumed[0]["utterance_id"] == ready["utterance_id"]
    external = _audit("auto.queue_asked_externally", s.session_id)
    assert [e["text"] for e in external] == ["Have you had this before?"]
    answered = _audit("auto.queue_answered", s.session_id)
    assert [(a["text"], a["at"]) for a in answered[:2]] == [(Q_SLEEP, "golden_exit"),
                                                           ("Have you had this before?", "golden_exit")]
    merges = _audit("auto.queue_merged", s.session_id)
    assert merges[-1]["discarded"] >= 1
    assert Q_SLEEP not in [c["text"] for c in consumed[1:]], "never asked by the machine"


def test_auto_enabled_records_the_machine_browser_and_microphone(gate):
    """G10: 487–490 knew only the sound check's OUTPUT label ("MacBook Air
    Speakers"). Now the sound check records the input label too, and the
    auto.enabled row carries `client`: the user agent from the socket's
    own headers, the platform and the current input label from the
    toggle, and the output and input labels the sound check recorded."""
    from auto_harness import _client_for, _make_user
    doctor = _make_user()
    client = _client_for(doctor)
    posted = client.post("/api/speech/sound-check/result", json={
        "noise_floor_rms": 0.0031, "peak_rms": 0.22, "mean_rms": 0.07, "answer": "yes",
        "device_label": "Default - MacBook Air Speakers (Built-in)",
        "input_label": "MacBook Air Microphone (Built-in)"})
    assert posted.status_code == 200
    with live(gate, user=doctor) as s:
        s.disclose()
        s.ws.send_text(json.dumps({"type": "auto", "on": True, "client": {
            "platform": "macOS", "input_label": "MacBook Air Microphone (Built-in)"}}))
        _collect_until(s.ws, {"auto_toggled"})
        _stop(s)
    enabled = _audit("auto.enabled", s.session_id)[0]
    record = enabled["client"]
    assert record["user_agent"], "from the socket's headers, not the client's say-so"
    assert record["platform"] == "macOS"
    assert record["input_label"] == "MacBook Air Microphone (Built-in)"
    assert record["output_label"] == "Default - MacBook Air Speakers (Built-in)"
    assert record["sound_check_input_label"] == "MacBook Air Microphone (Built-in)"
    import os as _os
    import psycopg as _psycopg
    with _psycopg.connect(_os.environ["DATABASE_URL"]) as conn:
        row = conn.execute("SELECT detail FROM audit_event WHERE action = 'speech.sound_check'"
                           " AND user_id = %s ORDER BY id DESC LIMIT 1", (doctor["id"],)).fetchone()[0]
    assert row["input_label"] == "MacBook Air Microphone (Built-in)"
    assert row["device_label"] == "Default - MacBook Air Speakers (Built-in)"


def test_auto_enabled_without_a_client_block_or_sound_check_records_nulls_not_nothing(gate):
    with live(gate) as s:
        s.disclose()
        s.toggle(True)
        _collect_until(s.ws, {"auto_toggled"})
        _stop(s)
    record = _audit("auto.enabled", s.session_id)[0]["client"]
    assert set(record) == {"user_agent", "platform", "input_label", "output_label", "sound_check_input_label"}
    assert record["platform"] is None and record["input_label"] is None
    assert record["output_label"] is None and record["sound_check_input_label"] is None
