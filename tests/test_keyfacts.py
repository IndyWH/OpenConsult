"""The key facts (spec 15.9, ruling 20; the details of part two of 5c;
V1_LESSONS 9.3, 9.8; the plan review's change 5). A made-up file."""

from openconsult.bench.speech import keyfacts
from tests.made_up_key_facts import MADE_UP, write_made_up

FACTS = keyfacts.KeyFacts(MADE_UP)
NEG = FACTS.negations


def fact(fact_id):
    return next(f for f in MADE_UP["scripts"]["MU"]["facts"] if f["id"] == fact_id)


def note(**sections):
    made = {"reasoning": "made up.", "subjective": [], "objective": [], "assessment": [], "plan": []}
    for section, texts in sections.items():
        made[section] = [{"text": t, "turns": [0]} for t in texts]
    return made


def outcome(text, fact_id):
    return keyfacts.outcome_for_entry(keyfacts.normalise(text), fact(fact_id), NEG)


def test_ruling_20_the_four_outcomes_for_one_entry():
    # A negative: found with a word of negation, changed without, missing without the words.
    assert outcome("No pain at rest", "MU-01") == "found"
    assert outcome("Pain at rest", "MU-01") == "changed"                     # the negative was lost
    assert outcome("Denies resting pain", "MU-01") == "found"               # a word the file adds
    assert outcome("Chest tightness", "MU-01") == "missing"
    assert outcome("Pain relieved by rest", "MU-01") is None                # unless: passed over
    # A figure: found, changed where another figure stands, part where none does, missing without the words.
    assert outcome("BP 150/95", "MU-02") == "found"
    assert outcome("BP 150/90", "MU-02") == "changed"                       # a figure that was changed
    assert outcome("BP raised", "MU-02") == "part"
    assert outcome("Pulse 80", "MU-02") == "missing"
    assert outcome("Blood pressure one hundred and fifty over ninety five", "MU-02") == "found"   # words become figures
    # A dose in other units: 1 g or 1000 mg are both right figures.
    assert outcome("Metforma 1g BD", "MU-05") == "found" and outcome("Metforma 1000mg", "MU-05") == "found"
    assert outcome("Metforma 500mg", "MU-05") == "changed" and outcome("Metforma", "MU-05") == "part"


def test_the_best_outcome_counts_sections_limit_the_search_and_the_nearest_entry_is_the_one_with_the_most_groups():
    both = note(subjective=["Pain at rest", "No pain at rest"], plan=["Went to hospital last year"])
    assert keyfacts.check_note(both, fact("MU-01"), NEG)["outcome"] == "found"          # the best over entries
    # A fact looked for in the plan only: an entry elsewhere is not read.
    elsewhere = note(subjective=["Straight to hospital if pain at rest"])
    assert keyfacts.check_note(elsewhere, fact("MU-03"), NEG)["outcome"] == "missing"
    assert keyfacts.check_note(note(plan=["A and E if pain at rest"]), fact("MU-03"), NEG)["outcome"] == "found"
    # The nearest entry holds the most groups; none when no entry holds a single group.
    near = keyfacts.check_note(note(subjective=["Father is well", "No cardiac history"]), fact("MU-04"), NEG)
    assert near["outcome"] == "missing" and near["nearest"] == {"section": "subjective", "text": "Father is well", "groups_met": 1}
    none = keyfacts.check_note(note(subjective=["No cardiac history"]), fact("MU-04"), NEG)
    assert none["outcome"] == "missing" and none["nearest"] is None
    full = keyfacts.check_note(note(subjective=["Dad had an MI at 60"]), fact("MU-04"), NEG)
    assert full["outcome"] == "found" and full["nearest"]["groups_met"] == 2 and full["groups"] == 2
    # A fact that is not a negative, found only beside a word of negation, is listed for reading.
    beside = keyfacts.check_note(note(subjective=["No father, heart attack"]), fact("MU-04"), NEG)
    assert beside["only_beside_negation"] is True and full["only_beside_negation"] is False
    assert keyfacts.best([]) == "missing" and keyfacts.best(["missing", "part", "changed"]) == "changed"


def test_a_reading_that_is_not_whole_counts_a_fact_only_if_one_of_its_speeches_was_read():
    assert [f["id"] for f in FACTS.facts_of("MU")] == ["MU-01", "MU-02", "MU-03", "MU-04", "MU-05"]
    assert [f["id"] for f in FACTS.facts_of("MU", last_speech=2)] == ["MU-01", "MU-05"]
    assert [f["id"] for f in FACTS.facts_of("MU", last_speech=2, skipped=(2,))] == ["MU-01"]
    assert FACTS.facts_of("not a script") == []


def test_9_3_every_alternative_and_negation_word_goes_through_the_matching(tmp_path):
    read = keyfacts.KeyFacts.read(write_made_up(tmp_path))
    assert "nil" in read.negations and "afebrile" in read.negations and "not" in read.negations
    assert read.kinds[0] == "red_flag" and read.kinds[-1] == "plan"
    # Curly apostrophes and capitals on the note's side read the same as the file's words.
    assert keyfacts.outcome_for_entry(keyfacts.normalise("DENIES pain AT REST"), fact("MU-01"), read.negations) == "found"
