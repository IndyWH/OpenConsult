"""The parts reading of the bench and the marks of step 6c (spec 15.10,
rulings 22 and 24, the details of step 6c: The bench of parts against
whole, The bench of Claude Haiku, and of 6c2: The count again; R18;
V1_LESSONS 9.4). A made-up voice worker and a made-up language model;
every reply is made up."""

import json
import math
import re
import shutil

import pytest

from openconsult import words
from openconsult.bench import cli
from openconsult.bench.speech import commands, commands2, model_lines, pages, stop_marks
from openconsult.bench.writer import ResultWriter
from openconsult.consult import joined
from openconsult.db import open_database
from openconsult.llm.door import Door
from openconsult.llm.engine import EngineTimeout
from openconsult.llm.profile import GEMMA_4_QAT
from openconsult.llm.record import ModelCalls
from tests.fakes import FakeEngine
from tests.made_up_part_two import ScriptedEngine, build
from tests.test_voice import MadeUpVoiceWorker

PAGES = ["nemotron--one", "nemotron_tied_pair--one", "whisperx_pyannote--one"]


class LabelsEngine(FakeEngine):
    """Names every line of every call, but times out on the calls whose
    order of arrival is in `fails`."""

    def __init__(self, fails=()):
        super().__init__(script=[])
        self.fails = set(fails)

    def chat(self, call):
        self.calls.append(call)
        if len(self.calls) in self.fails:
            raise EngineTimeout("made-up: no answer")
        if call.job == "bench_drug_name":
            return self.chat_item(call, {"doubtful": [{"line": 1, "heard": "metformin", "meant": "metformin"}]})
        count = len(re.findall(r"^\[\d+\] ", call.user, flags=re.M))
        return self.chat_item(call, {"lines": [{"line": i, "label": "doctor" if i % 2 else "patient"} for i in range(1, count + 1)]})


@pytest.fixture
def stored(tmp_path, recordings_kept, monkeypatch):
    return build(tmp_path, recordings_kept, monkeypatch, MadeUpVoiceWorker, with_calls=False)


def calls_into(stored, out, engine, jobs):
    """The pages copied under a folder of their own, and the jobs run there."""
    if not (out / "results").exists():
        shutil.copytree(stored["out"] / "results", out / "results")
    door = Door(engine, ModelCalls(open_database(out / "calls" / "calls.db")), GEMMA_4_QAT)
    return [commands2.speech_calls(out, stored["folder"], [stored["scripts"]], job, None, stored["data"],
                                   say=stored["said"].append, make_door=lambda p: door) for job in jobs]


def test_6c_the_parts_reading_cuts_each_page_in_two_with_the_apps_function_sends_every_part_and_never_asks_twice(stored, tmp_path):
    # Details, The bench of parts against whole: half the page rounded up, the overlap 10, each part a call of its own.
    engine = LabelsEngine(fails={1})                 # the first part of the first page gets no answer
    assert calls_into(stored, tmp_path / "parts", engine, ["label_check_parts"]) == [5]
    results = ResultWriter(tmp_path / "parts" / "calls").read_all()
    assert sorted(chain for (job, chain) in results if job == "label_check_parts") == PAGES
    assert len(engine.calls) == 6                    # two calls a page; the second part is sent although the first failed
    for chain in PAGES:
        record = results[("label_check_parts", chain)]
        lines = model_lines.lines_of(pages.stop_pieces(ResultWriter(tmp_path / "parts").read(*chain.split("--"))))
        cut = joined.cut(lines, whole=0, part=math.ceil(len(lines) / 2), overlap=joined.OVERLAP_LINES)
        assert [(p["k"], p["overlap"], p["lines"]) for p in record["parts"]] == [(p["k"], p["overlap"], [ln["n"] for ln in p["lines"]]) for p in cut]
        assert len(record["parts"]) == 2 and [len(p["lines"]) - p["overlap"] for p in record["parts"]] == [math.ceil(len(lines) / 2), len(lines) // 2]
        assert record["user"] == [model_lines.lines_text(joined.numbered(p)) for p in cut]
        assert all(text.startswith("TRANSCRIPT:\n[1] ") for text in record["user"])
        assert all(p["call"]["job"] == "bench_label_check" and p["call"]["max_tokens"] == 3000 for p in record["parts"])
    failed, whole = results[("label_check_parts", PAGES[0])], results[("label_check_parts", PAGES[2])]
    assert not failed["call"]["ok"] and failed["call"]["failure"] == "too_slow" and failed["labels"] is None      # all or nothing
    assert failed["parts"][0]["labels"] is None and failed["parts"][1]["labels"] is not None                    # the second part answered, and is counted
    assert whole["call"]["ok"] and sorted(int(n) for n in whole["labels"]) == [ln["n"] for ln in whole["lines"]]
    # 15.10 ruling 24: each part and the page keep the counts of the reply; a part with no answer has none.
    none = {"named_twice": 0, "dropped": 0, "made_unsure": []}
    assert [p["counts"] for p in failed["parts"]] == [None, none] and failed["counts"] == none
    assert [p["counts"] for p in whole["parts"]] == [none, none] and whole["counts"] == none
    assert calls_into(stored, tmp_path / "parts", engine, ["label_check_parts"]) == [0] and len(engine.calls) == 6
    assert stored["said"][-1] == words.BENCH_CALLS_DONE.format(made=0, failed=0, kept=3)


def marks_run(stored, write, **folders):
    return stop_marks.speech_stop_marks(folders["local"], folders.get("parts"), folders.get("cloud"), None, stored["folder"],
                                        [stored["scripts"]], stored["marks"], write, say=stored["said"].append)


def test_6c_the_marks_are_counted_from_the_stored_results_alone_twice_the_same_bytes_and_never_over_a_file(stored, tmp_path):
    # P1 and P2 (the parts against the whole) and H1, H2, D1 to D3 (ruling 22; 15.13 ruling 8), on made-up replies.
    local, parts, cloud, dead = (tmp_path / name for name in ("local", "parts", "cloud", "dead"))
    # The local whole reading: the first page gets no answer, the second reply misses a line and is refused, the third is taken.
    calls_into(stored, local, ScriptedEngine(), ["label_check", "drug_name"])
    calls_into(stored, parts, LabelsEngine(), ["label_check_parts"])
    calls_into(stored, cloud, LabelsEngine(), ["label_check", "label_check_parts", "drug_name"])
    calls_into(stored, dead, LabelsEngine(fails=set(range(1, 40))), ["label_check", "label_check_parts", "drug_name"])
    assert marks_run(stored, tmp_path / "w1", local=local, parts=parts, cloud=cloud) == 0
    assert marks_run(stored, tmp_path / "w2", local=local, parts=parts, cloud=cloud) == 0
    for name in ("scores.json", "report.md"):
        assert (tmp_path / "w1" / name).read_bytes() == (tmp_path / "w2" / name).read_bytes()
    assert marks_run(stored, tmp_path / "w1", local=local, parts=parts, cloud=cloud) == 6      # never over a file
    for place in (commands.REPO / "x", tmp_path / "owner-data" / "o", stored["folder"] / "o"):
        assert marks_run(stored, place, local=local, parts=parts) == 6 and not place.exists()   # R18
    scored = json.loads((tmp_path / "w1" / "scores.json").read_text(encoding="utf-8"))
    marks, rows = scored["marks"], {f"{r['arm']} {r['recording']}": r for r in scored["pages"]}
    assert scored["rule"] == "15.10 ruling 24"
    # A page whose whole reply was not taken is reported and not judged.
    assert marks["judged"] == 1 and marks["not_judged"] == ["nemotron one", "nemotron_tied_pair one"]
    assert [rows[p]["local"]["whole"]["state"] for p in sorted(rows)] == ["failed", "refused", "taken"]
    judged = rows["whisperx_pyannote one"]
    assert marks["judged_words"] == judged["words"]
    assert marks["P1"] == {"holds": True, "pages_missed": []}
    assert marks["P2"]["allowance"] == judged["words"] // 200 and marks["P2"]["line"] == marks["P2"]["whole_wrong"] + marks["P2"]["allowance"]
    assert marks["P2"]["whole_wrong"] == judged["local"]["whole"]["wrong"] and marks["P2"]["parts_wrong"] == judged["local"]["parts"]["wrong"]
    assert marks["P2"]["holds"] == (marks["P2"]["parts_wrong"] <= marks["P2"]["line"])
    assert judged["local"]["parts"]["parts"] == 2 and judged["local"]["parts"]["parts_answered"] == 2
    assert marks["H1"]["holds"] and marks["H1"]["parts_pages"] == 3
    assert marks["H2"]["whole"] == {"local": judged["local"]["whole"]["wrong"], "cloud": judged["cloud"]["whole"]["wrong"]}
    assert marks["H2"]["parts"]["local"] == marks["H2"]["parts"]["cloud"] and marks["H2"]["holds"]      # the same made-up replies
    assert marks["D1"] == {"holds": True, "answered": 3, "pages": 3}
    assert marks["D2"]["holds"] and marks["D3"]["holds"]
    # The local made-up reply holds one entry that is not on its line; code dropped it on every page, and it is counted.
    stored_drug = [r for (job, _), r in ResultWriter(local / "calls").read_all().items() if job == "drug_name"]
    dropped = sum(len(r["dropped"]) for r in stored_drug)
    assert dropped >= 3 and marks["invents_nothing"]["local"] == {
        "label_entries_with_more_than_a_number_and_a_label": 0, "drug_entries_dropped": dropped,
        "drug_entries_kept": sum(len(r["kept"]) for r in stored_drug)}
    assert marks["invents_nothing"]["cloud"]["drug_entries_dropped"] == sum(
        len(r["dropped"]) for (job, _), r in ResultWriter(cloud / "calls").read_all().items() if job == "drug_name")
    assert marks["invents_nothing"]["cloud"]["label_entries_with_more_than_a_number_and_a_label"] == 0
    report = (tmp_path / "w1" / "report.md").read_text(encoding="utf-8")
    assert "- P1: holds." in report and "| whisperx_pyannote one |" in report and "chest" not in report     # counts, never a word of a page
    assert words.BENCH_STOP_MARKS_RULE.format(rule="15.10 ruling 24") in report and "| Named twice | Dropped |" in report
    assert (judged["local"]["whole"]["named_twice"], judged["local"]["whole"]["dropped"], judged["local"]["parts"]["made_unsure_words"]) == (0, 0, 0)
    assert marks["P2_if_made_unsure_were_wrong"]["holds"] == marks["P2"]["holds"]                           # no line was made unsure here
    # A cloud model whose every call fails misses H1 and D1, by the page.
    assert marks_run(stored, tmp_path / "w3", local=local, parts=parts, cloud=dead) == 0
    missed = json.loads((tmp_path / "w3" / "scores.json").read_text(encoding="utf-8"))["marks"]
    assert not missed["H1"]["holds"] and missed["H1"]["whole_missed"] == ["whisperx_pyannote one"] and len(missed["H1"]["parts_missed"]) == 3
    assert missed["D1"] == {"holds": False, "answered": 0, "pages": 3}
    # Without the parts and the cloud folders the marks that need them are not made up.
    assert marks_run(stored, tmp_path / "w4", local=local) == 0
    assert set(json.loads((tmp_path / "w4" / "scores.json").read_text(encoding="utf-8"))["marks"]) == {"judged", "judged_words", "not_judged"}


def stored_call(folder, job, chain, change):
    """One stored result of a call read, changed and written back: the test's hand on what is stored."""
    path = folder / "calls" / "results" / job / f"{chain}.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    change(record)
    path.write_text(json.dumps(record), encoding="utf-8")
    return record


def test_6c2_the_count_again_judges_every_stored_reply_afresh_and_never_reads_the_stored_labels_or_refusals(stored, tmp_path):
    # The prompt of 6c2, change 2; the details of 6c2, The count again; 15.10 ruling 24.
    local, parts = tmp_path / "local", tmp_path / "parts"
    calls_into(stored, local, LabelsEngine(), ["label_check", "drug_name"])
    calls_into(stored, parts, LabelsEngine(), ["label_check_parts"])
    assert marks_run(stored, tmp_path / "w1", local=local, parts=parts) == 0
    first = json.loads((tmp_path / "w1" / "scores.json").read_text(encoding="utf-8"))
    assert first["marks"]["judged"] == 3 and first["marks"]["P1"]["holds"]

    # The stored labels and refusals, written by the rule of their day, are made wrong everywhere: no byte of the tables changes.
    def spoil(record):
        for found in [record] + record.get("parts", []):
            found["labels"], found["refusal"] = {n: "unsure" for n in (found["labels"] or {})}, {"reason": "refused", "missing": [1]}
    for chain in PAGES:
        stored_call(local, "label_check", chain, spoil)
        stored_call(parts, "label_check_parts", chain, spoil)
    assert marks_run(stored, tmp_path / "w2", local=local, parts=parts) == 0
    for name in ("scores.json", "report.md"):
        assert (tmp_path / "w1" / name).read_bytes() == (tmp_path / "w2" / name).read_bytes()

    # Ruling 24 on stored replies. Page one, whole: line 1 named again with another label, and a number off the page.
    def twice_and_off(record):
        record["call"]["answer"]["lines"] += [{"line": 1, "label": "patient"}, {"line": 99, "label": "doctor"}]
    stored_call(local, "label_check", PAGES[0], twice_and_off)
    # Page one, in parts: in the second part its first new line is named again with another label (it is made unsure),
    # and its first carried line too (counted as named twice, but its label comes from the part before).
    def in_a_part(record):
        second = record["parts"][1]
        new_line = second["overlap"] + 1
        given = {e["line"]: e["label"] for e in second["call"]["answer"]["lines"]}
        other = lambda n: "patient" if given[n] == "doctor" else "doctor"   # noqa: E731
        second["call"]["answer"]["lines"] += [{"line": new_line, "label": other(new_line)}, {"line": 1, "label": other(1)},
                                              {"line": 0, "label": "doctor"}]
    record = stored_call(parts, "label_check_parts", PAGES[0], in_a_part)
    assert record["parts"][1]["overlap"] >= 1
    # Page two, in parts: the first part's reply misses its last line. All or nothing: the page is refused, though the other part is taken.
    stored_call(parts, "label_check_parts", PAGES[1], lambda r: r["parts"][0]["call"]["answer"]["lines"].pop())
    assert marks_run(stored, tmp_path / "w3", local=local, parts=parts) == 0
    scored = json.loads((tmp_path / "w3" / "scores.json").read_text(encoding="utf-8"))
    rows = {f"{r['arm']}--{r['recording']}": r["local"] for r in scored["pages"]}
    before = {f"{r['arm']}--{r['recording']}": r["local"] for r in first["pages"]}
    one, was = rows[PAGES[0]], before[PAGES[0]]
    assert (one["whole"]["state"], one["whole"]["named_twice"], one["whole"]["dropped"], one["whole"]["made_unsure_lines"]) == ("taken", 1, 1, 1)
    assert one["whole"]["made_unsure_words"] > 0 and one["whole"]["unsure"] == was["whole"]["unsure"] + one["whole"]["made_unsure_words"]
    assert one["whole"]["right"] + one["whole"]["wrong"] == was["whole"]["right"] + was["whole"]["wrong"] - one["whole"]["made_unsure_words"]
    assert (one["parts"]["state"], one["parts"]["named_twice"], one["parts"]["dropped"], one["parts"]["made_unsure_lines"]) == ("taken", 2, 1, 1)
    assert (one["parts"]["parts"], one["parts"]["parts_answered"], one["parts"]["parts_refused"]) == (2, 2, 0)
    two = rows[PAGES[1]]
    assert (two["parts"]["state"], two["parts"]["parts_answered"], two["parts"]["parts_refused"]) == ("refused", 2, 1)
    assert two["parts"]["right"] == two["parts"]["wrong"] == 0 and two["parts"]["unsure"] > 0            # no label is taken from either part
    assert scored["marks"]["P1"] == {"holds": False, "pages_missed": [PAGES[1].replace("--", " ")]} and scored["marks"]["judged"] == 3
    made = scored["marks"]["P2_if_made_unsure_were_wrong"]
    assert (made["whole_made_unsure_words"], made["parts_made_unsure_words"]) == (one["whole"]["made_unsure_words"], one["parts"]["made_unsure_words"])
    assert made["parts_wrong"] == scored["marks"]["P2"]["parts_wrong"] + made["parts_made_unsure_words"]
    assert scored["kinds"]["nemotron"]["local_whole"]["named_twice"] == 1 and scored["kinds"]["nemotron"]["local_parts"]["dropped"] == 1

    # The proof before the count: a stored call whose text is not the page's text stops the count, and nothing is written.
    stored_call(parts, "label_check_parts", PAGES[2], lambda r: r["user"].__setitem__(0, r["user"][0] + " more"))
    assert marks_run(stored, tmp_path / "w4", local=local, parts=parts) == 9 and not (tmp_path / "w4").exists()
    assert stored["said"][-1] == words.BENCH_NOT_THE_PAGE.format(call="label_check_parts on whisperx_pyannote, one")


def test_6c_the_bench_command_names_the_parts_reading_and_the_marks(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(commands2, "speech_calls", lambda *a, **k: seen.append((a, k)) or 0)
    assert cli.main(["speech-calls", "--out", str(tmp_path / "o"), "--recordings", "r", "--scripts", "a", "--job", "label_check_parts"]) == 0
    assert seen[0][0][3] == "label_check_parts"
    monkeypatch.setattr(stop_marks, "speech_stop_marks", lambda *a, **k: seen.append((a, k)) or 0)
    assert cli.main(["speech-stop-marks", "--local", "l", "--parts", "p", "--cloud", "c", "--recordings", "r", "--scripts", "a",
                     "--marks", "m", "--write", "w"]) == 0
    assert [str(x) for x in seen[1][0][:4]] == ["l", "p", "c", "None"] and str(seen[1][0][7]) == "w"
