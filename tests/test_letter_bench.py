"""The letters bench and its scoring (spec 15.12, ruling 10 and the
detail The bench; R18; V1_LESSONS 9.4; 5.2: the scoring is a plain
function over stored results, and what a model says is never asserted).
Made-up notes, a made-up server, made results."""

import json

import pytest

from openconsult.bench import letter_marks as marks
from openconsult.bench import letters as bench
from openconsult.bench.cases import load_cases
from openconsult.bench.cli import main
from openconsult.bench.replay import Chain
from openconsult.bench.writer import ResultWriter
from openconsult.consult import letter_check, referral_note
from openconsult.db import open_database
from openconsult.llm.door import Door
from openconsult.llm.record import ModelCalls
from openconsult.llm.vllm import VllmEngine
from openconsult.settings import paths
from tests.fakes import CALL, REVISION, FakeEngine, chat_reply, describe
from tests.test_referral_note import TEXT

NOTE_C = ("Subjective\nSix weeks of food sticking.\nPatient's ideas: a made idea. Patient's expectations: hoped for a scan.\n\n"
          "Objective\nWeight 71 kg.\n\nAssessment\nA made impression.\n\nPlan\nUrgent referral to a made-up specialty.\n")
LIST_ANSWER = {"reasoning": "made", "referrals": [
    {"specialty": "A made-up specialty", "title": "Physician", "reason": "made", "urgency": "urgent", "lines": [9], "suggestion": False},
    {"specialty": "Another specialty", "title": "Surgeon", "reason": "made", "urgency": "routine", "lines": [2], "suggestion": True}]}
LETTER_ANSWER = {"reasoning": "made", "paragraphs": [
    {"text": "Thank you for seeing this 58-year-old man with six weeks of food sticking. He hoped for a scan.", "note_lines": [2, 3]},
    {"text": "He weighs 71 kg. He has lost 9 kg.", "note_lines": [5]}]}


def made_cases(tmp_path, with_a=True):
    folder = tmp_path / "cases"
    folder.mkdir()
    (folder / "C.txt").write_text(NOTE_C, encoding="utf-8")
    (folder / "A.txt").write_text(TEXT, encoding="utf-8")
    listed = [{"name": "C_made", "group": "stage8a", "kind": "approved_note", "file": "C.txt", "age": 58, "sex": "M",
               "expected": {"stated_referrals": ["made-up specialty"], "has_expectations_line": True}}]
    if with_a:
        listed.append({"name": "A_made", "group": "stage8a", "kind": "approved_note", "file": "A.txt", "age": 64, "sex": "F",
                       "expected": {"stated_referrals": [], "has_expectations_line": True}})
    (folder / "cases.json").write_text(json.dumps(listed), encoding="utf-8")
    return folder


def test_ruling_10_the_letters_bench_goes_through_the_door_with_the_apps_own_numbering_frames_and_check(tmp_path, clock):
    cases = load_cases(made_cases(tmp_path))
    db = open_database(tmp_path / "calls.db")
    engine = FakeEngine({"referrals": [LIST_ANSWER] * 3, "letter": [LETTER_ANSWER] * 3})
    door = Door(engine, ModelCalls(db, clock))
    writer = ResultWriter(tmp_path / "out")
    with pytest.raises(ValueError):
        bench.run(door, cases, writer, {}, [Chain("A1", 0.0, 42)])             # A_made states no referral and none is named: no call
    assert engine.calls == []
    summary = bench.run(door, cases, writer, {"A_made": "Named specialty"}, [Chain("A1", 0.0, 42)], log=lambda line: None)
    assert summary == {"run": 2, "kept": 0}
    c = writer.read("C_made", "A1")
    # The messages are the app's own, byte for byte; the check's figures are the app's for the same paragraphs.
    assert engine.calls_for("referrals")[0].user == referral_note.list_message(NOTE_C, cases[0].patient)
    assert engine.calls_for("letter")[0].user == referral_note.letter_message(NOTE_C, "made-up specialty", cases[0].patient)
    assert engine.calls_for("letter")[1].user == referral_note.letter_message(TEXT, "Named specialty", cases[1].patient)
    assert [(i["kind"], i["specialty"], i["lines"]) for i in c["list"]["items"]] == [("stated", "A made-up specialty", [9]), ("suggested", "Another specialty", [2])]
    lines = referral_note.numbered_lines(NOTE_C)
    checked = letter_check.check(LETTER_ANSWER["paragraphs"], lines, {"58"})
    letter = c["letters"][0]
    assert (letter["specialty"], letter["body"], letter["total"], letter["grounded"], letter["placeholders"], letter["dropped"], letter["refused"]) == \
        ("made-up specialty", checked.paragraphs, 4, 3, 1, 0, False)
    assert letter["check_detail"] == checked.detail and letter["model_body"] == LETTER_ANSWER["paragraphs"] and letter["failure"] is None
    assert c["lines"][8] == {"n": 9, "section": "plan", "heading": False, "text": "Urgent referral to a made-up specialty."}
    assert c["expected"]["stated_referrals"] == ["made-up specialty"] and c["case_sha256"] == cases[0].sha256
    assert (c["kind"], c["engine"], c["model_tag"], c["temperature"], c["seed"]) == ("letters", "ollama", "gemma4:26b-a4b-it-qat", 0.0, 42)
    assert set(c["prompts"]) == {"letter", "referrals", "letter.frame", "referrals.frame", "letter.withheld"}
    assert bench.arm_differs(c, door) is None
    assert "letters" in bench.arm_differs({**c, "kind": "replay"}, door)
    assert "prompts" in bench.arm_differs({**c, "prompts": {}}, door)
    # A stopped run carries on from the chains without a result; a failed call is kept in the result and the chain goes on.
    engine.script["letter"].append(__import__("openconsult.llm.engine", fromlist=["EngineTimeout"]).EngineTimeout("no answer"))
    summary = bench.run(door, cases, writer, {"A_made": "Named specialty"}, [Chain("A1", 0.0, 42), Chain("B1", 0.5, 1)], log=lambda line: None)
    assert summary == {"run": 2, "kept": 2}
    assert writer.read("C_made", "B1")["letters"][0]["failure"] is None
    failed = writer.read("A_made", "B1")["letters"][0]
    assert failed["failure"].startswith("too_slow") and failed["body"] is None and failed["refused"] is None
    db.close()


def test_R18_9_4_the_letters_command_writes_only_under_its_folder_and_names_its_engine(server, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(paths, "default_data_folder", lambda: tmp_path / "app-data")
    cases = made_cases(tmp_path)
    describe(server, VllmEngine)

    def answer(body):
        job = body["response_format"]["json_schema"]["name"]
        return chat_reply(json.dumps(LIST_ANSWER if job == "referrals" else LETTER_ANSWER))

    server.routes["/v1/chat/completions"] = answer
    base = ["letters", "--cases", str(cases), "--kind", "vllm", "--engine", server.address, "--model", CALL.tag, "--digest", REVISION,
            "--chains", "A1", "--data-folder", str(tmp_path / "data")]
    # A folder under the app's data folder, the given data folder or the repo is refused before any call (R18).
    assert main([*base, "--out", str(tmp_path / "data" / "out")]) == 6
    assert main([*base, "--out", str(tmp_path / "app-data" / "out")]) == 6
    assert server.chats() == []
    # A case that states no referral with no --letter stops before any call.
    assert main([*base, "--out", str(tmp_path / "out")]) == 9 and server.chats() == []
    assert main([*base, "--out", str(tmp_path / "out"), "--letter", "A_made=Named specialty"]) == 0
    result = ResultWriter(tmp_path / "out").read("C_made", "A1")
    assert (result["engine"], result["engine_version"], result["model_tag"], result["model_digest"]) == ("vllm", "0.0-made-up", CALL.tag, REVISION)
    assert len(server.chats()) == 1 + 2 + 2            # the unmeasured first call, then a list and a letter for each case
    # A run again keeps every result and makes no call; the scoring then reads the folder alone.
    before = len(server.chats())
    assert main([*base, "--out", str(tmp_path / "out"), "--letter", "A_made=Named specialty"]) == 0 and len(server.chats()) == before
    assert main(["letters-score", "--out", str(tmp_path / "out"), "--write", str(tmp_path / "marks")]) == 1    # one chain, not 13: no mark holds
    assert (tmp_path / "marks" / "marks.md").exists()
    assert main(["letters-score", "--out", str(tmp_path / "out"), "--write", str(tmp_path / "marks")]) == 6    # never over
    capsys.readouterr()


# ------------------------------------------------------------- the scoring

def made_letter(specialty="made-up specialty", refused=False, placeholders=0, reasons=(), assessment=(), model_text="Made up.", failure=None):
    detail = {"paragraphs": [{"valid": [2], "assessment_cited": list(assessment),
                              "sentences": [{"text": model_text, "verdict": "placeholder" if r else "kept", "reason": r} for r in (reasons or [None])]}]}
    return {"specialty": specialty, "call_id": 1, "wall_ms": 4000, "failure": failure, "reasoning": "x", "output_tokens": 300,
            "model_body": [{"text": model_text, "note_lines": [2]}], "body": [model_text], "check_detail": detail,
            "total": 2, "grounded": 2 - placeholders, "placeholders": placeholders, "dropped": 0, "refused": refused}


def made_chain(case, name, letters, stated=("made-up specialty",), expected=("made-up specialty",), list_failure=None):
    items = [{"kind": "stated", "specialty": s, "title": "Physician", "reason": "x", "urgency": "urgent", "lines": [8], "position": i}
             for i, s in enumerate(stated)]
    items.append({"kind": "suggested", "specialty": "Other", "title": "x", "reason": "x", "urgency": "routine", "lines": [2], "position": len(items)})
    lines = [{"n": 1, "section": "subjective", "heading": True, "text": "Subjective"}, {"n": 2, "section": "subjective", "heading": False, "text": "made"},
             {"n": 7, "section": "plan", "heading": True, "text": "Plan"},
             {"n": 8, "section": "plan", "heading": False, "text": "Urgent referral to a made-up specialty and to ENT."}]
    return {"case": case, "chain": name, "expected": {"stated_referrals": list(expected)}, "lines": lines,
            "list": {"call_id": 1, "wall_ms": 2000, "failure": list_failure, "items": items, "output_tokens": 100}, "letters": letters}


def made_results(case, n=13, expected=("made-up specialty",), stated=("made-up specialty",), bad=None):
    """n chains of one case; the first `bad[k]` chains carry the fault k."""
    bad = bad or {}
    found = {}
    for i in range(n):
        letters = [made_letter(refused=i < bad.get("refused", 0), placeholders=1 if i < bad.get("placeholder", 0) else 0,
                               reasons=["number"] if i < bad.get("number", 0) else (["upgrade"] if i < bad.get("upgrade", 0) else []),
                               assessment=[9] if i < bad.get("assessment", 0) else [],
                               model_text="The patient hopes for a scan." if i < bad.get("expectation", 0) else "Made up.",
                               failure="too_slow: x" if i < bad.get("failed", 0) else None)]
        if "second" in bad:
            letters.append(made_letter(specialty="ENT", refused=i < bad["second"]))
        found[(case, f"C{i}")] = made_chain(case, f"C{i}", letters, stated=() if i < bad.get("no_stated", 0) else stated, expected=expected)
    return found


def test_ruling_10_the_letters_scoring_counts_the_marks_on_made_results(tmp_path):
    held = marks.score({**made_results("C_made"), **made_results("A_hypo", expected=(), stated=()),
                        **made_results("D_made", expected=("made-up specialty", "ENT"), stated=("made-up specialty", "ENT"), bad={"second": 0})})
    assert held["held"] and [(m["mark"], m["case"]) for m in held["marks"]] == [
        ("M1", "A_hypo"), ("M2", "A_hypo"), ("M3", "A_hypo"), ("M4", "A_hypo"), ("M5", "A_hypo"),
        ("M1", "C_made"), ("M2", "C_made"), ("M3", "C_made"), ("M5", "C_made"),
        ("M1", "D_made"), ("M2", "D_made"), ("M3", "D_made"), ("M5", "D_made")]
    t = held["cases"]["C_made"]
    assert (t["chains"], t["letters"], t["refused"], t["placeholder"], t["assessment_cited"], t["number_outside"], t["stated_ok"]) == (13, 13, 0, 0, 0, 0, 13)
    assert (t["list_s"], t["letter_s"], t["longest_s"], t["longest_reply_tokens"], t["suggested"]) == (2.0, 4.0, 4.0, 300, 1)
    assert held["cases"]["D_made"]["letters"] == 26
    # Each mark missed on made tables that miss it; M2 holds at 1 placeholder chain and misses at 2.
    missed = marks.score({**made_results("C_made", bad={"refused": 1, "placeholder": 2, "assessment": 1}),
                          **made_results("A_hypo", expected=(), stated=("Stated anyway",), bad={"expectation": 1, "number": 1}),
                          **made_results("D_made", expected=("made-up specialty", "ENT"), stated=("made-up specialty",), bad={"second": 1})})
    by = {(m["mark"], m["case"]): m["held"] for m in missed["marks"]}
    assert not missed["held"]
    assert (by["M1", "C_made"], by["M2", "C_made"], by["M3", "C_made"], by["M5", "C_made"]) == (False, False, False, True)
    assert (by["M3", "A_hypo"], by["M4", "A_hypo"], by["M5", "A_hypo"]) == (False, False, False)      # A: a stated item breaks M5
    assert (by["M1", "D_made"], by["M5", "D_made"]) == (False, False)                                 # D: one bad letter of two fails the chain; ENT not stated
    assert marks.score(made_results("C_made", bad={"placeholder": 1}))["marks"][1]["held"]
    assert not marks.score(made_results("C_made", n=12))["held"]                                      # a 12-chain case meets no mark
    assert marks.score(made_results("C_made", bad={"failed": 1}))["cases"]["C_made"]["failed_call"] == ["C0"]
    assert marks.score(made_results("C_made", bad={"no_stated": 1}))["cases"]["C_made"]["stated_ok"] == 12
    assert marks.score(made_results("C_made", bad={"upgrade": 2}))["cases"]["C_made"]["upgrade"] == 2
    assert marks.score(made_results("A_hypo", expected=(), stated=(), bad={"expectation": 3}))["cases"]["A_hypo"]["expectation_model"] == 3
    # The stated item is found only with its plan line holding the word.
    chain = made_chain("C_made", "x", [made_letter()])
    assert marks.stated_found(chain, "made-up specialty") and marks.stated_found(chain, "ENT") is False
    chain["list"]["items"][0]["lines"] = [2]
    assert not marks.stated_found(chain, "made-up specialty")
    with pytest.raises(marks.MarksRefused):
        marks.score({})
    text = marks.as_markdown(held)
    assert "| C_made | 13 | none | 13 | 0 | 0 | 0 | 0 | 0 |" in text and "Mark M4, A_hypo" in text and "Every mark held" in text
    assert "MISSED" in marks.as_markdown(missed)
    marks.write(tmp_path / "marks", held)
    assert json.loads((tmp_path / "marks" / "marks.json").read_text(encoding="utf-8"))["held"] is True
    with pytest.raises(marks.MarksRefused):
        marks.write(tmp_path / "marks", held)
