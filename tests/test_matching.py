"""The matching of words (spec 15.9, the details of 5c: the matching;
ruling 15). Made-up words only."""

from openconsult.speech.matching import Pair, SPELLINGS, align, hyphenated, normalise


def test_the_matching_ignores_capitals_and_punctuation_and_makes_numbers_units_hyphens_and_spellings_the_same():
    assert normalise("Right. The BP: 150 over 95, I'd say!") == ["right", "the", "bp", "150", "over", "95", "i'd", "say"]
    assert normalise("one hundred and fifty over ninety five") == ["150", "over", "95"]
    assert normalise("twenty-five, two thousand and ten, one point five") == ["25", "2010", "1.5"]
    assert normalise("eighty milligrams, five hundred micrograms, two per cent, 10 percent") == \
        ["80", "mg", "500", "mcg", "2", "%", "10", "%"]
    assert normalise("co-codamol and walk-in") == ["cocodamol", "and", "walkin"]
    assert normalise("co codamol", joinable=hyphenated("co-codamol")) == ["cocodamol"]
    assert normalise("anemia, hemoglobin, color, center") == ["anaemia", "haemoglobin", "colour", "centre"]
    assert normalise("Anaemia") == normalise("anemia") and "anemia" in SPELLINGS


def test_the_steps_run_in_one_fixed_order_apostrophes_hyphens_numbers_units_spellings():
    # Hyphens and joining before numbers: three wheeler joins to the
    # script's three-wheeler and does not become 3 wheeler first.
    joinable = hyphenated("his three-wheeler")
    assert normalise("three wheeler", joinable) == ["threewheeler"] == normalise("three-wheeler")
    assert normalise("three wheeler") == ["3", "wheeler"]
    # A curly apostrophe and a straight one are the same word.
    assert normalise("don’t") == normalise("don't") == ["don't"]
    # A slash between two figures is the word over; a figure against its unit is split.
    assert normalise("148/88") == ["148", "over", "88"] == normalise("148 over 88")
    assert normalise("80mg twice") == ["80", "mg", "twice"] == normalise("80 mg twice")
    assert normalise("B12 and 10/10/2026") == ["b12", "and", "10/10/2026"]      # not two figures: left alone
    # Numbers before units, so five milligrams is 5 mg.
    assert normalise("five milligrams") == ["5", "mg"]


def test_the_alignment_classes_each_page_word_as_heard_in_place_of_or_from_nowhere():
    spoken = normalise("no chest pain at rest today")
    page = normalise("no chess bone at rest today thank you")
    pairs = align(spoken, page)
    kinds = [p.kind for p in pairs]
    assert kinds == ["heard", "replaced", "replaced", "heard", "heard", "heard", "nowhere", "nowhere"]
    assert pairs[1] == Pair(1, 1, "replaced") and pairs[6] == Pair(None, 6, "nowhere")
    # Words dropped are missing; the longer side of a differing block gives the extras.
    dropped = align(normalise("go straight to the hospital"), normalise("go hospital"))
    assert [p.kind for p in dropped] == ["heard", "missing", "missing", "missing", "heard"]
    mixed = align(["a", "b", "c", "d"], ["a", "x", "d"])
    assert [p.kind for p in mixed] == ["heard", "replaced", "missing", "heard"]
    assert align([], []) == [] and [p.kind for p in align([], ["x"])] == ["nowhere"]
