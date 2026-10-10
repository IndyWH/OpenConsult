"""The reference from a script (spec 13.4; 15.9, the details of 5c: the
reference; 13.4 rule 5). The script is made up."""

from openconsult.bench.speech import reference
from openconsult.bench.speech.reference import Agreed, agreement, build, names_as_cut, occurrences, safety_nets_as_cut
from openconsult.speech.matching import align, normalise
from tests.made_up_recordings import SCRIPT


def test_13_4_the_reference_is_the_scripts_speeches_numbered_from_one_with_their_speakers():
    ref = build(SCRIPT)
    assert [(s.number, s.speaker) for s in ref.speeches] == [(1, "DOCTOR"), (2, "PATIENT"), (3, "DOCTOR"),
                                                            (4, "PATIENT"), (5, "DOCTOR"), (6, "PATIENT")]
    assert ref.speech_of(3).text.startswith("Your blood pressure")          # the stage direction is not spoken
    assert ref.norms[:5] == ["any", "chest", "pain", "at", "rest"]
    assert [w.speech for w in ref.words if w.norm == "metformin"] == [2]
    assert "cocodamol" in ref.joinable and ref.norms.count("cocodamol") == 1
    assert ref.norms[ref.norms.index("is") + 1:ref.norms.index("is") + 4] == ["150", "over", "95"]
    assert ref.last_speech is None and reference.LEAST_ARMS_TO_AGREE == 3


def test_a_reading_that_is_not_whole_is_cut_after_its_last_speech():
    cut = build(SCRIPT, last_speech=4)
    assert [s.number for s in cut.speeches] == [1, 2, 3, 4] and cut.last_speech == 4
    assert "hospital" not in cut.norms and "high" in cut.norms
    whole = build(SCRIPT)
    names = {"metformin": 1, "co-codamol": 1, "aspirin": 0}
    assert names_as_cut(whole, names) == {"metformin": [(18, 18)], "co-codamol": [(20, 20)], "aspirin": []}
    assert occurrences(whole, "Chest Pain") == [(1, 2), (12, 13)]            # a run of words, as whole words
    assert occurrences(whole, "pain at") == [(2, 3), (13, 14)] and occurrences(whole, "rest.") == [(4, 4), (15, 15), (36, 36)]
    assert safety_nets_as_cut(whole, [5]) == [5] and safety_nets_as_cut(cut, [5]) == []


def test_the_notes_on_speeches_read_differently_change_the_reference():
    noted = build(SCRIPT, read_differently=[{"speech": 4, "said": "Is that very high, doctor?"},
                                            {"speech": 6, "skipped": True}])
    assert noted.speech_of(4).text == "Is that very high, doctor?" and "very" in noted.norms
    assert [s.number for s in noted.speeches] == [1, 2, 3, 4, 5]             # speech 6 was not read
    assert noted.speech_of(5).speaker == "DOCTOR"


def page_of(ref, text):
    page = normalise(text, ref.joinable)
    return align(ref.norms, page), page


def test_13_4_rule_5_where_every_arm_agrees_against_the_script_it_counts_against_no_arm():
    ref = build("**DOCTOR:** heart sounds are normal, no murmurs\n")
    same = {arm: page_of(ref, "heart sounds are normal normalist") for arm in ("a", "b", "c")}
    found = agreement(ref, same)
    # The alignment pairs the differing words in order: normalist stands
    # in place of no, and murmurs is missing from every arm.
    assert found == [Agreed(4, "no", "normalist", "agreed", ("a", "b", "c")),
                     Agreed(5, "murmurs", None, "missing_everywhere", ("a", "b", "c"))]
    # Two arms are not enough; three where one heard it right is not agreement;
    # three different words are not agreement.
    assert agreement(ref, {k: same[k] for k in ("a", "b")}) == []
    heard = dict(same, c=page_of(ref, "heart sounds are normal, no murmurs"))
    assert agreement(ref, heard) == []
    different = dict(same, c=page_of(ref, "heart sounds are normal nervous"))
    assert [a.kind for a in agreement(ref, different)] == ["missing_everywhere"]
