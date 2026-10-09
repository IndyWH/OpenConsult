"""The shape of a line (spec 11.4), what a choice declares (11.5 rule 5),
and the merge into turns as a plain function (V1_LESSONS 1.3)."""

import pytest

from openconsult.speech.lines import Declares, Line, failed_final, failed_live
from openconsult.speech.turns import as_line, merge_into_turns


def seg(start, end, text, speaker=None, scores=None):
    words = []
    for i, word in enumerate(text.split()):
        entry = {"word": word, "start": start + i * 0.1, "end": start + i * 0.1 + 0.05}
        if speaker:
            entry["speaker"] = speaker
        if scores:
            entry["score"] = scores[i]
        words.append(entry)
    return {"start": start, "end": end, "text": text, "words": words}


def test_11_4_a_line_has_a_speaker_or_none_times_and_a_confidence_or_none():
    line = Line(None, 0.0, 1.5, "made up", None)
    assert (line.speaker, line.confidence) == (None, None)
    with_both = as_line(seg(0.0, 1.0, "two words", speaker="SPEAKER_00", scores=[0.8, 0.6]))
    assert with_both == Line("SPEAKER_00", 0.0, 1.0, "two words", 0.7)


def test_11_5_rule_5_a_declaration_says_live_at_stop_or_none():
    assert Declares("at_stop", "at_stop", True).second_transcript
    with pytest.raises(ValueError):
        Declares("sometimes", "live", False)


def test_a_failure_must_be_one_of_the_named_reasons():
    assert failed_live("died", "made up", 1.0, None).failure == "died"
    assert not failed_final("no_answer", "made up", None).ok
    with pytest.raises(ValueError):
        failed_live("exploded", "made up", 0.0, None)


# -------------------------------------------------------- the merge (1.3)

CASES = [
    # Same cluster, consecutive: one turn, word-weighted confidence.
    ([seg(0, 1, "a b", "S0", [0.8, 0.8]), seg(1, 2, "c", "S0", [0.2]), seg(2, 3, "d", "S1", [0.5])],
     [Line("S0", 0.0, 2.0, "a b c", 0.6), Line("S1", 2.0, 3.0, "d", 0.5)]),
    # A single cluster keeps the segment boundaries (v1, recording 66).
    ([seg(0, 1, "a", "S0", [0.9]), seg(1, 2, "b", "S0", [0.7])],
     [Line("S0", 0.0, 1.0, "a", 0.9), Line("S0", 1.0, 2.0, "b", 0.7)]),
    # Empty text is skipped; no scored word gives no confidence (change 4), never 0.5.
    ([seg(0, 1, "   ", "S0"), seg(1, 2, "a", "S0"), seg(2, 3, "b", "S1")],
     [Line("S0", 1.0, 2.0, "a", None), Line("S1", 2.0, 3.0, "b", None)]),
    # A turn with scores joined by one without keeps the mean of the scored words.
    ([seg(0, 1, "a", "S0", [0.4]), seg(1, 2, "b", "S0"), seg(2, 3, "c", "S1", [0.9])],
     [Line("S0", 0.0, 2.0, "a b", 0.4), Line("S1", 2.0, 3.0, "c", 0.9)]),
    # No speakers at all: one cluster of none, boundaries kept.
    ([seg(0, 1, "a"), seg(1, 2, "b")],
     [Line(None, 0.0, 1.0, "a", None), Line(None, 1.0, 2.0, "b", None)]),
]


@pytest.mark.parametrize("raw, turns", CASES)
def test_1_3_the_merge_into_turns_is_a_plain_function(raw, turns):
    assert merge_into_turns(raw) == turns


def test_1_3_the_merge_changes_no_raw_segment():
    raw = [seg(0, 1, "a b", "S0", [0.8, 0.8]), seg(1, 2, "c", "S0", [0.2])]
    before = [dict(s) for s in raw]
    merge_into_turns(raw)
    assert raw == before
