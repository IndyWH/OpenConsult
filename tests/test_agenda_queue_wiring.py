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

# Long enough that one injected line clears CDS_MIN_NEW_CHARS on its own.
FILLER = "The patient describes the pain in detail, at length, over several sentences here. " * 3


def land_pass(s, *lines: str, tries: int = 60):
    """Let a CDS pass run on transcript growth — NOT one auto mode asked
    for — and wait for it to land. The harness's commit_transcript moves
    the sent-length marker so passes never fire from it; here the
    marker is left behind, as live transcription leaves it."""
    before = s.entry["agenda"].current_version
    def _inject():
        s.entry["transcript_parts"].extend(lines or (FILLER,))
    s.ws.portal.call(_inject)
    for _ in range(tries):
        s.probe()
        if s.entry["agenda"].current_version > before:
            return s.entry["agenda"].current_version
        time.sleep(0.03)
    raise AssertionError("no CDS pass landed")


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
        version = land_pass(s)
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
        land_pass(s)
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
        land_pass(s)
        v2 = land_pass(s)
        assert pending_texts(s) == [Q_SLEEP, Q_ONSET, Q_TABLETS, Q_RADIATE]
        radiate = s.auto["queue"].find(Q_RADIATE)
        assert radiate.absent_count == 1 and radiate.status is ItemStatus.PENDING
        _stop(s)
    rows = _audit("auto.queue_merged", s.session_id)
    assert [r["version"] for r in rows] == [v2 - 1, v2]
    assert (rows[1]["added"], rows[1]["refreshed"], rows[1]["discarded"],
            rows[1]["dropped_absent"], rows[1]["capped"]) == (2, 1, 0, 0, 0)
    assert rows[1]["pending"] == 4
