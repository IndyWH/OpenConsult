"""The line for Alba (spec 15.9, ruling 29; the details of 5e). Made-up
results only: what a speech choice hears is never asserted."""

from openconsult.bench.speech import alba
from openconsult.bench.speech.pages import build_page, live_pieces
from openconsult.bench.speech.reference import build

SCRIPT = ("**DOCTOR:** Where is the pain today?\n"
          "**PATIENT:** In my lower back, and it goes down one leg.\n"
          "**DOCTOR:** Any numbness between the legs?\n"
          "**PATIENT:** No numbness at all.\n"
          "**DOCTOR:** Good. See you next week.\n")
REF = build(SCRIPT)
LOUD, QUIET = -20.0, -55.0


def windows(length_s: float, quiet: list[tuple[float, float]]) -> list[float]:
    """Loud all through, but for the stretches given, in windows of 0.1 s."""
    return [QUIET if any(a <= i / 10 < b for a, b in quiet) else LOUD for i in range(int(length_s * 10))]


def result_of(lines: list[tuple[float, dict]], quiet: list[tuple[float, float]], slack: float = 0.0) -> dict:
    """Each line with the moment its piece arrived."""
    pieces = [{"n": int(t * 4), "t": t, "partial": "", "lines": [line]} for t, line in lines]
    return {"pieces": pieces, "stop": {"t": 60.0, "last_live": [], "lines": [], "raw": []}, "time_slack_s": slack,
            "loudness": {"window_s": 0.1, "dbfs": windows(60.0, quiet)}}


def line(start, end, text):
    return {"start": start, "end": end, "text": text, "speaker": None}


def rows_of(result):
    return alba.speeches_of(result, REF, build_page("live", live_pieces(result), REF))


def test_ruling_29_the_seconds_from_the_patients_last_word_to_the_final_line_both_ways():
    # The worked example of the plan: the patient's last line ends at 41.30 by the choice; the sound is quiet from
    # 41.4 until the doctor's line starts at 42.2; the line arrived final with the piece at 42.25.
    result = result_of([(36.0, line(34.0, 35.5, "Where is the pain today?")),
                        (42.25, line(38.0, 41.3, "In my lower back, and it goes down one leg.")),
                        (45.0, line(42.2, 44.0, "Any numbness between the legs?")),
                        (47.0, line(45.5, 46.2, "No numbness at all.")),
                        (52.0, line(49.0, 51.0, "Good. See you next week."))],
                       quiet=[(41.4, 42.2), (46.3, 49.0)])
    first, second = rows_of(result)
    assert (first["speech"], first["by_choice"], first["by_sound"], first["end_sound"]) == (2, 0.95, 0.85, 41.4)
    assert first["after_reply"] is True                       # final at 42.25, the reply began at 42.2
    assert (second["speech"], second["by_choice"], second["by_sound"], second["after_reply"]) == (4, 0.8, 0.7, False)
    found = alba.summary([first, second])
    assert found["speeches"] == 2 and found["after_reply"] == 1
    assert found["by_sound"] == {"n": 2, "median": 0.775, "longest": 0.85, "within": {"0.8": 1, "1.5": 2, "3.0": 2}}
    assert found["by_choice"]["within"] == {"0.8": 1, "1.5": 2, "3.0": 2}
    # One of the two was final only after the reply had begun: it counts as late, so the typical is not within 0.8.
    assert found["serves"]["by"] == "the sound" and found["serves"]["late_after_reply"] == 1 and found["serves"]["yes"] is False


def test_ruling_29_a_pause_inside_the_patients_sentence_does_not_move_the_end_of_the_speech_back():
    # The last run of quiet before the reply is taken, not the longest: the patient pauses 1.5 s inside the
    # sentence (39.0 to 40.5) and only 0.3 s lies between the last word and the reply.
    result = result_of([(42.0, line(38.0, 41.3, "In my lower back, and it goes down one leg.")),
                        (45.0, line(41.7, 44.0, "Any numbness between the legs?"))],
                       quiet=[(39.0, 40.5), (41.4, 41.7)])
    row = rows_of(result)[0]
    assert row["end_sound"] == 41.4 and row["by_sound"] == 0.6 and row["after_reply"] is True
    # A quiet run shorter than 0.2 s is not a pause.
    assert alba.quiet_runs(windows(10.0, [(2.0, 2.1), (5.0, 5.2)]), 0.1, 0.0, 10.0) == [(5.0, 5.2)]


def test_ruling_29_speeches_counted_apart_and_the_reading_taken_by_the_choices_time_when_the_sound_has_no_pauses():
    # A line that runs on into the doctor's words gives no time for the patient's last word: apart, both ways, and late.
    result = result_of([(46.0, line(38.0, 45.0, "In my lower back, and it goes down one leg. Any numbness between the legs?")),
                        (47.0, line(45.5, 46.2, "No numbness at all.")),
                        (50.0, line(46.25, 49.0, "Good. See you next week."))], quiet=[])
    first, second = rows_of(result)
    assert first["apart_choice"] == first["apart_sound"] == "the line runs on into the doctor's words" and first["after_reply"]
    # No quiet anywhere: no pause found for the sound; the choice's own time still gives its seconds.
    assert second["apart_sound"] == "no pause was found before the reply" and second["by_sound"] is None
    assert second["by_choice"] == 0.8 and second["after_reply"] is True          # final at 47.0, the reply's line starts at 46.25
    # More than half without a pause: the yes or no is taken by the choice's own time, and says why.
    quick = {"speech": 4, "t_final": 47.0, "by_choice": 0.5, "by_sound": None, "apart_choice": None,
             "apart_sound": "no pause was found before the reply", "after_reply": False}
    found = alba.summary([quick, dict(quick, speech=6), dict(quick, speech=8, by_sound=0.4, apart_sound=None)])
    assert found["serves"] == {"by": "the choice's own time", "why": "more than half of the speeches had no pause in the sound",
                               "judged": 3, "late_after_reply": 0, "typical": 0.5, "yes": True}
    assert found["apart"] == {"apart_sound": {"no pause was found before the reply": 2}}
    # A speech of which no word was heard is counted apart and judged neither way.
    silent = result_of([(52.0, line(49.0, 51.0, "Good. See you next week."))], quiet=[])
    assert [r["apart_choice"] for r in rows_of(silent)] == ["no word of the speech was heard"] * 2
    assert alba.summary(rows_of(silent))["serves"]["yes"] is False and alba.summary([])["serves"]["yes"] is False


def test_ruling_29_yes_when_the_typical_wait_by_the_sound_is_within_the_first_figure():
    rows = [{"speech": n, "t_final": 10.0, "by_choice": 1.0, "by_sound": wait, "apart_choice": None, "apart_sound": None,
             "after_reply": False} for n, wait in ((2, 0.4), (4, 0.7), (6, 2.5))]
    found = alba.summary(rows)
    assert found["serves"]["yes"] is True and found["serves"]["typical"] == 0.7 and found["by_sound"]["within"]["0.8"] == 2
    rows[1]["after_reply"] = rows[0]["after_reply"] = True
    late = alba.summary(rows)
    assert late["serves"]["yes"] is False and late["serves"]["typical"] is None and late["after_reply"] == 2
    assert alba.WITHIN_S == (0.8, 1.5, 3.0) and alba.SERVES_WITHIN_S == 0.8


def test_ruling_29_a_pause_inside_a_short_reply_of_the_doctor_is_not_taken_for_the_end_of_the_patients_speech():
    # Found on the run of 5e: the patient ends at 41.4, the doctor answers two words from 42.3 and pauses at 43.0.
    # With a second of slack on the choice's times the search runs past the reply's start; the pause inside the
    # reply begins after the reply's own line and is not the patient's.
    result = result_of([(43.3, line(38.0, 41.3, "In my lower back, and it goes down one leg.")),
                        (46.0, line(42.3, 44.5, "Any numbness between the legs?"))],
                       quiet=[(41.4, 42.3), (43.0, 43.6)], slack=1.0)
    row = rows_of(result)[0]
    assert row["end_sound"] == 41.4 and row["by_sound"] == 1.9
    assert row["after_reply"] is True                         # final at 43.3, the reply began at 42.3 by the sound


def test_ruling_29_no_seconds_are_given_where_the_line_may_not_be_the_last_of_the_speech():
    # Found on the run of 5e, twice. One: words that match no speech of the script arrive between the patient's
    # line and the reply; whose they are is not known, so the speech is counted apart both ways.
    result = result_of([(42.0, line(38.0, 41.3, "In my lower back, and it goes down one leg.")),
                        (44.0, line(41.5, 41.9, "zzz qqq")),
                        (46.0, line(42.3, 44.5, "Any numbness between the legs?"))],
                       quiet=[(41.4, 41.5), (41.9, 42.3)])
    row = rows_of(result)[0]
    assert row["apart_choice"] == row["apart_sound"] == "words that match no speech lie between the line and the reply"
    assert row["by_choice"] is None and row["by_sound"] is None and row["after_reply"] is None
    assert alba.summary([row])["serves"]["judged"] == 0
    # Two: the sound goes on after the line was final (a noise, or words nobody wrote): seconds below nought
    # are not a wait, so the sound gives none and the choice's own time stands alone.
    result = result_of([(42.0, line(38.0, 41.3, "In my lower back, and it goes down one leg.")),
                        (46.0, line(43.0, 44.5, "Any numbness between the legs?"))],
                       quiet=[(42.5, 43.0)])
    row = rows_of(result)[0]
    assert row["by_sound"] is None and row["apart_sound"] == "the sound went on after the line was final"
    assert row["by_choice"] == 0.7 and row["after_reply"] is False
