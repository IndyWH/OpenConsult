"""The shape of a line (spec 11.4), what a choice declares (11.5 rule 5),
and the merge into turns as a plain function (V1_LESSONS 1.3)."""

import json
import os
import subprocess
import sys

import pytest

from openconsult.speech.lines import Declares, Line, failed_final, failed_live
from openconsult.speech.turns import as_line, merge_into_turns, speaker_of


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
    # Empty text is skipped; no scored word gives no confidence (spec 11.4: a score or none), never 0.5.
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


def test_1_3_a_segment_split_evenly_between_two_speakers_has_no_speaker_whatever_the_hash_seed():
    # Two words of each cluster: the segment is in doubt, so it is shown as unsure
    # (spec 15.9 ruling 4), and the answer cannot depend on a set's order
    # (stage 5c: one recording scored two ways). Run under more than one seed.
    first_s1 = {"start": 0.0, "end": 1.0, "text": "a b c d", "words": [
        {"word": "a", "speaker": "S1"}, {"word": "b", "speaker": "S0"},
        {"word": "c", "speaker": "S0"}, {"word": "d", "speaker": "S1"}]}
    first_s0 = {"start": 0.0, "end": 1.0, "text": "a b c d", "words": [
        {"word": "a", "speaker": "S0"}, {"word": "b", "speaker": "S1"},
        {"word": "c", "speaker": "S1"}, {"word": "d", "speaker": "S0"}]}
    assert speaker_of(first_s1) is None and speaker_of(first_s0) is None
    majority = {"start": 0.0, "end": 1.0, "text": "a b c", "words": [
        {"word": "a", "speaker": "S1"}, {"word": "b", "speaker": "S0"}, {"word": "c", "speaker": "S0"}]}
    assert speaker_of(majority) == "S0"                                   # most words still win
    assert speaker_of({"start": 0.0, "end": 1.0, "text": "a", "words": [{"word": "a"}]}) is None
    assert merge_into_turns([first_s1, dict(majority, start=1.0, end=2.0)])[0].speaker is None
    for seed in ("0", "1", "2", "random"):
        code = ("import json, sys; from openconsult.speech.turns import speaker_of; "
                "print(json.dumps([speaker_of(s) for s in json.load(sys.stdin)]))")
        out = subprocess.run([sys.executable, "-c", code], input=json.dumps([first_s1, first_s0, majority]),
                             capture_output=True, text=True, check=True,
                             env={**os.environ, "PYTHONHASHSEED": seed}).stdout
        assert json.loads(out) == [None, None, "S0"], seed
