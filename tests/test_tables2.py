"""The scores and the tables of part two from the stored results alone
(spec 15.8 ruling 26; 15.9, the details of part two of 5c; 13.4 rule 2;
V1_LESSONS 9.4). Made-up results."""

import json

import pytest

from openconsult import words
from openconsult.bench.speech import commands
from tests.made_up_part_two import build
from tests.test_voice import MadeUpVoiceWorker


@pytest.fixture
def part_two(tmp_path, recordings_kept, monkeypatch):
    return build(tmp_path, recordings_kept, monkeypatch, MadeUpVoiceWorker)


def score(part_two, write, **extra):
    said = part_two["said"]
    return commands.speech_score(part_two["out"], part_two["folder"], [part_two["scripts"]], part_two["marks"], write,
                                 say=said.append, **extra), said


def test_15_8_ruling_26_the_tables_of_part_two_are_the_same_byte_for_byte_and_put_the_patient_first(tmp_path, part_two):
    files = {"key_facts_path": part_two["key_facts"], "drug_list_path": part_two["drug_list"]}
    code, said = score(part_two, tmp_path / "w1", **files)
    assert code == 0 and said[-1].startswith("Scored part two as well: 3 pages, 14 calls, 3 voice results")
    assert score(part_two, tmp_path / "w2", **files)[0] == 0
    for name in ("scores.json", "report.md"):
        assert (tmp_path / "w1" / name).read_bytes() == (tmp_path / "w2" / name).read_bytes()
    assert score(part_two, tmp_path / "w1", **files)[0] == 6                         # never written over
    text = (tmp_path / "w1" / "report.md").read_text(encoding="utf-8")
    assert "# Part two: what is done with the transcripts\nTHIS IS A REHEARSAL. NO FIGURE IN IT COUNTS." in text.replace("\n\n", "\n")
    assert "| speech choice | a drug written as another real drug |" in text
    scored = json.loads((tmp_path / "w1" / "scores.json").read_text(encoding="utf-8"))["part_two"]
    arms = scored["arms"]
    assert sorted(arms) == ["nemotron", "nemotron_tied_pair", "whisperx_pyannote"]
    nem = scored["recordings"]["one"]["arms"]["nemotron"]
    assert nem["label_check"]["failed"] and nem["who"]["counts"]["label_check"]["right"] == 0        # the failed call: all unsure
    assert scored["recordings"]["one"]["arms"]["nemotron_tied_pair"]["label_check"]["refused"]
    assert nem["voice"]["lines"] == 3 and nem["who"]["counts"]["together"]["unsure"] >= 0
    assert set(nem["ways"]) == {"list", "second_listen", "model"} and nem["ways"]["model"]["dropped"] == 1
    assert "second_listen" not in scored["recordings"]["one"]["arms"]["nemotron_tied_pair"]["ways"]
    assert nem["classes"]["real_drug_not_spoken"] == 0 and arms["nemotron"]["wrong_drug"] == 0
    r1, r2 = nem["notes"]["rounds"]["1"], nem["notes"]["rounds"]["2"]
    assert [f["outcome"] for f in r1["key_facts"]] == ["found", "found", "found", "missing", "missing"]
    assert not r1["reasoning_cut"] and r2["reasoning_cut"] and len(r1["bad_turns"]) == 1                # turns [9] names no turn
    assert [f["figure"] for f in r1["figures_not_spoken"]] == ["150", "2"]      # the page wrote 115, and 2/52 was never said
    assert nem["notes"]["chance"] == {"facts": 5, "differ": 0, "ids": []}
    assert sorted(nem["notes"]["not_found"]) == ["MU-04", "MU-05"] and nem["notes"]["not_found"]["MU-04"]["script_missed"]
    assert arms["nemotron"]["facts_not_found"] == 2 and arms["nemotron"]["facts_not_found_script_found"] == 0
    assert scored["calls"]["label_check"] == {**scored["calls"]["label_check"], "calls": 3, "ok": 2, "failed": {"too_slow": 1}, "refused": 1}
    assert scored["calls"]["note"]["calls"] == 6 and scored["drug_list"]["names"] == 8
    assert "also not found from the script" in text and "MU-04" in text


def test_with_no_result_of_part_two_the_marks_of_part_one_are_written_and_no_file_is_needed(tmp_path, recordings_kept, monkeypatch):
    part = build(tmp_path, recordings_kept, monkeypatch, MadeUpVoiceWorker, with_calls=False)
    import shutil
    shutil.rmtree(part["out"] / "voice")
    shutil.rmtree(part["out"] / "calls")
    code, said = score(part, tmp_path / "w")
    assert code == 0 and said[-1].startswith("Scored 4 results of 4 arms")
    text = (tmp_path / "w" / "report.md").read_text(encoding="utf-8")
    assert "Part two" not in text and "part_two" not in json.loads((tmp_path / "w" / "scores.json").read_text())


def test_with_results_of_part_two_and_a_file_lacking_the_command_says_which_and_writes_nothing(tmp_path, part_two):
    code, said = score(part_two, tmp_path / "w", drug_list_path=part_two["drug_list"])
    assert code == 9 and said[-1] == words.BENCH_NEEDS_FILE.format(option="--key-facts", what="the key-fact file")
    code, said = score(part_two, tmp_path / "w", key_facts_path=part_two["key_facts"])
    assert code == 9 and said[-1] == words.BENCH_NEEDS_FILE.format(option="--drug-list", what="the drug list")
    assert not (tmp_path / "w").exists()
