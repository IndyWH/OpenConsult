"""The marks of the letters bench (spec 15.12, ruling 10), read from the
stored results alone, the marks fixed as numbers before the run
(STAGE8A_PLAN, 28 Oct 2026, item 6; the plan review, points 1 and 2). A
chain holds a mark when every letter of it does, so every mark is n of
13 per case. What a model said is counted here, never asserted in a
test."""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from openconsult.consult import letter_check
from openconsult.consult.referrals import holds_words

CHAINS = 13
MARK_PLACEHOLDER_ABSENT = 12     # M2: the placeholder absent in at least 12 of 13
CASE_A = "A_hypo"                # M4: the one note with no expectations line


class MarksRefused(Exception):
    pass


def failed_call(chain: dict) -> bool:
    return bool(chain["list"].get("failure")) or any(l.get("failure") for l in chain["letters"])


def refused(chain: dict) -> bool:
    return any(l.get("refused") for l in chain["letters"])


def placeholder(chain: dict) -> bool:
    return any(l.get("placeholders", 0) > 0 for l in chain["letters"])


def cites_assessment(chain: dict) -> bool:
    return any(letter_check.cites_assessment(l.get("check_detail")) for l in chain["letters"])


def number_outside(chain: dict) -> bool:
    return any(letter_check.NUMBER in letter_check.reasons_of(l.get("check_detail")) for l in chain["letters"])


def upgrade(chain: dict) -> bool:
    return any(letter_check.UPGRADE in letter_check.reasons_of(l.get("check_detail")) for l in chain["letters"])


def _expectation_in(paragraphs) -> bool:
    texts = [p["text"] if isinstance(p, dict) else str(p) for p in (paragraphs or [])]
    return any(letter_check.expectation_sentence(s) for t in texts for s in letter_check.sentences_of(t))


def expectation_model(chain: dict) -> bool:
    return any(_expectation_in(l.get("model_body")) for l in chain["letters"])


def expectation_checked(chain: dict) -> bool:
    return any(_expectation_in(l.get("body")) for l in chain["letters"])


def stated_found(chain: dict, specialty: str) -> bool:
    """A stated item whose specialty holds the expected word and whose
    lines hold a Plan line whose words hold it."""
    plan = {line["n"]: line["text"] for line in chain["lines"] if line["section"] == "plan" and not line["heading"]}
    for item in chain["list"]["items"]:
        if item["kind"] != "stated" or not holds_words(item["specialty"], specialty):
            continue
        if any(n in plan and holds_words(plan[n], specialty) for n in item["lines"]):
            return True
    return False


def stated_ok(chain: dict) -> bool:
    """M5: every expected specialty found with its plan line; with none
    expected, an empty stated list."""
    expected = [s for s in (chain.get("expected") or {}).get("stated_referrals", []) if s]
    if not expected:
        return not any(i["kind"] == "stated" for i in chain["list"]["items"])
    return all(stated_found(chain, s) for s in expected)


def case_table(results: dict, case: str) -> dict:
    chains = [r for (name, _), r in sorted(results.items()) if name == case]
    list_walls = [r["list"]["wall_ms"] for r in chains]
    letter_walls = [l["wall_ms"] for r in chains for l in r["letters"]]
    outputs = [c.get("output_tokens") or 0 for r in chains for c in [r["list"], *r["letters"]]]
    return {"chains": len(chains), "failed_call": sorted(r["chain"] for r in chains if failed_call(r)),
            "letters": sum(len(r["letters"]) for r in chains),
            "refused": sum(refused(r) for r in chains), "placeholder": sum(placeholder(r) for r in chains),
            "assessment_cited": sum(cites_assessment(r) for r in chains), "number_outside": sum(number_outside(r) for r in chains),
            "upgrade": sum(upgrade(r) for r in chains),
            "expectation_model": sum(expectation_model(r) for r in chains), "expectation_checked": sum(expectation_checked(r) for r in chains),
            "stated_ok": sum(stated_ok(r) for r in chains),
            "suggested": statistics.median([sum(i["kind"] == "suggested" for i in r["list"]["items"]) for r in chains]) if chains else None,
            "list_s": round(statistics.median(list_walls) / 1000, 2) if list_walls else None,
            "letter_s": round(statistics.median(letter_walls) / 1000, 2) if letter_walls else None,
            "longest_s": round(max(list_walls + letter_walls) / 1000, 2) if letter_walls or list_walls else None,
            "longest_reply_tokens": max(outputs) if outputs else None}


def score(results: dict) -> dict:
    """The table for each case and the five marks, each n of 13 per case."""
    cases = sorted({name for name, _ in results})
    if not cases:
        raise MarksRefused("no result to score")
    tables = {case: case_table(results, case) for case in cases}
    marks = []
    for case in cases:
        t = tables[case]
        full = t["chains"] == CHAINS
        marks.append({"mark": "M1", "case": case, "text": f"no letter refused and no failed call, {CHAINS} of {CHAINS}",
                      "figure": f"{t['chains'] - t['refused'] - len(t['failed_call'])} of {t['chains']}",
                      "held": full and t["refused"] == 0 and not t["failed_call"]})
        marks.append({"mark": "M2", "case": case, "text": f"the placeholder absent, at least {MARK_PLACEHOLDER_ABSENT} of {CHAINS}",
                      "figure": f"{t['chains'] - t['placeholder']} of {t['chains']}",
                      "held": full and t["chains"] - t["placeholder"] >= MARK_PLACEHOLDER_ABSENT})
        marks.append({"mark": "M3", "case": case, "text": f"no citation into Assessment and no number outside the cited lines, {CHAINS} of {CHAINS}",
                      "figure": f"{t['chains'] - t['assessment_cited']} and {t['chains'] - t['number_outside']} of {t['chains']}",
                      "held": full and t["assessment_cited"] == 0 and t["number_outside"] == 0})
        if case == CASE_A:
            marks.append({"mark": "M4", "case": case, "text": f"no expectation sentence in the model's body, {CHAINS} of {CHAINS}",
                          "figure": f"{t['chains'] - t['expectation_model']} of {t['chains']}",
                          "held": full and t["expectation_model"] == 0})
        marks.append({"mark": "M5", "case": case, "text": f"the stated list as expected, {CHAINS} of {CHAINS}",
                      "figure": f"{t['stated_ok']} of {t['chains']}", "held": full and t["stated_ok"] == CHAINS})
    return {"cases": tables, "marks": marks, "held": all(m["held"] for m in marks)}


def as_markdown(marked: dict) -> str:
    lines = ["| case | chains | failed call | letters | refused | placeholder | Assessment cited | number outside | upgrade | "
             "expectation (model) | expectation (checked) | stated as expected | suggested (median) | list s | letter s | longest s | longest reply tokens |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for case, t in marked["cases"].items():
        lines.append(f"| {case} | {t['chains']} | {', '.join(t['failed_call']) or 'none'} | {t['letters']} | {t['refused']} | {t['placeholder']} | "
                     f"{t['assessment_cited']} | {t['number_outside']} | {t['upgrade']} | {t['expectation_model']} | {t['expectation_checked']} | "
                     f"{t['stated_ok']} | {t['suggested']} | {t['list_s']} | {t['letter_s']} | {t['longest_s']} | {t['longest_reply_tokens']} |")
    lines.append("")
    for m in marked["marks"]:
        lines.append(f"- Mark {m['mark']}, {m['case']}, {m['text']}: {m['figure']}: {'held' if m['held'] else 'MISSED'}")
    lines.append(f"- Every mark {'held' if marked['held'] else 'did not hold'}.")
    return "\n".join(lines) + "\n"


def write(folder: Path, marked: dict) -> None:
    """marks.json and marks.md, never over a file that exists."""
    folder = Path(folder)
    for name in ("marks.json", "marks.md"):
        if (folder / name).exists():
            raise MarksRefused(f"{folder / name} exists and is never written over")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "marks.json").write_text(json.dumps(marked, indent=1, ensure_ascii=False), encoding="utf-8")
    (folder / "marks.md").write_text(as_markdown(marked), encoding="utf-8")
