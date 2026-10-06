"""The arms of the engine bench side by side, and what counts as faster
(spec 15.8, ruling 10). Fixed before the run.

Rule A: an engine is a candidate only if its full arm meets every hard
mark. Rule B: its typical pass, the median wall time of its passes of
495 as mark T17 measures it, must be at least 1 second shorter than the
baseline arm's. A smaller difference is a figure, not a win. An arm
whose calls were sent together has chains A1 to A3 only: it is held to
the same second against the same three chains of the baseline sent one
after another, and its marks are set beside the same three chains of
its own engine's full arm.
"""

from __future__ import annotations

from openconsult.bench import score

FASTER_BY_MS = 1000
A_CHAINS = ("A1", "A2", "A3")


def typical(results: dict, chains: tuple | None = None) -> dict:
    """The typical pass and the slowest, in ms, over the passes of 495;
    and the median over every pass of every case beside it."""
    mine = {k: r for k, r in results.items() if chains is None or k[1] in chains}
    of_495 = [p["wall_ms"] for r in mine.values() if r["group"] == "495" for p in r["passes"]]
    of_all = [p["wall_ms"] for r in mine.values() for p in r["passes"]]
    return {"passes": len(of_495), "median_ms": score.med(of_495), "slowest_ms": max(of_495, default=None),
            "all_passes": len(of_all), "all_median_ms": score.med(of_all)}


def held_against(arm: dict, base: dict, candidate: bool) -> dict:
    if arm["median_ms"] is None or base["median_ms"] is None:
        return {"shorter_by_ms": None, "faster": False}
    shorter = base["median_ms"] - arm["median_ms"]
    return {"shorter_by_ms": shorter, "faster": bool(candidate and shorter >= FASTER_BY_MS)}


def values(results: dict) -> dict:
    return {m["n"]: m["value"] for m in score.marks(results)}


def table(arms: dict[str, dict], baseline: str, pairs: dict[str, str] | None = None) -> dict:
    """arms: each arm's results by name. pairs: for an arm sent together,
    the name of the full arm of the same engine."""
    pairs = pairs or {}
    scored = {name: score.summary(results) for name, results in arms.items()}
    rows = {}
    for name, results in arms.items():
        together = any(r.get("together") for r in results.values())
        row = {"together": together, "chains": len(results), "failed_chains": scored[name]["failed_chains"],
               "empty_replies": scored[name]["empty_replies"], "kept_lists": scored[name]["kept_lists"],
               "marks": values(results), "typical": typical(results)}
        if together:
            full = pairs[name]
            same = {k: r for k, r in arms[full].items() if k[1] in A_CHAINS}
            row["full_arm"] = full
            row["marks_one_after_another"] = values(same)
            row["marks_changed"] = [n for n, v in row["marks"].items()
                                    if not n.startswith("T") and v != row["marks_one_after_another"][n]]
            row["against"] = held_against(row["typical"], typical(arms[baseline], A_CHAINS), scored[full]["candidate"])
            row["against_all_chains"] = held_against(row["typical"], typical(arms[baseline]), scored[full]["candidate"])
        else:
            row["candidate"] = scored[name]["candidate"]
            row["missed"] = [m["n"] for m in scored[name]["marks"] if m["kind"] == "hard" and not m["met"]]
            row["met"] = {m["n"]: m["met"] for m in scored[name]["marks"]}
            if name != baseline:
                row["against"] = held_against(row["typical"], typical(arms[baseline]), row["candidate"])
        rows[name] = row
    return {"baseline": baseline, "faster_by_ms": FASTER_BY_MS, "arms": rows}


def _shown(value) -> str:
    if isinstance(value, dict):
        return "; ".join(f"{k}: {v}" for k, v in value.items())
    if isinstance(value, float):
        return f"{value:.2f}"
    return "-" if value is None else str(value)


def _seconds(ms) -> str:
    return "-" if ms is None else f"{ms / 1000:.2f}"


def as_markdown(found: dict) -> str:
    arms = found["arms"]
    names = list(arms)
    lines = ["| | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for n in next(iter(arms.values()))["marks"]:
        lines.append(f"| {n} | " + " | ".join(_shown(arms[a]["marks"][n]) for a in names) + " |")
    for label, pick in (("chains", lambda r: r["chains"]), ("failed chains", lambda r: len(r["failed_chains"])),
                        ("empty replies", lambda r: r["empty_replies"]), ("kept lists", lambda r: r["kept_lists"]),
                        ("typical pass of 495, s", lambda r: _seconds(r["typical"]["median_ms"])),
                        ("slowest pass of 495, s", lambda r: _seconds(r["typical"]["slowest_ms"])),
                        ("median pass, all cases, s", lambda r: _seconds(r["typical"]["all_median_ms"]))):
        lines.append(f"| {label} | " + " | ".join(str(pick(arms[a])) for a in names) + " |")
    lines.append("")
    base = found["baseline"]
    for name, row in arms.items():
        if row["together"]:
            changed = ", ".join(row["marks_changed"]) or "none"
            lines.append(f"{name}: the two calls sent together, chains A1 to A3. Marks that differ from the same "
                         f"three chains of {row['full_arm']}: {changed}.")
        elif row["candidate"]:
            lines.append(f"{name}: Candidate: yes")
        else:
            lines.append(f"{name}: Candidate: NO, missed {', '.join(row['missed'])}")
        against = row.get("against")
        if against is None or against["shorter_by_ms"] is None:
            continue
        shorter = against["shorter_by_ms"]
        moved = f"{_seconds(shorter)} s shorter" if shorter >= 0 else f"{_seconds(-shorter)} s longer"
        mine = _seconds(row["typical"]["median_ms"])
        theirs = _seconds(row["typical"]["median_ms"] + shorter)
        if against["faster"]:
            verdict = "Faster in a way that matters to the patient: yes"
        elif shorter >= found["faster_by_ms"]:
            verdict = "Not a candidate, so not called faster"
        else:
            verdict = "Not called faster (under 1 second)"
        lines.append(f"{name}: Typical pass {mine} s against {theirs} s on {base}: {moved}. {verdict}.")
    return "\n".join(lines) + "\n"
