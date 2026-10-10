"""The scores and the tables from stored results alone (spec 15.8 ruling
26; 15.9, the details of 5c; V1_LESSONS 9.4). Made-up results, made by
the replay with a made-up worker behind the door."""

import datetime as dt
import json

import pytest

from openconsult.bench.speech import tables
from openconsult.bench.speech.arms import ARMS
from openconsult.bench.speech.banked import load_list, named
from openconsult.bench.speech.replay import run
from openconsult.bench.speech.sound import read_wav
from openconsult.bench.writer import Refused, ResultWriter
from openconsult.speech.choices import NEMOTRON, WHISPERX_PYANNOTE
from openconsult.speech.door import Door
from tests.fakes import MadeUpWorker
from tests.made_up_recordings import made_up_recordings, scripts_folder
from tests.test_speech_door import seg
from tests.test_speech_replay import FakeClock

NOW = dt.datetime(2026, 10, 10, 12, 0, 0)
MARKS = {"v1_line": {"drugs": ["metformin"], "tests": ["ECG"]},
         "scripts": {"MU": {"drugs": {"metformin": 1, "co-codamol": 1}, "tests": {}, "safety_net_speeches": [5]}}}
S1 = "Any chest pain at rest, or when you climb the stairs?"
S2 = "No chest pain at rest. I take metformin and co-codamol."
S3 = "Your blood pressure is 150 over 95."
S4 = "Is that high?"
S5 = "If the pain comes at rest, go straight to the hospital. Understood?"
S6 = "Understood, doctor."


def whisperx_worker():
    """Live hears everything; the pass at Stop drops speeches 3 and 4."""
    live = [[] for _ in range(12)]
    live[5] = [{"start": 0.5, "end": 1.2, "text": S1}, {"start": 1.2, "end": 1.5, "text": S2}]
    live[8] = [{"start": 1.5, "end": 1.8, "text": S3 + " " + S4}]
    final = {"last_live": [{"start": 1.8, "end": 2.4, "text": S5 + " " + S6}],
             "segments": [seg(0.5, 1.2, S1, "S0", 0.9), seg(1.2, 1.5, S2, "S1", 0.9),
                          seg(1.8, 2.2, S5, "S0", 0.9), seg(2.2, 2.4, S6, "S1", 0.9)], "seconds": {"stop": 1.0}}
    return MadeUpWorker(live=live, final=final)


def nemotron_worker():
    live = [[] for _ in range(12)]
    live[6] = [{"id": 1, "start": 0.5, "end": 1.5, "text": S1 + " " + S2, "speaker": "S1", "confidence": None}]
    live[9] = [{"id": 2, "start": 1.5, "end": 1.8, "text": "Your blood pressure is 115 over 95. Is that high?", "speaker": "S2", "confidence": None}]
    final = {"last_live": [{"id": 3, "start": 1.8, "end": 2.4, "text": S5 + " " + S6, "speaker": "S1", "confidence": None}],
             "revisions": [], "seconds": {"tail": 0.1}, "notes": {"late_changes": [{"id": 1, "text": S1 + " " + S2 + " today", "end": 1.6}]}}
    return MadeUpWorker(live=live, final=final)


def results_of(folder, out):
    listed = load_list(folder)
    one = named(listed, "one")
    pcm = read_wav(one.path, 16000)
    writer = ResultWriter(out)
    clock = FakeClock()
    for arm, choice, worker in (("whisperx_pyannote", WHISPERX_PYANNOTE, whisperx_worker()),
                                ("nemotron", NEMOTRON, nemotron_worker()),
                                ("nemotron_tied_pair", ARMS["nemotron_tied_pair"].choice, nemotron_worker()),
                                ("speechmatics", ARMS["speechmatics"].choice, MadeUpWorker(die_after=4))):
        door = Door(choice, make_worker=lambda w=worker: w, installed=lambda: True)
        writer.write(arm, "one", run(door, ARMS[arm], one, pcm, sleep=clock.sleep, clock=clock, now=lambda: NOW))
    return listed, writer.read_all()


def test_V1_LESSONS_9_4_the_tables_are_the_same_byte_for_byte_and_never_written_over(tmp_path, recordings_kept):
    folder = made_up_recordings(recordings_kept.folder)
    recordings_kept.settle()
    listed, results = results_of(folder, tmp_path / "out")
    scored = tables.score_all(results, listed, [scripts_folder(tmp_path)], MARKS)
    text = tables.as_markdown(scored)
    first = tables.write(tmp_path / "w1", scored, text)
    tables.write(tmp_path / "w2", tables.score_all(results, listed, [scripts_folder(tmp_path)], MARKS), text)
    assert (tmp_path / "w1" / "scores.json").read_bytes() == (tmp_path / "w2" / "scores.json").read_bytes()
    assert (tmp_path / "w1" / "report.md").read_bytes() == (tmp_path / "w2" / "report.md").read_bytes()
    with pytest.raises(Refused):
        tables.write(tmp_path / "w1", scored, text)
    assert text.splitlines()[2] == "THIS IS A REHEARSAL. NO FIGURE IN IT COUNTS."
    assert json.loads(first[0].read_text())["arms"]["nemotron"]["recordings"] == ["one"]


def test_the_scores_hold_the_marks_of_every_arm_and_the_first_table_puts_the_patient_first(tmp_path, recordings_kept):
    folder = made_up_recordings(recordings_kept.folder)
    recordings_kept.settle()
    listed, results = results_of(folder, tmp_path / "out")
    scored = tables.score_all(results, listed, [scripts_folder(tmp_path)], MARKS)
    one = scored["recordings"]["one"]
    wx = one["arms"]["whisperx_pyannote"]
    # The pass at Stop dropped speeches 3 and 4 (10 words): a passage, covered by the gap of the live page.
    assert [p["missing"] for p in wx["stop"]["passages"]] == [10] and wx["stop"]["passages"][0]["gap"]
    assert wx["stop"]["hard"] == {"passages_without_sign": 0, "words_from_silence": 0, "real_words_refused": 0}
    assert wx["live"]["passages"] == [] and wx["live"]["wait"]["to_final"]["n"] == 4
    assert wx["stop"]["who_spoke"]["mapping"] == {"S0": "DOCTOR", "S1": "PATIENT"} and wx["stop"]["who_spoke"]["wrong"] == 0
    assert wx["stop"]["drugs"]["caught"] == 2 and wx["stop"]["drugs"]["in_line"] == {"spoken": 1, "caught": 1}
    nem = one["arms"]["nemotron"]["stop"]
    assert [(p["spoken"], p["written"]) for p in nem["differ"]["numbers_changed"]] == [("150", "115")]
    assert nem["wait"]["to_final"]["n"] == 3 and "times" in nem                      # against WhisperX's word times
    assert one["arms"]["nemotron_tied_pair"]["late_changes"] == {"lines_changed_late": 1, "words_page_lacks": 1}
    assert one["arms"]["speechmatics"] == {"failed": {"at": "feed", "piece": 3, "failure": "died", "detail": "made-up: died with exit code 3"}}
    assert one["agreed"] == [] and one["spoken_words"] == 45 and one["names_as_cut"] == {"metformin": 1, "co-codamol": 1}
    arms = scored["arms"]
    assert arms["speechmatics"] == {"recordings": [], "failed": ["one"], "passages_without_sign": 0, "words_from_silence": 0,
                                    "real_words_refused": 0, "invented_let_through": 0}
    assert arms["nemotron_tied_pair"]["late_changes"] == {"lines_changed_late": 1, "words_page_lacks": 1}
    text = tables.as_markdown(scored)
    assert "| whisperx_pyannote | no | no | 0 | 0 | one | none |" in text
    assert "| speechmatics | no | no | 0 | 0 | none | one |" in text
    assert "late changes: 1 lines, 1 words lacking" in text and "failed at feed" in text


def test_a_script_must_be_found_with_the_lists_checksum(tmp_path, recordings_kept):
    folder = made_up_recordings(recordings_kept.folder)
    recordings_kept.settle()
    listed, results = results_of(folder, tmp_path / "out")
    with pytest.raises(tables.ScriptNotFound, match="none of the script folders"):
        tables.score_all(results, listed, [tmp_path / "nowhere"], MARKS)
    changed = scripts_folder(tmp_path / "changed")
    (changed / "made_up.md").write_text("**DOCTOR:** Another script.\n", encoding="utf-8")
    with pytest.raises(tables.ScriptNotFound, match="checksum"):
        tables.score_all(results, listed, [changed], MARKS)
