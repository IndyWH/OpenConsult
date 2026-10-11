"""The notes and their five counts (spec 15.9, rulings 19 and 20; 13.3 mark
6; 13.4 rule 6; 15.8 ruling 16; the plan review's change 3). Made-up
notes against made-up transcripts; no model wrote any of them."""

from openconsult.bench.speech import keyfacts, notes
from openconsult.speech.matching import normalise
from tests.made_up_drugs import made_up_list
from tests.made_up_key_facts import MADE_UP

TRANSCRIPT = normalise("I take one gram of metforma twice a day for two weeks. Blood pressure one hundred and fifty over ninety five.")


def note(reasoning="Made up.", **sections):
    made = {"reasoning": reasoning, "subjective": [], "objective": [], "assessment": [], "plan": []}
    for section, entries in sections.items():
        made[section] = [{"text": t, "turns": turns} for t, turns in entries]
    return made


def test_ruling_19_every_figure_the_transcript_does_not_hold_with_doses_in_other_units_and_the_short_forms():
    made = note(subjective=[("Metforma 1g BD", [0]), ("Metforma 1000mg", [0]), ("Metforma 1,000 mg", [0]),
                            ("Course 2/52", [0]), ("BP 150/95", [1]), ("BP 110/52", [1]), ("T2DM, HbA1c pending", [0]),
                            ("Metforma 500mg", [0]), ("Follow up 3/12", [0])])
    found = notes.figures_not_spoken(made, TRANSCRIPT)
    assert [(f["figure"], f["unit"], f["text"]) for f in found] == [
        ("110", None, "BP 110/52"), ("52", None, "BP 110/52"),      # 110/52: the slash is over, both figures kept, neither spoken
        ("500", "mg", "Metforma 500mg"),                             # 500 mg is not 1 g
        ("3", None, "Follow up 3/12")]                               # three months was never said
    # 1 g, 1000 mg and 1,000 mg are the spoken gram; 2/52 is the spoken two weeks; 150 and 95 were spoken in words;
    # the 2 of T2DM and the 1 of HbA1c are not figures.
    assert notes.read_short_forms("2/52 and 110/52 and 24/7 and 25/7 and 1,000") == "2 weeks and 110/52 and 24 days and 25/7 and 1000"
    # A turn citation inside the text is not a figure, and 5-10 is two figures (found in the rehearsal's tables).
    cited = note(subjective=[("Pain lasting 5-10 mins, radiates to left arm [8].", [8]), ("Breathless [12, 13]", [12, 13])])
    found = notes.figures_not_spoken(cited, normalise("lasts five to ten minutes"))
    assert found == [] and notes.read_short_forms("mins [12, 13] and 5-10") == "mins   and 5 to 10"
    assert [f["figure"] for f in notes.figures_not_spoken(cited, normalise("lasts five minutes"))] == ["10"]
    assert notes.figures_with_units(normalise("40mg once, 2 weeks")) == [("40", "mg"), ("2", None)]


def test_15_8_ruling_16_a_reasoning_that_stops_in_the_middle_of_a_sentence_is_counted():
    assert notes.reasoning_cut("Chest pain on exertion; no red flags were")
    assert not notes.reasoning_cut("Chest pain on exertion. No red flags were raised.")
    assert not notes.reasoning_cut('He said "no pain at rest."') and not notes.reasoning_cut("Main problem (angina)?  ")
    assert not notes.reasoning_cut("Safety net given!") and notes.reasoning_cut("") and notes.reasoning_cut('said "')


def test_an_entry_whose_turns_are_empty_or_name_no_turn_that_exists_is_counted():
    made = note(subjective=[("a", []), ("b", [7]), ("c", [1, 7]), ("d", [0])], plan=[("e", [3]), ("f", [-1])])
    bad = notes.bad_turns(made, 4)
    assert [(b["section"], b["text"], b["turns"]) for b in bad] == [("subjective", "a", []), ("subjective", "b", [7]),
                                                                    ("plan", "f", [-1])]
    assert notes.bad_turns(note(), 4) == []


def test_ruling_19_the_drug_names_of_a_note(tmp_path):
    drugs = made_up_list(tmp_path)
    made = note(subjective=[("Metforma 1g BD", [0]), ("Takes Glucoform; medication name unclear", [0]),
                            ("Started Night Calm last week", [1])],
                plan=[("Continue night calm", [1]), ("Light mineral parafil for the skin", [2])])
    found = notes.drug_names_in_note(made, drugs, spoken_names=["metforma"], never_right=["metforma", "glucoform"])
    assert found["right_name_present"] == {"metforma": True, "glucoform": True}
    assert [(n["name"], n["section"]) for n in found["names_not_spoken"]] == [
        ("glucoform", "subjective"), ("night calm", "subjective"), ("night calm", "plan"), ("light mineral parafil", "plan")]
    assert found["unclear_entries"] == 1
    # One word of a longer name is not a name (the plan review's change 1): "light" alone, "night" alone.
    alone = notes.drug_names_in_note(note(plan=[("A light night", [0])]), drugs, [], ["dormirex"])
    assert alone["names_not_spoken"] == [] and alone["right_name_present"] == {"dormirex": False}


def test_13_4_rule_6_the_chance_between_two_notes_and_the_five_counts_together(tmp_path):
    facts = keyfacts.KeyFacts(MADE_UP)
    drugs = made_up_list(tmp_path)
    first = note("Fine.", subjective=[("No pain at rest", [0]), ("Metforma 1g BD", [0])], objective=[("BP 150/95", [1])])
    second = note("Fine", subjective=[("Pain at rest", [0]), ("Metforma 1g BD", [0])], objective=[("BP 150/90", [1])])
    one = notes.five_counts(first, TRANSCRIPT, 2, facts.facts_of("MU"), facts.negations, drugs, ["metforma"], [])
    two = notes.five_counts(second, TRANSCRIPT, 2, facts.facts_of("MU"), facts.negations, drugs, ["metforma"], [])
    assert [f["outcome"] for f in one["key_facts"]] == ["found", "found", "missing", "missing", "found"]
    assert [f["outcome"] for f in two["key_facts"]] == ["changed", "changed", "missing", "missing", "found"]
    assert not one["reasoning_cut"] and two["reasoning_cut"] and one["bad_turns"] == [] and one["entries"] == 3
    assert one["figures_not_spoken"] == [] and [f["figure"] for f in two["figures_not_spoken"]] == ["90"]
    assert notes.chance(one["key_facts"], two["key_facts"]) == {"facts": 5, "differ": 2, "ids": ["MU-01", "MU-02"]}
    assert notes.five_counts(first, TRANSCRIPT, 2, [], frozenset(), None, [], [])["drugs"] is None
