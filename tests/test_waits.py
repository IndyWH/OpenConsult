"""The wait, how exact the times are, and the signs counted (spec 13.3
mark 5; 15.9 ruling 12; the details of 5c). Made-up results only."""

from openconsult.bench.speech import waits
from openconsult.bench.speech.pages import build_page
from openconsult.bench.speech.reference import build
from openconsult.speech.missing import Gap, Stretch

SCRIPT = ("**DOCTOR:** If you get this pain at rest, go straight to the hospital.\n"
          "**PATIENT:** Understood doctor, straight to hospital.\n"
          "**DOCTOR:** Good. See you next week.\n")
REF = build(SCRIPT)


def piece(start, end, text, speaker=None):
    return {"start": start, "end": end, "text": text, "speaker": speaker}


def a_result():
    return {"pieces": [{"n": 2, "t": 0.5, "partial": "if you", "lines": []},
                       {"n": 3, "t": 0.75, "partial": "If you get this", "lines": []},
                       {"n": 5, "t": 1.25, "partial": "", "lines": [{"start": 0.1, "end": 1.0, "text": "If you get this pain"}]},
                       {"n": 9, "t": 2.25, "partial": "at rest go", "lines": []}],
            "stop": {"t": 3.0, "last_live": [{"start": 2.0, "end": 2.6, "text": "at rest, go straight"},
                                             {"start": 2.7, "end": 2.9, "text": "to the hospital"}],
                     "lines": [], "raw": []}}


def test_13_3_mark_5_the_wait_to_first_shown_runs_from_the_lines_start_to_final_from_its_end_and_the_true_times_go_to_the_first_and_last_line_of_a_speech():
    # Fix two of part two of 5c: the details of part one, corrected on 11 Oct 2026.
    found = waits.waits(a_result(), REF)
    rows = found["lines"]
    assert [(r["to_final"], r["to_first"]) for r in rows] == [(0.25, 0.4), (0.4, 0.25), (0.1, None)]
    assert rows[0]["t_first"] == 0.5 and rows[1]["t_first"] == 2.25 and found["never_shown"] == 1
    assert found["to_final"] == {"n": 3, "median": 0.25, "longest": 0.4}
    assert found["to_first"] == {"n": 2, "median": 0.325, "longest": 0.4}
    # The partial must hold the first two words in order and together.
    assert waits.first_shown([{"n": 1, "t": 0.1, "partial": "you if"}], 2, ["if", "you"]) is None
    assert waits.first_shown([{"n": 1, "t": 0.1, "partial": "if you"}, {"n": 3, "t": 0.3, "partial": "nothing"}], 4, ["if", "you"]) is None
    # On the made recording: the three lines are all of speech 1; only the
    # first gets the wait from the true start, only the last from the true end.
    live = build_page("live", [piece(0.1, 1.0, "If you get this pain"), piece(2.0, 2.6, "at rest, go straight"),
                               piece(2.7, 2.9, "to the hospital")], REF)
    true = waits.waits(a_result(), REF, live, true_times={1: (0.0, 2.8)})
    assert [r.get("speech") for r in true["lines"]] == [1, 1, 1]
    assert [r.get("to_first_true") for r in true["lines"]] == [0.5, None, None]
    assert [r.get("to_final_true") for r in true["lines"]] == [None, None, 0.2]
    assert true["to_final_true"] == {"n": 1, "median": 0.2, "longest": 0.2} and true["to_first_true"]["n"] == 1
    # A speech whose first line never showed has no wait from the true start.
    never = waits.waits(a_result(), REF, live, true_times={1: (0.0, 2.8)})
    assert all("to_first_true" not in r for r in never["lines"][1:])
    assert waits.waits({"pieces": [], "stop": None}, REF)["to_final"] == {"n": 0, "median": None, "longest": None}


def test_ruling_12_how_exact_the_times_are_on_a_made_recording_and_on_an_old_one():
    page = build_page("stop", [piece(0.2, 2.9, "If you get this pain at rest, go straight to the hospital", "A"),
                               piece(3.4, 5.6, "Understood doctor, straight to hospital", "B"),
                               piece(7.0, 8.0, "Good. See you next week", "A")], REF)
    made = waits.exactness_made(page, REF, {1: (0.0, 3.0), 2: (3.5, 5.5), 3: (6.0, 8.1)}, slack_s=0.0)
    assert [(r["speech"], r["start_off"], r["end_off"]) for r in made["rows"]] == [(1, 0.2, -0.1), (2, -0.1, 0.1), (3, 1.0, -0.1)]
    assert made["median_abs"] == 0.1 and made["largest_abs"] == 1.0 and made["beyond_figure"] == 6
    assert waits.exactness_made(page, REF, {1: (0.0, 3.0), 2: (3.5, 5.5), 3: (6.0, 8.1)}, slack_s=1.0)["beyond_figure"] == 0
    # An old recording: WhisperX's word times at Stop are the measure.
    words = [{"word": w, "start": round(0.1 * i, 2), "end": round(0.1 * i + 0.08, 2)} for i, w in enumerate(
        "If you get this pain at rest, go straight to the hospital. Understood doctor, straight to hospital. Good. See you next week.".split())]
    wx = {"stop": {"raw": [{"start": 0.0, "end": 2.0, "text": "x", "refused": False, "words": words[:12]},
                           {"start": 2.0, "end": 3.0, "text": "y", "refused": True, "words": []},
                           {"start": 2.0, "end": 3.0, "text": "z", "refused": False, "words": words[12:]}]}}
    times = waits.word_times_from_whisperx(wx, REF)
    assert len(times) == len(REF.words) and times[0] == (0.0, 0.08) and times[12] == (1.2, 1.28)
    other = build_page("stop", [piece(0.0, 1.5, "If you get this pain at rest, go straight to the hospital"),
                                piece(1.5, 2.0, "Understood doctor, straight to hospital")], REF)
    old = waits.exactness_old(other, REF, times, slack_s=1.0)
    assert [(r["start_off"], r["end_off"]) for r in old["rows"]] == [(0.0, 0.32), (0.3, 0.32)]
    assert old["beyond_figure"] == 0 and old["largest_abs"] == 0.32


def test_the_signs_of_the_check_are_counted_right_and_false():
    page = build_page("stop", [piece(0.0, 2.0, "If you get this pain at rest,"), piece(6.0, 8.0, "Understood doctor, straight to hospital. Good. See you next week.")], REF)
    live = build_page("live", [piece(0.0, 2.0, "If you get this pain at rest,"), piece(2.0, 6.0, "go straight to the hospital")], REF)
    gaps = [Gap(("go", "straight", "to", "the", "hospital"), 2.0, 6.0, 7), Gap(("if", "you", "get", "this", "pain"), 0.0, 2.0, 0)]
    stretches = [Stretch(2.5, 5.5), Stretch(9.0, 12.0)]
    found = waits.signs_counted(page, REF, set(), gaps, live, stretches, 12.0)
    assert found == {"right": 2, "false": 2, "missing_runs": 1}
    assert waits.missing_runs(page, REF, set()) == [[7, 8, 9, 10, 11]]
    assert waits.missing_runs(page, REF, {8}) == [[9, 10, 11]]           # an agreed place splits a run
