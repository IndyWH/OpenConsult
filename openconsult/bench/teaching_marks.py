"""The counts of the teaching bench (spec 15.14, ruling 14 and the details
of run 10a; the README of the bench material): from the stored files
alone, no engine. Code counts wherever the answer is a number: hard mark
four, hard mark five, the counted part of hard mark six, and the counts
the README lists. Hard marks one to three, and whether a fresh case is
clinically right, are Cowork's to read and are never judged here.

What the README leaves unclear is counted apart and never as a hard mark
(the plan of run 10a, item 11, as mail 2 settled it). A reply that is
not the form is counted there and in no other count.

The feedback is counted twice where the two can differ (mails 3 and 4 of
the run): RAW, on the answer as the model gave it, and SHOWN, on what a
learner would be shown by the rule of teaching/shown.py. Hard mark five
is judged on SHOWN: a red flag the learner did not ask about, shown as
met. A turn that is not the doctor's is counted RAW only, because the
rule drops it before a learner sees it."""

from __future__ import annotations

import json
import re
import statistics
from pathlib import Path

from openconsult.bench import teaching
from openconsult.bench.writer import ResultWriter
from openconsult.llm.jobs import job as job_named
from openconsult.prompts import loader
from openconsult.teaching import frames, shown

NUMBER = r"(?<![\w.,])\d+(?:[.,]\d+)?\s*"
# Hard mark six as the README writes it: a number followed by one of these six, as whole words.
DOSE = re.compile(NUMBER + r"(?:mg|microgram|g|ml|unit|units)\b", re.IGNORECASE)
# Near forms, counted apart and never as the mark.
NEAR = re.compile(NUMBER + r"(?:micrograms|mcg|µg|μg|grams?|milligrams?|millilitres?|milliliters?|iu|international units?)\b", re.IGNORECASE)
PIECES = re.compile(r"[,;()/]|\bor\b|\band\b", re.IGNORECASE)
LISTS = ("differential", "investigations", "plan")
CASE_REPLIES, CASE_EXAMINATIONS = 30, 3      # one whole teaching case, as the details count it: one case, 30 replies, 3 examinations, one feedback


class MarksRefused(Exception):
    pass


def file_of(row: dict) -> str:
    return f"{row['part']}__{row['case']}__{row['item']}__r{row['round']}__{row['arm']}.json"


def plain(text: str) -> str:
    """Words alone, in small letters, one space between: for finding one text in another."""
    return " ".join(re.findall(r"[a-z0-9']+", str(text).lower()))


def texts_in(part, where: str = ""):
    """Every text a part of a case holds, each with where it stands."""
    if isinstance(part, dict):
        for key, value in part.items():
            yield from texts_in(value, f"{where}.{key}" if where else key)
    elif isinstance(part, list):
        for n, value in enumerate(part, 1):
            yield from texts_in(value, f"{where}[{n}]")
    elif isinstance(part, str):
        yield where, part


# ------------------------------------------------------------ one reply

def actor_marks(row: dict, case: dict) -> dict:
    line = next(found for found in case["bench"]["lines"] if f"line{found['n']:02d}" == row["item"])
    marks = {"agenda_closed": line["kind"] == "agenda_closed"}
    if not row["ok"]:
        return {**marks, "A1_not_the_form": True}
    used, facts = set(row["answer"]["facts_used"]), len(case["scenario"]["facts"])
    said, opening = plain(row["answer"]["reply"]), re.split(r"[.!?]+", case["scenario"]["opening_words"])
    return {**marks,
            "A2_a_number_the_card_does_not_have": sorted(n for n in used if n < 1 or n > facts),
            "A3_none_of_the_facts_expected": line["kind"] in ("open", "direct") and bool(line["expects_any"]) and not used & set(line["expects_any"]),
            "A4_a_fact_forbidden_at_this_line": sorted(used & set(line["forbids"])),
            "A5_an_absent_line_with_a_fact": line["kind"] == "absent" and bool(used),
            # Mail 2, point 3: at the first line, a reply that says a whole sentence of the opening words again (four words or more).
            "first_line_says_the_opening_words_again": line["n"] == 1 and any(
                len(plain(sentence).split()) >= 4 and plain(sentence) in said for sentence in opening)}


def examination_marks(row: dict, case: dict) -> dict:
    request = case["bench"]["examination_requests"][int(row["item"].removeprefix("request")) - 1]
    if not row["ok"]:
        return {"E0_not_the_form": True}
    asked, extra, expects = set(row["answer"]["asked"]), row["answer"]["not_in_case"], set(request["expects"])
    held, neither = bool(request["held"]), bool(request.get("neither"))
    findings = len(case["scenario"]["examination"]) + len(case["scenario"]["results"])
    missing = sorted(expects - asked)
    return {"HARD_MARK_FOUR": held and bool(missing) and bool(extra),
            "E1_an_expected_finding_missing": missing,
            "E2_a_finding_not_expected": sorted(asked - expects),
            "E3_not_held_but_a_finding_given": not held and not neither and bool(asked),
            "E4_not_an_examination_but_listed": neither and bool(asked or extra),
            "apart_held_nothing_missing_but_not_in_case_filled": held and not missing and bool(extra),
            "apart_a_number_the_case_does_not_have": sorted(n for n in asked if n < 1 or n > findings)}


def feedback_marks(row: dict, case: dict) -> dict:
    bench = case["bench"]
    transcript = next(found for found in bench["transcripts"] if found["name"] == row["item"])
    answers = next(found for found in bench["answers"] if found["name"] == transcript["answers"])
    if not row["ok"]:
        return {"F0_not_the_form": True}
    answer, verdicts = row["answer"], {}
    for point in answer["points"]:
        verdicts.setdefault(point["number"], []).append(point["met"])
    points = sum(len(case["scenario"]["marking_points"][heading]) for heading in frames.HEADINGS)
    spoken = teaching.conversation(case, transcript["lines"])
    doctors = shown.doctors_turns(spoken)
    # SHOWN: what a learner would be shown, by the rule that stands between the answer and the page (mail 3).
    seen = {point["number"]: point["met"] for point in shown.shown(answer, spoken, points)["points"]}
    expects_met, not_met = transcript.get("expects_met", []), set(transcript.get("expects_not_met", []))
    asserted, red = transcript.get("expects_most_important_missed"), set(bench.get("red_flag_points", [])) & not_met
    returned = [turn for point in answer["points"] for turn in point["turns"]] + list(answer["signpost_turns"])
    raw_missed = sorted(p for p in expects_met if verdicts.get(p) and not all(verdicts[p]))      # it came back, and not met
    shown_missed = sorted(p for p in expects_met if not seen[p])
    marks = {"HARD_MARK_FIVE_SHOWN_a_red_flag_shown_as_met": sorted(p for p in red if seen[p]),
             "RAW_a_red_flag_returned_met": sorted(p for p in red if any(verdicts.get(p, []))),
             "RAW_ONLY_a_turn_that_is_not_the_doctors": sorted({turn for turn in returned if turn not in doctors}),
             "F1_RAW_expected_met_returned_not_met": raw_missed,
             "F1_SHOWN_expected_met_shown_not_met": shown_missed,
             "F1_of_which_made_by_the_rule": sorted(set(shown_missed) - set(raw_missed)),
             "F2_RAW_expected_not_met_returned_met": sorted(p for p in not_met if any(verdicts.get(p, []))),
             "F2_SHOWN_expected_not_met_shown_met": sorted(p for p in not_met if seen[p]),
             "F3_most_important_missed_differs": asserted is not None and answer["most_important_missed"] not in {asserted, *bench.get("points_not_asserted", [])},
             "RAW_points_not_returned": sorted(set(range(1, points + 1)) - set(verdicts)),
             "RAW_points_returned_twice": sorted(p for p, found in verdicts.items() if len(found) > 1),
             "RAW_points_the_case_does_not_have": sorted(p for p in verdicts if p < 1 or p > points),
             "SHOWN_signposting_taken_away": bool(answer["signposted"]) and not any(turn in doctors for turn in answer["signpost_turns"])}
    for name in LISTS:
        named = {entry["number"] for entry in answer[name] if entry["named"]}
        marks[f"F4_{name}_named_differs"] = named != set(answers[f"expects_{name}"])
    return marks


def writer_marks(row: dict) -> dict:
    if not row["ok"]:
        return {"W4_not_the_form": True, "W4_of_which_cut_at_the_limit": row["failure"] == "too_long"}
    case = row["answer"]
    one = plain(" ".join(text for _, text in texts_in(frames.part_one(case))))
    whole = [found["diagnosis"] for found in case["differential"] if plain(found["diagnosis"]) and plain(found["diagnosis"]) in one]
    pieces = [found["diagnosis"] for found in case["differential"] if found["diagnosis"] not in whole
              and any(len(plain(piece)) >= 4 and plain(piece) in one for piece in PIECES.split(found["diagnosis"]))]
    elsewhere = [where for where, text in texts_in({key: value for key, value in case.items() if key != "plan"})
                 if DOSE.search(text) or NEAR.search(text)]
    return {"HARD_MARK_SIX_a_dose_in_the_plan": [n for n, step in enumerate(case["plan"], 1) if DOSE.search(step["step"])],
            "apart_a_near_form_of_a_dose_in_the_plan": [n for n, step in enumerate(case["plan"], 1) if NEAR.search(step["step"])],
            "apart_a_dose_elsewhere_in_the_case": elsewhere,
            "W1_a_diagnosis_whole_in_part_one": whole,
            "apart_a_piece_of_a_diagnosis_in_part_one": pieces,
            "W2_a_heading_with_fewer_than_three_or_more_than_six_points": [
                heading for heading in frames.HEADINGS if not 3 <= len(case["marking_points"][heading]) <= 6],
            "W3_a_differential_of_fewer_than_three_or_more_than_five": not 3 <= len(case["differential"]) <= 5}


def fresh_row(row: dict) -> dict:
    """One line of the table of fresh scenarios (mail 2): nothing is judged by it."""
    expected, case = row["expected"], row["answer"] if row["ok"] else None
    found = {"file": file_of(row), "run": expected.get("n"), "topic": expected.get("topic"), "level": expected.get("level")}
    if case is None:
        return {**found, "form": False}
    return {**found, "form": True, "age": case["patient"]["age"], "sex": case["patient"]["sex"],
            "first_diagnosis": case["differential"][0]["diagnosis"] if case["differential"] else None, "facts": len(case["facts"]),
            "marking_points": sum(len(case["marking_points"][heading]) for heading in frames.HEADINGS)}


# ------------------------------------------------------------ one arm

def counted(rows: list[dict], marks_of) -> dict:
    """Each count of a part: the stored files it holds, with what was found in each."""
    found: dict = {}
    for row in rows:
        for name, value in marks_of(row).items():
            found.setdefault(name, {})
            if value:
                found[name][file_of(row)] = value
    return {"calls": len(rows), **found}


def times(rows: list[dict]) -> dict:
    """For each job: the seconds typical and slowest, the tokens, and the longest reply beside the limits."""
    found = {}
    for part, job_name in teaching.JOB_OF.items():
        mine = [row for row in rows if row["part"] == part]
        if not mine:
            continue
        job = job_named(job_name)
        walls = [row["wall_ms"] for row in mine]
        read = [row["prompt_tokens"] for row in mine if row["prompt_tokens"] is not None]
        written = [row["output_tokens"] for row in mine if row["output_tokens"] is not None]
        found[job_name] = {"calls": len(mine), "the_form": sum(row["ok"] for row in mine), "held_thinking": sum(bool(row["thinking"]) for row in mine),
                           "failures": sorted({row["failure"] for row in mine if not row["ok"]}),
                           "wall_ms_median": round(statistics.median(walls)), "wall_ms_slowest": max(walls),
                           "tokens_read": sum(read), "tokens_written": sum(written),
                           "tokens_read_mean": round(statistics.mean(read)) if read else None,
                           "tokens_written_mean": round(statistics.mean(written)) if written else None,
                           "longest_reply_tokens": max(written, default=None), "limit_tokens": job.max_tokens,
                           "limit_s": job.timeout_s}
    return found


def rounds(rows: list[dict]) -> dict:
    """The rounds side by side: of the calls answered in the form in both, how many replies differ."""
    by_call: dict = {}
    for row in rows:
        by_call.setdefault((row["part"], row["case"], row["item"]), {})[row["round"]] = row
    found = {}
    for part in teaching.PARTS:
        pairs = [held for (of_part, _, _), held in sorted(by_call.items()) if of_part == part and 1 in held and 2 in held]
        both = [held for held in pairs if held[1]["ok"] and held[2]["ok"]]
        differ = [file_of(held[2]) for held in both if held[1]["answer"] != held[2]["answer"]]
        found[part] = {"in_both_rounds": len(pairs), "the_form_in_both": len(both), "replies_that_differ": len(differ), "files": differ}
    return found


def line_through(points: list[tuple[float, float]]) -> tuple[float, float] | None:
    """The straight line of least squares through the points: where it starts and how it rises."""
    if len({x for x, _ in points}) < 2:
        return None
    mean_x, mean_y = statistics.mean(x for x, _ in points), statistics.mean(y for _, y in points)
    rise = sum((x - mean_x) * (y - mean_y) for x, y in points) / sum((x - mean_x) ** 2 for x, _ in points)
    return mean_y - rise * mean_x, rise


def one_case(rows: list[dict], timed: dict) -> dict | None:
    """The tokens and the cost of one whole teaching case, as the details count it, by the means of this bench;
    and beside it an estimate, because a consultation of 30 replies reads more by its end than the bench's lines do."""
    jobs = [timed.get(name) for name in ("teaching_case", "teaching_patient", "teaching_examination", "teaching_feedback")]
    if any(job is None or job["tokens_read_mean"] is None or job["tokens_written_mean"] is None for job in jobs):
        return None
    case, patient, examination, feedback = jobs
    read = case["tokens_read_mean"] + CASE_REPLIES * patient["tokens_read_mean"] + CASE_EXAMINATIONS * examination["tokens_read_mean"] + feedback["tokens_read_mean"]
    written = (case["tokens_written_mean"] + CASE_REPLIES * patient["tokens_written_mean"]
               + CASE_EXAMINATIONS * examination["tokens_written_mean"] + feedback["tokens_written_mean"])
    found = {"tokens_read": read, "tokens_written": written, "us_cents": round(100 * teaching.dollars(read, written), 2)}
    replies = line_through([(int(row["item"].removeprefix("line")), row["prompt_tokens"]) for row in rows
                            if row["part"] == "actor" and row["prompt_tokens"] is not None])
    marked = line_through([(len(row["expected"]["lines"]), row["prompt_tokens"]) for row in rows
                           if row["part"] == "feedback" and row["prompt_tokens"] is not None])
    if replies and marked:
        longer = round(case["tokens_read_mean"] + sum(replies[0] + replies[1] * n for n in range(1, CASE_REPLIES + 1))
                       + CASE_EXAMINATIONS * examination["tokens_read_mean"] + marked[0] + marked[1] * CASE_REPLIES)
        found["estimate_for_30_lines"] = {"tokens_read": longer, "tokens_written": written,
                                          "us_cents": round(100 * teaching.dollars(longer, written), 2)}
    return found


def arm_marks(rows: list[dict], cases: dict) -> dict:
    of = {part: [row for row in rows if row["part"] == part] for part in teaching.PARTS}
    timed = times(rows)
    first = rows[0] if rows else {}
    return {"engine": first.get("engine"), "engine_version": first.get("engine_version"), "model": first.get("model_tag"),
            "model_digest": first.get("model_digest"), "calls": len(rows),
            "actor": counted(of["actor"], lambda row: actor_marks(row, cases[row["case"]])),
            "examination": counted(of["examination"], lambda row: examination_marks(row, cases[row["case"]])),
            "feedback": counted(of["feedback"], lambda row: feedback_marks(row, cases[row["case"]])),
            "writer": counted(of["writer"], writer_marks),
            "fresh": [fresh_row(row) for row in of["writer"]],
            "times": timed, "rounds": rounds(rows),
            "one_teaching_case": one_case(rows, timed) if first.get("engine") == "claude" else None,
            "dollars": round(teaching.dollars(sum(row["prompt_tokens"] or 0 for row in rows), sum(row["output_tokens"] or 0 for row in rows)), 4)}


# ------------------------------------------------------------ the proof of the words

def words(arms: dict[str, list[dict]]) -> dict:
    """Every stored request holds its job's prompt file letter for letter, and the arms were sent the same words
    for the same call. Read from the request as it crossed the wire. What a service adds by itself is outside this."""
    wrong_system, wrong_user, by_call = [], [], {}
    for rows in arms.values():
        for row in rows:
            system, user = teaching.wire_parts(row["request"])
            if system != loader.prompt(job_named(row["job"]).prompt):
                wrong_system.append(file_of(row))
            if user is None or user != row["user"]:
                wrong_user.append(file_of(row))
            by_call.setdefault((row["part"], row["case"], row["item"], row["round"]), []).append((file_of(row), user))
    shared = {call: found for call, found in by_call.items() if len(found) > 1}
    differ = sorted(found[0][0] for found in shared.values() if len({user for _, user in found}) > 1)
    return {"requests_read": sum(len(rows) for rows in arms.values()), "system_is_not_the_prompt_file": sorted(wrong_system),
            "user_is_not_the_words_built": sorted(wrong_user), "calls_sent_to_more_than_one_arm": len(shared),
            "arms_sent_different_words": differ, "held": not (wrong_system or wrong_user or differ)}


# ------------------------------------------------------------ all arms

HARD = {"four": ("examination", ("HARD_MARK_FOUR",)),
        # Judged on what a learner would be shown (the owner's ruling of 24 Nov 2026): a turn that is not the doctor's
        # cannot reach a learner by the rule of teaching/shown.py, and is counted RAW only.
        "five": ("feedback", ("HARD_MARK_FIVE_SHOWN_a_red_flag_shown_as_met",)),
        "six_the_counted_part": ("writer", ("HARD_MARK_SIX_a_dose_in_the_plan",))}


def score(arms: dict[str, list[dict]], material: teaching.Material) -> dict:
    cases = {case["id"]: case for case in material.cases}
    kept = {name: [row for row in rows if not row.get("trial")] for name, rows in arms.items()}
    marked = {name: arm_marks(rows, cases) for name, rows in kept.items()}
    hard = {name: {mark: sorted({file for count in counts for file in found[part].get(count, {})})
                   for mark, (part, counts) in HARD.items()} for name, found in marked.items()}
    return {"arms": marked, "hard_marks_code_can_count": hard, "words": words(kept),
            "prices": {"read": teaching.PRICE_READ, "written": teaching.PRICE_WRITTEN, "of": teaching.PRICES_OF},
            "held": not any(files for found in hard.values() for files in found.values())}


def _table(head: list[str], rows: list[list]) -> list[str]:
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows] + [""]


def _by_round(files: dict) -> str:
    """A count as total (round 1 + round 2)."""
    first = sum("__r1__" in name for name in files)
    return f"{len(files)} ({first} + {len(files) - first})"


def as_markdown(marked: dict) -> str:
    arms = list(marked["arms"])
    out = ["# The teaching bench: the counts", "",
           "From the stored files alone. A count is given as total (round 1 + round 2). Hard marks one to three are not counted here.", ""]
    out += ["## The hard marks code can count", ""] + _table(["hard mark", *arms], [
        [mark, *[len(marked["hard_marks_code_can_count"][arm][mark]) for arm in arms]] for mark in HARD])
    for arm in arms:
        for mark, files in marked["hard_marks_code_can_count"][arm].items():
            out += [f"- {arm}, hard mark {mark}: {name}" for name in files]
    for part in teaching.PARTS:
        names = sorted({name for arm in arms for name in marked["arms"][arm][part] if name != "calls"})
        out += ["", f"## {part}", ""] + _table(["count", *arms], [["calls", *[marked["arms"][arm][part]["calls"] for arm in arms]]] + [
            [name, *[_by_round(marked["arms"][arm][part].get(name, {})) for arm in arms]] for name in names])
    out += ["", "## The seconds and the tokens", ""] + _table(
        ["arm", "job", "calls", "the form", "typical s", "slowest s", "limit s", "read (mean)", "written (mean)", "longest reply", "limit"],
        [[arm, job, t["calls"], t["the_form"], round(t["wall_ms_median"] / 1000, 1), round(t["wall_ms_slowest"] / 1000, 1), t["limit_s"],
          t["tokens_read_mean"], t["tokens_written_mean"], t["longest_reply_tokens"], t["limit_tokens"]]
         for arm in arms for job, t in marked["arms"][arm]["times"].items()])
    out += ["## The two rounds side by side", ""] + _table(["arm", "part", "in both rounds", "the form in both", "replies that differ"], [
        [arm, part, r["in_both_rounds"], r["the_form_in_both"], r["replies_that_differ"]]
        for arm in arms for part, r in marked["arms"][arm]["rounds"].items() if r["in_both_rounds"]])
    for arm in arms:
        found = marked["arms"][arm]
        if found["one_teaching_case"]:
            out += [f"## One whole teaching case on {arm}", "", json.dumps(found["one_teaching_case"]), ""]
        out += [f"## The fresh scenarios of {arm}", ""] + _table(
            ["run", "topic", "level", "age", "sex", "first diagnosis", "facts", "marking points"],
            [[f["run"], f["topic"], f["level"], f.get("age", "not the form"), f.get("sex", ""), f.get("first_diagnosis", ""),
              f.get("facts", ""), f.get("marking_points", "")] for f in found["fresh"]])
    w = marked["words"]
    out += ["## The proof of the words", "", f"{w['requests_read']} stored requests read; the system part is not the prompt file in "
            f"{len(w['system_is_not_the_prompt_file'])}; the user part is not the words built in {len(w['user_is_not_the_words_built'])}; "
            f"{w['calls_sent_to_more_than_one_arm']} calls were sent to more than one arm, and the arms' words differ in "
            f"{len(w['arms_sent_different_words'])}. Held: {w['held']}.", ""]
    return "\n".join(out)


def write(folder: Path, marked: dict) -> None:
    """marks.json and marks.md, never over a file that exists."""
    folder = Path(folder)
    for name in ("marks.json", "marks.md"):
        if (folder / name).exists():
            raise MarksRefused(f"{folder / name} exists and is never written over")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "marks.json").write_text(json.dumps(marked, indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    (folder / "marks.md").write_text(as_markdown(marked), encoding="utf-8")


def read_arm(folder: Path) -> list[dict]:
    """The stored calls of an arm's folder, the trial's left out, in the order of their names."""
    held = ResultWriter(Path(folder)).read_all()
    return [row for (part, _), row in sorted(held.items()) if part != teaching.TRIAL]
