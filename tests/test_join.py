"""The join of the Nemotron choice (spec 15.9, ruling 8; ruling 4;
V1_LESSONS 2.1): words with times and stretches with speakers become
lines, and no word is ever changed, added or removed. Loaded by path, as
the worker loads it. Every word here is made up."""

import importlib.util
import random
from pathlib import Path

import pytest

JOIN = Path(__file__).resolve().parents[1] / "openconsult" / "speech" / "nemotron" / "join.py"
spec = importlib.util.spec_from_file_location("nemotron_join", JOIN)
join_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(join_module)
join, speaker_of, stretches_of = join_module.join, join_module.speaker_of, join_module.stretches_of


def words_of(text, start=0.0, step=0.3, length=0.25):
    return [{"word": w, "start": round(start + i * step, 3), "end": round(start + i * step + length, 3)}
            for i, w in enumerate(text.split())]


def flat(lines):
    return [(w["word"], w["start"], w["end"]) for line in lines for w in line["words"]]


def test_ruling_8_the_words_out_are_the_words_in_whatever_the_labels():
    words = words_of("ask not what your country can do for you. ask what you can do for your country.")
    for seed in range(50):
        rnd = random.Random(seed)
        stretches = [{"start": rnd.uniform(0, 6), "end": rnd.uniform(0, 6), "speaker": rnd.choice(["S1", "S2", "S3"])}
                     for _ in range(rnd.randint(0, 12))]
        stretches = [{**s, "end": max(s["start"], s["end"])} for s in stretches]
        lines = join(words, stretches)
        assert flat(lines) == [(w["word"], w["start"], w["end"]) for w in words]
        assert " ".join(line["text"] for line in lines) == " ".join(w["word"] for w in words)
        for line in lines:
            assert line["start"] == line["words"][0]["start"] and line["end"] == max(w["end"] for w in line["words"])
    assert join([], [{"start": 0, "end": 1, "speaker": "S1"}]) == []


def test_ruling_4_a_word_no_stretch_covers_has_no_speaker():
    assert speaker_of({"start": 1.0, "end": 1.3}, [{"start": 0.0, "end": 0.9, "speaker": "S1"}]) is None
    assert speaker_of({"start": 1.0, "end": 1.3}, []) is None
    assert speaker_of({"start": 1.0, "end": 1.3}, [{"start": 1.3, "end": 2.0, "speaker": "S1"}]) is None   # touching is not covering


def test_ruling_4_a_word_two_speakers_cover_equally_has_no_speaker():
    both = [{"start": 0.0, "end": 1.15, "speaker": "S1"}, {"start": 1.15, "end": 2.0, "speaker": "S2"}]
    assert speaker_of({"start": 1.0, "end": 1.3}, both) is None
    more = [{"start": 0.0, "end": 1.2, "speaker": "S1"}, {"start": 1.15, "end": 2.0, "speaker": "S2"}]
    assert speaker_of({"start": 1.0, "end": 1.3}, more) == "S1"
    split = [{"start": 1.0, "end": 1.1, "speaker": "S1"}, {"start": 1.2, "end": 1.3, "speaker": "S1"},
             {"start": 1.1, "end": 1.2, "speaker": "S2"}]
    assert speaker_of({"start": 1.0, "end": 1.3}, split) == "S1"             # the sum of a speaker's stretches


def test_ruling_4_the_nearest_stretch_is_never_used():
    # The join of Task 15 gave a word with no overlapping stretch the nearest one; this one never does.
    near = [{"start": 0.0, "end": 0.95, "speaker": "S1"}, {"start": 3.0, "end": 4.0, "speaker": "S2"}]
    lines = join(words_of("um", start=1.0), near)
    assert [line["speaker"] for line in lines] == [None]


CASES = [
    # one speaker, one sentence: one line
    ("ask not what", [("S1", 0.0, 2.0)], [("S1", "ask not what")]),
    # a sentence's end closes the line
    ("ask not. what you", [("S1", 0.0, 2.0)], [("S1", "ask not."), ("S1", "what you")]),
    # a change of speaker closes the line
    ("ask not what you", [("S1", 0.0, 0.6), ("S2", 0.6, 2.0)], [("S1", "ask not"), ("S2", "what you")]),
    # a word with no speaker is its own run
    ("ask not what you", [("S1", 0.0, 0.6), ("S1", 0.9, 2.0)], [("S1", "ask not"), (None, "what"), ("S1", "you")]),
]


@pytest.mark.parametrize("text, spans, expected", CASES)
def test_a_line_closes_on_a_sentence_end_or_a_speaker_change(text, spans, expected):
    stretches = [{"speaker": s, "start": a, "end": b} for s, a, b in spans]
    assert [(line["speaker"], line["text"]) for line in join(words_of(text), stretches)] == expected


def test_a_line_closes_on_a_pause():
    words = words_of("ask not") + words_of("what you", start=2.0)          # a gap of 1.45 s before "what"
    lines = join(words, [{"speaker": "S1", "start": 0.0, "end": 3.0}])
    assert [line["text"] for line in lines] == ["ask not", "what you"]
    close = words_of("ask not") + words_of("what you", start=1.5)         # a gap of 0.95 s: one line
    assert [line["text"] for line in join(close, [{"speaker": "S1", "start": 0.0, "end": 3.0}])] == ["ask not what you"]
    assert join_module.PAUSE_S == 1.0


def test_2_1_slots_beyond_the_number_given_make_no_stretch():
    frames = [[0.9, 0.1, 0.0], [0.9, 0.6, 0.0], [0.2, 0.7, 0.9], [0.1, 0.1, 0.9]]
    assert stretches_of(frames, 0.08, 3) == [
        {"start": 0.0, "end": 0.16, "speaker": "S1"}, {"start": 0.08, "end": 0.24, "speaker": "S2"},
        {"start": 0.16, "end": 0.32, "speaker": "S3"}]
    two = stretches_of(frames, 0.08, 2)
    assert {s["speaker"] for s in two} == {"S1", "S2"}                      # the third slot makes no stretch
    assert stretches_of(frames, 0.08, 1) == [{"start": 0.0, "end": 0.16, "speaker": "S1"}]
    assert stretches_of([], 0.08, 2) == []
    # And its words then have no speaker, never the nearest.
    word = {"start": 0.25, "end": 0.3}
    assert speaker_of(word, two) is None and speaker_of(word, stretches_of(frames, 0.08, 3)) == "S3"
