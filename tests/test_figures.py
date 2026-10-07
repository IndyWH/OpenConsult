"""The figures of 7 Oct in the bench's own tool (spec 15.8, rulings 17,
18, 21, 22 and 26, and the details bullet on the publish step). Every
arm, reply and figure here is made up."""

import copy
import json

import pytest

from openconsult.bench import export, figures, score
from openconsult.bench.cli import main
from openconsult.bench.writer import ResultWriter
from tests.test_score import a_pass, full_results

ROUNDS = {"card_mib": 24564, "baseline": "base", "baseline_together": "base-together",
          "arms": {"base": {"engine": "Base", "way": "one after another"},
                   "other": {"engine": "Other", "way": "one after another"},
                   "base-together": {"engine": "Base", "way": "together"},
                   "other-together": {"engine": "Other", "way": "together"}},
          "rounds": {"1": {"chain": "A1", "stress": ["B1", "B2", "B3"]}, "2": {"chain": "A2", "stress": ["B4", "B5", "B6"]},
                     "3": {"chain": "A3", "stress": ["B7", "B8", "B9", "B10"]}}}
REASONING_OK = {"reasoning": "Made up.", "time_critical_possible": False, "already_done_or_arranged": False, "urgent_actions": []}


def a_call(outcome="ok", wall_ms=1000, write_ms=800, output_tokens=100, reply=REASONING_OK):
    text = json.dumps(reply) if isinstance(reply, dict) else reply
    return {"outcome": outcome, "wall_ms": wall_ms, "write_ms": write_ms, "output_tokens": output_tokens, "text": text}


def an_arm(by_round=(4000, 4000, 4000), stress_ms=3000, only_a=False, emergency_fire=True):
    """A made-up arm: results that meet every mark, with the passes of
    each chain at 0 taking the round's time, and one made-up call for
    each pass's two jobs."""
    results = copy.deepcopy(full_results(emergency_fire=emergency_fire))
    chain_ms = {f"A{i + 1}": ms for i, ms in enumerate(by_round)}
    calls = {}
    for (case, chain), r in list(results.items()):
        if only_a and chain not in chain_ms:
            del results[(case, chain)]
            continue
        for p in r["passes"]:
            p["wall_ms"] = chain_ms.get(chain, stress_ms)
            for job in ("alarm", "assessment"):
                calls[(case, chain, p["point"], job)] = a_call(wall_ms=p["wall_ms"] // 2, write_ms=p["wall_ms"] // 4)
    return {"results": results, "calls": calls}


def four_arms(other=(3500, 3500, 3500), base=(4000, 4000, 4000), other_together=(3000, 3000, 3000),
              base_together=(3400, 3400, 3400)):
    return {"base": an_arm(base), "other": an_arm(other),
            "base-together": an_arm(base_together, only_a=True), "other-together": an_arm(other_together, only_a=True)}


def judgement(found, arm, against):
    return next(j for j in found["judgements"] if (j["arm"], j["against"]) == (arm, against))


@pytest.mark.parametrize("round_ms, faster", [((3500, 3500, 3500), True), ((3500, 3501, 3500), False)])
def test_ruling_17_the_half_second_on_the_line_and_just_under_it(round_ms, faster):
    found = figures.figures(ROUNDS, four_arms(other=round_ms))
    j = judgement(found, "other", "base")
    assert j["typical_ms"] == list(round_ms) and j["against_typical_ms"] == [4000, 4000, 4000]
    assert j["shorter_by_ms"] == [4000 - ms for ms in round_ms] and j["faster"] is faster
    line = next(l for l in figures.as_markdown(found).splitlines() if l.startswith("- other (") and " against base (" in l)
    assert ("Faster by the rule: at least 0.50 s shorter in each of the three rounds" in line) is faster
    assert ("Not called faster: under 0.50 s in at least one round. A figure, not a win." in line) is not faster
    # The seven judgements, from the arms' roles and not from their names.
    assert [(j["arm"], j["against"]) for j in found["judgements"]] == [
        ("other", "base"), ("other-together", "base-together"), ("base-together", "base"), ("other-together", "base")]


def test_ruling_17_one_round_under_the_line_is_a_figure_and_not_a_win():
    found = figures.figures(ROUNDS, four_arms(other=(3400, 3400, 3600)))
    j = judgement(found, "other", "base")
    assert j["shorter_by_ms"] == [600, 600, 400] and j["in_every_round"] is False and j["verdict"] == "a figure, not a win"
    said = figures.as_markdown(found)
    assert "other (3.40, 3.40, 3.60 s) against base (4.00, 4.00, 4.00 s): 0.60 s shorter, then 0.60 s shorter, then 0.40 s shorter. " \
           "Not called faster: under 0.50 s in at least one round. A figure, not a win." in said
    # A difference below zero is written as longer, never as shorter by a negative number (change 3).
    found = figures.figures(ROUNDS, four_arms(other=(3990, 4050, 4010)))
    assert "0.01 s shorter, then 0.05 s longer, then 0.01 s longer." in figures.as_markdown(found)
    assert judgement(found, "other", "base")["shorter_by_ms"] == [10, -50, -10]


def test_ruling_21_an_unsteady_day_calls_no_arm_faster():
    found = figures.figures(ROUNDS, four_arms(base=(4000, 4300, 4000), other=(3000, 3000, 3000)))
    assert found["steadiness"] == {"typical_ms_by_round": [4000, 4300, 4000], "spread_ms": 300, "steady": False, "line_ms": 250}
    j = judgement(found, "other", "base")
    assert j["shorter_by_ms"] == [1000, 1300, 1000] and j["in_every_round"] and not j["faster"]
    assert j["verdict"] == "the day was unsteady, so no arm is called faster"
    assert all(not j["faster"] for j in found["judgements"])
    said = figures.as_markdown(found)
    assert "The day was unsteady: the typical pass of base was 4.00, 4.30, 4.00 s in the three rounds, 0.30 s apart, " \
           "over the 0.25 s line. No arm is called faster." in said
    # On the line is steady.
    found = figures.figures(ROUNDS, four_arms(base=(4000, 4250, 4000), other=(3000, 3000, 3000)))
    assert found["steadiness"]["steady"] is True and judgement(found, "other", "base")["faster"] is True
    assert "The day was steady: the typical pass of base was 4.00, 4.25, 4.00 s in the three rounds, within 0.25 s " \
           "(the line is 0.25 s)." in figures.as_markdown(found)


def test_ruling_18_a_failed_chain_at_0_is_set_against_one_at_0_5():
    arms = four_arms(other=(3000, 3000, 3000))
    arms["other"]["results"][("15", "A2")]["failed"] = "a call failed at point 8: too_long"
    found = figures.figures(ROUNDS, arms)
    other = found["arms"]["other"]
    assert other["candidate"] is False and other["at_temperature_0"]["failed"] == ["15/A2"]
    assert other["replies"]["failed_chains"] == {"at 0.0": ["15/A2"]}
    assert judgement(found, "other", "base")["verdict"] == "not a candidate, so not called faster"
    assert "Not a candidate, so not called faster." in figures.as_markdown(found)
    arms = four_arms(other=(3000, 3000, 3000))
    arms["other"]["results"][("15", "B4")]["failed"] = "a call failed at point 8: too_long"
    found = figures.figures(ROUNDS, arms)
    other = found["arms"]["other"]
    assert other["candidate"] is True and other["stress_test"]["failed"] == ["15/B4"]
    assert other["all_chains"]["hard_met"] is False and other["replies"]["failed_chains"] == {"at 0.5": ["15/B4"]}
    assert judgement(found, "other", "base")["faster"] is True
    assert "failed: 15/B4. It bars nothing." in figures.as_markdown(found)


def test_ruling_26_the_temperature_is_read_from_the_data_and_a_wrong_rounds_file_is_refused():
    arms = four_arms()
    for arm in arms.values():
        for (case, chain), r in arm["results"].items():
            r["temperature"] = {"A1": 0.5, "B1": 0.0}.get(chain, r["temperature"])   # the names lie
    rounds = copy.deepcopy(ROUNDS)
    rounds["rounds"]["1"] = {"chain": "B1", "stress": ["A1", "B2", "B3"]}
    found = figures.figures(rounds, arms)
    assert found["arms"]["base"]["rounds"]["1"]["chain"] == "B1" and found["arms"]["base"]["candidate"] is True
    assert found["arms"]["base"]["at_temperature_0"]["chains"] == 3
    with pytest.raises(figures.FiguresRefused, match="chain A1 is named as a round's chain at temperature 0, "
                                                      "but its results are at temperature 0.5"):
        figures.figures(ROUNDS, arms)
    with pytest.raises(figures.FiguresRefused, match="names arms that were not given: other-together"):
        figures.figures(ROUNDS, {name: arm for name, arm in four_arms().items() if name != "other-together"})


def test_ruling_22_the_tokens_written_and_the_time_for_each_token():
    calls = [a_call(wall_ms=1000, write_ms=800, output_tokens=100), a_call(wall_ms=3000, write_ms=2200, output_tokens=300),
             a_call(outcome="too_long", wall_ms=9000, write_ms=9000, output_tokens=1000),   # not ok: left out
             a_call(wall_ms=500, write_ms=None, output_tokens=50)]                             # no writing time: all in only
    found = figures.per_token(calls)
    assert found == {"calls": 3, "tokens_written": 450, "ms_per_token_all_in": 10.0, "ms_per_token_writing": 7.5,
                     "tokens_written_median": 100}
    assert figures.per_token([]) == {"calls": 0, "tokens_written": 0, "ms_per_token_all_in": None,
                                     "ms_per_token_writing": None, "tokens_written_median": None}
    found = figures.figures(ROUNDS, four_arms())
    r = found["arms"]["base"]["rounds"]["1"]
    # 51 passes in a chain (11 of 495, 7 of each travel case, 2 of each of the 13 scripts), two calls each; the round adds B1 to B3.
    assert r["per_token"]["calls"] == 102 and r["per_token_round"]["calls"] == 4 * 102 and r["alarm_median_ms"] == 2000


def test_15_8_the_counts_from_the_replies_on_made_up_replies():
    arm = an_arm(only_a=True)
    results, calls = arm["results"], arm["calls"]
    # One chain at 0 of 495: every allowed sentence end is whole; a letter is cut; a reply not ok, and one that is
    # not its form, are counted apart and never as cut.
    points = [p["point"] for p in results[("495", "A1")]["passes"]]
    ends = [".", "?", "!", ")", "]", '"', "'", "%"]
    for point, end in zip(points, ends):
        calls[("495", "A1", point, "alarm")] = a_call(reply={**REASONING_OK, "reasoning": f"Whole{end}  "})
    calls[("495", "A1", points[8], "alarm")] = a_call(reply={**REASONING_OK, "reasoning": "Cut mid"})
    calls[("495", "A1", points[9], "alarm")] = a_call(outcome="too_long", reply="{not json")
    calls[("495", "A1", points[10], "alarm")] = a_call(reply="[1, 2]")
    # Time critical with no action: the pass's flag, whole in A2 and cut in A3.
    for chain, reasoning in (("A2", "Said whole."), ("A3", "Said and cut")):
        p = results[("495", chain)]["passes"][0]
        p["alarm"]["flag_without_action"] = True
        calls[("495", chain, p["point"], "alarm")] = a_call(reply={**REASONING_OK, "reasoning": reasoning,
                                                                    "time_critical_possible": True})
    # The first alarm: travel case 1 fires at turn 4 in two chains and at turn 8 in the third; script 03 never.
    results[("T1", "A3")]["passes"][0]["alarm"]["actions"] = []
    results[("T1", "A3")]["passes"][0]["alarm"]["raw_actions"] = []      # the reply itself named none
    found = figures.from_replies(arm)
    assert found["cut_mid_sentence"] == {"alarm at 0.0": 2}            # "Cut mid" and "Said and cut"
    assert found["counted_apart"] == {"alarm ok at 0.0": 1, "alarm too_long at 0.0": 1}
    assert found["time_critical_no_action"] == {"at 0.0, cut": 1, "at 0.0, whole": 1}
    assert found["first_alarm"]["T1"] == {"at 0.0: pass 4": 2, "at 0.0: pass 8": 1}
    assert found["first_alarm"]["03"] == {"at 0.0: never": 3}
    assert "T1" not in found["same_answer_at_0"] and {"03", "495"} <= set(found["same_answer_at_0"])
    # The made-up scripts open with a pass that lists nothing: 18 empty lists a chain, none of them kept.
    assert found["failed_chains"] == {} and found["empty_lists"] == {"at 0.0": 54} and found["kept_lists"] == {"at 0.0": 0}
    # Empty and kept lists, by temperature, and a chain at 0.5 beside the three at 0.
    full = an_arm()
    kept = full["results"][("495", "B2")]["passes"][1]["assessment"]
    kept["kept"] = True
    full["results"][("495", "A1")]["passes"][0]["assessment"]["differentials"] = []
    full["results"][("495", "A1")]["passes"][0]["names"] = []        # so that chain's answers differ from A2's and A3's
    found = figures.from_replies(full)
    assert found["empty_lists"] == {"at 0.0": 55, "at 0.5": 181} and found["kept_lists"] == {"at 0.0": 0, "at 0.5": 1}
    assert found["same_answer_at_0"] == sorted({c for c, _ in full["results"]} - {"495"})


def test_ruling_26_the_same_figures_from_the_public_form_as_from_the_private_one(tmp_path, bench_folders, clock, capsys):
    """A made-up arm run through the real door and exported; the figures
    from the public folder equal the figures from the private folder."""
    from openconsult.bench.cases import load_cases
    from openconsult.bench.replay import CHAINS, run
    from openconsult.db import open_database
    from openconsult.llm.door import Door
    from openconsult.llm.record import ModelCalls
    from tests.fakes import FakeEngine
    cases, out = bench_folders
    db = open_database(out / "calls.db")
    door = Door(FakeEngine(), ModelCalls(db, clock))
    run(door, load_cases(cases), ResultWriter(out), CHAINS, log=lambda line: None)
    public = tmp_path / "public"
    rounds = {"baseline": "made-up", "arms": {"made-up": {"engine": "Made-up", "way": "one after another"}},
              "rounds": {"1": {"chain": "A1", "stress": ["B1", "B2", "B3"]}, "2": {"chain": "A2", "stress": ["B4", "B5", "B6"]},
                         "3": {"chain": "A3", "stress": ["B7", "B8", "B9", "B10"]}}}
    assert main(["export", "--public", str(public), "--arm", "made-up", "--out", str(out)]) == 0
    (public / "rounds.json").write_text(json.dumps(rounds), encoding="utf-8")
    (tmp_path / "rounds.json").write_text(json.dumps(rounds), encoding="utf-8")
    db.close()
    from_private = figures.figures(rounds, {"made-up": figures.private_arm(out)})
    from_public = figures.figures(rounds, figures.public_arms(public, rounds))
    assert from_public == from_private
    assert from_public["arms"]["made-up"]["rounds"]["1"]["passes"] == 2 and from_public["arms"]["made-up"]["candidate"] is False
    # The one command, both ways: it prints the same, and writes only with --out, never over a file that exists.
    capsys.readouterr()
    assert main(["figures", "--public", str(public)]) == 0
    printed = capsys.readouterr().out
    assert printed == figures.as_markdown(from_public) and "## Who is a candidate" in printed
    assert main(["figures", "--rounds", str(tmp_path / "rounds.json"), "--arm", f"made-up={out}", "--out", str(tmp_path / "written")]) == 0
    capsys.readouterr()
    assert json.loads((tmp_path / "written" / "figures.json").read_text(encoding="utf-8")) == json.loads(json.dumps(from_private))
    assert (tmp_path / "written" / "figures.md").read_text(encoding="utf-8") == printed
    assert main(["figures", "--public", str(public), "--out", str(tmp_path / "written")]) == 7
    assert "is never written over" in capsys.readouterr().out
    assert sorted(p.name for p in public.glob("figures.*")) == []
