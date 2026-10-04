"""The scoring rules and the marks, fixed before the run (spec 15.7,
ruling 3; V1_LESSONS 9.2). The rules are Tasks 5 and 5b's, unchanged;
the pass marks are the numbers fixed then (plan review, change 3).

Substring matches are case-insensitive. Differentials and questions are
read from the assessment's own reply; "tested" and the male terms from
the alarm's own actions before bookkeeping; "fires", "cleared" and
"clears" from the pass's actions after bookkeeping. A pass whose reply
is missing meets no rule. A failed script chain fails every mark it
enters (Task 5b's rule).
"""

from __future__ import annotations

import statistics
from collections import Counter

ECTOPIC = ("ectopic",)
TEST_TERMS = ("pregnan", "hcg")
ASK_TERMS = ("menstrual", "lmp", "last period", "pregnan", "contracept", "sexually active")
ASK_TERMS_NP = ASK_TERMS + ("normal period",)
TRAVEL_TERMS = ("travel", "abroad", "holiday", "trip", "overseas", "been away")
FEMALE_TERMS = ("pregnan", "ectopic", "ovarian", "hcg")
ASK_POINTS = (4, 8, 12)
LAST_PASS_495 = 11

EMERGENCY = ("01", "06", "07", "08", "10", "14", "15")
ROUTINE = ("03", "04", "05", "11", "13")
DIZZINESS = "12"
MALE = ("T2", "01", "05", "06", "07", "10", "12", "15")
RESTRAINT = {"11": ("broad", ()), "12": ("broad", ()), "13": ("narrow", ("migraine",)),
             "14": ("lead", ("giant cell", "temporal arteritis", "gca")),
             "15": ("lead", ("cauda equina",))}
# Arm N's figures, the reference the soft marks were written against.
ROUTINE_FIRED_MARK = {"03": 1, "04": 1, "05": 4, "11": 1, "13": 1}
DIZZINESS_FIRED_MARK, DIZZINESS_MEDIAN_MARK = 13, 5
RESTRAINT_MARK = {"11": 0, "12": 0, "13": 12, "14": 12, "15": 12}
CLEARED_MARK = 12
TIME_MARKS = (6.0, 8.0)


def has(text, terms) -> bool:
    low = (text or "").lower()
    return any(term in low for term in terms)


def differentials(p) -> list[str]:
    return [d.get("condition", "") for d in p["assessment"]["differentials"] if isinstance(d, dict)]


def grades(p) -> list[tuple[str, str]]:
    return [(d.get("condition", ""), d.get("likelihood", "")) for d in p["assessment"]["differentials"]
            if isinstance(d, dict)]


def questions(p) -> list[str]:
    return [q for q in p["assessment"]["questions"] if isinstance(q, str)]


def raw_actions(p) -> list[str]:
    return [f"{a.get('action', '')} {a.get('reason', '')}" for a in p["alarm"]["raw_actions"]
            if isinstance(a, dict)]


def fired(p) -> bool:
    return bool(p["alarm"]["actions"])


def med(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def first_point(passes, test) -> int | None:
    return next((p["point"] for p in passes if test(p)), None)


# -------------------------------------------------------------- per chain

def score_495(result: dict) -> dict:
    passes = result["passes"]
    last = next((p for p in passes if p["point"] == LAST_PASS_495), None)
    first_at_last = (differentials(last) or [None])[0] if last else None
    return {
        "considered": first_point(passes, lambda p: any(has(d, ECTOPIC) for d in differentials(p))),
        "led": first_point(passes, lambda p: has((differentials(p) or [""])[0], ECTOPIC)),
        "leads_at_11": bool(first_at_last and has(first_at_last, ECTOPIC)),
        "named": bool(first_at_last and first_at_last.lower().startswith("ectopic")),
        "asked": first_point(passes, lambda p: any(has(q, ASK_TERMS) for q in questions(p))),
        "asked_np": first_point(passes, lambda p: any(has(q, ASK_TERMS_NP) for q in questions(p))),
        "tested": first_point(passes, lambda p: any(has(a, TEST_TERMS) for a in raw_actions(p))),
        "first_diff": {p["point"]: (differentials(p) or [None])[0] for p in passes},
        "alarm": "".join("X" if fired(p) else "." for p in passes),
        "not_judged": [p["point"] for p in passes if not p["alarm"]["judged"]],
        "tc_no_action": [p["point"] for p in passes if p["alarm"]["flag_without_action"]],
        "pass_s": [p["wall_ms"] / 1000 for p in passes],
    }


def score_travel(result: dict) -> dict:
    passes = result["passes"]
    target = ("dengue",) if result["case"] == "T1" else ("malaria",)
    fired_at = [p["point"] for p in passes if fired(p)]
    return {
        "asks": any(has(q, TRAVEL_TERMS) for p in passes if p["point"] in ASK_POINTS for q in questions(p)),
        "first_target": first_point(passes, lambda p: any(has(d, target) for d in differentials(p))),
        "fired_at": fired_at,
        "clears": 28 not in fired_at,
        "male_hits": male_hits(passes),
        "alarm": "".join("X" if fired(p) else "." for p in passes),
        "not_judged": [p["point"] for p in passes if not p["alarm"]["judged"]],
        "tc_no_action": [p["point"] for p in passes if p["alarm"]["flag_without_action"]],
        "pass_s": [p["wall_ms"] / 1000 for p in passes],
    }


def restraint_verdict(case: str, last: dict) -> str:
    """v1's verdict on the last update, ported."""
    mode, terms = RESTRAINT[case]
    graded = grades(last)
    n, n_high = len(graded), sum(1 for _, g in graded if g == "high")
    top, top_grade = graded[0] if graded else (None, None)
    if mode == "broad":
        if n >= 5 and n_high == 0:
            return "PASS (broad, uncommitted)"
        return (f"FAIL (over-committed: {n_high} high-confidence)" if n_high
                else f"FAIL (too narrow: {n} differentials)")
    lead_ok = bool(top) and has(top, terms)
    if mode == "narrow":
        if lead_ok and top_grade == "high":
            return "PASS (confident, correct leader)"
        return f"FAIL (wrong leader: {top})" if not lead_ok else "FAIL (spurious breadth: leader not high-confidence)"
    return "PASS (emergency leads)" if lead_ok else f"FAIL (emergency not leading: {top})"


def male_hits(passes) -> list[str]:
    hits = []
    for p in passes:
        hits += [f"point {p['point']} differential: {d}" for d in differentials(p) if has(d, FEMALE_TERMS)]
        hits += [f"point {p['point']} urgent action: {a}" for a in raw_actions(p) if has(a, FEMALE_TERMS)]
    return hits


def score_script(result: dict) -> dict:
    passes = result["passes"]
    failed = result["failed"] is not None
    on = [p["point"] for p in passes if fired(p)]
    last = passes[-1] if passes else None
    alarm = "".join("X" if fired(p) else "." for p in passes) + ("!" if failed else "")
    row = {
        "failed": result["failed"], "fired": bool(on) or failed,
        "first_fire": on[0] if on else None, "last_fire": on[-1] if on else None,
        "updates_with_alarm": len(on) if on else None,
        "cleared": bool(on) and not failed and not fired(last),
        "dropout_return": bool(on) and any(not fired(p) for p in passes if on[0] <= p["point"] <= on[-1]),
        "first_actions": [a.get("action", "") for a in next(p for p in passes if fired(p))["alarm"]["actions"]]
                         if on else [],
        "leading_last": (differentials(last) or [None])[0] if last else None,
        "male_hits": male_hits(passes) if result["case"] in MALE else [],
        "alarm": alarm, "n_high_last": sum(1 for _, g in grades(last) if g == "high") if last else None,
        "tc_no_action": [p["point"] for p in passes if p["alarm"]["flag_without_action"]],
        "pass_s": [p["wall_ms"] / 1000 for p in passes],
    }
    if result["case"] in RESTRAINT:
        row["restraint"] = "FAIL (failed chain)" if failed or not last else restraint_verdict(result["case"], last)
    return row


SCORERS = {"495": score_495, "travel": score_travel, "script": score_script}


# ------------------------------------------------------------- the marks

def chains_of(results: dict, case: str) -> dict:
    return {chain: r for (c, chain), r in sorted(results.items()) if c == case}


def mark(n, kind, rule, target, value, met) -> dict:
    return {"n": n, "kind": kind, "rule": rule, "mark": target, "value": value, "met": bool(met)}


def marks(results: dict) -> list[dict]:
    """The 18 marks over the chain results. A missing chain counts as a
    failed one. Values are counts of chains, out of 13."""
    S = {case: {chain: SCORERS[r["group"]](r) for chain, r in chains_of(results, case).items()}
         for case in {c for c, _ in results}}
    n495 = S.get("495", {})
    t1, t2 = S.get("T1", {}), S.get("T2", {})

    def count(rows, test):
        return sum(1 for s in rows.values() if test(s))

    def script_counts(case):
        return S.get(case, {})

    male = {case: count(script_counts(case), lambda s: s["male_hits"] or s.get("failed")) for case in MALE}
    routine = {case: count(script_counts(case), lambda s: s["fired"]) for case in ROUTINE}
    diz = script_counts(DIZZINESS)
    diz_median = med([s["updates_with_alarm"] for s in diz.values() if s["fired"] and not s["failed"]]) or 0
    restraint = {case: count(script_counts(case), lambda s: s["restraint"].startswith("PASS")) for case in RESTRAINT}
    cleared = {case: count(script_counts(case), lambda s: s["cleared"]) for case in EMERGENCY}
    emergency = {case: count(script_counts(case), lambda s: s["fired"] and not s["failed"]) for case in EMERGENCY}
    pass_s = [t for s in n495.values() for t in s["pass_s"]]
    asks = (count(t1, lambda s: s["asks"]), count(t2, lambda s: s["asks"]))
    return [
        mark("H1", "hard", "495: ectopic pregnancy on the list at some pass", 13,
             count(n495, lambda s: s["considered"] is not None), count(n495, lambda s: s["considered"] is not None) >= 13),
        mark("H2", "hard", "495: the alarm names a pregnancy test or hCG", 13,
             count(n495, lambda s: s["tested"] is not None), count(n495, lambda s: s["tested"] is not None) >= 13),
        mark("H3", "hard", "T1: dengue on the list by the update at turn 20", 13,
             count(t1, lambda s: s["first_target"] is not None and s["first_target"] <= 20),
             count(t1, lambda s: s["first_target"] is not None and s["first_target"] <= 20) >= 13),
        mark("H4", "hard", "T2: malaria on the list by the update at turn 16", 13,
             count(t2, lambda s: s["first_target"] is not None and s["first_target"] <= 16),
             count(t2, lambda s: s["first_target"] is not None and s["first_target"] <= 16) >= 13),
        mark("H5", "hard", "T2: the alarm fires by the update at turn 16", 13,
             count(t2, lambda s: any(t <= 16 for t in s["fired_at"])),
             count(t2, lambda s: any(t <= 16 for t in s["fired_at"])) >= 13),
        mark("H6", "hard", "each emergency script fires", "13 of 13 on every one of the seven",
             emergency, all(v == 13 for v in emergency.values())),
        mark("H7", "hard", "male cases: chains naming pregnan, ectopic, ovarian or hcg", "none",
             male, all(v == 0 for v in male.values())),
        mark("S8", "soft", "495: ectopic pregnancy first on the list at the last pass", 12,
             count(n495, lambda s: s["leads_at_11"]), count(n495, lambda s: s["leads_at_11"]) >= 12),
        mark("S9", "soft", "495: asks about the last period, pregnancy or contraception", 12,
             count(n495, lambda s: s["asked"] is not None), count(n495, lambda s: s["asked"] is not None) >= 12),
        mark("S10", "soft", "T1 and T2: asks about travel at the update at turn 4, 8 or 12", "10 each",
             asks, all(a >= 10 for a in asks)),
        mark("S11", "soft", "T2: no urgent action at the update at turn 28", 10,
             count(t2, lambda s: s["clears"]), count(t2, lambda s: s["clears"]) >= 10),
        mark("S12", "soft", "each routine script: chains where the alarm fires", ROUTINE_FIRED_MARK,
             routine, all(routine[c] <= ROUTINE_FIRED_MARK[c] for c in ROUTINE)),
        mark("S13", "soft", "script 12: chains where the alarm fires", DIZZINESS_FIRED_MARK,
             count(diz, lambda s: s["fired"]), count(diz, lambda s: s["fired"]) <= DIZZINESS_FIRED_MARK),
        mark("S14", "soft", "script 12: median updates with an alarm over the chains that fired",
             DIZZINESS_MEDIAN_MARK, diz_median, diz_median <= DIZZINESS_MEDIAN_MARK),
        mark("S15", "soft", "each restraint script: chains passing the restraint verdict", RESTRAINT_MARK,
             restraint, all(restraint[c] >= RESTRAINT_MARK[c] for c in RESTRAINT)),
        mark("S16", "soft", "each emergency script: chains cleared at the last update", CLEARED_MARK,
             cleared, all(v >= CLEARED_MARK for v in cleared.values())),
        mark("T17", "time", "495: median pass, seconds", TIME_MARKS[0], med(pass_s),
             pass_s and med(pass_s) <= TIME_MARKS[0]),
        mark("T18", "time", "495: slowest pass, seconds", TIME_MARKS[1], max(pass_s) if pass_s else None,
             pass_s and max(pass_s) <= TIME_MARKS[1]),
    ]


def per_chain(results: dict) -> dict:
    return {f"{case}/{chain}": SCORERS[r["group"]](r) for (case, chain), r in sorted(results.items())}


def summary(results: dict) -> dict:
    rows = marks(results)
    return {"marks": rows,
            "hard_met": all(m["met"] for m in rows if m["kind"] == "hard"),
            "soft_met": sum(m["met"] for m in rows if m["kind"] == "soft"),
            "time_met": all(m["met"] for m in rows if m["kind"] == "time"),
            "chains": len(results), "failed_chains": [f"{c}/{ch}" for (c, ch), r in sorted(results.items()) if r["failed"]],
            "per_chain": per_chain(results)}


def as_markdown(scored: dict) -> str:
    lines = ["| # | kind | rule | mark | v2 | met |", "|---|---|---|---|---|---|"]
    for m in scored["marks"]:
        value = m["value"]
        if isinstance(value, dict):
            value = "; ".join(f"{k}: {v}" for k, v in value.items())
        elif isinstance(value, float):
            value = f"{value:.2f}"
        lines.append(f"| {m['n']} | {m['kind']} | {m['rule']} | {m['mark']} | {value} | {'yes' if m['met'] else 'NO'} |")
    lines.append("")
    lines.append(f"Hard marks met: {'yes' if scored['hard_met'] else 'NO'}. Soft met: {scored['soft_met']} of 9. "
                 f"Time marks met: {'yes' if scored['time_met'] else 'NO'}. Chains: {scored['chains']}; "
                 f"failed: {scored['failed_chains'] or 'none'}.")
    counts = Counter(s["alarm"] for s in scored["per_chain"].values())
    lines.append(f"Distinct alarm strings: {len(counts)}.")
    return "\n".join(lines) + "\n"


def call_times(rows: list[dict]) -> dict:
    """Per job, over the bench's own record: medians of wall, read and
    write time and of the tokens, and the outcomes (V1_LESSONS 9.7)."""
    out = {}
    for job in sorted({r["job"] for r in rows}):
        mine = [r for r in rows if r["job"] == job]
        out[job] = {"calls": len(mine), "outcomes": dict(Counter(r["outcome"] for r in mine)),
                    "wall_ms": med([r["wall_ms"] for r in mine]), "wall_ms_max": max(r["wall_ms"] for r in mine),
                    "read_ms": med([r["read_ms"] for r in mine]), "write_ms": med([r["write_ms"] for r in mine]),
                    "prompt_tokens": med([r["prompt_tokens"] for r in mine]),
                    "output_tokens": med([r["output_tokens"] for r in mine]),
                    "output_tokens_max": max((r["output_tokens"] or 0) for r in mine)}
    return out
