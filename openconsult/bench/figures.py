"""The figures of the engine bench, by the rules of 7 Oct (spec 15.8,
rulings 17, 18, 21, 22 and 26). One command gives them from the public
folder alone, with no engine and no private file, and the same code
gives the same figures from the private result folders.

The rounds are data: a rounds file names the arms and their roles (the
engine, calls one after another or together), the baseline arm, and for
each round its chain at temperature 0 and its chains of the stress test.
The temperature of a chain is read from the results, never from its name.

Rule A, who is a candidate, is score.is_candidate (ruling 18). Rule B:
the typical pass of a round is the median of the passes of consultation
495 in that round's chain at temperature 0; an arm is called faster only
if it is a candidate and at least 0.50 s shorter than the arm it is held
against in each round (ruling 17). If the baseline's own rounds differ by
more than 0.25 s the day was unsteady and no arm is called faster
(ruling 21). Beside the wait: the tokens written and the time for each
token, all in and writing only (ruling 22). Every difference is worked
from the milliseconds and rounded once, for showing.
"""

from __future__ import annotations

import json
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from openconsult.bench import export, score
from openconsult.bench.replay import answer_text
from openconsult.bench.writer import Refused, ResultWriter
from openconsult.db import open_database
from openconsult.llm.record import ModelCalls

FASTER_BY_MS = 500          # ruling 17: half a second, in every round
STEADY_WITHIN_MS = 250      # ruling 21: Ollama's own rounds, calls one after another
TYPICAL_OF = "495"          # the consultation whose passes give the typical pass
# A reasoning that ends otherwise was cut mid-sentence (the stray quote, rulings 16 and 22).
SENTENCE_ENDS = (".", "?", "!", ")", "]", '"', "'", "%")
JOBS = ("alarm", "assessment")


class FiguresRefused(Exception):
    pass


# -------------------------------------------------------------- the arms

def private_arm(folder: Path) -> dict:
    """An arm from its result files and its record of calls."""
    folder = Path(folder)
    results = ResultWriter(folder).read_all()
    rows = {row["id"]: row for row in ModelCalls(open_database(folder / "calls.db")).rows()}
    calls = {}
    for (case, chain), r in results.items():
        for p in r["passes"]:
            for job in JOBS:
                row = rows[p[job]["call_id"]]
                calls[(case, chain, p["point"], job)] = {
                    "outcome": row["outcome"], "wall_ms": row["wall_ms"], "write_ms": row["write_ms"],
                    "output_tokens": row["output_tokens"], "text": answer_text(row["reply"])[0]}
    return {"results": results, "calls": calls}


def public_arm(folder: Path) -> dict:
    """The same arm from what is published: its replies alone."""
    lines = export.read_replies(Path(folder) / "replies.jsonl.gz")
    calls = {(line["case"], line["chain"], line["point"], line["job"]):
             {key: line[key] for key in ("outcome", "wall_ms", "write_ms", "output_tokens", "text")}
             for line in lines}
    return {"results": export.results_from_replies(lines), "calls": calls}


def read_rounds(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def public_arms(public: Path, rounds: dict) -> dict:
    return {name: public_arm(Path(public) / "arms" / name) for name in rounds["arms"]}


# ------------------------------------------------------------ the seconds

def calls_of(arm: dict, chains=None, job: str | None = None) -> list[dict]:
    return [call for (case, chain, point, j), call in arm["calls"].items()
            if (chains is None or chain in chains) and (job is None or j == job)]


def passes_of(arm: dict, chain: str, group: str | None = None) -> list[int]:
    return [p["wall_ms"] for (case, ch), r in arm["results"].items() if ch == chain
            and (group is None or r["group"] == group) for p in r["passes"]]


def per_token(calls: list[dict]) -> dict:
    """Over the calls that ended ok: the tokens written, the ms for each
    token all in (the whole wait) and writing only (the engine's own
    writing time), and the median tokens written in a call."""
    ok = [c for c in calls if c["outcome"] == "ok" and c["output_tokens"]]
    tokens = sum(c["output_tokens"] for c in ok)
    timed = [c for c in ok if c["write_ms"]]
    writing = sum(c["output_tokens"] for c in timed)
    return {"calls": len(ok), "tokens_written": tokens,
            "ms_per_token_all_in": round(sum(c["wall_ms"] for c in ok) / tokens, 2) if tokens else None,
            "ms_per_token_writing": round(sum(c["write_ms"] for c in timed) / writing, 2) if writing else None,
            "tokens_written_median": score.med([c["output_tokens"] for c in ok])}


def a_round(arm: dict, chain: str, stress: list[str]) -> dict | None:
    """One round of one arm: the typical pass of 495 in the round's chain
    at 0, the median over all cases beside it, each call's median, and
    the tokens and the time for each token over the chain and the round."""
    results = {key: r for key, r in arm["results"].items() if key[1] == chain}
    if not results:
        return None
    other = {r.get("temperature") for r in results.values()} - {0.0}
    if other:
        raise FiguresRefused(f"chain {chain} is named as a round's chain at temperature 0, "
                             f"but its results are at temperature {sorted(other)[0]}")
    of_495, of_all = passes_of(arm, chain, TYPICAL_OF), passes_of(arm, chain)
    return {"chain": chain, "typical_ms": score.med(of_495), "passes": len(of_495),
            "slowest_ms": max(of_495, default=None),
            "all_cases_median_ms": score.med(of_all), "all_cases_passes": len(of_all),
            "all_cases_slowest_ms": max(of_all, default=None),
            **{f"{job}_median_ms": score.med([c["wall_ms"] for c in calls_of(arm, (chain,), job)]) for job in JOBS},
            "per_token": per_token(calls_of(arm, (chain,))),
            "per_token_round": per_token(calls_of(arm, (chain, *stress)))}


def rounds_of(arm: dict, rounds: dict) -> dict:
    return {number: a_round(arm, spec["chain"], spec.get("stress", [])) for number, spec in rounds["rounds"].items()}


def typicals(arm_rounds: dict) -> list:
    return [r["typical_ms"] if r else None for r in arm_rounds.values()]


def steadiness(base_typicals: list) -> dict:
    """Ruling 21: the largest difference between the baseline's rounds."""
    known = [t for t in base_typicals if t is not None]
    spread = (max(known) - min(known)) if len(known) == len(base_typicals) and known else None
    return {"typical_ms_by_round": base_typicals, "spread_ms": spread,
            "steady": spread is not None and spread <= STEADY_WITHIN_MS, "line_ms": STEADY_WITHIN_MS}


def judge(name: str, against: str, mine: list, theirs: list, candidate: bool, steady: bool) -> dict:
    """Rule B for one arm against another, round by round."""
    shorter = [t - m if m is not None and t is not None else None for m, t in zip(mine, theirs)]
    every = bool(shorter) and all(d is not None and d >= FASTER_BY_MS for d in shorter)
    if not candidate:
        verdict = "not a candidate, so not called faster"
    elif not steady:
        verdict = "the day was unsteady, so no arm is called faster"
    elif every:
        verdict = "faster by the rule"
    else:
        verdict = "a figure, not a win"
    return {"arm": name, "against": against, "typical_ms": mine, "against_typical_ms": theirs,
            "shorter_by_ms": shorter, "in_every_round": every, "candidate": candidate, "verdict": verdict,
            "faster": verdict == "faster by the rule"}


def judgements(rounds: dict, found: dict, steady: bool) -> list[dict]:
    """The seven judgements of the details bullet: each arm one after
    another against the baseline; each together arm against the baseline
    together, and against the baseline one after another, the app today."""
    base, base_together = rounds["baseline"], rounds.get("baseline_together")
    roles = rounds["arms"]
    pairs = [(name, base) for name, role in roles.items() if role["way"] == "one after another" and name != base]
    if base_together:
        pairs += [(name, base_together) for name, role in roles.items()
                  if role["way"] == "together" and name != base_together]
    pairs += [(name, base) for name, role in roles.items() if role["way"] == "together"]
    return [judge(name, against, found[name]["typical_ms_by_round"], found[against]["typical_ms_by_round"],
                  found[name]["candidate"], steady) for name, against in pairs]


# -------------------------------------------------------- from the replies

def temperature_of(arm: dict) -> dict:
    return {key: r.get("temperature") for key, r in arm["results"].items()}


def readable(call: dict) -> dict | None:
    """The reply as its form, or None when the call did not end ok or its
    text cannot be read as its form. Such a reply is counted apart."""
    if call["outcome"] != "ok" or call["text"] is None:
        return None
    try:
        found = json.loads(call["text"])
    except ValueError:
        return None
    return found if isinstance(found, dict) else None


def from_replies(arm: dict) -> dict:
    """What the report states from the replies, by temperature."""
    temps = temperature_of(arm)
    cut, apart, no_action = Counter(), Counter(), Counter()
    for (case, chain, point, job), call in arm["calls"].items():
        t = temps[(case, chain)]
        reply = readable(call)
        if reply is None:
            apart[f"{job} {call['outcome']} at {t}"] += 1
            continue
        reasoning = (reply.get("reasoning") or "").rstrip()
        if not reasoning.endswith(SENTENCE_ENDS):
            cut[f"{job} at {t}"] += 1
    empty, kept, first = Counter(), Counter(), {}
    for (case, chain), r in sorted(arm["results"].items()):
        t = temps[(case, chain)]
        for p in r["passes"]:
            a = p["assessment"]
            if a["ok"] and (a.get("kept") or not a["differentials"]):
                empty[f"at {t}"] += 1
                kept[f"at {t}"] += a.get("kept", False)
            if p["alarm"]["flag_without_action"]:
                reply = readable(arm["calls"][(case, chain, p["point"], "alarm")])
                whole = reply is not None and (reply.get("reasoning") or "").rstrip().endswith(SENTENCE_ENDS)
                no_action[f"at {t}, {'whole' if whole else 'cut'}"] += 1
        if not r["failed"]:
            shows = next((p["point"] for p in r["passes"] if p["alarm"]["actions"]), None)
            first.setdefault(case, Counter())[f"at {t}: {'never' if shows is None else f'pass {shows}'}"] += 1
    return {"failed_chains": failed_by_temperature(arm), "cut_mid_sentence": dict(sorted(cut.items())),
            "counted_apart": dict(sorted(apart.items())), "empty_lists": dict(sorted(empty.items())),
            "kept_lists": dict(sorted(kept.items())), "time_critical_no_action": dict(sorted(no_action.items())),
            "first_alarm": {case: dict(sorted(c.items())) for case, c in first.items()},
            "same_answer_at_0": same_answer(score.chains_at(arm["results"], 0.0))}


def failed_by_temperature(arm: dict) -> dict:
    found = {}
    for (case, chain), r in sorted(arm["results"].items()):
        if r["failed"]:
            found.setdefault(f"at {r.get('temperature')}", []).append(f"{case}/{chain}")
    return found


def same_answer(at_zero: dict) -> list[str]:
    """The cases where every chain at 0 gave the same differential names
    and the same alarm actions at every pass. Needs two chains at least."""
    cases = sorted({case for case, _ in at_zero})
    same = []
    for case in cases:
        mine = [r for (c, _), r in sorted(at_zero.items()) if c == case]
        answers = {json.dumps([[p["names"], p["alarm"]["raw_actions"]] for p in r["passes"]], sort_keys=True)
                   for r in mine}
        if len(mine) >= 2 and len(answers) == 1:
            same.append(case)
    return same


# -------------------------------------------------------------- all of it

def one_arm(arm: dict, rounds: dict) -> dict:
    scored = score.summary(arm["results"])
    mine = rounds_of(arm, rounds)
    return {"candidate": scored["candidate"], "at_temperature_0": scored["at_temperature_0"],
            "stress_test": scored["stress_test"],
            "all_chains": {"chains": scored["chains"], "hard_met": scored["hard_met"], "soft_met": scored["soft_met"],
                           "time_met": scored["time_met"], "failed": scored["failed_chains"],
                           "marks": {m["n"]: m["value"] for m in scored["marks"]}},
            "rounds": mine, "typical_ms_by_round": typicals(mine),
            "typical_of_495_all_chains_ms": score.med([p["wall_ms"] for r in arm["results"].values()
                                                       if r["group"] == TYPICAL_OF for p in r["passes"]]),
            "per_token": {f"at {t}": per_token(calls_of(arm, {ch for _, ch in score.chains_at(arm["results"], t)}))
                          for t in sorted({r.get("temperature") for r in arm["results"].values()}, key=str)},
            "per_token_all": per_token(calls_of(arm)), "replies": from_replies(arm)}


def figures(rounds: dict, arms: dict) -> dict:
    """The figures of the public report, from the rounds file and the
    arms, whichever form they were read from."""
    missing = [name for name in rounds["arms"] if name not in arms]
    if missing:
        raise FiguresRefused(f"the rounds file names arms that were not given: {', '.join(missing)}")
    found = {name: one_arm(arms[name], rounds) for name in rounds["arms"]}
    steady = steadiness(found[rounds["baseline"]]["typical_ms_by_round"])
    return {"rules": {"faster_by_ms": FASTER_BY_MS, "steady_within_ms": STEADY_WITHIN_MS, "typical_of": TYPICAL_OF,
                      "sentence_ends": list(SENTENCE_ENDS)},
            "rounds": rounds["rounds"], "roles": rounds["arms"], "baseline": rounds["baseline"],
            "baseline_together": rounds.get("baseline_together"),
            "steadiness": steady, "judgements": judgements(rounds, found, steady["steady"]), "arms": found}


def write(out: Path, found: dict) -> None:
    """figures.json and figures.md, never over a file that exists."""
    out = Path(out)
    for name in ("figures.json", "figures.md"):
        if (out / name).exists():
            raise Refused(f"{out / name} exists and is never written over")
    out.mkdir(parents=True, exist_ok=True)
    (out / "figures.json").write_text(json.dumps(found, indent=1, ensure_ascii=False) + "\n",
                                      encoding="utf-8", newline="\n")
    (out / "figures.md").write_text(as_markdown(found), encoding="utf-8", newline="\n")


# ---------------------------------------------------------------- in words

def seconds(ms, places: int = 2) -> str:
    """Milliseconds as seconds, rounded half up once, from the decimal form
    of the number and not its binary form: 2,295 ms is 2.30 s, 1,605 is
    1.61. A median that ends in half a millisecond rounds the same way."""
    if ms is None:
        return "-"
    return str((Decimal(str(ms)) / 1000).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))


def two_places(value) -> str:
    """A time for each token, always with two places: 6.20, not 6.2."""
    return "-" if value is None else f"{value:.2f}"


def shorter_in_words(shorter_by_ms: list) -> str:
    """A difference below zero is written as longer, never as shorter by a
    negative number (HANDOVER, stage 3b)."""
    parts = []
    for d in shorter_by_ms:
        if d is None:
            parts.append("no figure")
        elif d >= 0:
            parts.append(f"{seconds(d)} s shorter")
        else:
            parts.append(f"{seconds(-d)} s longer")
    return ", then ".join(parts)


def as_markdown(found: dict) -> str:
    return "".join((candidates_in_words(found), judgements_in_words(found), rounds_table(found),
                    replies_in_words(found)))


def candidates_in_words(found: dict) -> str:
    lines = ["## Who is a candidate (Rule A, ruling 18)", ""]
    for name, arm in found["arms"].items():
        lines.append(f"- {name}: {score.candidate_line(arm['at_temperature_0'])}")
        stress = arm["stress_test"]
        if stress["chains"]:
            lines.append(f"  The stress test at 0.5, apart: {stress['chains']} chains; hard marks missed: "
                         f"{', '.join(stress['missed']) or 'none'}; failed: {', '.join(stress['failed']) or 'none'}. "
                         f"It bars nothing.")
    return "\n".join(lines) + "\n\n"


def judgements_in_words(found: dict) -> str:
    steady = found["steadiness"]
    base = found["baseline"]
    by_round = ", ".join(seconds(t) for t in steady["typical_ms_by_round"])
    lines = ["## Is an arm faster (Rule B, rulings 17 and 21)", ""]
    if steady["spread_ms"] is None:
        lines.append(f"The steadiness of the day cannot be judged: {base} has no typical pass in some round.")
    elif steady["steady"]:
        lines.append(f"The day was steady: the typical pass of {base} was {by_round} s in the three rounds, "
                     f"within {seconds(steady['spread_ms'])} s (the line is {seconds(steady['line_ms'])} s).")
    else:
        lines.append(f"The day was unsteady: the typical pass of {base} was {by_round} s in the three rounds, "
                     f"{seconds(steady['spread_ms'])} s apart, over the {seconds(steady['line_ms'])} s line. "
                     f"No arm is called faster.")
    lines.append("")
    for j in found["judgements"]:
        mine, theirs = ", ".join(seconds(t) for t in j["typical_ms"]), ", ".join(seconds(t) for t in j["against_typical_ms"])
        line = (f"- {j['arm']} ({mine} s) against {j['against']} ({theirs} s): {shorter_in_words(j['shorter_by_ms'])}. ")
        if j["faster"]:
            line += f"Faster by the rule: at least {seconds(FASTER_BY_MS)} s shorter in each of the three rounds."
        elif j["verdict"] == "a figure, not a win":
            line += f"Not called faster: under {seconds(FASTER_BY_MS)} s in at least one round. A figure, not a win."
        elif j["verdict"].startswith("not a candidate"):
            line += "Not a candidate, so not called faster."
        else:
            line += "The day was unsteady, so not called faster."
        lines.append(line)
    return "\n".join(lines) + "\n\n"


def rounds_table(found: dict) -> str:
    lines = ["## The seconds, round by round", "",
             "Typical = the median of the passes of consultation 495 in the round's chain at temperature 0, in seconds. "
             "Beside it the median over all cases, each call's median, the tokens written in the chain, and the "
             "milliseconds for each token written, all in and writing only.", "",
             "| arm | round | chain | typical | slowest | all cases | alarm | assessment | tokens written | ms/token all in | ms/token writing |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, arm in found["arms"].items():
        for number, r in arm["rounds"].items():
            if r is None:
                lines.append(f"| {name} | {number} | - | not run | | | | | | | |")
                continue
            t = r["per_token"]
            lines.append(f"| {name} | {number} | {r['chain']} | {seconds(r['typical_ms'])} | {seconds(r['slowest_ms'])} | "
                         f"{seconds(r['all_cases_median_ms'])} | {seconds(r['alarm_median_ms'])} | "
                         f"{seconds(r['assessment_median_ms'])} | {t['tokens_written']:,} | "
                         f"{two_places(t['ms_per_token_all_in'])} | {two_places(t['ms_per_token_writing'])} |")
    lines += ["", "Over all chains at each temperature: tokens written, ms for each token all in and writing only.", ""]
    for name, arm in found["arms"].items():
        parts = [f"{label}: {t['tokens_written']:,} tokens, {two_places(t['ms_per_token_all_in'])} and {two_places(t['ms_per_token_writing'])} ms"
                 for label, t in arm["per_token"].items() if t["calls"]]
        lines.append(f"- {name}: " + "; ".join(parts) + ".")
    return "\n".join(lines) + "\n\n"


def replies_in_words(found: dict) -> str:
    def said(counts: dict) -> str:
        return "; ".join(f"{k}: {v}" for k, v in counts.items()) or "none"

    lines = ["## From the replies", ""]
    for name, arm in found["arms"].items():
        r = arm["replies"]
        lines += [f"- {name}: chains failed {said({k: len(v) for k, v in r['failed_chains'].items()})}. "
                  f"Replies cut mid-sentence {said(r['cut_mid_sentence'])}. Counted apart {said(r['counted_apart'])}. "
                  f"Empty lists {said(r['empty_lists'])}; kept {said(r['kept_lists'])}. "
                  f"Time critical with no action {said(r['time_critical_no_action'])}. "
                  f"Same answer in every chain at 0: {len(r['same_answer_at_0'])} cases."]
    names = list(found["arms"])
    cases = sorted({case for arm in found["arms"].values() for case in arm["replies"]["first_alarm"]})
    lines += ["", "The pass at which the alarm first shows, by temperature (count of chains):", "",
              "| case | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for case in cases:
        lines.append(f"| {case} | " + " | ".join(said(found["arms"][n]["replies"]["first_alarm"].get(case, {}))
                                                  for n in names) + " |")
    return "\n".join(lines) + "\n"
