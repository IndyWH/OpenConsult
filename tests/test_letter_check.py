"""The letter check (spec 15.12, ruling 4 and its detail; the plan
review of 8a, point 1; R4, R5). Made letters on made notes: every rule
of the check has a case that shows it catching the thing it is for.
What a model says is never asserted here."""

from openconsult import words
from openconsult.consult import letter_check as lc
from openconsult.consult.note import CITATION_HALF, LETTER_GROUNDED_HALF
from openconsult.consult.referral_note import numbered_lines

NOTE = numbered_lines(
    "Subjective\nSix weeks of food sticking, solids first.\nLost about 4 kg in 2 months.\n"
    "Patient's ideas: a made-up idea. Patient's expectations: hoped for a scan.\n\n"
    "Objective\nWeight 71 kg. BP 142/86.\nHb 10.8 on bloods taken last week, MCV 76.\n\n"
    "Assessment\nA made-up impression.\n\n"
    "Plan\nUrgent referral to a made-up specialty on the two-week pathway.\nFerritin, U and E and LFT arranged today.\n")
# The lines: 1 Subjective, 2 sticking, 3 weight loss, 4 ICE, 5 Objective, 6 weight and BP, 7 Hb, 8 Assessment,
# 9 impression, 10 Plan, 11 referral, 12 arranged.
AGE = {"58"}


def para(text, lines):
    return {"text": text, "note_lines": lines}


def verdicts(checked, k=0):
    return [(s["verdict"], s["reason"]) for s in checked.detail["paragraphs"][k]["sentences"]]


def test_ruling_4_R4_R5_the_check_catches_each_thing_it_is_for():
    # A paragraph citing no valid line: every sentence replaced, one placeholder for the run (no_line); a heading is no line.
    none = lc.check([para("He is a smoker. He drinks.", [1, 99])], NOTE, AGE)
    assert none.paragraphs == [words.LETTER_PLACEHOLDER] and verdicts(none) == [("placeholder", "no_line")] * 2
    assert (none.total, none.grounded, none.placeholders, none.dropped) == (2, 0, 2, 0)
    # An Assessment citation is dropped and recorded on the paragraph; the sentences are judged on the valid lines left
    # (the plan review, point 1); with no valid line left they fail as no_line.
    mixed = lc.check([para("Food sticks on swallowing. He has lost 4 kg.", [2, 3, 9])], NOTE, AGE)
    assert mixed.paragraphs == ["Food sticks on swallowing. He has lost 4 kg."] and mixed.detail["paragraphs"][0]["assessment_cited"] == [9]
    assert mixed.detail["paragraphs"][0]["valid"] == [2, 3] and lc.cites_assessment(mixed.detail)
    only = lc.check([para("The impression is a made-up one.", [9])], NOTE, AGE)
    assert only.paragraphs == [words.LETTER_PLACEHOLDER] and verdicts(only) == [("placeholder", "no_line")] and only.refused
    assert not lc.cites_assessment(mixed.detail and {"paragraphs": [{"assessment_cited": []}]})
    # A number not in the cited lines; six weeks and 6 weeks the same; 142/86 read; a hyphen a space; the age excepted.
    good = lc.check([para("This 58-year-old man has had 6 weeks of food sticking and his BP was 142/86. He is on the two-week pathway.", [2, 6, 11])], NOTE, AGE)
    assert verdicts(good) == [("kept", None)] * 2 and good.grounded == 2
    bad = lc.check([para("He has had 8 weeks of food sticking.", [2])], NOTE, AGE)
    assert bad.paragraphs == [words.LETTER_PLACEHOLDER] and verdicts(bad) == [("placeholder", "number")]
    assert lc.check([para("This 58-year-old man has food sticking.", [2])], NOTE, set()).placeholders == 1   # the age counts only when allowed
    assert lc.numbers_in("six weeks, 142/86, 10.8 and a 2-week wait") == {"6", "142", "86", "10.8", "2"}
    # A planned test written as a result is an upgrade; the note's own result wording is not.
    upgrade = lc.check([para("Ferritin, U and E and LFT were performed today.", [12])], NOTE, AGE)
    assert verdicts(upgrade) == [("placeholder", "upgrade")]
    assert verdicts(lc.check([para("Ferritin, U and E and LFT were arranged today.", [12])], NOTE, AGE)) == [("kept", None)]
    assert verdicts(lc.check([para("Bloods last week showed Hb 10.8 with an MCV of 76.", [7])], NOTE, AGE)) == [("kept", None)]
    # A run of failed sentences gives one placeholder; a kept sentence between gives two.
    run = lc.check([para("He has had 8 weeks of this. He lost 9 kg. He weighs 71 kg. He lost 3 kg.", [2, 3, 6])], NOTE, AGE)
    assert run.paragraphs == [f"{words.LETTER_PLACEHOLDER} He weighs 71 kg. {words.LETTER_PLACEHOLDER}"] and run.placeholders == 3
    # An expectation sentence with no expectations line among the valid lines is dropped and counted, never replaced;
    # with the line, holding Patient's expectations: mid-line, kept.
    dropped = lc.check([para("Food sticks. He hoped for a scan and the patient expects one.", [2])], NOTE, AGE)
    assert dropped.paragraphs == ["Food sticks."] and verdicts(dropped) == [("kept", None), ("dropped", None)]
    assert (dropped.total, dropped.grounded, dropped.placeholders, dropped.dropped) == (2, 1, 0, 1)
    kept = lc.check([para("The patient expects a scan.", [4])], NOTE, AGE)
    assert kept.paragraphs == ["The patient expects a scan."] and kept.dropped == 0
    assert lc.expectation_sentence("Patient's expectations were discussed.") and not lc.expectation_sentence("He expects nothing.")
    # The model's own placeholder counts as a placeholder, never as grounded, and joins a run.
    own = lc.check([para(f"Food sticks. {words.LETTER_PLACEHOLDER} He lost 9 kg.", [2])], NOTE, AGE)
    assert own.paragraphs == [f"Food sticks. {words.LETTER_PLACEHOLDER}"] and verdicts(own)[1] == ("placeholder", "model_placeholder")
    assert (own.grounded, own.placeholders) == (1, 2)
    # An empty paragraph is omitted; a non-number citation is ignored; the detail names every verdict.
    empty = lc.check([para("", [2]), para("Food sticks.", [2, True, "x"])], NOTE, AGE)
    assert empty.paragraphs == ["Food sticks."] and empty.detail["paragraphs"][1]["valid"] == [2] and empty.total == 1
    assert lc.reasons_of(run.detail) == ["number", "number", "number"] and lc.reasons_of(None) == []


def test_ruling_4_fewer_than_half_grounded_is_refused_and_exactly_half_passes():
    assert LETTER_GROUNDED_HALF == CITATION_HALF == 0.5
    half = lc.check([para("Food sticks. He lost 9 kg.", [2]), para("He weighs 71 kg. He lost 3 kg.", [6])], NOTE, AGE)
    assert (half.total, half.grounded) == (4, 2) and not half.refused            # exactly half passes
    under = lc.check([para("Food sticks. He lost 9 kg. He lost 3 kg.", [2])], NOTE, AGE)
    assert (under.total, under.grounded, under.refused) == (3, 1, True)
    assert lc.check([], NOTE, AGE).refused and lc.check([para("", [2])], NOTE, AGE).refused     # none is refused
    assert lc.sentences_of("One. Two!  Three? ") == ["One.", "Two!", "Three?"] and lc.sentences_of("") == []
