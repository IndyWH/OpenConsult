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

import time

import pytest  # noqa: F401

from app import main as appmain
from app.agenda_queue import ItemStatus
from app.cds import OfficerVerdict
from auto_harness import (  # noqa: F401 - the fixture is used by name
    Q_ONSET, Q_RADIATE, Q_SLEEP, Q_TABLETS, _audit, _stop, gate, live, needs_db)

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
        # Same event-loop turn as the turn end: the plan task already exists
        # and the pass has been requested but has not landed.
        assert s.auto["turn_ended"] is True
        assert s.auto["plan_task"] is not None, "planned in _end_turn, not after on_fresh_agenda"
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
    after the golden exit's one."""
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


def test_empty_rule_one_nothing_pending_and_a_pass_running_gives_one_bridge_and_waits(gate, monkeypatch):
    """Spec §5: the queue is empty after the answer (its one item was just
    answered) and the post-answer pass is running → at most one "go on"
    and no question until the merge lands; then the head is asked."""
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
        monkeypatch.setattr(appmain, "AUTO_ENCOURAGER_QUIET_S", 1.75)
        s.turn_end("Tuesday night.")
        assert not s.auto["queue"].has_pending
        assert s.auto["plan_task"] is None or s.auto["plan_task"].done(), "nothing being prepared"
        assert s.auto["revision"] in ("requested", "running")
        heard = []
        q = 3.3
        for _ in range(5):
            q += 0.8
            s.quiet(q)
            heard += [m for m in s.probe() if m.get("type") == "auto_speak"]
            for m in heard:
                if m["ref_id"] == "go_on" and s.entry["pending_utterance"]:
                    s.play(m["utterance_id"])
        assert [m["ref_id"] for m in heard] == ["go_on"], "one bridge, no question, while the pass runs"
        s.ws.portal.call(gate_event.set)
        s.commit_transcript("still here")
        s.quiet(3.4)
        s.probe()
        nxt = s.wait_for_auto_speak()
        assert nxt["text"] == "Can you tell me more about your sleep?"
        _stop(s)


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
    handover, and anything-else is not spoken twice."""
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
        _stop(s)
    merges = _audit("auto.queue_merged", s.session_id)
    assert [(m["version"], m["discarded"], m["pending"]) for m in merges] == [
        (1, 0, 1), (2, 1, 0), (3, 1, 1), (4, 2, 0)]
    assert len(_audit("auto.handover", s.session_id)) == 1


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
    the queue never merged (landed before the machine was on). It is
    recorded asked (auto.queue_asked_externally, by=tap), its answer
    marks it answered, and when the next pass proposes the same words
    they are discarded at the merge — never asked by Alba."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_NAUSEA], [Q_ONSET], [Q_NAUSEA, Q_SLEEP]]
    with live(gate) as s:
        queue = s.auto["queue"]
        s.disclose()
        stale = s.land_pass()                          # v1 lands with the machine OFF: not merged
        assert queue.items == ()
        s.toggle(True)
        from auto_harness import _collect_until, _until
        seen = _collect_until(s.ws, {"auto_toggled"})
        invitation = next(m for m in seen if m.get("type") == "auto_speak")
        s.play(invitation["utterance_id"])
        s.probe()
        assert s.phase.value == "golden"
        s.to_open()                                    # v2 [Q_ONSET] merges
        first = s.wait_for_auto_speak()
        s.play(first["utterance_id"])
        import json
        s.ws.send_text(json.dumps({"type": "speak", "ref": {
            "kind": "cds_question", "assessment_version": stale, "index": 0}}))   # Q_NAUSEA, never merged
        ready = _until(s.ws, {"speak_ready"})
        recorded = queue.find(Q_NAUSEA)
        assert recorded is not None and recorded.status is ItemStatus.ASKED
        assert recorded.rank == -1 and not queue.has_pending
        s.play(ready["utterance_id"])
        s.turn_end("No, not sick at all.")
        assert recorded.status is ItemStatus.ANSWERED
        nxt = s.wait_for_auto_speak()                  # v3 proposes Q_NAUSEA again: discarded
        assert nxt["text"] == "Can you tell me more about your sleep?"
        _stop(s)
    ext = _audit("auto.queue_asked_externally", s.session_id)
    assert len(ext) == 1 and ext[0]["text"] == Q_NAUSEA and ext[0]["by"] == "tap"
    assert ext[0]["version"] == stale and ext[0]["utterance_id"] == ready["utterance_id"]
    merges = _audit("auto.queue_merged", s.session_id)
    assert merges[-1]["version"] == 3 and merges[-1]["discarded"] == 1
    assert merges[-1]["discarded_items"][0]["text"] == Q_NAUSEA
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
