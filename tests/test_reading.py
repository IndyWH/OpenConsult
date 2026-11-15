"""The turn rule of the reading view (spec 15.10 rulings 14, 35 and 42; the
details of step 6e, What a turn is), case by case on made-up pages. The
rule alone: no app, no page."""

from itertools import product

from openconsult.consult.reading import FOLD_WORDS, entries_of


def line(n: int, label: str, text: str = "made up words", unsure: bool = False) -> dict:
    return {"n": n, "label": label, "text": text, "unsure": unsure or label == "unsure"}


def page(*lines) -> list[dict]:
    """Lines given as (label, text) or (label, text, unsure), numbered from 1."""
    return [line(n, *given) for n, given in enumerate(lines, start=1)]


def read(lines: list[dict]) -> list[tuple[str, list[int]]]:
    return [(entry["speaker"], [held["n"] for held in entry["lines"]]) for entry in entries_of(lines)]


def test_rulings_35_42_neighbouring_lines_of_one_speaker_are_one_turn_so_the_page_reads_doctor_patient_doctor_patient():
    # The room run of 15 Nov 2026: one greeting and one question stood as ten lines of one to six words.
    lines = page(("doctor", "Good morning"), ("doctor", "come in"), ("doctor", "and have a seat."), ("patient", "Thank you"),
                 ("patient", "doctor."), ("doctor", "What brings you in?"), ("patient", "A cough."))
    assert read(lines) == [("doctor", [1, 2, 3]), ("patient", [4, 5]), ("doctor", [6]), ("patient", [7])]


def test_ruling_42_an_unsure_run_of_three_words_or_fewer_between_two_lines_of_one_speaker_sits_inside_that_turn():
    one = page(("doctor", "Let us go through them"), ("unsure", "Tell"), ("doctor", "me what you take"), ("patient", "Yes."))
    assert read(one) == [("doctor", [1, 2, 3]), ("patient", [4])]
    # A run of neighbouring unsure lines counts together: one word and two words are three, and the turn runs on.
    run = page(("patient", "It was"), ("unsure", "um"), ("unsure", "about then"), ("patient", "a week ago."))
    assert read(run) == [("patient", [1, 2, 3, 4])] and FOLD_WORDS == 3
    # The line inside the turn is still an unsure line: it is given no speaker (15.9 ruling 4).
    assert [held["label"] for held in entries_of(one)[0]["lines"]] == ["doctor", "unsure", "doctor"]
    # Two runs in one turn are each judged on their own.
    two = page(("doctor", "a"), ("unsure", "b"), ("doctor", "c"), ("unsure", "d e f"), ("doctor", "g"))
    assert read(two) == [("doctor", [1, 2, 3, 4, 5])]


def test_ruling_42_an_unsure_run_is_an_entry_of_its_own_at_a_change_of_speaker_at_the_start_at_the_end_and_with_more_than_three_words():
    # At a change of speaker 19 such words belonged to the speaker before and 12 to the one after: no rule would be right.
    change = page(("doctor", "Any pain"), ("unsure", "said"), ("patient", "No."))
    assert read(change) == [("doctor", [1]), ("unsure", [2]), ("patient", [3])]
    start = page(("unsure", "Right"), ("doctor", "come in"), ("doctor", "please."))
    assert read(start) == [("unsure", [1]), ("doctor", [2, 3])]
    end = page(("doctor", "Goodbye"), ("doctor", "then."), ("unsure", "Bye"))
    assert read(end) == [("doctor", [1, 2]), ("unsure", [3])]
    # Four words, in one line or over two: not folded, and the speaker's lines either side are two turns.
    long_line = page(("doctor", "Any pain"), ("unsure", "well not just now"), ("doctor", "at night?"))
    assert read(long_line) == [("doctor", [1]), ("unsure", [2]), ("doctor", [3])]
    long_run = page(("doctor", "Any pain"), ("unsure", "well not"), ("unsure", "just now"), ("doctor", "at night?"))
    assert read(long_run) == [("doctor", [1]), ("unsure", [2, 3]), ("doctor", [4])]


def test_ruling_14_a_line_the_check_named_that_had_no_first_speaker_still_counts_as_unsure():
    # The check's label is taken as the line's label, and the line is still shown as unsure: it counts as it is shown.
    named = page(("doctor", "Any pain"), ("patient", "said", True), ("patient", "No."))
    assert read(named) == [("doctor", [1]), ("unsure", [2]), ("patient", [3])]
    inside = page(("doctor", "Let us"), ("patient", "Tell", True), ("doctor", "me more"))
    assert read(inside) == [("doctor", [1, 2, 3])]
    # A line the check called unsure keeps its label and is shown unsure: the same.
    called = page(("patient", "It hurts"), ("doctor", "here and there and everywhere", True), ("patient", "a lot."))
    assert read(called) == [("patient", [1]), ("unsure", [2]), ("patient", [3])]


def test_6e_a_line_with_no_words_stays_where_it_stands_and_adds_no_words_and_a_page_of_one_line_and_an_empty_page():
    # A drug-name correction can leave a line with no words (the plan review of 6d, point 1; ruling 40). It counts by the
    # speaker it is shown with, and adds nothing to the count of three.
    same = page(("doctor", "Do you take"), ("doctor", ""), ("doctor", "every day?"))
    assert read(same) == [("doctor", [1, 2, 3])]
    other = page(("doctor", "Do you take"), ("patient", ""), ("doctor", "every day?"))
    assert read(other) == [("doctor", [1]), ("patient", [2]), ("doctor", [3])]
    counted = page(("doctor", "a"), ("unsure", "b c d"), ("unsure", ""), ("doctor", "e"))
    assert read(counted) == [("doctor", [1, 2, 3, 4])]
    assert read(page(("unsure", ""))) == [("unsure", [1])] and read(page(("patient", "Hello."))) == [("patient", [1])]
    assert entries_of([]) == []


def test_6e_every_line_is_in_exactly_one_entry_in_order_and_no_two_neighbouring_entries_are_one_speakers():
    # Every page of five lines that can be made of the three speakers and of lines of no, one and four words.
    kinds = [(label, text) for label in ("doctor", "patient", "unsure") for text in ("", "word", "four words in it")]
    pages = 0
    for made in product(kinds, repeat=5):
        lines = page(*made)
        entries = entries_of(lines)
        assert [held["n"] for entry in entries for held in entry["lines"]] == [1, 2, 3, 4, 5], made
        assert all(a["speaker"] != b["speaker"] for a, b in zip(entries, entries[1:])), made
        assert all(held is lines[held["n"] - 1] for entry in entries for held in entry["lines"])      # the page's own lines, not copies
        # A line under a speaker is always in an entry of that speaker: only an unsure line is ever shown inside another's turn.
        assert all(held["label"] in (entry["speaker"], "unsure") for entry in entries for held in entry["lines"]), made
        pages += 1
    assert pages == 9 ** 5
