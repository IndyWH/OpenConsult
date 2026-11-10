"""The tables of 5e from the stored results alone (spec 15.9, rulings 27 to
33; the details of 5e; V1_LESSONS 9.4; 15.8 ruling 26). Made-up results:
no figure here says anything of a speech choice."""

import json

import pytest

from openconsult.bench.speech import alba, commands, commands2, speechmatics_upload, tables, tables5e, upload, voice
from openconsult.bench.speech.druglist import CLOSE_AT
from openconsult.bench.speech.upload import Http
from openconsult.bench.writer import ResultWriter
from openconsult.speech.nemotron.wordflow import WORD_CLOSE_S
from tests.made_up_part_two import build
from tests.made_up_recordings import made_sound
from tests.made_up_upload_services import MADE_UP_KEY, MadeUpSpeechmatics
from tests.test_voice import MadeUpVoiceWorker


@pytest.fixture
def five(tmp_path, recordings_kept, monkeypatch):
    """Part two's made-up results, with what 5e adds: the label check as the
    app sends it, a whole recording sent to a made-up service, and a page
    read with a voice cut from another recording."""
    made = build(tmp_path, recordings_kept, monkeypatch, MadeUpVoiceWorker)
    out = made["out"]
    assert commands2.speech_calls(out, made["folder"], [made["scripts"]], "label_check_app", None, made["data"],
                                  say=made["said"].append, make_door=lambda p: made["door"]) in (0, 5)
    one = ResultWriter(out).read("nemotron", "one")
    described = {key: one[key] for key in ("recording", "recording_sha256", "script", "script_key", "script_sha256", "speakers",
                                           "machine_voices", "consent")}
    sent = upload.run_upload(speechmatics_upload, Http(speechmatics_upload.EU_HOST, MadeUpSpeechmatics()), MADE_UP_KEY, b"RIFF",
                             "sound-1.wav", described, made_sound(3.0), 16000, clock=lambda: 0.0, sleep=lambda s: None)
    ResultWriter(out).write("speechmatics_upload", "one", sent)
    learnt = ResultWriter(out / "voice").read("nemotron", "one")
    ResultWriter(out / "voice").write("nemotron", "one--from-voice_two", dict(learnt, doctor_voice="voice_two"))
    made["database"].close()
    return made


def score(five, write, counting=True):
    return commands.speech_score(five["out"], five["folder"], [five["scripts"]], five["marks"], write, say=five["said"].append,
                                 key_facts_path=five["key_facts"], drug_list_path=five["drug_list"], counting=counting)


def test_V1_LESSONS_9_4_the_tables_of_5e_written_twice_are_the_same_bytes_and_nothing_is_called_a_rehearsal(tmp_path, five):
    assert score(five, tmp_path / "w1") == 0 and score(five, tmp_path / "w2") == 0
    for name in ("scores.json", "report.md"):
        assert (tmp_path / "w1" / name).read_bytes() == (tmp_path / "w2" / name).read_bytes()
    text = (tmp_path / "w1" / "report.md").read_text(encoding="utf-8")
    assert tables.COUNTING in text and "REHEARSAL" not in text and "# The tables of 5e" in text
    # Without the word that the figures count, the tables are those of a rehearsal and hold nothing of 5e.
    assert score(five, tmp_path / "w3", counting=False) == 0
    rehearsal = (tmp_path / "w3" / "report.md").read_text(encoding="utf-8")
    assert tables.REHEARSAL in rehearsal and "# The tables of 5e" not in rehearsal
    assert "five_e" not in json.loads((tmp_path / "w3" / "scores.json").read_text(encoding="utf-8"))


def test_5e_the_first_table_has_a_row_for_each_of_the_eight_kinds_of_page(tmp_path, five):
    assert score(five, tmp_path / "w") == 0
    scored = json.loads((tmp_path / "w" / "scores.json").read_text(encoding="utf-8"))["five_e"]
    assert sorted(scored["kinds"]) == sorted(arm for arm, _ in tables5e.KINDS) and len(tables5e.KINDS) == 8
    table = tables5e.first_table(scored["kinds"])
    assert len(table) == 2 + 8 and table[0].count("|") == table[2].count("|")
    # The line for Alba stands on a live row only: a whole recording sent at Stop has no live text.
    assert scored["kinds"]["speechmatics_upload"]["alba"] is None and "no live text" in table[2 + 6]
    assert scored["kinds"]["nemotron"]["alba"]["serves"]["yes"] in (True, False) and "(a reading;" in table[2 + 2]
    assert "no page" in table[2 + 7]                                  # no result of that kind was stored
    # The label check both ways, the app's first; the voice by its source.
    nemotron = scored["kinds"]["nemotron"]["wrong_speaker"]
    assert set(nemotron) == {"choice", "label_check_app", "label_check_app_failed", "label_check_own", "label_check_own_failed",
                             "voice", "together"}
    assert list(nemotron["voice"]) == ["voice_two"]
    page = scored["recordings"]["one"]["pages"]["nemotron"]
    assert page["sizes"]["label_check"]["reply_limit"] == 3000 and page["sizes"]["label_check"]["context"] == 16384
    assert page["sizes"]["label_check"]["lines"] == page["who_app"]["rows"] and page["sizes"]["note"]["turns"] >= 1
    up = scored["recordings"]["one"]["pages"]["speechmatics_upload"]["upload"]
    assert up["gone"] is True and up["counted_s"] == 7.0 and up["applied"]["domain"] == "medical"


def test_5e_the_other_values_change_no_stored_figure_and_no_figure_of_the_code(tmp_path, five):
    assert score(five, tmp_path / "w") == 0
    scored = json.loads((tmp_path / "w" / "scores.json").read_text(encoding="utf-8"))
    five_e = scored["five_e"]
    # The draft figures stand as they were (the details of 5e: not changed in code).
    assert (CLOSE_AT, WORD_CLOSE_S, voice.BAND) == (0.75, 2.0, 0.1)
    assert five_e["figures"] == {"closeness": 0.75, "band": 0.1, "cluster_threshold": voice.CLUSTER_THRESHOLD}
    page = five_e["recordings"]["one"]["pages"]["nemotron"]
    assert list(page["closeness"]) == ["0.65", "0.70", "0.75", "0.80", "0.85"]
    marks = [page["closeness"][value]["marks"] for value in page["closeness"]]
    assert marks == sorted(marks, reverse=True)                        # a stricter value never marks more
    # At the code's own value the table agrees with the list's marks of part two.
    listed = scored["part_two"]["recordings"]["one"]["arms"]["nemotron"]["ways"]["list"]
    assert page["closeness"]["0.75"]["marks"] == sum(listed["places"].values())
    assert list(page["voice_bands"]) == ["0.05", "0.10", "0.15", "0.20"]
    assert page["voice_bands"]["0.10"] == page["voice"]                # the band of the code gives the reading of the tables
    # The close of a word: from the largest gap a Nemotron result stored, and nothing else.
    results = {("nemotron", "x"): {"stop": {"notes": {"largest_gap_inside_word_frames": 16, "tokens_after_close_by_time": 0}}},
               ("nemotron_tied_pair", "x"): {"stop": {"notes": {"largest_gap_inside_word_frames": 99}}}}
    assert tables5e.word_close_table(results) == {"x": {"largest_gap_s": 1.28, "tokens_after_close_by_time": 0,
                                                        "would_cut": {"0.5": True, "1.0": True, "1.5": False, "2.0": False}}}


def test_5e_the_loudness_of_a_recording_and_the_two_lists_for_listening():
    # 10 s of sound: words from 1.0 to 2.0 (loud), a pause, a quiet word at 5.0 to 5.5, then nothing.
    windows = [-60.0] * 100
    for i in range(10, 21):
        windows[i] = -18.0
    for i in range(50, 56):
        windows[i] = -42.0
    tokens = [{"norm": "one", "start": 1.0, "end": 1.5}, {"norm": "two", "start": 1.5, "end": 2.0},
              {"norm": "three", "start": 5.0, "end": 5.5}, {"norm": "four", "start": None, "end": None}]
    found = tables5e.loudness_of({"loudness": {"dbfs": windows, "window_s": 0.1}}, tokens)
    assert found["speech"]["n"] == 17 and found["speech"]["p50"] == -18.0 and found["pause"]["p50"] == -60.0
    assert found["speech_at_or_below"] == {"-40.0": 6, "-30.0": 6}     # the quiet word lies under both figures
    assert found["pause_above"] == {"-40.0": 0, "-30.0": 0}
    assert tables5e._clock(125.25) == "2:05.2" and tables5e._clock(None) == "?"
    from openconsult.bench.speech.reference import build as build_reference
    reference = build_reference("**DOCTOR:** One two three four.\n")
    rec_one = {"arms": {"nemotron": {"stop": {"rule": {"invented_let_through": [
        {"word": "um", "piece": [61.0, 61.08, "um"], "loudest_dbfs": -47.0}]}}}},
               "agreed": [{"index": 2, "speech": 1, "spoken": "three", "written": "tree", "kind": "agreed", "arms": ["a", "b", "c"],
                           "touches": []},
                          {"index": 0, "speech": 1, "spoken": "one", "written": None, "kind": "left out", "arms": [], "touches": []}]}
    lists = tables5e.listen_lists("made", rec_one, tokens, reference)
    assert lists["let_through"] == [{"recording": "made", "arm": "nemotron", "page": "stop", "at": "1:01.0", "word": "um",
                                     "loudest_dbfs": -47.0}]
    assert lists["agreed"] == [{"recording": "made", "at": "0:05.0", "speech": 1, "script": "three", "written": "tree",
                                "touches": [], "arms": 3}]


def test_5e_the_cell_for_alba_says_yes_or_no_as_a_reading_with_its_counts():
    rows = [{"speech": 2, "t_final": 5.0, "by_choice": 0.5, "by_sound": 0.4, "apart_choice": None, "apart_sound": None,
             "after_reply": False}]
    cell = tables5e._alba_cell(alba.summary(rows))
    assert cell.startswith("yes (a reading; by the sound: typical 0.4 s; 1 of 1 within 0.8 s by the sound; 0 of 1 final only after")
    late = tables5e._alba_cell(alba.summary([dict(rows[0], after_reply=True)]))
    assert late.startswith("no (a reading; by the sound: typical: late; ") and tables5e._alba_cell(None) == "no live text"


def test_R31_nothing_of_5e_is_built_into_the_app():
    # No pass at Stop, no voice method, no way of spotting a drug name, no new job and no new choice in the app.
    from openconsult.llm.jobs import JOBS
    from openconsult.speech.choices import CHOICES
    assert sorted(JOBS) == ["alarm", "assessment", "guideline", "label_check", "letter", "note", "referrals"]
    assert sorted(CHOICES) == ["assemblyai", "nemotron", "speechmatics", "whisperx_pyannote"]
    assert all(choice.declares.second_transcript is False for name, choice in CHOICES.items() if choice.key)
    import openconsult
    from pathlib import Path
    root = Path(openconsult.__file__).resolve().parent
    for path in root.rglob("*.py"):
        if "bench" in path.relative_to(root).parts:
            continue
        text = path.read_text(encoding="utf-8")
        assert "voicecut" not in text and "tables5e" not in text and "bench.speech.alba" not in text
