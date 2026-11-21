"""The number of a turn and the chips of a note entry (spec 15.13, ruling
71; the details of step 9f, The number of a turn and The chips of the
simple note), case by case on made-up pages. In the simple view an entry
of the note carries one small chip for each turn of speech it rests on,
so that the check of an entry against what was said stays one press
away. The two rules alone: no app, no page, and no model reads either."""

from openconsult.consult.note import turns_of as model_turns
from openconsult.consult.reading import chips_of, entries_of, numbers_of
from tests.test_reading import page

# Doctor, patient, a word with no speaker at a change of speaker, doctor with a word with no speaker inside, patient.
PAGE = page(("doctor", "Good morning"), ("doctor", "come in."), ("patient", "Thank you."), ("unsure", "Yes."),
            ("doctor", "What do you"), ("unsure", "take"), ("doctor", "for the sugar?"), ("patient", "A white tablet."))


def numbers(lines: list[dict]) -> dict[int, int]:
    return numbers_of(entries_of(lines))


def test_9f_the_turns_are_numbered_from_1_in_order_as_the_page_shows_them_and_an_unsure_entry_like_any_turn():
    found = numbers(PAGE)
    # Five entries: lines 1 and 2; line 3; the unsure line 4 on its own; lines 5 to 7, the unsure word folded in; line 8.
    assert found == {1: 1, 2: 1, 3: 2, 4: 3, 5: 4, 6: 4, 7: 4, 8: 5}
    # Every line has exactly one number, the numbers run from 1 with none left out, and they never go back.
    assert sorted(found) == [line["n"] for line in PAGE] and sorted(set(found.values())) == [1, 2, 3, 4, 5]
    assert [found[n] for n in sorted(found)] == sorted(found.values())
    assert numbers([]) == {} and numbers(page(("patient", "Yes."))) == {1: 1}
    # The turns a model cites are another rule's, numbered from 0, and stay as they are: nothing here reaches them.
    assert [turn["n"] for turn in model_turns(PAGE)] == [0, 1, 2, 3, 4, 5, 6] and model_turns(PAGE)[0]["lines"] == [1, 2]


def test_ruling_71_one_chip_for_each_turn_that_holds_a_cited_line_in_order_each_number_once():
    found = numbers(PAGE)
    assert chips_of([3], found) == [2]                                  # an entry in one turn
    assert chips_of([1, 3, 8], found) == [1, 2, 5]                      # in several: one each, in order
    assert chips_of([8, 1, 3, 1], found) == [1, 2, 5]                   # however the record lists its lines
    assert chips_of([5, 6, 7], found) == [4] and chips_of([1, 2], found) == [1]   # several lines of one turn: one chip
    assert chips_of([], found) == []                                    # an entry that cites nothing has none
    assert chips_of([6], found) == [4]                                  # a line inside a folded unsure run: the turn it sits in
    assert chips_of([4], found) == [3]                                  # an unsure entry of its own is a turn like any
    assert chips_of([2, 99], found) == [1] and chips_of([99], found) == []   # a cited line that is not on the page gives none


def test_ruling_71_no_chip_is_dropped_or_gathered_into_a_range_however_many_there_are():
    # Since run 9b a note entry in cloud mode cites 20 to 55 lines (15.13, ruling 46): forty lines here, in twelve turns.
    lines = page(*[("doctor" if (n // 4) % 2 == 0 else "patient", "word") for n in range(48)])
    found = numbers(lines)
    assert len(set(found.values())) == 12
    cited = list(range(1, 41))
    assert chips_of(cited, found) == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert chips_of(list(range(1, 49)), found) == list(range(1, 13))


def test_9f_after_a_speaker_is_corrected_the_turns_are_those_of_that_moment_and_the_chips_follow():
    lines = page(("doctor", "Good morning"), ("doctor", "I take a white tablet."), ("doctor", "Every day?"), ("patient", "Yes."))
    assert numbers(lines) == {1: 1, 2: 1, 3: 1, 4: 2} and chips_of([2, 4], numbers(lines)) == [1, 2]
    # The doctor sets line 2 to the patient: it is now a turn of its own, and every later turn has a new number.
    corrected = [{**line, "label": "patient"} if line["n"] == 2 else line for line in lines]
    assert numbers(corrected) == {1: 1, 2: 2, 3: 3, 4: 4} and chips_of([2, 4], numbers(corrected)) == [2, 4]
    # The entry's lines are the record's and did not change: only how the page is shown did.
    assert chips_of([1, 2, 3], numbers(lines)) == [1] and chips_of([1, 2, 3], numbers(corrected)) == [1, 2, 3]
