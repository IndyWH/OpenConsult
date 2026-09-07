"""The standing question queue — the properties AGENDA_QUEUE_SPEC.md §2
pins, each test's docstring naming its property.

Slice 1 of seven (spec §9): the pure module, unwired and inert. These
tests drive `app.agenda_queue.AgendaQueue` with a counter clock and no
session; the wiring (slice 2), the re-ranker call (slice 3) and the
panel (slice 4) are tested when they land.
"""

from __future__ import annotations

import types

import pytest

from app import agenda_queue
from app.agenda_queue import (DEFAULT_ABSENT_PASSES, DEFAULT_QUEUE_MAX,
                              AgendaQueue, AgendaQueueError, ItemStatus,
                              question_key)


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        self.now += 1.0
        return self.now


def make(**kw) -> AgendaQueue:
    return AgendaQueue(clock=Clock(), **kw)


RISK = "Do you have any other risk factors (e.g., diabetes, high cholesterol)?"
RISK_REWORDED = "Do you have any other risk factors, e.g. diabetes or high cholesterol?"
DURATION = "How long has the chest pain lasted?"
BREATH = "Have you had any shortness of breath?"
NAUSEA = "Have you felt sick or vomited?"


def ids(items) -> list[str]:
    return [i.id for i in items]


# --- the guarantee ---------------------------------------------------------

def test_an_asked_question_never_re_enters_on_any_later_merge():
    """§2, the guarantee: a new-pass question matching an ASKED item is
    discarded — whatever the pass says, on every later pass — and the
    discard is counted in the merge event."""
    q = make()
    q.merge(1, [RISK, DURATION])
    asked = q.consume()["id"]
    assert q.get(asked).status is ItemStatus.ASKED
    for version in (2, 3, 4, 5):
        (merged, *rest) = q.merge(version, [RISK, DURATION, BREATH])
        assert merged["discarded"] == 1
        assert merged["discarded_items"][0]["id"] == asked
        assert asked not in ids(q.pending)
        assert q.get(asked).status is ItemStatus.ASKED
    # And the text is not silently re-added as a second item either.
    assert sum(1 for i in q.items if i.key == question_key(RISK)) == 1


def test_an_answered_question_never_re_enters_on_any_later_merge():
    """§2, the guarantee: the same for an ANSWERED item — answered is
    terminal, and the pass cannot re-open it."""
    q = make()
    q.merge(1, [RISK, DURATION])
    asked = q.consume()["id"]
    q.answered(asked)
    for version in (2, 3, 4):
        merged = q.merge(version, [RISK])[0]
        assert merged["discarded"] == 1 and merged["added"] == 0
        assert q.get(asked).status is ItemStatus.ANSWERED
        assert not q.has_pending or asked not in ids(q.pending)


def test_the_486_case_the_risk_factors_question_is_discarded_after_being_answered():
    """Consultation 486: the CDS kept the risk-factors question at the top
    of every pass after the patient had answered it (smoking, blood
    pressure, family history — the model read its own parenthetical
    literally) and it was asked twice. With the queue: asked, answered,
    then proposed again — reworded, with different punctuation — on the
    next three passes, it is discarded each time and the head moves on."""
    q = make()
    q.merge(1, [RISK, DURATION, BREATH])
    ask = q.consume()
    assert ask["text"] == RISK
    q.answered(ask["id"])
    for version in (2, 3, 4):
        merged = q.merge(version, [RISK_REWORDED, DURATION, BREATH])[0]
        assert merged["discarded"] == 1
        assert merged["discarded_items"][0]["status"] == "answered"
        assert q.head is not None and q.head.text == DURATION
    assert [i.status for i in q.items if i.text == RISK] == [ItemStatus.ANSWERED]
    assert RISK_REWORDED not in [i.text for i in q.items]


# --- merge ------------------------------------------------------------------

def test_merge_has_exactly_three_outcomes_refresh_discard_append():
    """§2: a question matching a PENDING item refreshes it (last_seen,
    absent_count reset, same id), one matching an asked item is
    discarded, and one matching nothing is appended with this pass as
    its first_version."""
    q = make()
    q.merge(1, [RISK, DURATION])
    asked = q.consume()["id"]                     # RISK asked
    duration = q.get("q2")
    merged = q.merge(2, [RISK, DURATION, BREATH])[0]
    assert (merged["added"], merged["refreshed"], merged["discarded"]) == (1, 1, 1)
    assert duration.last_seen_version == 2 and duration.first_version == 1
    assert duration.absent_count == 0
    breath = q.get(merged["added_ids"][0])
    assert breath.text == BREATH and breath.first_version == 2
    assert q.get(asked).status is ItemStatus.ASKED


def test_a_pending_item_survives_one_absent_pass_and_is_dropped_after_three():
    """D-A: absence from one pass is weak evidence — the item stays, with
    absent_count 1; absence from AUTO_QUEUE_ABSENT_PASSES (3) consecutive
    passes drops it, audited queue_dropped_absent; a mention in between
    resets the count."""
    q = make()
    q.merge(1, [RISK, DURATION])
    duration = q.get("q2")
    assert DEFAULT_ABSENT_PASSES == 3
    q.merge(2, [RISK])
    assert duration.pending and duration.absent_count == 1
    q.merge(3, [RISK, DURATION])                  # mentioned again: reset
    assert duration.absent_count == 0
    q.merge(4, [RISK])
    q.merge(5, [RISK])
    assert duration.pending and duration.absent_count == 2
    events = q.merge(6, [RISK])
    assert duration.status is ItemStatus.DROPPED and duration.drop_reason == "absent"
    assert duration.absent_count == 3
    dropped = [e for e in events if e.kind == "queue_dropped_absent"]
    assert [e["id"] for e in dropped] == ["q2"]
    assert events[0]["dropped_absent"] == 1
    assert ids(q.pending) == ["q1"]


def test_absent_passes_is_configurable():
    """D-A's three is owner-tunable: with absent_passes=1 a single absence
    drops."""
    q = make(absent_passes=1)
    q.merge(1, [RISK, DURATION])
    events = q.merge(2, [RISK])
    assert q.get("q2").status is ItemStatus.DROPPED
    assert events[1].kind == "queue_dropped_absent"


def test_matching_is_exact_equality_after_normalisation_not_similarity():
    """The slice-3 rule (F4): two questions match only when their E3
    token sets are EQUAL. Punctuation, case and stop words do not
    separate them; a different question on the same topic does."""
    q = make()
    q.merge(1, [RISK])
    merged = q.merge(2, [RISK_REWORDED, "Do you have any risk factors like diabetes?"])[0]
    assert merged["refreshed"] == 1 and merged["added"] == 1
    assert q.get("q1").text == RISK               # the first wording is kept


def test_a_question_repeated_within_one_pass_counts_once():
    """§2: a pass that lists the same question twice adds one item and
    reports the duplicate."""
    q = make()
    merged = q.merge(1, [RISK, RISK_REWORDED, DURATION])[0]
    assert merged["added"] == 2 and merged["duplicates"] == 1


def test_a_question_of_only_stop_words_still_has_an_identity():
    """The E3 normaliser strips stop words; a question made only of them
    must not collapse to the empty key (which would match every other
    such question and nothing at all in match_action)."""
    assert question_key("Do the same now?") == frozenset({"do", "the", "same", "now"})
    assert question_key("Do the same now?") != question_key("Check today?")


def test_a_dropped_item_is_a_fresh_proposal_if_a_pass_raises_it_again():
    """§2 names three outcomes and none for DROPPED: a question the queue
    gave up on for absence re-enters as a NEW item (new id, this pass as
    first_version) — the guarantee is about asked and answered only."""
    q = make(absent_passes=1)
    q.merge(1, [RISK, DURATION])
    q.merge(2, [RISK])
    assert q.get("q2").status is ItemStatus.DROPPED
    merged = q.merge(3, [RISK, DURATION])[0]
    assert merged["added"] == 1
    new = q.get(merged["added_ids"][0])
    assert new.id != "q2" and new.text == DURATION and new.first_version == 3


# --- consume and answered ----------------------------------------------------

def test_consume_marks_the_head_asked_and_answered_marks_it_answered():
    """§2: consume() takes the head — it becomes ASKED with a timestamp
    and leaves the pending order; answered(id) makes it ANSWERED. Both
    return their event."""
    q = make()
    q.merge(1, [RISK, DURATION])
    ev = q.consume()
    assert ev.kind == "queue_consumed" and ev["by"] == "auto" and ev["rank"] == 0
    item = q.get(ev["id"])
    assert item.status is ItemStatus.ASKED and item.asked_at is not None
    assert ids(q.pending) == ["q2"] and q.get("q2").rank == 0
    ans = q.answered(item.id)
    assert ans.kind == "queue_answered" and ans["id"] == item.id
    assert item.status is ItemStatus.ANSWERED and item.answered_at > item.asked_at


def test_a_doctor_tap_consumes_the_tapped_item_not_the_head():
    """D-E: consume(item_id, by='tap') takes that pending item; the head
    stays pending and the flow continues from it."""
    q = make()
    q.merge(1, [RISK, DURATION, BREATH])
    ev = q.consume("q3", by="tap")
    assert ev["by"] == "tap" and ev["id"] == "q3" and ev["rank"] == 2
    assert ids(q.pending) == ["q1", "q2"]


def test_consume_and_answered_refuse_what_the_state_does_not_permit():
    """Raised, never swallowed: consume on nothing pending, consume of a
    non-pending id, answered of an item that was never asked."""
    q = make()
    with pytest.raises(AgendaQueueError):
        q.consume()
    q.merge(1, [RISK, DURATION])
    with pytest.raises(AgendaQueueError):
        q.consume("nope")
    with pytest.raises(AgendaQueueError):
        q.answered("q1")                         # pending, not asked
    asked = q.consume()["id"]
    with pytest.raises(AgendaQueueError):
        q.consume(asked)                         # asked, not pending
    q.answered(asked)
    with pytest.raises(AgendaQueueError):
        q.answered(asked)                        # already answered


# --- apply_rerank -----------------------------------------------------------

def test_apply_rerank_reorders_only_pending_items_and_ignores_unknown_ids():
    """§3, the no-invention guard: the re-ranker's order applies to
    pending items only; an id that is not a known pending item — a
    fabricated id, an asked item, an answered item, a dropped item — is
    IGNORED, never acted on, and every ignored id is returned in the
    event so the wiring can audit it."""
    q = make(absent_passes=1)
    q.merge(1, [RISK, DURATION, BREATH, NAUSEA])
    asked = q.consume()["id"]                    # q1 asked
    q.merge(2, [DURATION, BREATH])               # q4 dropped (absent)
    assert q.get("q4").status is ItemStatus.DROPPED
    ev = q.apply_rerank(["q3", "made-up", asked, "q4", "q2"], {"q99": "answered", asked: "answered"})
    assert ev.kind == "queue_reranked"
    assert ids(q.pending) == ["q3", "q2"]
    assert ev["order"] == ["q3", "q2"] and ev["before"] == ["q2", "q3"]
    assert set(ev["ignored"]) == {"made-up", asked, "q4", "q99"}
    assert ev["drops"] == []
    assert q.get(asked).status is ItemStatus.ASKED
    assert q.get("q4").status is ItemStatus.DROPPED
    assert [q.get(i).rank for i in ("q3", "q2")] == [0, 1]


def test_apply_rerank_drops_pending_items_with_the_reranker_reason():
    """§2/§3: a drop names a pending item and is applied with the
    re-ranker's one-word reason; an id in both lists is dropped; pending
    items the re-ranker did not mention keep their previous relative
    order after the ones it did."""
    q = make()
    q.merge(1, [RISK, DURATION, BREATH, NAUSEA])
    ev = q.apply_rerank(["q4", "q2"], {"q2": "addressed"}, ms=312.0)
    assert ids(q.pending) == ["q4", "q1", "q3"]
    assert ev["drops"] == [{"id": "q2", "text": DURATION, "reason": "addressed"}]
    assert ev["unmentioned"] == ["q1", "q3"] and ev["ignored"] == [] and ev["ms"] == 312.0
    assert q.get("q2").status is ItemStatus.DROPPED and q.get("q2").drop_reason == "addressed"


def test_apply_rerank_with_nothing_valid_changes_nothing():
    """Fail-soft's shape: an answer made only of unknown ids leaves the
    order exactly as it was and names every id as ignored."""
    q = make()
    q.merge(1, [RISK, DURATION])
    ev = q.apply_rerank(["x", "y"], ["z"])
    assert ids(q.pending) == ["q1", "q2"] and set(ev["ignored"]) == {"x", "y", "z"}


# --- the cap and the baseline order ----------------------------------------

def test_the_cap_drops_the_lowest_ranked_excess_and_audits_it():
    """D-D: at most AUTO_QUEUE_MAX (8) pending; the excess with the
    lowest rank is dropped with reason 'capped' and audited queue_capped
    naming each dropped item and its rank."""
    assert DEFAULT_QUEUE_MAX == 8
    q = make()
    q.merge(1, [DURATION, BREATH])
    texts = [f"Question number {n} about symptom {n}?" for n in range(9)]
    events = q.merge(2, texts)
    assert len(q.pending) == 8
    # The pass's nine listed items outrank the two unlisted ones; the
    # lowest ranks are the pass's ninth, then the two carried over.
    capped = [e for e in events if e.kind == "queue_capped"]
    assert len(capped) == 1
    dropped = capped[0]["dropped"]
    assert [d["rank"] for d in dropped] == [8, 9, 10]
    assert {d["id"] for d in dropped} == {"q11", "q1", "q2"}
    assert all(q.get(d["id"]).drop_reason == "capped" for d in dropped)
    assert events[0]["capped"] == 3 and events[0]["pending"] == 8
    assert [i.rank for i in q.pending] == list(range(8))


def test_the_cap_is_configurable():
    """D-D's eight is owner-tunable."""
    q = make(max_pending=2)
    events = q.merge(1, [RISK, DURATION, BREATH])
    assert ids(q.pending) == ["q1", "q2"] and events[1].kind == "queue_capped"


def test_baseline_order_is_the_latest_pass_then_previous_order_for_the_rest():
    """§2: without a re-rank, the pending order is the latest pass's own
    order for the items it listed (refreshed or new, interleaved as the
    pass put them), then the unlisted pending items in their previous
    order. Ranks follow."""
    q = make()
    q.merge(1, [RISK, DURATION, BREATH, NAUSEA])          # q1 q2 q3 q4
    q.merge(2, [NAUSEA, "Any sweating?", DURATION])       # listed: q4 q5 q2
    assert ids(q.pending) == ["q4", "q5", "q2", "q1", "q3"]
    assert [i.rank for i in q.pending] == [0, 1, 2, 3, 4]
    q.merge(3, [BREATH])
    assert ids(q.pending) == ["q3", "q4", "q5", "q2", "q1"]
    # Absence counted against the unlisted only.
    assert [q.get(i).absent_count for i in ("q3", "q4", "q5", "q2", "q1")] == [0, 1, 1, 1, 2]


def test_head_is_rank_zero_and_moves_as_the_queue_changes():
    """§5: Alba asks from the head; after a consume the next pending item
    is the head, and a merge may change the head before the next ask."""
    q = make()
    assert q.head is None and not q.has_pending
    q.merge(1, [RISK, DURATION])
    assert q.head.id == "q1"
    q.consume()
    assert q.head.id == "q2"
    q.merge(2, [BREATH, DURATION])
    assert q.head.id == "q3"


# --- topics and the panel view ------------------------------------------------

def test_topic_matching_uses_the_existing_topic_threshold_by_meaning():
    """§2: an item's topic is matched by the E3 similarity at the topic
    threshold (AUTO_TOPIC_MATCH_THRESHOLD's 0.6) — the D3 cone's identity,
    so "this chest pain" and "the pain" are one topic."""
    q = make()
    q.merge(1, [(RISK, "risk factors"), (DURATION, "this chest pain"), BREATH])
    q.set_topic("q3", "breathing")
    assert ids(q.pending_on_topic("the chest pain")) == ["q2"]
    assert ids(q.pending_on_topic("risk factors")) == ["q1"]
    assert q.pending_on_topic("headache") == ()
    # The threshold is the caller's: "chest discomfort" scores 0.516
    # against "this chest pain" — not the same topic at 0.6, the same at 0.5.
    assert q.pending_on_topic("chest discomfort") == ()
    assert ids(q.pending_on_topic("chest discomfort", threshold=0.5)) == ["q2"]


def test_the_snapshot_shows_pending_in_order_asked_answered_and_dropped():
    """§6 (for slice 4): the panel's view — pending in order, asked and
    answered listed, dropped listed separately — is JSON-ready."""
    import json
    q = make(absent_passes=1)
    q.merge(1, [RISK, DURATION, BREATH])
    asked = q.consume()["id"]
    q.merge(2, [DURATION])
    snap = q.snapshot()
    json.dumps(snap)
    assert snap["version"] == 2
    assert [i["id"] for i in snap["pending"]] == ["q2"]
    assert [i["id"] for i in snap["asked"]] == [asked]
    assert [i["id"] for i in snap["dropped"]] == ["q3"]
    assert snap["answered"] == []


# --- purity -------------------------------------------------------------------

def test_the_module_imports_nothing_outside_the_stdlib_and_the_e3_normaliser():
    """Spec §2 / the house pattern of app/auto_mode.py: stdlib only plus
    app.auto_mode's normaliser — no FastAPI, no DB, no model calls, no
    threads, no other app module. Checked from the module's globals."""
    imported_modules = {v.__name__ for v in vars(agenda_queue).values()
                        if isinstance(v, types.ModuleType)}
    assert imported_modules <= {"time", "re"}
    for name, value in vars(agenda_queue).items():
        module = getattr(value, "__module__", "") or ""
        if module.startswith("app."):
            assert module in {"app.agenda_queue", "app.auto_mode"}, (name, module)
        assert not module.startswith(("fastapi", "psycopg", "starlette",
                                      "threading", "asyncio", "httpx")), name
    from app.auto_mode import match_action, normalise_action
    assert agenda_queue.normalise_action is normalise_action
    assert agenda_queue.match_action is match_action
