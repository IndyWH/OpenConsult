"""The line for Alba (spec 15.9, ruling 29; 13.3 mark 5; the details of
5e). For a live arm, and for every speech of the patient that a speech of
the doctor follows: the seconds from the end of the patient's last word
to the moment the last line of that speech was final. The end of the
last word is taken two ways, side by side: the choice's own time for it,
and the sound itself, from the stored loudness. A reading only: the line
itself is set at stage 12. The replay may flatter a choice: a doctor's
reply can close the patient's line, and in auto mode nobody speaks until
the questioner does; so a line that was final only after the reply had
begun is counted, and counts as late for the yes or no."""

from __future__ import annotations

import statistics

from openconsult.bench.speech.pages import Page
from openconsult.bench.speech.reference import Reference
from openconsult.bench.speech.waits import live_lines
from openconsult.speech.loudness import QUIET_DBFS
from openconsult.speech.matching import normalise

WITHIN_S = (0.8, 1.5, 3.0)       # 0.8 is what a call of 2.2 s leaves of the questioner's 3 (D32)
SERVES_WITHIN_S = WITHIN_S[0]
LEAST_PAUSE_S = 0.2              # a run of quiet windows this long is a pause
LATE = float("inf")


def _lines_with_speeches(result: dict, reference: Reference, live_page: Page) -> list[dict]:
    """Every live line with the speeches of its heard words, in order."""
    found, offset = [], 0
    for line in live_lines(result):
        words = normalise(line["text"], reference.joinable)
        speeches = [reference.words[live_page.spoken_of[offset + k]].speech for k in range(len(words))
                    if live_page.kind_of.get(offset + k) == "heard" and (offset + k) in live_page.spoken_of]
        offset += len(words)
        found.append({**line, "speeches": speeches})
    return found


def quiet_runs(windows: list[float | None], window_s: float, start_s: float, end_s: float,
               threshold: float = QUIET_DBFS, least_s: float = LEAST_PAUSE_S) -> list[tuple[float, float]]:
    """The runs of quiet windows of least_s or more inside the stretch, cut
    at its two ends."""
    first, last = max(0, int(round(start_s / window_s))), min(len(windows), int(round(end_s / window_s)))
    runs, begun = [], None
    for index in range(first, last + 1):
        quiet = index < last and (windows[index] is None or windows[index] <= threshold)
        if quiet and begun is None:
            begun = index
        elif not quiet and begun is not None:
            if (index - begun) * window_s >= least_s - 1e-9:
                runs.append((round(begun * window_s, 3), round(index * window_s, 3)))
            begun = None
    return runs


def speeches_of(result: dict, reference: Reference, live_page: Page) -> list[dict]:
    """One row for each speech of the patient that a speech of the doctor
    follows."""
    windows, window_s = result["loudness"]["dbfs"], result["loudness"]["window_s"]
    slack = float(result.get("time_slack_s") or 0.0)
    lines = _lines_with_speeches(result, reference, live_page)
    rows = []
    for index, speech in enumerate(reference.speeches[:-1]):
        reply = reference.speeches[index + 1]
        if speech.speaker != "PATIENT" or reply.speaker != "DOCTOR":
            continue
        row = {"speech": speech.number, "t_final": None, "by_choice": None, "by_sound": None, "apart_choice": None,
               "apart_sound": None, "after_reply": None}
        holding = [i for i, line in enumerate(lines) if speech.number in line["speeches"]]
        if not holding:
            row["apart_choice"] = row["apart_sound"] = "no word of the speech was heard"
            rows.append(row)
            continue
        last = lines[holding[-1]]
        row["t_final"] = last["t"]
        runs_on = any(number > speech.number for number in last["speeches"])
        reply_line = next((line for line in lines[holding[-1]:] if reply.number in line["speeches"]), None)
        if runs_on:
            row["apart_choice"] = row["apart_sound"] = "the line runs on into the doctor's words"
            row["after_reply"] = True
            rows.append(row)
            continue
        row["end_choice"] = last["end"]
        row["by_choice"] = round(last["t"] - last["end"], 3)
        bound = (reply_line["start"] if reply_line is not None else last["end"] + 3.0) + slack
        runs = quiet_runs(windows, window_s, (last["start"] + last["end"]) / 2 - slack, bound)
        reply_began = reply_line["start"] if reply_line is not None else None
        if runs:
            # The last pause before the reply: a pause inside the patient's sentence never moves the end back.
            row["end_sound"], reply_by_sound = runs[-1]
            row["by_sound"] = round(last["t"] - row["end_sound"], 3)
            if reply_line is not None and reply_by_sound < bound:
                reply_began = reply_by_sound
        else:
            row["apart_sound"] = "no pause was found before the reply"
        row["after_reply"] = reply_began is not None and last["t"] > reply_began
        rows.append(row)
    return rows


def _counted(values: list[float]) -> dict:
    return {"n": len(values), "median": round(statistics.median(values), 3) if values else None,
            "longest": round(max(values), 3) if values else None,
            "within": {str(limit): sum(1 for v in values if v <= limit) for limit in WITHIN_S}}


def summary(rows: list[dict]) -> dict:
    """The typical and the longest, the counts within each figure, the
    speeches counted apart, and the reading: serves Alba, yes or no. Yes
    when the typical wait is within SERVES_WITHIN_S, by the sound; a
    speech whose line was final only after the reply had begun counts as
    late whatever its seconds. If more than half of the speeches have no
    pause in the sound, the reading is taken by the choice's own time."""
    found = {"speeches": len(rows), "after_reply": sum(1 for r in rows if r["after_reply"]),
             "by_choice": _counted([r["by_choice"] for r in rows if r["by_choice"] is not None]),
             "by_sound": _counted([r["by_sound"] for r in rows if r["by_sound"] is not None]), "apart": {}}
    for way in ("apart_choice", "apart_sound"):
        for row in rows:
            if row[way]:
                found["apart"].setdefault(way, {}).setdefault(row[way], 0)
                found["apart"][way][row[way]] += 1
    no_pause = sum(1 for r in rows if r["apart_sound"] == "no pause was found before the reply")
    way = "by_choice" if rows and no_pause > len(rows) / 2 else "by_sound"
    judged = [LATE if row["after_reply"] else row[way] for row in rows if row[way] is not None or row["after_reply"]]
    found["serves"] = {"by": "the choice's own time" if way == "by_choice" else "the sound",
                       "why": "more than half of the speeches had no pause in the sound" if way == "by_choice" else None,
                       "judged": len(judged), "late_after_reply": sum(1 for v in judged if v == LATE),
                       "typical": None if not judged else (None if statistics.median(judged) == LATE
                                                           else round(statistics.median(judged), 3)),
                       "yes": bool(judged) and statistics.median(judged) <= SERVES_WITHIN_S}
    return found
