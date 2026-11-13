"""The parts reading of the bench and the marks of step 6c (spec 15.10,
ruling 22 and the details of step 6c: The bench of parts against whole,
The bench of Claude Haiku; R18; V1_LESSONS 9.4). A made-up voice worker
and a made-up language model; every reply is made up."""

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
    import json
    scored = json.loads((tmp_path / "w1" / "scores.json").read_text(encoding="utf-8"))
    marks, rows = scored["marks"], {f"{r['arm']} {r['recording']}": r for r in scored["pages"]}
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
    # A cloud model whose every call fails misses H1 and D1, by the page.
    assert marks_run(stored, tmp_path / "w3", local=local, parts=parts, cloud=dead) == 0
    missed = json.loads((tmp_path / "w3" / "scores.json").read_text(encoding="utf-8"))["marks"]
    assert not missed["H1"]["holds"] and missed["H1"]["whole_missed"] == ["whisperx_pyannote one"] and len(missed["H1"]["parts_missed"]) == 3
    assert missed["D1"] == {"holds": False, "answered": 0, "pages": 3}
    # Without the parts and the cloud folders the marks that need them are not made up.
    assert marks_run(stored, tmp_path / "w4", local=local) == 0
    assert set(json.loads((tmp_path / "w4" / "scores.json").read_text(encoding="utf-8"))["marks"]) == {"judged", "judged_words", "not_judged"}


def test_6c_the_bench_command_names_the_parts_reading_and_the_marks(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(commands2, "speech_calls", lambda *a, **k: seen.append((a, k)) or 0)
    assert cli.main(["speech-calls", "--out", str(tmp_path / "o"), "--recordings", "r", "--scripts", "a", "--job", "label_check_parts"]) == 0
    assert seen[0][0][3] == "label_check_parts"
    monkeypatch.setattr(stop_marks, "speech_stop_marks", lambda *a, **k: seen.append((a, k)) or 0)
    assert cli.main(["speech-stop-marks", "--local", "l", "--parts", "p", "--cloud", "c", "--recordings", "r", "--scripts", "a",
                     "--marks", "m", "--write", "w"]) == 0
    assert [str(x) for x in seen[1][0][:4]] == ["l", "p", "c", "None"] and str(seen[1][0][7]) == "w"
