"""The banked list and where recordings are kept (spec 13.2 item 6; 13.4
rule 3; R18; V1_LESSONS 9.4, 9.5, 12). Every recording here is made sound."""

import json

import pytest

from openconsult.bench.speech import banked, sound
from openconsult.bench.speech.banked import BadList, NotListed, RecordingChanged, check_file, load_list, named
from openconsult.bench.writer import Refused, ResultWriter
from tests.made_up_recordings import entry, made_up_recordings, write_wav


def test_13_4_rule_3_recordings_come_only_from_the_list(recordings_kept):
    folder = made_up_recordings(recordings_kept.folder)
    (folder / "stray.wav").write_bytes(b"RIFF")                     # a file in the folder the list does not name
    recordings_kept.settle()
    listed = load_list(folder)
    assert [r.name for r in listed] == ["one", "two"]
    one = named(listed, "one")
    assert one.path == folder / "one.wav" and one.rate == 16000 and one.speakers == 2 and one.whole
    assert one.entry["room"] == "not known" and one.read_differently == ()
    assert not one.cloud_allowed("speechmatics") and named(listed, "two").cloud_allowed("speechmatics")
    with pytest.raises(NotListed):
        named(listed, "stray")
    assert banked.folders_of(listed) == [folder.resolve()]


def test_R18_a_recording_whose_checksum_differs_is_refused_before_anything_is_read_as_sound(recordings_kept):
    folder = made_up_recordings(recordings_kept.folder)
    pcm = sound.read_wav(folder / "one.wav", 16000)
    write_wav(folder / "one.wav", pcm[:-2] + b"\0\1")               # the bytes change, the list does not
    recordings_kept.settle()
    listed = load_list(folder)
    with pytest.raises(RecordingChanged, match="one.wav has sha256"):
        check_file(named(listed, "one"))
    check_file(named(listed, "two"))                               # the twin: an unchanged file passes
    (folder / "two.wav").unlink()
    with pytest.raises(RecordingChanged, match="missing"):
        check_file(named(listed, "two"))
    recordings_kept.settle()


def test_R18_the_guard_fails_a_test_that_writes_where_recordings_are_kept(recordings_kept):
    folder = made_up_recordings(recordings_kept.folder)
    recordings_kept.settle()
    recordings_kept.check()                                                 # nothing written: quiet
    (folder / "new.wav").write_bytes(b"x")
    with pytest.raises(pytest.fail.Exception, match="R18"):
        recordings_kept.check()
    (folder / "new.wav").unlink()
    (folder / "one.wav").write_bytes((folder / "one.wav").read_bytes())    # the same bytes, written again
    with pytest.raises(pytest.fail.Exception, match="one.wav"):
        recordings_kept.check()
    recordings_kept.settle()                                                # so the teardown passes after the twin


def test_9_4_results_never_go_into_the_repo_the_data_folders_or_a_recordings_folder(tmp_path, recordings_kept):
    folder = made_up_recordings(recordings_kept.folder)
    recordings_kept.settle()
    repo, data, workers = tmp_path / "repo", tmp_path / "data", tmp_path / "workers"
    forbidden = (repo, data, workers, *banked.folders_of(load_list(folder)))
    for place in (repo / "x", data, workers / "speech", folder, folder / "results"):
        with pytest.raises(Refused):
            ResultWriter(place, forbidden=forbidden)
    writer = ResultWriter(tmp_path / "out", forbidden=forbidden)
    writer.write("arm", "one", {"n": 1})
    with pytest.raises(Refused):
        writer.write("arm", "one", {"n": 2})
    assert writer.read("arm", "one") == {"n": 1}


def test_a_list_that_is_not_whole_is_refused(tmp_path):
    folder = tmp_path / "rec"
    folder.mkdir()

    def listed(**over):
        (folder / "recordings.json").write_text(json.dumps({"recordings": [entry("x", "x.wav", "0" * 64, **over)]}))
        return load_list(folder)

    with pytest.raises(BadList, match="last speech"):
        listed(whole=False)
    with pytest.raises(BadList, match="rate"):
        listed(rate=44100)
    with pytest.raises(BadList, match="consent"):
        listed(consent={"recording": True})
    with pytest.raises(BadList, match="speakers"):
        listed(speakers=0)
    assert listed(whole=False, last_speech=26)[0].last_speech == 26
    assert listed(date="not known", parts="not known")[0].entry["date"] == "not known"
    (folder / "recordings.json").write_text(json.dumps({"recordings": [{"name": "x"}]}))
    with pytest.raises(BadList, match="missing"):
        load_list(folder)
    with pytest.raises(BadList, match="no recordings.json"):
        load_list(tmp_path / "nowhere")


def test_the_recording_is_read_as_wav_16_bit_one_channel_in_quarter_second_pieces(tmp_path, recordings_kept):
    folder = made_up_recordings(recordings_kept.folder, rate=48000, seconds=1.0)
    recordings_kept.settle()
    pcm = sound.read_wav(folder / "one.wav", 48000)
    assert sound.seconds_of(pcm, 48000) == 1.0 and len(sound.pieces(pcm, 48000)) == 4
    assert all(len(p) == 48000 // 4 * 2 for p in sound.pieces(pcm, 48000))
    with pytest.raises(sound.BadSound, match="expected 1, 16, 16000"):
        sound.read_wav(folder / "one.wav", 16000)
    import wave
    stereo = tmp_path / "stereo.wav"
    with wave.open(str(stereo), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(16000)
        out.writeframes(bytes(16000))
    with pytest.raises(sound.BadSound):
        sound.read_wav(stereo, 16000)
    (tmp_path / "not.wav").write_bytes(b"not a wav")
    with pytest.raises(sound.BadSound, match="not a WAV"):
        sound.read_wav(tmp_path / "not.wav", 16000)
