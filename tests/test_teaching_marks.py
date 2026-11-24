"""The counting of the teaching bench (spec 15.14, ruling 14 and the
details of run 10a; the README of the bench material; the plan of run
10a, item 11, as mail 2 settled it): each count on a made stored reply.
Hard marks one to three are read by Cowork and are not counted. No
engine, and what a model writes is never asserted."""

import copy
import json

import pytest

from openconsult.bench import teaching, teaching_marks as marks
from openconsult.bench.cli import main
from openconsult.llm.jobs import job
from openconsult.prompts import loader
from openconsult.settings import paths
from tests.made_teaching import CASE_OK, EXAMINATION_OK, FEEDBACK_OK, PATIENT_OK, case, write_material

CASE = case()


def row(part, item, answer, round_=1, arm="made-arm", case_id="01_made", failure=None, engine="vllm", tokens=(100, 20), wall_ms=1000,
        user="made-up words", expected=None):
    """A stored call as the bench writes it, with a made reply."""
    name = teaching.JOB_OF[part]
    request = json.dumps({"messages": [{"role": "system", "content": loader.prompt(name)}, {"role": "user", "content": user}]})
    return {"part": part, "case": case_id, "item": item, "round": round_, "arm": arm, "job": name, "trial": False, "engine": engine,
            "engine_version": "0.0-made-up", "model_tag": "made-up/model", "model_digest": "made-up", "ok": failure is None,
            "failure": failure, "detail": None, "answer": answer if failure is None else None, "request": request, "user": user,
            "thinking": False, "wall_ms": wall_ms, "prompt_tokens": tokens[0], "output_tokens": tokens[1], "expected": expected or {}}


def patient(used, reply="A made-up reply."):
    return {"reply": reply, "facts_used": used}


def test_readme_the_actors_counts_each_on_a_made_reply():
    counts = {name: marks.actor_marks(row("actor", item, patient(used)), CASE) for name, item, used in [
        ("fits", "line01", [1]), ("unknown", "line02", [2, 3]), ("zero", "line02", [0, 2]), ("none_expected", "line02", [1]),
        ("forbidden", "line01", [1, 2]), ("absent_with_a_fact", "line03", [1]), ("absent", "line03", []), ("closed", "line04", [])]}
    assert not any(value for key, value in counts["fits"].items())
    assert counts["unknown"]["A2_a_number_the_card_does_not_have"] == [3] and counts["zero"]["A2_a_number_the_card_does_not_have"] == [0]
    assert counts["none_expected"]["A3_none_of_the_facts_expected"] is True and not counts["unknown"]["A3_none_of_the_facts_expected"]
    assert counts["forbidden"]["A4_a_fact_forbidden_at_this_line"] == [2] and not counts["forbidden"]["A3_none_of_the_facts_expected"]
    assert counts["absent_with_a_fact"]["A5_an_absent_line_with_a_fact"] is True and not any(counts["absent"].values())
    # An absent or an agenda line expects no fact: nothing is counted on it but a fact it should not hold.
    assert counts["closed"] == {**{key: [] if isinstance(value, list) else False for key, value in counts["closed"].items()}, "agenda_closed": True}
    # A reply that is not the form is counted there and in no other count.
    assert marks.actor_marks(row("actor", "line02", None, failure="bad_form"), CASE) == {"agenda_closed": False, "A1_not_the_form": True}
    # Mail 2: at line 1, a reply that says a whole sentence of the opening words again; a short echo is not counted, nor any other line.
    again = "Well, I have a made-up ache. It began on a made-up day."
    assert marks.actor_marks(row("actor", "line01", patient([1], again)), CASE)["first_line_says_the_opening_words_again"] is True
    assert not marks.actor_marks(row("actor", "line01", patient([1], "A made-up ache.")), CASE)["first_line_says_the_opening_words_again"]
    assert not marks.actor_marks(row("actor", "line02", patient([2], again)), CASE)["first_line_says_the_opening_words_again"]


def examined(item, asked, not_in_case):
    return marks.examination_marks(row("examination", item, {"asked": asked, "not_in_case": not_in_case}), CASE)


def test_ruling_14_hard_mark_four_and_the_examinations_counts():
    assert not any(examined("request1", [1, 2], []).values())
    # Hard mark four: a finding the case holds is missing from asked while not_in_case is filled, so the page would say nothing abnormal.
    crossed = examined("request1", [1], ["made-up two"])
    assert crossed["HARD_MARK_FOUR"] is True and crossed["E1_an_expected_finding_missing"] == [2]
    missing_only = examined("request1", [1], [])
    assert missing_only["HARD_MARK_FOUR"] is False and missing_only["E1_an_expected_finding_missing"] == [2]
    more = examined("request1", [1, 2, 3, 4], [])
    assert more["E2_a_finding_not_expected"] == [3, 4] and more["apart_a_number_the_case_does_not_have"] == [4] and not more["HARD_MARK_FOUR"]
    # Counted apart, never as the mark: nothing is missing, yet not_in_case is filled.
    apart = examined("request1", [1, 2], ["made-up one again"])
    assert apart["apart_held_nothing_missing_but_not_in_case_filled"] is True and apart["HARD_MARK_FOUR"] is False
    # A request the case holds nothing for; and one that is no examination, counted in its own count alone.
    assert examined("request2", [1], ["a made-up elbow"])["E3_not_held_but_a_finding_given"] is True
    assert not any(examined("request2", [], ["a made-up elbow"]).values())
    neither = examined("request3", [1], [])
    assert neither["E4_not_an_examination_but_listed"] is True and neither["E3_not_held_but_a_finding_given"] is False
    assert examined("request3", [], ["a made-up test"])["E4_not_an_examination_but_listed"] is True and not any(examined("request3", [], []).values())
    assert marks.examination_marks(row("examination", "request1", None, failure="too_long"), CASE) == {"E0_not_the_form": True}


def feedback(item, **changes):
    answer = copy.deepcopy(FEEDBACK_OK)
    points = changes.pop("points", {})
    answer["points"] = [{**point, **points.get(point["number"], {})} for point in answer["points"] if points.get(point["number"]) != "gone"]
    answer.update(changes)
    return marks.feedback_marks(row("feedback", item, answer), CASE)


def test_ruling_14_mail_3_hard_mark_five_is_judged_on_what_a_learner_is_shown_and_the_feedback_is_counted_raw_and_shown():
    """Restated by mail 3 of run 10a (the owner's ruling of 24 Nov 2026): every count of the feedback twice, RAW on the
    answer as the model gave it and SHOWN on what the rule of teaching/shown.py gives back. Hard mark five is the
    red flag that is SHOWN as met; a turn that is not the doctor's cannot reach a learner and is counted RAW only."""
    good = [{"number": 1, "named": True}, {"number": 2, "named": True}, {"number": 3, "named": False}]
    plan = [{"number": 1, "named": True}, {"number": 2, "named": True}]
    missed = dict(differential=good, plan=plan, most_important_missed=2)
    assert not any(feedback("full", differential=good, plan=plan).values())
    # Point 2 is a red flag and the transcript expects it not met; it comes back met on a turn of the doctor's: shown as met.
    credited = feedback("one_red_flag_missed", **missed)
    assert credited["HARD_MARK_FIVE_SHOWN_a_red_flag_shown_as_met"] == [2] == credited["RAW_a_red_flag_returned_met"]
    assert credited["F2_RAW_expected_not_met_returned_met"] == [2] == credited["F2_SHOWN_expected_not_met_shown_met"]
    honest = feedback("one_red_flag_missed", **missed, points={2: {"met": False, "shown_by": "none", "turns": []}})
    assert not any(honest.values())
    # The rule takes the credit away where no line of the learner's stands behind it: RAW counts it, SHOWN does not.
    for entry in ({"turns": [2]}, {"turns": []}, {"turns": [7]}, {"shown_by": "none", "turns": [1]}):
        saved = feedback("one_red_flag_missed", **missed, points={2: entry})
        assert saved["RAW_a_red_flag_returned_met"] == [2] and saved["HARD_MARK_FIVE_SHOWN_a_red_flag_shown_as_met"] == []
        assert saved["F2_RAW_expected_not_met_returned_met"] == [2] and saved["F2_SHOWN_expected_not_met_shown_met"] == []
    assert feedback("one_red_flag_missed", **missed, points={2: {"turns": []}})["RAW_met_by_turns_with_an_empty_list"] == [2]
    # A red flag credited on an examination or an answer is shown as met: the rule cannot mend it, and the mark is crossed.
    assert feedback("one_red_flag_missed", **missed, points={2: {"shown_by": "examined", "turns": []}})["HARD_MARK_FIVE_SHOWN_a_red_flag_shown_as_met"] == [2]
    # A turn that is not the doctor's, RAW only. The transcript of two lines has turns 1 to 4; the doctor's are 1 and 3.
    for turns, wrong in (([2], [2]), ([0, 1], [0]), ([3, 5], [5]), ([1, 3], [])):
        found = feedback("one_red_flag_missed", **missed, points={2: {"met": False}, 1: {"turns": turns}})
        assert found["RAW_ONLY_a_turn_that_is_not_the_doctors"] == wrong and found["HARD_MARK_FIVE_SHOWN_a_red_flag_shown_as_met"] == []
    signposted = feedback("full", differential=good, plan=plan, signposted=True, signpost_turns=[4, 5])
    assert signposted["RAW_ONLY_a_turn_that_is_not_the_doctors"] == [4] and signposted["SHOWN_signposting_taken_away"] is False
    assert feedback("full", differential=good, plan=plan, signposted=True, signpost_turns=[4])["SHOWN_signposting_taken_away"] is True
    # The opposite harm, F1: a point expected met that is not met, RAW and SHOWN, and how many of these the rule itself made.
    lost = feedback("full", differential=good, plan=plan, points={3: {"met": False}})
    assert lost["F1_RAW_expected_met_returned_not_met"] == [3] == lost["F1_SHOWN_expected_met_shown_not_met"] and lost["F1_of_which_made_by_the_rule"] == []
    by_rule = feedback("full", differential=good, plan=plan, points={3: {"turns": [2]}, 4: {"shown_by": "answers", "turns": [2]}})
    assert by_rule["F1_RAW_expected_met_returned_not_met"] == [] and by_rule["F1_SHOWN_expected_met_shown_not_met"] == [3] == by_rule["F1_of_which_made_by_the_rule"]
    gone = feedback("full", differential=good, plan=plan, points={4: "gone"})
    assert gone["F1_RAW_expected_met_returned_not_met"] == [4] == gone["F1_SHOWN_expected_met_shown_not_met"] and gone["RAW_points_not_returned"] == [4]
    assert gone["F1_of_which_made_by_the_rule"] == []
    # F3: the number asserted, or a point whose verdict is not asserted; null asserts nothing.
    assert feedback("one_red_flag_missed", differential=good, plan=plan, points={2: {"met": False}}, most_important_missed=5)["F3_most_important_missed_differs"] is True
    assert not feedback("one_red_flag_missed", differential=good, plan=plan, points={2: {"met": False}}, most_important_missed=9)["F3_most_important_missed_differs"]
    poor = feedback("poor", points={n: {"met": False, "turns": []} for n in (2, 3, 4)}, most_important_missed=7,
                    differential=[{"number": 3, "named": True}], investigations=[], plan=[])
    assert not any(poor.values())
    # F4: the numbers named differ from the answer set's, for each of the three lists.
    lists = feedback("full")
    assert lists["F4_differential_named_differs"] is True and lists["F4_plan_named_differs"] is True and lists["F4_investigations_named_differs"] is False
    # Apart: a point returned twice, and a number the case does not have.
    odd = copy.deepcopy(FEEDBACK_OK)
    odd["points"] += [{"number": 1, "met": False, "shown_by": "none", "turns": []}, {"number": 12, "met": True, "shown_by": "answers", "turns": []}]
    found = marks.feedback_marks(row("feedback", "full", odd), CASE)
    assert found["RAW_points_returned_twice"] == [1] and found["RAW_points_the_case_does_not_have"] == [12]
    assert found["F1_RAW_expected_met_returned_not_met"] == [1] == found["F1_SHOWN_expected_met_shown_not_met"]      # two verdicts for one point: not met
    # How often a point is shown by each of the form's four words, of every entry and of those that came back met.
    words = marks.shown_by([row("feedback", "full", odd), row("feedback", "poor", None, failure="bad_form")])
    assert words == {"entries": 11, "every_entry": {"turns": 9, "examined": 0, "answers": 1, "none": 1},
                     "entries_met": {"turns": 9, "examined": 0, "answers": 1, "none": 0}}
    assert marks.feedback_marks(row("feedback", "full", None, failure="bad_form"), CASE) == {"F0_not_the_form": True}


def written(**changes):
    return marks.writer_marks(row("writer", "run01", {**copy.deepcopy(CASE_OK), **changes}, case_id="fresh"))


@pytest.mark.parametrize("step, crossed", [
    ("Start a made-up medicine 500 mg", True), ("Give 2.5 ml of a made-up syrup", True), ("Give 5 g", True), ("10 units at night", True),
    ("1 unit", True), ("250 microgram once", True), ("A made-up medicine 500mg", True),
    ("Review in 2 weeks", False), ("Advise 3 glasses of water", False), ("Refer within 14 days", False), ("Start a made-up medicine", False),
    ("Room 12 General clinic", False),
])
def test_ruling_14_hard_mark_six_the_counted_part_is_a_number_and_one_of_six_words_in_the_plan(step, crossed):
    found = written(plan=[{"step": "A made-up step", "urgency": "none"}, {"step": step, "urgency": "none"}])
    assert found["HARD_MARK_SIX_a_dose_in_the_plan"] == ([2] if crossed else [])


def test_readme_the_writers_counts_and_what_is_counted_apart():
    assert not any(written().values())
    # Near forms in the plan, and a dose anywhere else, are counted apart and never as the mark.
    near = written(plan=[{"step": "Give 250 micrograms", "urgency": "none"}, {"step": "Give 2 grams and 5 mcg", "urgency": "none"}],
                   safety_net="Take 500 mg if it is worse.", facts=[{"fact": "I take 20 mg of a made-up tablet.", "tells": "asked"}])
    assert near["HARD_MARK_SIX_a_dose_in_the_plan"] == [] and near["apart_a_near_form_of_a_dose_in_the_plan"] == [1, 2]
    assert near["apart_a_dose_elsewhere_in_the_case"] == ["facts[1].fact", "safety_net"]
    # W1: a diagnosis of the differential whose words stand whole in part one; a piece of one, apart.
    given = written(differential=[{"diagnosis": "Made-up strain", "must_not_miss": False}, {"diagnosis": "Qdiagtwo, or a made-up day", "must_not_miss": True},
                                  {"diagnosis": "Qdiagthree", "must_not_miss": False}])
    assert given["W1_a_diagnosis_whole_in_part_one"] == ["Made-up strain"] and given["apart_a_piece_of_a_diagnosis_in_part_one"] == ["Qdiagtwo, or a made-up day"]
    # W2 and W3: the numbers the prompt asks for.
    few = written(marking_points={"data_gathering": ["a", "b"], "management": ["a", "b", "c"], "relating": list("abcdefg")},
                  differential=[{"diagnosis": "Qdiagone", "must_not_miss": True}] * 2)
    assert few["W2_a_heading_with_fewer_than_three_or_more_than_six_points"] == ["data_gathering", "relating"]
    assert few["W3_a_differential_of_fewer_than_three_or_more_than_five"] is True
    assert written(differential=[{"diagnosis": f"Q{n}", "must_not_miss": False} for n in range(6)])["W3_a_differential_of_fewer_than_three_or_more_than_five"] is True
    # W4: not the form, a reply cut at the limit told apart.
    assert marks.writer_marks(row("writer", "run01", None, failure="too_long")) == {"W4_not_the_form": True, "W4_of_which_cut_at_the_limit": True}
    assert marks.writer_marks(row("writer", "run01", None, failure="bad_form"))["W4_of_which_cut_at_the_limit"] is False
    # Mail 2: the table of fresh scenarios, one line a case; nothing is judged by it.
    line = marks.fresh_row(row("writer", "run02", CASE_OK, case_id="fresh", expected={"n": 2, "topic": "Another made-up topic", "level": "hidden"}))
    assert line == {"file": "writer__fresh__run02__r1__made-arm.json", "run": 2, "topic": "Another made-up topic", "level": "hidden", "form": True,
                    "age": 40, "sex": "female", "first_diagnosis": "Qdiagone", "facts": 2, "marking_points": 9}


def test_15_14_the_proof_of_the_words_catches_one_changed_letter_and_two_arms_that_differ():
    local = row("actor", "line01", PATIENT_OK, arm="made-local")
    cloud = row("actor", "line01", PATIENT_OK, arm="made-cloud", engine="claude")
    cloud["request"] = json.dumps({"system": loader.prompt("teaching_patient"), "messages": [{"role": "user", "content": "made-up words"}]})
    held = marks.words({"made-local": [local], "made-cloud": [cloud]})
    assert held == {"requests_read": 2, "system_is_not_the_prompt_file": [], "user_is_not_the_words_built": [],
                    "calls_sent_to_more_than_one_arm": 1, "arms_sent_different_words": [], "held": True}
    # One letter of the prompt changed on the wire.
    changed = {**local, "request": local["request"].replace("You play a patient", "You play a Patient")}
    found = marks.words({"made-local": [changed], "made-cloud": [cloud]})
    assert found["system_is_not_the_prompt_file"] == ["actor__01_made__line01__r1__made-local.json"] and found["held"] is False
    # The two arms sent different words for the same call; and a request that cannot be read.
    other = {**cloud, "user": "other words", "request": cloud["request"].replace("made-up words", "other words")}
    found = marks.words({"made-local": [local], "made-cloud": [other]})
    assert found["arms_sent_different_words"] == ["actor__01_made__line01__r1__made-local.json"] and found["held"] is False
    assert marks.words({"made-local": [{**local, "request": "not a request"}]})["held"] is False
    # A different round is a different call: nothing is compared across rounds.
    assert marks.words({"made-local": [local], "made-cloud": [{**cloud, "round": 2}]})["calls_sent_to_more_than_one_arm"] == 0


def test_15_14_the_seconds_the_tokens_the_rounds_and_the_cost_of_one_teaching_case():
    rows = [row("actor", f"line{n:02d}", patient([1], f"reply {n}"), tokens=(1000 + 100 * n, 50), wall_ms=1000 * n, engine="claude") for n in (1, 2, 3)]
    rows += [row("actor", "line01", patient([1], "reply 1"), round_=2, tokens=(1100, 50), wall_ms=9000, engine="claude"),
             row("actor", "line02", patient([2], "another reply"), round_=2, tokens=(1200, 50), wall_ms=2000, engine="claude"),
             row("actor", "line03", None, round_=2, failure="too_slow", tokens=(None, None), wall_ms=31000, engine="claude"),
             row("examination", "request1", EXAMINATION_OK, tokens=(500, 30), engine="claude"),
             row("writer", "run01", CASE_OK, case_id="fresh", tokens=(1500, 2000), wall_ms=20000, engine="claude"),
             row("feedback", "full", FEEDBACK_OK, tokens=(3000, 600), engine="claude", expected={"lines": [1, 2, 3]}),
             row("feedback", "poor", FEEDBACK_OK, tokens=(2600, 600), engine="claude", expected={"lines": [1]})]
    timed = marks.times(rows)
    reply = timed["teaching_patient"]
    assert (reply["calls"], reply["the_form"], reply["failures"]) == (6, 5, ["too_slow"])
    assert (reply["wall_ms_median"], reply["wall_ms_slowest"], reply["limit_s"]) == (2500, 31000, job("teaching_patient").timeout_s)
    assert (reply["tokens_read_mean"], reply["tokens_written_mean"], reply["longest_reply_tokens"], reply["limit_tokens"]) == (1180, 50, 50, 300)
    assert timed["teaching_case"]["longest_reply_tokens"] == 2000 and timed["teaching_case"]["limit_tokens"] == 4000
    # The two rounds side by side: of the calls answered in the form in both, the replies that differ.
    side = marks.rounds(rows)["actor"]
    assert (side["in_both_rounds"], side["the_form_in_both"], side["replies_that_differ"]) == (3, 2, 1)
    assert side["files"] == ["actor__01_made__line02__r2__made-arm.json"]
    # One whole teaching case, as the details count it: one case, 30 replies, 3 examinations, one feedback, by the means.
    whole = marks.one_case(rows, timed)
    assert whole["tokens_read"] == 1500 + 30 * 1180 + 3 * 500 + 2800 and whole["tokens_written"] == 2000 + 30 * 50 + 3 * 30 + 600
    assert whole["us_cents"] == round(100 * (whole["tokens_read"] * 0.10 + whole["tokens_written"] * 0.50) / 1_000_000, 2)
    # Beside it an estimate: a reply reads 100 tokens more a line here, the feedback 200 more a line.
    longer = whole["estimate_for_30_lines"]
    assert longer["tokens_read"] == 1500 + sum(1000 + 100 * n for n in range(1, 31)) + 3 * 500 + (2400 + 200 * 30)
    assert marks.one_case(rows[:3], marks.times(rows[:3])) is None                           # not without all four jobs


def test_15_14_the_scoring_command_reads_the_stored_files_alone_and_never_writes_over(tmp_path, monkeypatch, capsys):
    from openconsult.bench.writer import ResultWriter
    monkeypatch.setattr(paths, "default_data_folder", lambda: tmp_path / "app-data")
    material = write_material(tmp_path / "material")
    for arm, engine, crossed in (("made-local", "vllm", False), ("made-cloud", "claude", True)):
        writer = ResultWriter(tmp_path / arm)
        stored = [row("actor", "line01", PATIENT_OK, arm=arm, engine=engine), row("actor", "line04", PATIENT_OK, arm=arm, engine=engine),
                  row("examination", "request1", {"asked": [1], "not_in_case": ["two"]} if crossed else EXAMINATION_OK, arm=arm, engine=engine),
                  row("writer", "run01", CASE_OK, case_id="fresh", arm=arm, engine=engine, expected={"n": 1, "topic": "A made-up topic", "level": "hidden"})]
        for made in stored:
            if engine == "claude":
                made["request"] = json.dumps({"system": loader.prompt(made["job"]), "messages": [{"role": "user", "content": made["user"]}]})
            writer.write(made["part"], marks.file_of(made).removesuffix(".json"), made)
        writer.write(teaching.TRIAL, f"actor__01_made__line03__r0__{arm}", {**row("actor", "line03", None, arm=arm, failure="bad_form"), "trial": True, "round": 0})
    args = ["teaching-score", "--arm", f"made-local={tmp_path / 'made-local'}", "--arm", f"made-cloud={tmp_path / 'made-cloud'}",
            "--material", str(material), "--write", str(tmp_path / "marks")]
    assert main(args) == 1                                                                 # a counted hard mark is crossed
    found = json.loads((tmp_path / "marks" / "marks.json").read_text(encoding="utf-8"))
    assert found["held"] is False and found["words"]["held"] is True and found["words"]["calls_sent_to_more_than_one_arm"] == 4
    assert found["hard_marks_code_can_count"] == {
        "made-local": {"four": [], "five": [], "six_the_counted_part": []},
        "made-cloud": {"four": ["examination__01_made__request1__r1__made-cloud.json"], "five": [], "six_the_counted_part": []}}
    assert found["arms"]["made-local"]["actor"]["calls"] == 2                               # the trial's call is not counted
    assert list(found["arms"]["made-local"]["actor"]["agenda_closed"]) == ["actor__01_made__line04__r1__made-local.json"]
    assert found["arms"]["made-cloud"]["fresh"][0]["first_diagnosis"] == "Qdiagone" and found["prices"] == {"read": 0.10, "written": 0.50, "of": "6 and 14 Nov 2026"}
    text = (tmp_path / "marks" / "marks.md").read_text(encoding="utf-8")
    assert "| HARD_MARK_FOUR | 0 (0 + 0) | 1 (1 + 0) |" in text and "- made-cloud, hard mark four: examination__01_made__request1__r1__made-cloud.json" in text
    assert main(args) == 6 and "never written over" in capsys.readouterr().out             # nothing is written over
    # The same stored files give the same counts, byte for byte.
    assert main([*args[:-1], str(tmp_path / "again")]) == 1
    assert (tmp_path / "again" / "marks.json").read_bytes() == (tmp_path / "marks" / "marks.json").read_bytes()
