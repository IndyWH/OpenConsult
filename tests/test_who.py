"""Who spoke, four readings side by side (spec 15.9, ruling 4; rulings 17
and 22; the details of part two of 5c). Made-up lines against a made-up
script."""

from openconsult.bench.speech import model_lines, who
from openconsult.bench.speech.reference import build

SCRIPT = ("**DOCTOR:** Any chest pain at rest?\n**PATIENT:** No. Not at rest.\n"
          "**DOCTOR:** Only on the stairs.\n**PATIENT:** Is that bad?\n")
REF = build(SCRIPT)
# The choice heard the lines right, with S1 the doctor, line 3 with no
# speaker, and the last with a third label; "now" was never spoken.
LINES = model_lines.lines_of([
    {"speaker": "S1", "start": 0.0, "end": 1.3, "text": "Any chest pain at rest?"},
    {"speaker": "S2", "start": 1.6, "end": 2.9, "text": "No. Not at rest."},
    {"speaker": None, "start": 3.1, "end": 4.0, "text": "Only on the stairs now."},
    {"speaker": "S3", "start": 5.5, "end": 6.0, "text": "Is that bad?"}])


def test_ruling_4_the_four_readings_are_counted_word_by_word_and_together_stands_only_where_voice_and_words_agree():
    labels = {1: "doctor", 2: "patient", 3: "doctor", 4: "unsure"}
    voice = {1: "doctor", 2: "not_doctor", 3: "not_doctor", 4: "doctor"}
    found = who.four_readings(LINES, REF, labels, voice)
    counts = found["counts"]
    # The choice: S1 the doctor (5 right), S2 the patient (4 right), none unsure (4), S3 beyond the fit: wrong (3); "now" apart.
    assert counts["choice"] == {"right": 9, "wrong": 3, "unsure": 4, "nowhere": 1}
    # The label check: lines 1 to 3 right (13), line 4 unsure (3).
    assert counts["label_check"] == {"right": 13, "wrong": 0, "unsure": 3, "nowhere": 1}
    # The voice: not doctor counts as the patient: line 3 wrong (4), line 4 wrong (3).
    assert counts["voice"] == {"right": 9, "wrong": 7, "unsure": 0, "nowhere": 1}
    # Together: lines 1 and 2 agree (9 right); line 3 disagrees (unsure); line 4 the words are unsure (unsure).
    assert counts["together"] == {"right": 9, "wrong": 0, "unsure": 7, "nowhere": 1}
    assert found["lines"][3] == {"n": 4, "words": 3, "choice": "other", "label_check": "unsure", "voice": "doctor", "together": "unsure"}
    assert found["lines"][2]["choice"] == "unsure" and found["lines"][2]["voice"] == "patient"


def test_ruling_17_a_refused_label_check_leaves_every_word_unsure_and_without_the_voice_there_is_no_reading():
    found = who.four_readings(LINES, REF, None, None)
    assert found["counts"]["label_check"] == {"right": 0, "wrong": 0, "unsure": 16, "nowhere": 1}
    assert found["counts"]["voice"] == {"not_run": True} and found["counts"]["together"] == {"not_run": True}
    # With the voice but a refused label check, together is unsure everywhere.
    with_voice = who.four_readings(LINES, REF, None, {1: "doctor", 2: "not_doctor", 3: "unsure", 4: "unsure"})
    assert with_voice["counts"]["together"] == {"right": 0, "wrong": 0, "unsure": 16, "nowhere": 1}
    assert with_voice["counts"]["voice"] == {"right": 9, "wrong": 0, "unsure": 7, "nowhere": 1}
