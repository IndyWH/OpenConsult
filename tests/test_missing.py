"""The check for missing speech (spec 11.5 rule 2; D45; 15.9 ruling 13).
Made-up lines and made loudness; nothing here hears a model."""

import math

from openconsult.speech.lines import Line
from openconsult.speech.missing import (JOIN_GAP_S, LEAST_SPEECH_S, LEAST_WORDS, SPEECH_DBFS, Gap, Stretch,
                                        missing_from_final, speech_stretches, uncovered_speech)


def line(start, end, text, speaker=None):
    return Line(speaker, start, end, text, None)


def test_ruling_13_D45_five_live_words_missing_at_stop_are_a_gap():
    live = [line(0.0, 2.0, "Any chest pain at rest?"),
            line(2.5, 6.0, "No, go straight to the hospital, to the emergency department."),
            line(6.5, 7.0, "Understood.")]
    final = [line(0.0, 2.0, "Any chest pain at rest?", "S1"), line(2.5, 2.7, "No.", "S2"), line(6.5, 7.0, "Understood.", "S2")]
    gaps = missing_from_final(live, final)
    assert gaps == [Gap(("go", "straight", "to", "the", "hospital", "to", "the", "emergency", "department"), 2.5, 6.0, 6)]
    # Four missing words are no gap; five garbled into five others are no gap (they show on the page).
    four = [line(0.0, 2.0, "go straight to the hospital now")]
    assert missing_from_final(four, [line(0.0, 2.0, "go now")]) == []
    assert missing_from_final(four, [line(0.0, 2.0, "go stray tour that hospice now")]) == []
    assert missing_from_final(four, [line(0.0, 2.0, "now")]) == [Gap(("go", "straight", "to", "the", "hospital"), 0.0, 2.0, 0)]
    assert LEAST_WORDS == 5 and missing_from_final([], []) == []


def test_11_5_rule_2_speech_that_no_line_covers_is_a_sign():
    window_s = 0.1
    quiet, loud = -60.0, -20.0
    windows = [quiet] * 10 + [loud] * 30 + [quiet] * 10          # speech from 1.0 to 4.0 s
    assert speech_stretches(windows, window_s) == [(1.0, 4.0)]
    assert uncovered_speech(windows, window_s, []) == [Stretch(1.0, 4.0)]
    assert uncovered_speech(windows, window_s, [line(0.9, 4.1, "covered")]) == []
    assert uncovered_speech(windows, window_s, [line(1.0, 1.5, "a")]) == [Stretch(1.5, 4.0)]
    short = [quiet] * 10 + [loud] * 19 + [quiet] * 10            # 1.9 s: not a stretch
    assert uncovered_speech(short, window_s, []) == []
    # A quiet gap of 0.4 s inside speech is joined; one of 0.6 s splits it.
    joined = [loud] * 15 + [quiet] * 4 + [loud] * 15
    assert speech_stretches(joined, window_s) == [(0.0, 3.4)]
    split = [loud] * 15 + [quiet] * 6 + [loud] * 15
    assert speech_stretches(split, window_s) == [(0.0, 1.5), (2.1, 3.6)]
    # Exactly the figure is not speech; silence (None or -inf) is not speech.
    assert speech_stretches([SPEECH_DBFS] * 30 + [None] * 5 + [-math.inf] * 5, window_s) == []
    assert (LEAST_SPEECH_S, JOIN_GAP_S, SPEECH_DBFS) == (2.0, 0.5, -30.0)


def test_the_check_does_not_look_wider_than_the_lines_own_times():
    # A line that ends 2.5 s before the speech ends leaves a sign, whatever
    # a choice's times allow: the rule against words from silence keeps the
    # word where times are in doubt, and this check shows the sign.
    windows = [-20.0] * 50                                        # speech 0.0 to 5.0 s
    assert uncovered_speech(windows, 0.1, [line(0.0, 2.5, "the first half")]) == [Stretch(2.5, 5.0)]
    # Two lines leave a gap of 2.0 s between them: a sign; of 1.9 s: none.
    assert uncovered_speech(windows, 0.1, [line(0.0, 1.0, "a"), line(3.0, 5.0, "b")]) == [Stretch(1.0, 3.0)]
    assert uncovered_speech(windows, 0.1, [line(0.0, 1.1, "a"), line(3.0, 5.0, "b")]) == []
