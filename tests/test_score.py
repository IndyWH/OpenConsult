"""The scoring rules and the marks on made-up rows (V1_LESSONS 9.2, 9.3;
spec 15.7 ruling 3; Task 5b's rule for a failed chain)."""

from openconsult.bench import score
from openconsult.bench.replay import CHAINS


def a_pass(point, diffs=(), questions=(), raw_actions=(), actions=None, judged=True, flag=False, wall_ms=4000):
    raw = [{"action": a, "reason": "made up"} for a in raw_actions]
    return {"point": point, "wall_ms": wall_ms, "names": [c for c, _ in diffs],
            "alarm": {"judged": judged, "actions": raw if actions is None else actions,
                      "raw_actions": raw, "flag_without_action": flag, "failure": None if judged else "too_slow"},
            "assessment": {"ok": True, "differentials": [{"condition": c, "likelihood": g} for c, g in diffs],
                           "questions": list(questions)}}


def a_result(case, group, passes, chain="A1", failed=None):
    return {"case": case, "group": group, "chain": chain, "failed": failed, "passes": passes}


def test_9_2_the_495_rules_score_made_up_passes_as_written():
    passes = [a_pass(p, diffs=[("Made-up thing", "low")]) for p in range(1, 12)]
    passes[1] = a_pass(2, diffs=[("Other", "low"), ("An ECTOPIC Pregnancy", "high")],
                       questions=["When was your last normal period?"])
    passes[3] = a_pass(4, diffs=[("Ectopic pregnancy", "high")], questions=["Are you sexually active?"],
                       raw_actions=["Urgent HCG test"], actions=[])
    passes[10] = a_pass(11, diffs=[("Ectopic pregnancy", "high")], raw_actions=["Admit"], flag=False)
    s = score.score_495(a_result("495", "495", passes))
    assert (s["considered"], s["led"], s["asked"], s["asked_np"], s["tested"]) == (2, 4, 4, 2, 4)
    assert s["leads_at_11"] and s["named"] and s["alarm"] == "..........X"
    # A pass with nothing matching meets no rule, and the leader at 11 decides named.
    quiet = score.score_495(a_result("495", "495", [a_pass(p) for p in range(1, 12)]))
    assert quiet["considered"] is None and not quiet["leads_at_11"] and quiet["tested"] is None
    ruptured = passes[:10] + [a_pass(11, diffs=[("Ruptured ectopic pregnancy", "high")])]
    r = score.score_495(a_result("495", "495", ruptured))
    assert r["leads_at_11"] and not r["named"]


def test_9_2_the_travel_rules_score_made_up_updates_as_written():
    points = [4, 8, 12, 16, 20, 24, 28]
    passes = [a_pass(t) for t in points]
    passes[2] = a_pass(12, questions=["Have you been abroad recently?"])
    passes[3] = a_pass(16, diffs=[("Malaria", "high")], raw_actions=["Blood film"])
    passes[4] = a_pass(20, diffs=[("Dengue fever", "moderate")], raw_actions=["Admit"])
    t2 = score.score_travel(a_result("T2", "travel", passes))
    assert t2["asks"] and t2["first_target"] == 16 and t2["fired_at"] == [16, 20] and t2["clears"]
    assert t2["male_hits"] == []
    t1 = score.score_travel(a_result("T1", "travel", passes))
    assert t1["first_target"] == 20
    late = [a_pass(t, questions=["Any travel?"] if t == 16 else ()) for t in points]
    late[-1] = a_pass(28, raw_actions=["Admit"])
    s = score.score_travel(a_result("T1", "travel", late))
    assert not s["asks"] and s["first_target"] is None and not s["clears"]
    hit = score.score_travel(a_result("T2", "travel", [a_pass(4, raw_actions=["Urgent hCG"])]))
    assert hit["male_hits"] == ["point 4 urgent action: Urgent hCG made up"]


def test_9_2_the_script_rules_score_made_up_updates_as_written():
    passes = [a_pass(4), a_pass(8, raw_actions=["Bedside ECG"]), a_pass(12, raw_actions=["ECG"]),
              a_pass(16, raw_actions=["Admit"], actions=[]), a_pass(20)]
    s = score.score_script(a_result("01", "script", passes))
    assert s["fired"] and (s["first_fire"], s["last_fire"], s["updates_with_alarm"]) == (8, 12, 2)
    assert s["cleared"] and not s["dropout_return"] and s["alarm"] == ".XX.." and s["first_actions"] == ["Bedside ECG"]
    gap = score.score_script(a_result("10", "script", [a_pass(4, raw_actions=["x"]), a_pass(8), a_pass(12, raw_actions=["y"])]))
    assert gap["dropout_return"] and not gap["cleared"]
    # The restraint verdicts, each mode, and the male terms.
    broad = [("A", "low"), ("B", "low"), ("C", "moderate"), ("D", "low"), ("E", "low")]
    assert score.score_script(a_result("11", "script", [a_pass(4, diffs=broad)]))["restraint"].startswith("PASS")
    assert "over-committed" in score.score_script(a_result("11", "script", [a_pass(4, diffs=broad[:4] + [("E", "high")])]))["restraint"]
    assert "too narrow" in score.score_script(a_result("12", "script", [a_pass(4, diffs=broad[:3])]))["restraint"]
    assert score.score_script(a_result("13", "script", [a_pass(4, diffs=[("Migraine with aura", "high")])]))["restraint"].startswith("PASS")
    assert "spurious" in score.score_script(a_result("13", "script", [a_pass(4, diffs=[("Migraine", "moderate")])]))["restraint"]
    assert "wrong leader" in score.score_script(a_result("13", "script", [a_pass(4, diffs=[("Tension headache", "high")])]))["restraint"]
    assert score.score_script(a_result("14", "script", [a_pass(4, diffs=[("GCA", "high")])]))["restraint"].startswith("PASS")
    assert "not leading" in score.score_script(a_result("15", "script", [a_pass(4, diffs=[("Sciatica", "high")])]))["restraint"]
    male = score.score_script(a_result("10", "script", [a_pass(4, diffs=[("Ovarian torsion", "low")], raw_actions=["Rule out ectopic"], actions=[])]))
    assert male["male_hits"] == ["point 4 differential: Ovarian torsion", "point 4 urgent action: Rule out ectopic made up"]
    assert score.score_script(a_result("08", "script", [a_pass(4, diffs=[("Ovarian torsion", "low")])]))["male_hits"] == []


def full_results(emergency_fire=True):
    """Thirteen chains of every case, all meeting every mark."""
    results = {}
    for chain in CHAINS:
        p495 = [a_pass(p, diffs=[("Ectopic pregnancy", "high")], questions=["Last period?"],
                       raw_actions=["Pregnancy test"], actions=[]) for p in range(1, 12)]
        results[("495", chain.name)] = a_result("495", "495", p495, chain.name)
        for case, target in (("T1", "Dengue"), ("T2", "Malaria")):
            tp = [a_pass(t, diffs=[(target, "high")], questions=["Any travel?"],
                         raw_actions=["Admit"] if t < 28 else ()) for t in (4, 8, 12, 16, 20, 24, 28)]
            results[(case, chain.name)] = a_result(case, "travel", tp, chain.name)
        for case in score.EMERGENCY:
            sp = [a_pass(4, raw_actions=["Admit"] if emergency_fire else ()), a_pass(8)]
            if case in score.RESTRAINT:
                sp[-1] = a_pass(8, diffs=[("Giant cell arteritis", "high") if case == "14" else ("Cauda equina", "high")])
            results[(case, chain.name)] = a_result(case, "script", sp, chain.name)
        for case in score.ROUTINE + (score.DIZZINESS,):
            diffs = [("Migraine", "high")] if case == "13" else [(f"Made-up {i}", "low") for i in range(5)]
            results[(case, chain.name)] = a_result(case, "script", [a_pass(4), a_pass(8, diffs=diffs)], chain.name)
    return results


def test_9_2_the_marks_are_met_on_a_full_made_up_run_and_missed_when_a_chain_fails():
    scored = score.summary(full_results())
    assert scored["hard_met"] and scored["time_met"] and scored["soft_met"] == 9 and scored["chains"] == 16 * 13
    assert "H1 | hard" in score.as_markdown(scored)
    missed = score.summary(full_results(emergency_fire=False))
    assert not missed["hard_met"] and [m["n"] for m in missed["marks"] if not m["met"]] == ["H6", "S16"]


def test_9_2_a_failed_chain_is_scored_as_failed_on_every_mark_it_enters():
    results = full_results()
    results[("10", "B3")]["failed"] = "a call failed at point 8: too_long"
    results[("13", "B3")]["failed"] = "a call failed at point 4: unreachable"
    by_n = {m["n"]: m for m in score.marks(results)}
    assert by_n["H6"]["value"]["10"] == 12 and not by_n["H6"]["met"]          # not fired
    assert by_n["H7"]["value"]["10"] == 1 and not by_n["H7"]["met"]           # a match
    assert by_n["S12"]["value"]["13"] == 1 and by_n["S12"]["met"]             # fired, within 13's mark of 1
    assert by_n["S15"]["value"]["13"] == 12 and by_n["S15"]["met"]            # not passing, within 12
    assert by_n["S16"]["value"]["10"] == 12 and by_n["S16"]["met"]            # not cleared, within 12
    results[("12", "A1")]["failed"] = "x"
    assert score.marks(results)[13]["value"] == 0                              # out of the median
    # A missing chain counts as failed too: fewer than 13 on H6.
    del results[("06", "B10")]
    assert not {m["n"]: m for m in score.marks(results)}["H6"]["met"]
