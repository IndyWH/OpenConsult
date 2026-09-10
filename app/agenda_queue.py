"""The standing question queue — pure.

AGENDA_QUEUE_SPEC.md §2 (the queue), with owner decisions D-A (absence
from three consecutive passes drops), D-D (a cap of eight pending) and
D-E (a doctor tap consumes the tapped item). Slice 1 of the build (§9)
landed this module inert; slice 2 wired it (app/main.py: one queue per
auto session, passes merge, Alba asks from the head); the re-ranker is
slice 3. AUTO_MODE_ENABLED is untouched.

WHAT THIS MODULE IS
-------------------
A plain, in-memory queue of the questions the CDS has proposed for one
session, and the rules by which passes merge into it, Alba consumes from
it, and a re-ranker's answer is applied to it. Stdlib only, plus the
existing E3 normaliser from app.auto_mode: no FastAPI, no database, no
model calls, no threads, no timers. The clock is an injected callable
returning monotonic seconds so tests control time.

THE GUARANTEE, BY CONSTRUCTION
------------------------------
Consultation 486 asked the risk-factors question twice: every pass kept
it at the top of a wholesale-replaced agenda, and the model's literal
reading of its own parenthetical kept it "unanswered". Here an item that
has been ASKED or ANSWERED is never pending again: a later pass's
question that matches one is DISCARDED at the merge, whatever the pass
says, and `apply_rerank` touches pending items only. No prompt is
involved; the status is the guarantee.

MATCHING
--------
A question matches an item when their normalised token sets are EQUAL
(the slice-3 rule for "no question is asked twice", owner decision
2026-09-07, F4): the E3 normaliser — lower-case, punctuation stripped,
the small stop-word list removed — and exact equality, not the 0.6
similarity used for actions and topics, because two questions on one
topic are legitimately different questions. Topic matching (an item's
topic against a topic string, for the D3 cone) uses the E3 similarity at
the existing topic threshold.

EVENTS
------
Every state change returns one or more `QueueEvent` records — small,
flat, ready to be audited by the wiring: `queue_merged` (added /
refreshed / discarded, version), `queue_dropped_absent`, `queue_capped`,
`queue_consumed`, `queue_asked_externally` (a doctor's tap on a question
the queue never held, recorded so it can never re-enter), `queue_requeued`
(a politeness-aborted ask back to pending at its rank), `queue_dropped`
(the wiring gave up on an item),
`queue_answered`, `queue_reranked` (with the ids the re-ranker named
that were IGNORED — the no-invention guard, §3).

NUMBERS
-------
The defaults here (cap 8, three absent passes, topic threshold 0.6)
are the spec's; the owner-tunable settings AUTO_QUEUE_MAX,
AUTO_QUEUE_ABSENT_PASSES and AUTO_TOPIC_MATCH_THRESHOLD are read by the
wiring and passed in at construction. This module reads no environment.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum

from app.auto_mode import match_action, normalise_action

__all__ = [
    "AgendaQueue",
    "AgendaQueueError",
    "AgendaItem",
    "ItemStatus",
    "QueueEvent",
    "question_key",
    "DEFAULT_QUEUE_MAX",
    "DEFAULT_ABSENT_PASSES",
    "DEFAULT_TOPIC_MATCH_THRESHOLD",
]

# Spec §8: D-D (queue cap), D-A (absent passes); the topic threshold is the
# existing AUTO_TOPIC_MATCH_THRESHOLD default.
DEFAULT_QUEUE_MAX = 8
DEFAULT_ABSENT_PASSES = 3
DEFAULT_TOPIC_MATCH_THRESHOLD = 0.6

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class AgendaQueueError(RuntimeError):
    """An operation the queue does not permit (consume from an empty
    queue, answer an item that was never asked). Raised, never swallowed:
    each is a wiring error and the place to learn of it is a test."""


class ItemStatus(str, Enum):
    PENDING = "pending"
    ASKED = "asked"
    ANSWERED = "answered"
    DROPPED = "dropped"


def question_key(text: str) -> frozenset[str]:
    """The identity a question is matched by: the E3 normaliser's token
    set. A question made only of stop words ("Do it now?") would
    normalise to nothing and match nothing, so it falls back to its bare
    tokens — never to the empty set, which must not match anything."""
    key = normalise_action(text)
    if key:
        return key
    return frozenset(_TOKEN_RE.findall(str(text).casefold()))


@dataclass(slots=True)
class AgendaItem:
    """One proposed question and its life in the queue (spec §2)."""

    id: str
    text: str
    key: frozenset[str]
    topic: str | None
    first_version: int
    last_seen_version: int
    rank: int
    status: ItemStatus
    created_at: float
    updated_at: float
    asked_at: float | None = None
    answered_at: float | None = None
    dropped_at: float | None = None
    drop_reason: str | None = None
    absent_count: int = 0

    @property
    def pending(self) -> bool:
        return self.status is ItemStatus.PENDING

    def as_dict(self) -> dict:
        """A flat, JSON-ready view for the panel and the audit trail."""
        return {
            "id": self.id, "text": self.text, "topic": self.topic,
            "first_version": self.first_version,
            "last_seen_version": self.last_seen_version,
            "rank": self.rank, "status": self.status.value,
            "absent_count": self.absent_count,
            "created_at": self.created_at, "updated_at": self.updated_at,
            "asked_at": self.asked_at, "answered_at": self.answered_at,
            "dropped_at": self.dropped_at, "drop_reason": self.drop_reason,
        }


@dataclass(frozen=True, slots=True)
class QueueEvent:
    """One audited state change: its kind (`queue_merged`, ...), the clock
    reading, and a flat mapping of details for the audit row."""

    kind: str
    at: float
    details: Mapping = field(default_factory=dict)

    def __getitem__(self, name: str):
        return self.details[name]


class AgendaQueue:
    """The standing question queue for one session (spec §2).

    Construct with the owner's numbers and a clock; drive it with
    `merge`, `consume`, `answered` and `apply_rerank`. Pending items are
    kept in rank order (`pending`); `head` is the one Alba asks next.
    """

    def __init__(self, *, max_pending: int = DEFAULT_QUEUE_MAX,
                 absent_passes: int = DEFAULT_ABSENT_PASSES,
                 topic_threshold: float = DEFAULT_TOPIC_MATCH_THRESHOLD,
                 clock: Callable[[], float] = time.monotonic) -> None:
        if max_pending < 1:
            raise AgendaQueueError("the queue cap must be at least 1")
        if absent_passes < 1:
            raise AgendaQueueError("absent passes must be at least 1")
        self.max_pending = int(max_pending)
        self.absent_passes = int(absent_passes)
        self.topic_threshold = float(topic_threshold)
        self._clock = clock
        self._items: dict[str, AgendaItem] = {}   # insertion order = creation order
        self._order: list[str] = []                # pending ids, head first
        self._next_id = 1
        self._last_version: int | None = None

    # -- what the wiring and the panel read --------------------------------

    @property
    def items(self) -> tuple[AgendaItem, ...]:
        """Every item ever added, in creation order, whatever its status."""
        return tuple(self._items.values())

    @property
    def pending(self) -> tuple[AgendaItem, ...]:
        """The pending items in rank order, head first."""
        return tuple(self._items[i] for i in self._order)

    @property
    def head(self) -> AgendaItem | None:
        return self._items[self._order[0]] if self._order else None

    @property
    def has_pending(self) -> bool:
        return bool(self._order)

    @property
    def last_version(self) -> int | None:
        """The most recent pass version merged, if any."""
        return self._last_version

    def get(self, item_id: str) -> AgendaItem | None:
        return self._items.get(item_id)

    def by_status(self, status: ItemStatus) -> tuple[AgendaItem, ...]:
        return tuple(i for i in self._items.values() if i.status is status)

    def find(self, text: str) -> AgendaItem | None:
        """The item `text` matches — exact equality of normalised token
        sets — among those that are pending, asked or answered; None when
        nothing does. Dropped items do not match: a question the queue
        gave up on is a new proposal if a pass raises it again."""
        key = question_key(text)
        for item in self._items.values():
            if item.status is not ItemStatus.DROPPED and item.key == key:
                return item
        return None

    def pending_on_topic(self, topic: str,
                         threshold: float | None = None) -> tuple[AgendaItem, ...]:
        """The pending items whose topic is `topic` by meaning — the E3
        similarity at the topic threshold (the D3 cone's identity)."""
        t = self.topic_threshold if threshold is None else threshold
        return tuple(i for i in self.pending if i.topic
                     and match_action(topic, [i.topic], t) is not None)

    def snapshot(self) -> dict:
        """A JSON-ready view of the whole queue for the panel (§6)."""
        return {"version": self._last_version,
                "pending": [i.as_dict() for i in self.pending],
                "asked": [i.as_dict() for i in self.by_status(ItemStatus.ASKED)],
                "answered": [i.as_dict() for i in self.by_status(ItemStatus.ANSWERED)],
                "dropped": [i.as_dict() for i in self.by_status(ItemStatus.DROPPED)]}

    # -- the operations (spec §2) -------------------------------------------

    def merge(self, pass_version: int,
              questions: Iterable[str | tuple[str, str | None]]) -> tuple[QueueEvent, ...]:
        """A CDS pass lands: merge its questions_to_ask into the queue.

        Each question is a text, or a (text, topic) pair. Three outcomes
        per question: it matches a PENDING item → that item is refreshed
        (last_seen_version, absent_count reset); it matches an ASKED or
        ANSWERED item → DISCARDED, so an asked question can never
        re-enter; it matches nothing → appended. A question repeated
        within one pass counts once.

        Then the bookkeeping the decisions ask for: every pending item the
        pass did not mention has its absent_count raised and, at
        `absent_passes` consecutive absences, is dropped (D-A,
        `queue_dropped_absent`); the pending order becomes the pass's own
        order for the items it listed, then the unlisted survivors in
        their previous order (the baseline order, §2); and the pending
        set is capped at `max_pending` by dropping the lowest-ranked
        excess (D-D, `queue_capped`).

        Returns the events in the order they happened, `queue_merged`
        first.
        """
        now = self._clock()
        version = int(pass_version)
        events: list[QueueEvent] = []
        listed: list[str] = []          # pending ids the pass named, in its order
        seen_keys: set[frozenset[str]] = set()
        added: list[str] = []
        refreshed: list[str] = []
        discarded: list[dict] = []
        duplicates = 0

        for entry in questions:
            text, topic = (entry, None) if isinstance(entry, str) else (entry[0], entry[1])
            text = str(text).strip()
            if not text:
                continue
            key = question_key(text)
            if key in seen_keys:
                duplicates += 1
                continue
            seen_keys.add(key)
            match = self.find(text)
            if match is None:
                item = self._append(text, key, topic, version, now)
                added.append(item.id)
                listed.append(item.id)
            elif match.status is ItemStatus.PENDING:
                match.last_seen_version = version
                match.absent_count = 0
                match.updated_at = now
                if topic and not match.topic:
                    match.topic = topic
                refreshed.append(match.id)
                listed.append(match.id)
            else:
                # ASKED or ANSWERED: the guarantee. Not pending, not
                # re-added, whatever the pass says.
                discarded.append({"id": match.id, "text": text,
                                  "status": match.status.value})

        # D-A: absence bookkeeping for the pending items the pass omitted.
        listed_set = set(listed)
        dropped_absent: list[str] = []
        for item_id in list(self._order):
            if item_id in listed_set:
                continue
            item = self._items[item_id]
            item.absent_count += 1
            item.updated_at = now
            if item.absent_count >= self.absent_passes:
                self._drop(item, "absent", now)
                dropped_absent.append(item.id)

        # The baseline order (§2).
        unlisted = [i for i in self._order if i not in listed_set]
        self._order = [i for i in listed if i in self._items
                       and self._items[i].status is ItemStatus.PENDING] + unlisted
        self._renumber()
        self._last_version = version

        # D-D: the cap.
        capped = self._cap(now)

        events.append(QueueEvent("queue_merged", now, {
            "version": version,
            "added": len(added), "refreshed": len(refreshed),
            "discarded": len(discarded), "duplicates": duplicates,
            "added_ids": list(added), "refreshed_ids": list(refreshed),
            "discarded_items": list(discarded),
            "dropped_absent": len(dropped_absent), "capped": len(capped),
            "pending": len(self._order)}))
        for item_id in dropped_absent:
            item = self._items[item_id]
            events.append(QueueEvent("queue_dropped_absent", now, {
                "version": version, "id": item.id, "text": item.text,
                "absent_count": item.absent_count,
                "last_seen_version": item.last_seen_version}))
        if capped:
            events.append(QueueEvent("queue_capped", now, {
                "version": version, "cap": self.max_pending,
                "dropped": [{"id": i.id, "text": i.text, "rank": i.rank} for i in capped]}))
        return tuple(events)

    def consume(self, item_id: str | None = None, *, by: str = "auto") -> QueueEvent:
        """Take a question to ask: the head, or the pending item the doctor
        tapped (D-E). It becomes ASKED and leaves the pending order.
        `by` is recorded ("auto" or "tap"). Raises when the queue has no
        pending item, or the id is not a pending item."""
        if item_id is None:
            if not self._order:
                raise AgendaQueueError("consume() on a queue with nothing pending")
            item_id = self._order[0]
        item = self._items.get(item_id)
        if item is None or item.status is not ItemStatus.PENDING:
            raise AgendaQueueError(f"consume({item_id!r}): not a pending item")
        now = self._clock()
        rank = item.rank
        self._order.remove(item_id)
        item.status = ItemStatus.ASKED
        item.asked_at = now
        item.updated_at = now
        self._renumber()
        return QueueEvent("queue_consumed", now, {
            "id": item.id, "text": item.text, "topic": item.topic, "by": by,
            "rank": rank, "version": item.last_seen_version,
            "pending": len(self._order)})

    def add_asked(self, text: str, *, by: str = "tap",
                  version: int | None = None) -> QueueEvent:
        """A question asked from OUTSIDE the queue — the doctor tapped a
        panel question the queue never held (an older version's item, or
        one the machine had not merged) — is recorded as an ASKED item so
        it can never re-enter: a later pass proposing it is discarded at
        the merge like any asked question (D-E, spec §2). It was never
        pending, so it has no rank in the order and is not a consume.
        Raises if the text already matches a live item — the caller should
        have consumed or found it."""
        text = str(text).strip()
        if not text:
            raise AgendaQueueError("add_asked() with an empty text")
        if self.find(text) is not None:
            raise AgendaQueueError(f"add_asked({text!r}): already a live item")
        now = self._clock()
        item_id = f"q{self._next_id}"
        self._next_id += 1
        v = self._last_version if version is None else int(version)
        item = AgendaItem(id=item_id, text=text, key=question_key(text), topic=None,
                          first_version=v if v is not None else 0,
                          last_seen_version=v if v is not None else 0,
                          rank=-1, status=ItemStatus.ASKED,
                          created_at=now, updated_at=now, asked_at=now)
        self._items[item_id] = item
        return QueueEvent("queue_asked_externally", now, {
            "id": item.id, "text": item.text, "by": by, "version": item.first_version,
            "pending": len(self._order)})

    def requeue(self, item_id: str) -> QueueEvent:
        """An ASKED question was never actually put to the patient — the
        politeness abort declined to play it because the patient had
        resumed speaking (PHASE_7C_SPEC.md §5) — so it goes back to
        PENDING at the rank it held when it was consumed (or the tail if
        the pending set has shrunk below that). Nothing else about it
        changes: same id, same first_version, same text. Raises unless
        the item is ASKED."""
        item = self._items.get(item_id)
        if item is None or item.status is not ItemStatus.ASKED:
            raise AgendaQueueError(f"requeue({item_id!r}): not an asked item")
        now = self._clock()
        position = min(max(item.rank, 0), len(self._order))
        self._order.insert(position, item_id)
        item.status = ItemStatus.PENDING
        item.asked_at = None
        item.updated_at = now
        self._renumber()
        return QueueEvent("queue_requeued", now, {
            "id": item.id, "text": item.text, "rank": item.rank,
            "pending": len(self._order)})

    def drop(self, item_id: str, reason: str) -> QueueEvent:
        """The wiring gives up on a PENDING item for a reason of its own
        (today: its text can no longer be resolved to a recorded agenda
        version, so the whitelist cannot speak it). Audited like every
        other drop; the item is DROPPED and, like any dropped item, a
        fresh proposal if a later pass raises it again. Raises unless the
        item is PENDING."""
        item = self._items.get(item_id)
        if item is None or item.status is not ItemStatus.PENDING:
            raise AgendaQueueError(f"drop({item_id!r}): not a pending item")
        now = self._clock()
        self._drop(item, str(reason or "wiring"), now)
        self._renumber()
        return QueueEvent("queue_dropped", now, {
            "id": item.id, "text": item.text, "reason": item.drop_reason,
            "pending": len(self._order)})

    def answered(self, item_id: str) -> QueueEvent:
        """The patient's turn ended with speech after this ASKED question
        (the F5 rule): it becomes ANSWERED. Raises unless the item is ASKED."""
        item = self._items.get(item_id)
        if item is None or item.status is not ItemStatus.ASKED:
            raise AgendaQueueError(f"answered({item_id!r}): not an asked item")
        now = self._clock()
        item.status = ItemStatus.ANSWERED
        item.answered_at = now
        item.updated_at = now
        return QueueEvent("queue_answered", now, {
            "id": item.id, "text": item.text,
            "asked_for_s": None if item.asked_at is None else round(now - item.asked_at, 3)})

    def apply_rerank(self, order_ids: Iterable[str], drop_ids: Iterable[str] | Mapping[str, str],
                     *, ms: float | None = None, apply_drops: bool = True) -> QueueEvent:
        """Apply a re-ranker's answer (§3) to the PENDING items only.

        `order_ids` are the ids still worth asking, best first; `drop_ids`
        the ids the patient has already addressed — a mapping id → the
        re-ranker's one-word reason, or a bare iterable. Any id that is
        not a known PENDING item is IGNORED and returned in the event's
        `ignored` list — the no-invention guard: the re-ranker cannot add
        a question, resurrect one, or touch an asked one. Pending items
        the re-ranker did not mention keep their previous relative order
        after the ones it did.

        With `apply_drops` (the flag-on case) an id in both lists is
        dropped and every drop marks its item dropped with the reason.
        Without it (§3 as amended 2026-09-10, owner decision after
        consultation 491: the re-ranker re-orders only, never drops) the
        drops are received, checked against the same guard and returned
        as `drops_advised` — id, text, reason — but none is applied:
        nothing changes status, an advised item named in the order keeps
        its place there, and one not named follows the named ones.
        """
        now = self._clock()
        before = list(self._order)          # the order the verdict was applied to, drops included
        pending = set(self._order)
        reasons: dict[str, str] = (dict(drop_ids) if isinstance(drop_ids, Mapping)
                                   else {str(i): "rerank" for i in drop_ids})
        ignored: list[str] = []
        advised: list[str] = []
        for item_id in reasons:
            if item_id in pending and item_id not in advised:
                advised.append(item_id)
            elif item_id not in pending:
                ignored.append(item_id)
        drops = advised if apply_drops else []
        order: list[str] = []
        for item_id in order_ids:
            item_id = str(item_id)
            if item_id in pending and item_id not in drops:
                if item_id not in order:
                    order.append(item_id)
            elif item_id not in pending and item_id not in ignored:
                ignored.append(item_id)
        for item_id in drops:
            self._drop(self._items[item_id], str(reasons[item_id] or "rerank"), now)
        rest = [i for i in self._order if i not in order and i not in drops]
        self._order = order + rest
        self._renumber()
        return QueueEvent("queue_reranked", now, {
            "before": before, "order": list(self._order),
            "drops": [{"id": i, "text": self._items[i].text, "reason": reasons[i]} for i in drops],
            "drops_advised": [{"id": i, "text": self._items[i].text, "reason": reasons[i]}
                              for i in advised],
            "ignored": ignored, "unmentioned": rest,
            "ms": ms, "version": self._last_version})

    def set_topic(self, item_id: str, topic: str | None) -> None:
        """Record the topic the topic call assigned to a question."""
        item = self._items[item_id]
        item.topic = topic
        item.updated_at = self._clock()

    # -- internals ----------------------------------------------------------

    def _append(self, text: str, key: frozenset[str], topic: str | None,
                version: int, now: float) -> AgendaItem:
        item_id = f"q{self._next_id}"
        self._next_id += 1
        item = AgendaItem(id=item_id, text=text, key=key, topic=topic,
                          first_version=version, last_seen_version=version,
                          rank=len(self._order), status=ItemStatus.PENDING,
                          created_at=now, updated_at=now)
        self._items[item_id] = item
        self._order.append(item_id)
        return item

    def _drop(self, item: AgendaItem, reason: str, now: float) -> None:
        if item.id in self._order:
            self._order.remove(item.id)
        item.status = ItemStatus.DROPPED
        item.drop_reason = reason
        item.dropped_at = now
        item.updated_at = now

    def _cap(self, now: float) -> list[AgendaItem]:
        excess = self._order[self.max_pending:]
        dropped = []
        for item_id in excess:
            item = self._items[item_id]
            self._drop(item, "capped", now)
            dropped.append(item)
        return dropped

    def _renumber(self) -> None:
        for rank, item_id in enumerate(self._order):
            self._items[item_id].rank = rank
