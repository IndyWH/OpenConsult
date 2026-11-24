"""The rule by code between the feedback's answer and the page (spec
15.14; the owner's rule of 24 Nov 2026, mail 3 of run 10a, point 3, as
mail 4 keeps it: (a), (d), (e) and (f), and that dropping a turn never
changes met). Made answers and a made consultation; what a model writes
is never asserted."""

import copy

from openconsult.teaching.shown import doctors_turns, shown

# A made consultation of three lines: the doctor's turns are 1, 3 and 5, the patient's 2, 4 and 6.
SPOKEN = [("doctor", "first line"), ("patient", "first reply"), ("doctor", "second line"), ("patient", "second reply"),
          ("doctor", "third line"), ("patient", "third reply")]


def point(number, met=True, turns=(1,)):
    return {"number": number, "met": met, "turns": list(turns)}


def answer(points, signposted=False, signpost_turns=()):
    return {"reasoning": "made up", "points": points, "differential": [{"number": 1, "named": True}], "differential_extra": ["made up"],
            "investigations": [], "investigations_extra": [], "plan": [], "plan_extra": [], "most_important_missed": 0, "done_well": [1],
            "signposted": signposted, "signpost_turns": list(signpost_turns)}


def test_mail_3_an_answer_with_nothing_to_mend_comes_back_the_same():
    given = answer([point(1), point(2, turns=[3, 5]), point(3, turns=[]), point(4, met=False, turns=[]), point(5, met=False, turns=[1])],
                   signposted=True, signpost_turns=[3])
    before = copy.deepcopy(given)
    assert shown(given, SPOKEN, 5) == before and given == before          # the same, and the answer itself is not changed
    assert doctors_turns(SPOKEN) == {1, 3, 5} and doctors_turns([]) == set()


def test_mail_3_a_a_number_that_is_not_a_turn_of_the_doctors_is_dropped_from_every_list():
    given = answer([point(1, turns=[1, 2, 3]), point(2, turns=[4, 6]), point(3, met=False, turns=[2, 0, 7, 5])],
                   signposted=True, signpost_turns=[4, 5, 9, -1])
    found = shown(given, SPOKEN, 3)
    assert [p["turns"] for p in found["points"]] == [[1, 3], [], [5]]     # a turn of the patient's, and a number that is not there
    assert found["signpost_turns"] == [5] and found["signposted"] is True


def test_mail_4_dropping_a_turn_never_changes_met():
    # The form cannot tell a point shown by an answer from one shown in the consultation: a point that came back met
    # stays met when every one of its turns is dropped, and one that came back with no turn at all stays met too.
    given = answer([point(1, turns=[2, 4]), point(2, turns=[]), point(3, turns=[8]), point(4, turns=[2, 3]), point(5, met=False, turns=[2])])
    found = shown(given, SPOKEN, 5)
    assert [(p["met"], p["turns"]) for p in found["points"]] == [(True, []), (True, []), (True, []), (True, [3]), (False, [])]
    assert [p["met"] for p in found["points"]] == [p["met"] for p in given["points"]]


def test_mail_3_d_signposted_is_false_when_no_turn_is_left():
    assert shown(answer([point(1)], signposted=True, signpost_turns=[2, 6]), SPOKEN, 1)["signposted"] is False
    assert shown(answer([point(1)], signposted=True, signpost_turns=[]), SPOKEN, 1)["signposted"] is False
    assert shown(answer([point(1)], signposted=True, signpost_turns=[1]), SPOKEN, 1)["signposted"] is True
    assert shown(answer([point(1)], signposted=False, signpost_turns=[1]), SPOKEN, 1)["signposted"] is False      # never from false to true


def test_mail_3_e_a_point_that_did_not_come_back_is_not_met_and_one_that_came_back_twice_only_if_every_entry_is():
    given = answer([point(1), point(3, turns=[3]), point(3, turns=[5]), point(4), point(4, met=False, turns=[]),
                    point(5, turns=[1]), point(5, turns=[2]), point(9)])
    found = shown(given, SPOKEN, 6)
    assert [p["number"] for p in found["points"]] == [1, 2, 3, 4, 5, 6]      # one entry a marking point of the case, in order; point 9 is none of them
    by_number = {p["number"]: p for p in found["points"]}
    assert by_number[2] == {"number": 2, "met": False, "turns": []} == {**by_number[6], "number": 2}
    assert (by_number[3]["met"], by_number[3]["turns"]) == (True, [3, 5])     # twice, and every entry met
    assert by_number[4]["met"] is False                                       # twice, one entry not met
    assert (by_number[5]["met"], by_number[5]["turns"]) == (True, [1])        # twice and both met: the patient's turn is dropped, met stands


def test_mail_3_f_nothing_is_ever_turned_from_not_met_to_met():
    not_met = [point(n, met=False, turns=turns) for n, turns in enumerate([[1, 3], [], [2], [5], [9]], 1)]
    found = shown(answer(not_met + [point(1), point(2, turns=[])]), SPOKEN, 5)
    assert not any(p["met"] for p in found["points"])
    # And every other part of the answer is given back as it came.
    given = answer([point(1, turns=[2])], signposted=True, signpost_turns=[2])
    found = shown(given, SPOKEN, 1)
    assert {key: value for key, value in found.items() if key not in ("points", "signposted", "signpost_turns")} == {
        key: value for key, value in given.items() if key not in ("points", "signposted", "signpost_turns")}
