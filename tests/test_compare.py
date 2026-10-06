"""The arms side by side, and the two rules of ruling 10 (spec 15.8):
who is a candidate, and what counts as faster. All rows are made up."""

import copy
import json

import pytest

from openconsult.bench import compare, score
from openconsult.bench.cli import main
from openconsult.bench.writer import ResultWriter
from tests.test_score import a_pass, a_result, full_results


def an_arm(pass_ms=4000, a_chains_ms=None, emergency_fire=True, only_a=False, together=False):
    """A full made-up run that meets every mark, with its passes at the given times."""
    results = copy.deepcopy(full_results(emergency_fire=emergency_fire))
    for (case, chain), r in list(results.items()):
        if only_a and chain not in compare.A_CHAINS:
            del results[(case, chain)]
            continue
        r["together"] = together
        for p in r["passes"]:
            p["wall_ms"] = a_chains_ms if a_chains_ms is not None and chain in compare.A_CHAINS else pass_ms
    return results


def test_ruling_10_an_arm_that_misses_a_hard_mark_is_not_a_candidate():
    found = compare.table({"base": an_arm(), "quick": an_arm(pass_ms=1000, emergency_fire=False),
                           "sound": an_arm(pass_ms=1000)}, baseline="base")
    quick, sound = found["arms"]["quick"], found["arms"]["sound"]
    # However fast it is: three seconds shorter, and still not a candidate and not called faster.
    assert quick["candidate"] is False and quick["missed"] == ["H6"]
    assert quick["against"] == {"shorter_by_ms": 3000, "faster": False}
    assert "quick: Candidate: NO, missed H6" in compare.as_markdown(found)
    assert "Not a candidate, so not called faster" in compare.as_markdown(found)
    # The twin: the same speed with every hard mark met.
    assert sound["candidate"] is True and sound["against"] == {"shorter_by_ms": 3000, "faster": True}
    assert score.summary(an_arm())["candidate"] is True
    assert score.summary(an_arm(emergency_fire=False))["candidate"] is False


@pytest.mark.parametrize("pass_ms, faster", [(3001, False), (3000, True), (4500, False)])
def test_ruling_10_faster_means_a_typical_pass_one_second_shorter(pass_ms, faster):
    found = compare.table({"base": an_arm(pass_ms=4000), "other": an_arm(pass_ms=pass_ms)}, baseline="base")
    other = found["arms"]["other"]
    assert other["typical"]["median_ms"] == pass_ms and other["typical"]["passes"] == 13 * 11
    assert other["against"] == {"shorter_by_ms": 4000 - pass_ms, "faster": faster}
    said = compare.as_markdown(found)
    assert ("Faster in a way that matters to the patient: yes" in said) is faster
    assert ("Not called faster (under 1 second)" in said) is not faster
    assert "base: Candidate: yes" in said and "against" not in found["arms"]["base"]


def test_ruling_10_an_arm_sent_together_is_held_against_the_same_three_chains():
    # The baseline's three chains at temperature 0 take 4.0 s a pass; its ten others take 3.0 s.
    base = an_arm(pass_ms=3000, a_chains_ms=4000)
    sent = an_arm(pass_ms=2900, only_a=True, together=True)
    found = compare.table({"base": base, "sent": sent}, baseline="base", pairs={"sent": "base"})
    row = found["arms"]["sent"]
    assert row["together"] and row["chains"] == 16 * 3 and row["typical"]["passes"] == 3 * 11
    assert row["against"] == {"shorter_by_ms": 1100, "faster": True}             # the same three chains
    assert row["against_all_chains"] == {"shorter_by_ms": 100, "faster": False}  # beside it, not the rule
    assert "candidate" not in row


def test_ruling_5_the_score_counts_empty_replies_and_kept_lists():
    listed = [("Made-up thing", "low")]
    kept = a_pass(2, diffs=listed)
    kept["assessment"]["kept"] = True                  # the reply's own list was empty; the earlier one stands
    first_empty = a_pass(1)
    first_empty["assessment"]["kept"] = False          # empty at the first pass: nothing to keep
    failed = a_pass(3)
    failed["assessment"]["ok"] = False                 # a failed call is not an empty reply
    before_ruling_5 = a_pass(2)                        # written by stage 3: no such mark, an empty list
    results = {("495", "A1"): a_result("495", "495", [first_empty, kept, failed]),
               ("495", "A2"): a_result("495", "495", [a_pass(1, diffs=listed), before_ruling_5], chain="A2")}
    found = score.empty_and_kept(results)
    assert (found["empty_replies"], found["kept_lists"]) == (3, 1)
    assert found["kept_at"] == ["495/A1 point 2"]
    assert found["empty_at"] == ["495/A1 point 1", "495/A1 point 2", "495/A2 point 2"]
    assert score.summary(results)["kept_lists"] == 1
    # A kept list is the list the rules read.
    assert score.score_495(results[("495", "A1")])["first_diff"][2] == "Made-up thing"


def test_15_8_one_table_sets_the_arms_side_by_side(tmp_path, capsys):
    full, sent = an_arm(), an_arm(pass_ms=2500, only_a=True, together=True)
    for p in sent[("495", "A1")]["passes"]:
        p["assessment"]["differentials"] = []          # one chain sent together never lists it
    folders = {}
    for name, results in (("one", an_arm(pass_ms=4200)), ("two", full), ("two-together", sent)):
        writer = ResultWriter(tmp_path / name)
        for (case, chain), r in results.items():
            writer.write(case, chain, r)
        folders[name] = tmp_path / name
    args = ["compare", "--out", str(tmp_path / "table"), "--baseline", "one", "--pair", "two-together=two"]
    assert main(args + [x for name, folder in folders.items() for x in ("--arm", f"{name}={folder}")]) == 0
    found = json.loads((tmp_path / "table" / "compare.json").read_text(encoding="utf-8"))
    assert list(found["arms"]) == ["one", "two", "two-together"] and found["baseline"] == "one"
    for row in found["arms"].values():
        assert len(row["marks"]) == 18 and {"typical", "empty_replies", "kept_lists", "failed_chains"} <= set(row)
    assert found["arms"]["two"]["marks"]["H1"] == 13 and found["arms"]["two"]["against"]["shorter_by_ms"] == 200
    together = found["arms"]["two-together"]
    # Beside the same three chains of its own engine's full arm, and what changed is named.
    assert together["full_arm"] == "two" and together["marks_one_after_another"]["H1"] == 3
    assert together["marks"]["H1"] == 2 and "H1" in together["marks_changed"] and "H2" not in together["marks_changed"]
    assert together["empty_replies"] == score.empty_and_kept(sent)["empty_replies"]
    said = (tmp_path / "table" / "compare.md").read_text(encoding="utf-8")
    assert "| | one | two | two-together |" in said and "| H1 | 13 | 13 | 2 |" in said
    assert "Marks that differ from the same three chains of two: H1" in said
    capsys.readouterr()
