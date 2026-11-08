"""The letter check (spec 15.12, ruling 4 and its detail; the plan
review of 8a, point 1; rulings 15, 16 and 33; 15.13 ruling 20, the number
rule marks instead of removing; R4, R5). Made letters on made notes:
every rule of the check has a case that shows it catching the thing it
is for. What a model says is never asserted here."""

from openconsult import words
from openconsult.consult import letter_check as lc
from openconsult.consult.note import CITATION_HALF, LETTER_GROUNDED_HALF
from openconsult.consult.referral_note import numbered_lines

NOTE = numbered_lines(
    "Subjective\nSix weeks of food sticking, solids first.\nLost about 4 kg in 2 months.\n"
    "Patient's ideas: a made-up idea. Patient's expectations: hoped for a scan.\n\n"
    "Objective\nWeight 71 kg. BP 142/86.\nHb 10.8 on bloods taken last week, MCV 76.\n\n"
    "Assessment\nA made-up impression.\n\n"
    "Plan\nUrgent referral to a made-up specialty on the two-week pathway.\nFerritin, U and E and LFT arranged today.\n"
    "Chest X-ray booked for 2 weeks' time.\n")
# The lines: 1 Subjective, 2 sticking, 3 weight loss, 4 ICE, 5 Objective, 6 weight and BP, 7 Hb, 8 Assessment,
# 9 impression, 10 Plan, 11 referral, 12 arranged, 13 booked.
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
    # 15.13 ruling 20: a figure the lines do not give marks the sentence and keeps it as written (the test below).
    bad = lc.check([para("He has had 8 weeks of food sticking.", [2])], NOTE, AGE)
    assert bad.paragraphs == ["He has had 8 weeks of food sticking."] and verdicts(bad) == [("marked", "number")]
    assert lc.check([para("This 58-year-old man has food sticking.", [2])], NOTE, set()).marked == 1   # the age counts only when allowed
    assert lc.numbers_in("six weeks, 142/86, 10.8 and a 2-week wait") == {"6", "142", "86", "10.8", "2"}
    # A planned test written as a result is an upgrade; the note's own result wording is not.
    upgrade = lc.check([para("Ferritin, U and E and LFT were performed today.", [12])], NOTE, AGE)
    assert verdicts(upgrade) == [("placeholder", "upgrade")]
    assert verdicts(lc.check([para("Ferritin, U and E and LFT were arranged today.", [12])], NOTE, AGE)) == [("kept", None)]
    assert verdicts(lc.check([para("Bloods last week showed Hb 10.8 with an MCV of 76.", [7])], NOTE, AGE)) == [("kept", None)]
    # A run of failed sentences gives one placeholder; a kept sentence between gives two (here upgrades: ruling 20 keeps a
    # sentence whose only failure is a number).
    run = lc.check([para("Ferritin was performed. LFT was performed. He weighs 71 kg. A chest X-ray was performed.", [6, 12, 13])], NOTE, AGE)
    assert run.paragraphs == [f"{words.LETTER_PLACEHOLDER} He weighs 71 kg. {words.LETTER_PLACEHOLDER}"] and run.placeholders == 3
    # An expectation sentence with no expectations line among the valid lines is dropped and counted, never replaced;
    # with the line, holding Patient's expectations: mid-line, kept.
    dropped = lc.check([para("Food sticks. He hoped for a scan and the patient expects one.", [2])], NOTE, AGE)
    assert dropped.paragraphs == ["Food sticks."] and verdicts(dropped) == [("kept", None), ("dropped", None)]
    assert (dropped.total, dropped.grounded, dropped.placeholders, dropped.dropped) == (2, 1, 0, 1)
    kept = lc.check([para("The patient expects a scan.", [4])], NOTE, AGE)
    assert kept.paragraphs == ["The patient expects a scan."] and kept.dropped == 0
    assert lc.expectation_sentence("Patient's expectations were discussed.") and not lc.expectation_sentence("He is expected in clinic.")
    # The model's own placeholder counts as a placeholder, never as grounded (the sentence after it is marked, ruling 20).
    own = lc.check([para(f"Food sticks. {words.LETTER_PLACEHOLDER} He lost 9 kg.", [2])], NOTE, AGE)
    assert own.paragraphs == [f"Food sticks. {words.LETTER_PLACEHOLDER} He lost 9 kg."] and verdicts(own)[1] == ("placeholder", "model_placeholder")
    assert (own.grounded, own.placeholders, own.marked) == (1, 1, 1)
    # An empty paragraph is omitted; a non-number citation is ignored; the detail names every verdict.
    empty = lc.check([para("", [2]), para("Food sticks.", [2, True, "x"])], NOTE, AGE)
    assert empty.paragraphs == ["Food sticks."] and empty.detail["paragraphs"][1]["valid"] == [2] and empty.total == 1
    assert lc.reasons_of(run.detail) == ["upgrade", "upgrade", "upgrade"] and lc.reasons_of(None) == []


def test_ruling_4_fewer_than_half_grounded_is_refused_and_exactly_half_passes():
    assert LETTER_GROUNDED_HALF == CITATION_HALF == 0.5
    half = lc.check([para("Food sticks. He lost 9 kg.", [2]), para("He weighs 71 kg. He lost 3 kg.", [6])], NOTE, AGE)
    assert (half.total, half.grounded) == (4, 2) and not half.refused            # exactly half passes
    under = lc.check([para("Food sticks. He lost 9 kg. He lost 3 kg.", [2])], NOTE, AGE)
    assert (under.total, under.grounded, under.refused) == (3, 1, True)
    assert lc.check([], NOTE, AGE).refused and lc.check([para("", [2])], NOTE, AGE).refused     # none is refused
    assert lc.sentences_of("One. Two!  Three? ") == ["One.", "Two!", "Three?"] and lc.sentences_of("") == []


def test_ruling_15_the_upgrade_rule_is_judged_per_sentence():
    # C's own shape (the second bench): a paragraph citing the results line and the arranged line. The true results
    # sentence stands, because line 7 holds every number of it; the sentence that turns the arranged tests into results
    # is replaced, because it has no number for a line to hold and line 12 only plans them.
    both = lc.check([para("Bloods last week showed Hb 10.8 with an MCV of 76. Ferritin, U and E and LFT were performed today.", [7, 12])], NOTE, AGE)
    assert verdicts(both) == [("kept", None), ("placeholder", "upgrade")]
    assert both.paragraphs == [f"Bloods last week showed Hb 10.8 with an MCV of 76. {words.LETTER_PLACEHOLDER}"]
    assert (both.total, both.grounded, both.placeholders) == (2, 1, 1)
    # The age among the sentence's numbers does not unseat the line that holds the rest.
    assert verdicts(lc.check([para("This 58-year-old man's bloods showed Hb 10.8.", [7, 12])], NOTE, AGE)) == [("kept", None)]
    # Numbers that no one cited line holds together, with a planned line cited: still an upgrade.
    assert verdicts(lc.check([para("Bloods showed Hb 10.8 and he weighs 71 kg.", [6, 7, 12])], NOTE, AGE)) == [("placeholder", "upgrade")]
    # Every cited line a planned one: an upgrade even when the numbers are held (the second way of the rule).
    assert verdicts(lc.check([para("A chest X-ray performed 2 weeks ago showed nothing.", [13])], NOTE, AGE)) == [("placeholder", "upgrade")]
    assert verdicts(lc.check([para("Ferritin was performed and the chest X-ray showed nothing.", [12, 13])], NOTE, AGE)) == [("placeholder", "upgrade")]
    # No planned line among the cited: a result verb stands, as before.
    assert verdicts(lc.check([para("Examination showed a BP of 142/86.", [6, 7])], NOTE, AGE)) == [("kept", None)]


def test_ruling_15_the_models_placeholder_is_caught_anywhere_in_a_sentence():
    # The second bench's A letters: a sentence ending in the placeholder (there, an allergy sentence, which ruling 16 now
    # drops before this rule is reached; here a sentence with no allergy word, so that this rule is the one judged).
    inside = lc.check([para(f"Food sticks. She has a history of {words.LETTER_PLACEHOLDER}. He lost 4 kg.", [2, 3])], NOTE, AGE)
    assert verdicts(inside) == [("kept", None), ("placeholder", "model_placeholder"), ("kept", None)]
    assert inside.paragraphs == [f"Food sticks. {words.LETTER_PLACEHOLDER} He lost 4 kg."]
    assert (inside.total, inside.grounded, inside.placeholders) == (3, 2, 1)
    # Mid-sentence too, never grounded though it holds no number; the closing bracket still ends a sentence, so the
    # words after it stand alone and are judged on their own.
    mid = lc.check([para(f"He takes {words.LETTER_PLACEHOLDER} for pain. He lost 9 kg.", [2])], NOTE, AGE)
    assert verdicts(mid) == [("placeholder", "model_placeholder"), ("kept", None), ("marked", "number")]     # ruling 20: marked, kept
    assert mid.paragraphs == [f"{words.LETTER_PLACEHOLDER} for pain. He lost 9 kg."]


def test_ruling_15_a_figure_inside_a_word_is_read_as_a_number():
    assert lc.numbers_in("T2DM, HbA1c 64 and vitamin B12 in 2 weeks") == {"2", "1", "64", "12"}
    note = numbered_lines("Subjective\nT2DM 9 years, HTN.\nType 2 diabetes for nine years.\n\nObjective\nHbA1c 64. eGFR 68.\n\n"
                          "Assessment\nA made-up impression.\n\nPlan\nNothing today.\n")
    # The lines: 1 Subjective, 2 T2DM, 3 type 2, 4 Objective, 5 HbA1c, 6 Assessment, 7 impression, 8 Plan, 9 nothing.
    # Both ways: type 2 diabetes against T2DM finds the 2, and T2DM against type 2 diabetes.
    assert verdicts(lc.check([para("She has had type 2 diabetes for 9 years.", [2])], note, set())) == [("kept", None)]
    assert verdicts(lc.check([para("T2DM for 9 years.", [3])], note, set())) == [("kept", None)]
    # A figure the lines lack is caught inside a word as well as alone: a unit the note does not give.
    # (ruling 20: a figure the lines lack marks the sentence, which stays as written.)
    assert verdicts(lc.check([para("HbA1c was 64 mmol/mol and eGFR 68 ml/min/1.73m².", [5])], note, set())) == [("marked", "number")]
    assert verdicts(lc.check([para("HbA1c was 64 and eGFR 68.", [5])], note, set())) == [("kept", None)]
    assert verdicts(lc.check([para("She has T2DM.", [5])], note, set())) == [("marked", "number")]


def test_ruling_16_an_allergy_sentence_stands_only_on_a_cited_allergy_line():
    # The third bench: six letters carried an allergy status the note does not hold, which no rule read because it
    # holds no number. Now a sentence holding the word allerg in any form stands only when one of the paragraph's valid
    # cited lines holds that word; otherwise it is dropped and counted, as the expectations rule drops its sentence.
    note = numbered_lines("Subjective\nSix weeks of food sticking.\nStopped before: ramipril (dry cough).\n"
                          "Allergic to penicillin (rash).\n\nObjective\nWeight 71 kg.\n\nAssessment\nA made-up impression.\n\n"
                          "Plan\nNothing today.\n")
    # The lines: 1 Subjective, 2 sticking, 3 stopped before, 4 allergic, 5 Objective, 6 weight, 7 Assessment, 8 impression,
    # 9 Plan, 10 nothing.
    # No known allergies, citing lines with no allergy word: dropped and counted, never replaced; the sentence beside it stands.
    none = lc.check([para("Food sticks. No known allergies.", [2, 6])], note, set())
    assert none.paragraphs == ["Food sticks."] and verdicts(none) == [("kept", None), ("dropped", "allergy")]
    assert (none.total, none.grounded, none.placeholders, none.dropped) == (2, 1, 0, 0)   # the four counts unchanged
    assert none.detail["allergies_dropped"] == 1 == lc.allergies_dropped(none.detail) and lc.allergies_dropped(None) == 0
    # Allergic to penicillin, citing the line that holds Allergic to penicillin: kept.
    kept = lc.check([para("She is allergic to penicillin, which causes a rash.", [4])], note, set())
    assert verdicts(kept) == [("kept", None)] and kept.detail["allergies_dropped"] == 0 and kept.grounded == 1
    # An allergy to ramipril, citing the Stopped before line: dropped; a side effect is not an allergy, and the paragraph goes.
    side = lc.check([para("She has an allergy to ramipril which caused a dry cough.", [3])], note, set())
    assert side.paragraphs == [] and verdicts(side) == [("dropped", "allergy")] and side.detail["allergies_dropped"] == 1
    # Every form of the word, and the rule judged before the others: a sentence citing no valid line, or holding a number
    # the lines lack, is dropped, not replaced; on the allergy line the other rules still apply.
    for sentence in ("Allergies: none.", "No allergens are known.", "She is allergic to nothing.", "ALLERGY: nil."):
        assert verdicts(lc.check([para(sentence, [2])], note, set())) == [("dropped", "allergy")], sentence
    assert verdicts(lc.check([para("No known allergies.", [99])], note, set())) == [("dropped", "allergy")]
    # The third bench's A letters: the model's placeholder inside an allergy sentence is dropped with it, so the page gets
    # neither the sentence nor a placeholder for it, as the prompt now says.
    assert verdicts(lc.check([para(f"She has an allergy to {words.LETTER_PLACEHOLDER}.", [2])], note, set())) == [("dropped", "allergy")]
    assert verdicts(lc.check([para("She has 3 allergies.", [4])], note, set())) == [("marked", "number")]    # ruling 20
    # A sentence with no allergy word is untouched by the rule, and a dropped sentence is not among the failed reasons.
    assert verdicts(lc.check([para("She weighs 71 kg.", [3, 6])], note, set())) == [("kept", None)]
    assert lc.reasons_of(none.detail) == [] and lc.reasons_of(side.detail) == []
    assert lc.reasons_of(lc.check([para("She has 3 allergies. No known allergies.", [4, 2])], note, set()).detail) == ["number"]


def test_ruling_33_the_expectation_pattern_reads_the_pronoun_form():
    # The fourth bench of 8a: the model wrote He hoped for a scan, which the pattern from v1 read as an ordinary
    # sentence, so it reached the page on lines that do not hold it. Now the pronoun form is an expectation sentence
    # too, and the rule of ruling 4 applies as before: kept on a cited line holding Patient's expectations and a
    # colon, else dropped and counted, never replaced.
    from openconsult.bench import letter_marks
    for sentence in ("He hoped for a scan.", "She wanted a stronger cream.", "The patient expects nothing.",
                     "They would like a referral.", "She is hoping for something that works.",
                     "The patient was hoping for a scan.", "This patient wants a scan.", "Patient's expectations were discussed."):
        assert lc.expectation_sentence(sentence), sentence
    for sentence in ("He has had six weeks of food sticking.", "She was started on a nasal spray two weeks ago.",
                     "They were told the plaques are not catching.", "He is expected in clinic next week.",
                     "The hoped-for result did not come."):
        assert not lc.expectation_sentence(sentence), sentence
    # Dropped and counted without the line among the valid lines; the sentence beside it stands; not a failed reason.
    dropped = lc.check([para("Food sticks. He hoped for a scan.", [2])], NOTE, AGE)
    assert dropped.paragraphs == ["Food sticks."] and verdicts(dropped) == [("kept", None), ("dropped", None)]
    assert (dropped.total, dropped.grounded, dropped.placeholders, dropped.dropped) == (2, 1, 0, 1)
    assert lc.reasons_of(dropped.detail) == []
    # Kept on the line, alone or among others; dropped, not replaced, when only the Assessment line is cited.
    assert verdicts(lc.check([para("She wanted a stronger cream.", [4])], NOTE, AGE)) == [("kept", None)]
    assert verdicts(lc.check([para("He hoped for a scan.", [2, 4])], NOTE, AGE)) == [("kept", None)]
    assert verdicts(lc.check([para("He hoped for a scan.", [9])], NOTE, AGE)) == [("dropped", None)]
    # An allergy sentence beside it is judged by its own rule, untouched.
    both = lc.check([para("He hoped for a scan. No known allergies.", [2])], NOTE, AGE)
    assert verdicts(both) == [("dropped", None), ("dropped", "allergy")] and both.dropped == 1 and both.detail["allergies_dropped"] == 1
    # The bench's two expectation readings go through the same function, so M4 on A reads the pronoun form too.
    def chain(text):
        return {"letters": [{"model_body": [{"text": text, "note_lines": [2]}], "body": [text]}]}
    assert letter_marks.expectation_model(chain("Food sticks. He hoped for a scan.")) and letter_marks.expectation_checked(chain("He hoped for a scan."))
    assert not letter_marks.expectation_model(chain("He has had six weeks of this.")) and not letter_marks.expectation_checked(chain("Food sticks."))


def test_ruling_20_a_true_sentence_holding_a_number_the_lines_do_not_give_is_kept_and_marked():
    # Run 9d: on case A the check replaced the sentence that correctly said ibuprofen was stopped, for a dose the cited
    # lines did not give, and what stayed read as if she still took it. Now a sentence whose only failure is a number
    # stays in the text as written, in the state marked, not grounded, with no placeholder; the page shows the words.
    one = lc.check([para("Food sticks on swallowing. He takes a made-up tablet 40 mg daily.", [2])], NOTE, AGE)
    assert one.paragraphs == ["Food sticks on swallowing. He takes a made-up tablet 40 mg daily."]        # the body as written
    assert verdicts(one) == [("kept", None), ("marked", "number")]
    assert (one.total, one.grounded, one.placeholders, one.dropped, one.marked, one.refused) == (2, 1, 0, 0, 1, False)
    assert one.detail["marked"] == 1 == lc.marked_count(one.detail) and lc.marked_count(None) == 0
    assert lc.reasons_of(one.detail) == ["number"]                                   # the bench's M3 still sees the number
    assert words.LETTER_PLACEHOLDER not in one.paragraphs[0]
    # The page's furniture: the marked sentences by paragraph of the body, a paragraph that put nothing on the page
    # skipped, and a sentence the doctor has edited away no longer marked.
    two = lc.check([para("Food sticks on swallowing. He takes a made-up tablet 40 mg daily.", [2]),
                    para("He hoped for a scan.", [2]),                                  # dropped whole: not on the page
                    para("He weighs 71 kg. He lost 9 kg.", [6])], NOTE, AGE)
    assert two.paragraphs == ["Food sticks on swallowing. He takes a made-up tablet 40 mg daily.", "He weighs 71 kg. He lost 9 kg."]
    assert lc.marked_sentences(two.detail, two.paragraphs) == [["He takes a made-up tablet 40 mg daily."], ["He lost 9 kg."]]
    edited = ["Food sticks on swallowing. He takes a made-up tablet daily.", "He weighs 71 kg. He lost 9 kg."]
    assert lc.marked_sentences(two.detail, edited) == [[], ["He lost 9 kg."]]
    assert lc.marked_sentences(None, ["x"]) == [[]]
    # A letter where most sentences hold such figures is still refused (the half rule): a letter full of unstated
    # figures never reaches the page as a letter.
    most = lc.check([para("He lost 9 kg. He lost 3 kg. He weighs 71 kg.", [6])], NOTE, AGE)
    assert (most.total, most.grounded, most.marked, most.refused) == (3, 1, 2, True)
    assert lc.check([para("He lost 9 kg. He weighs 71 kg.", [6])], NOTE, AGE).refused is False             # exactly half passes
    # A sentence that fails the number rule and another rule at once takes the other rule's treatment.
    assert verdicts(lc.check([para("He lost 9 kg.", [99])], NOTE, AGE)) == [("placeholder", "no_line")]
    assert verdicts(lc.check([para("Ferritin of 9 was performed today.", [12])], NOTE, AGE)) == [("placeholder", "upgrade")]
    assert verdicts(lc.check([para(f"He takes 9 mg of {words.LETTER_PLACEHOLDER}.", [2])], NOTE, AGE)) == [("placeholder", "model_placeholder")]
    assert verdicts(lc.check([para("He has 3 allergies.", [2])], NOTE, AGE)) == [("dropped", "allergy")]
    assert verdicts(lc.check([para("He hoped for 3 scans.", [2])], NOTE, AGE)) == [("dropped", None)]
    # The other rules stand: a true number in the lines is kept; the age is allowed.
    assert verdicts(lc.check([para("This 58-year-old man has lost 4 kg in 2 months.", [3])], NOTE, AGE)) == [("kept", None)]
