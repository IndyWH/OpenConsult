"""The checks at Stop and the gate (spec 15.10 ruling 8; 11.5 rules 2 and
5; V1_LESSONS 1.9, 3.6; R3). Made-up lines, made loudness; the two
functions of 5c are not changed here, only shown."""

from openconsult import words
from openconsult.consult.gate import LOW_CONFIDENCE, TOO_SHORT_WORDS, judge, missing_speech, word_count
from openconsult.speech.choices import ASSEMBLYAI, NEMOTRON, WHISPERX_PYANNOTE
from openconsult.speech.lines import Line


def row(n, text, label="patient", unsure=False, confidence=None):
    return {"n": n, "text": text, "label": label, "unsure": unsure, "confidence": confidence}


def test_ruling_8_the_gate_refuses_only_an_empty_or_too_short_transcript():
    empty = judge([], NEMOTRON.declares, "Nemotron")
    assert empty.refused and empty.warnings == [{"kind": "empty"}]
    short = judge([row(1, "word " * 59)], NEMOTRON.declares, "Nemotron")
    assert short.refused and short.warnings[0]["kind"] == "too_short"
    assert short.warnings[0]["detail"] == words.WARN_TOO_SHORT.format(words=59, least=TOO_SHORT_WORDS)
    enough = judge([row(1, "word " * 60)], NEMOTRON.declares, "Nemotron")
    assert not enough.refused and [w["kind"] for w in enough.warnings] == ["confidence_not_measured"]
    assert TOO_SHORT_WORDS == 60 and LOW_CONFIDENCE == 0.60


def test_3_6_the_word_count_reads_number_words_as_the_bench_does():
    assert word_count([row(1, "one hundred and ten milligrams")]) == 2          # 110 mg
    assert word_count([row(1, "I take two tablets, twice a day.")]) == 7


def test_ruling_8_a_missing_passage_a_line_with_no_speaker_and_low_confidence_are_flagged_never_refused():
    rows = [row(1, "word " * 30, label="doctor", confidence=0.9), row(2, "word " * 30, label="unsure", unsure=True, confidence=0.55),
            row(3, "word " * 5, label="patient", confidence=0.61)]
    verdict = judge(rows, ASSEMBLYAI.declares, "AssemblyAI")
    assert not verdict.refused
    assert [(w["kind"], w.get("line_n"), w.get("detail")) for w in verdict.warnings] == [
        ("no_speaker", 2, None), ("low_confidence", 2, "0.55")]
    # 11.5 rule 5: Nemotron gives no score, so the page says so and no line is called low confidence.
    verdict = judge(rows, NEMOTRON.declares, "Nemotron")
    assert [w["kind"] for w in verdict.warnings] == ["no_speaker", "confidence_not_measured"]
    assert verdict.warnings[1]["detail"] == "Nemotron"
    # WhisperX gives a score at Stop: a turn with none is not flagged (no made-up score).
    verdict = judge([row(1, "word " * 60, label="doctor", confidence=None)], WHISPERX_PYANNOTE.declares, "WhisperX")
    assert verdict.warnings == []


def test_11_5_rule_2_the_two_checks_of_5c_give_warnings_at_their_place():
    live = [Line(None, 0.0, 2.0, "go straight to the hospital now please", None),
            Line(None, 2.5, 3.0, "yes", None)]
    final = [Line("S1", 0.0, 2.0, "now please", None), Line("S2", 2.5, 3.0, "yes", None)]
    windows = [-20.0] * 60                                  # six seconds of speech; lines cover 0 to 3
    found = missing_speech(live, final, windows, second_transcript=True)
    assert found == [{"kind": "missing_passage", "start_s": 0.0, "end_s": 2.0, "detail": "go straight to the hospital"},
                     {"kind": "uncovered_speech", "start_s": 3.0, "end_s": 6.0}]
    # A one-transcript choice has no second transcript to set against: the sound check alone.
    assert [w["kind"] for w in missing_speech(live, final, windows, second_transcript=False)] == ["uncovered_speech"]
    assert missing_speech(live, final, [None] * 60, False) == []
