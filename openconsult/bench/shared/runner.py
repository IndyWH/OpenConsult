"""The searches of a setup or a base line of 5d, one begun every 5
seconds, and the side reading (spec 15.9, the details of 5d). A search
is one call for each name of its list, as v1 sends them; a search never
begins before the one before it has ended, and a start that is late for
that reason is counted; a list with no name gives no call and is
counted; a call that fails is kept as failed and nothing is asked a
second time (rule 22 of the stage). Every moment is kept, as seconds
from the start and as the machine's own clock, so the judge can set the
searches beside the chains and the recording."""

from __future__ import annotations

import time
from typing import Callable

from openconsult.bench.shared.embed import Embedder
from openconsult.bench.shared.searches import list_for, search_text, vector_fault

EVERY_S = 5.0
LATE_IF_S = 0.01       # a start this much after its due moment is a late start
WAIT_SLICE_S = 0.5     # the wait for a due moment is cut in slices, so a stop file is seen in time


def one_search(embedder: Embedder, k: int, names: list[str], due: float, clock: Callable, wall: Callable) -> dict:
    """One search: the names of one list, one call each, in order."""
    started = clock()
    record = {"k": k, "names": list(names), "due": round(due, 3), "started": round(started, 3), "started_epoch": wall(),
              "late_s": round(max(0.0, started - due), 3), "late": started - due > LATE_IF_S,
              "empty": not names, "calls": [], "ok": True, "error": None}
    for name in names:
        found = embedder.embed([search_text(name)])
        call = {"name": name, "wall_s": round(found.wall_s, 4), "ok": found.ok, "error": found.error, "fault": None,
                "own": found.own}
        if found.ok:
            if len(found.vectors) != 1:
                call["fault"] = f"{len(found.vectors)} vectors came back for one name"
            else:
                call["fault"] = vector_fault(found.vectors[0])
            call["ok"] = call["fault"] is None
        record["calls"].append(call)
        if not call["ok"]:
            record["ok"], record["error"] = False, call["error"] or f"{name}: {call['fault']}"
    record["ended"] = round(clock(), 3)
    record["seconds"] = round(record["ended"] - started, 4)
    return record


def run_searches(embedder: Embedder, lists: list[list[str]], every_s: float = EVERY_S, limit: int | None = None,
                 until: Callable[[], bool] | None = None, sleep: Callable = time.sleep,
                 clock: Callable = time.monotonic, wall: Callable = time.time, say: Callable = lambda line: None) -> dict:
    """Search k is due at t0 + k * every_s and takes list k. It runs until
    the limit, or until the stop condition is true, whichever comes
    first; no search starts after the stop condition is seen."""
    t0, t0_epoch, k, searches = clock(), wall(), 0, []
    stopped_by = None
    while True:
        if limit is not None and k >= limit:
            stopped_by = "limit"
            break
        due = t0 + k * every_s
        while clock() < due:
            if until is not None and until():
                break
            sleep(min(WAIT_SLICE_S, max(0.0, due - clock())))
        if until is not None and until():
            stopped_by = "stop"
            break
        record = one_search(embedder, k, list_for(k, lists), due - t0, lambda: clock() - t0, wall)
        searches.append(record)
        say(record)
        k += 1
    return {"embedding": embedder.name, "where": embedder.where, "info": embedder.info(), "every_s": every_s,
            "t0_epoch": t0_epoch, "searches": searches, "stopped_by": stopped_by,
            "late_starts": sum(1 for s in searches if s["late"]), "empty": sum(1 for s in searches if s["empty"]),
            "failed": sum(1 for s in searches if not s["ok"]),
            "median_s": _median([s["seconds"] for s in searches if s["ok"] and not s["empty"]])}


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)
    middle = ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2
    return round(middle, 4)


def run_index(embedder: Embedder, pieces: list[dict], size: int, clock: Callable = time.monotonic,
              wall: Callable = time.time) -> dict:
    """The side reading: the pieces sent size at a time, each batch one
    call, the time from the first batch's start to the last vector's return."""
    from openconsult.bench.shared.pieces import batches
    started, started_epoch, rows, ok = clock(), wall(), [], True
    for i, batch in enumerate(batches(pieces, size)):
        t = clock()
        found = embedder.embed([p["passage"] for p in batch])
        faults = [vector_fault(v) for v in found.vectors] if found.ok else []
        fault = next((f for f in faults if f), None) if found.ok and len(found.vectors) == len(batch) else \
            (None if not found.ok else f"{len(found.vectors)} vectors for {len(batch)} pieces")
        row = {"batch": i, "pieces": len(batch), "wall_s": round(clock() - t, 4), "ok": found.ok and fault is None,
               "error": found.error or fault, "own": found.own}
        rows.append(row)
        ok = ok and row["ok"]
    return {"embedding": embedder.name, "where": embedder.where, "info": embedder.info(), "batch_size": size,
            "pieces": len(pieces), "batches": rows, "seconds": round(clock() - started, 4), "started_epoch": started_epoch,
            "ok": ok}
