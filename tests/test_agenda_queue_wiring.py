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
        second = s.wait_for_auto_speak()          # pass 2 merged: Q_RISK discarded, Q_NAUSEA new head
        assert second["text"] == "Can you tell me more about nausea?"
        assert queue.find(Q_NAUSEA).status is ItemStatus.ASKED
        assert pending_texts(s) == [Q_ONSET]
        s.play(second["utterance_id"])
        s.turn_end("No, not sick.")
        third = s.wait_for_auto_speak()           # pass 3 proposes Q_RISK a third time: discarded again
        assert third["text"] == "Can you tell me more about the chest pain?"
        assert risk.status is ItemStatus.ANSWERED
        s.play(third["utterance_id"])
        assert "asked_answered" not in s.auto and "asked_open" not in s.auto, "retired"
        _stop(s)
    consumed = _audit("auto.queue_consumed", s.session_id)
    assert [c["text"] for c in consumed] == [Q_RISK, Q_NAUSEA, Q_ONSET]
    assert all(c["by"] == "auto" for c in consumed)
    assert [c["id"] for c in consumed] == [risk.id, "q3", "q2"], "consumed by id: the planned item, not whatever is head"
    answered = _audit("auto.queue_answered", s.session_id)
    assert [a["text"] for a in answered] == [Q_RISK, Q_NAUSEA]
    merges = _audit("auto.queue_merged", s.session_id)
    assert [(m["version"], m["discarded"]) for m in merges] == [(1, 0), (2, 1), (3, 1)]
    assert all(d["text"] == Q_RISK for m in merges[1:] for d in m["discarded_items"])
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
