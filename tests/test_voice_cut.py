"""The doctor's voice cut from a recording, and the voice method told its
source (spec 15.9, ruling 33; the details of 5e; R18). Made-up pages, made
sound and a made-up worker: nothing here hears a voice."""

import json
import wave

import pytest

from openconsult import words
from openconsult.bench.speech import banked, commands2, voice, voicecut
from openconsult.bench.speech.reference import build
from openconsult.bench.writer import ResultWriter
from openconsult.settings import paths
from openconsult.speech import environment
from openconsult.speech.choices import WHISPERX_PYANNOTE
from tests.made_up_recordings import entry, made_sound, made_up_recordings, scripts_folder, write_wav
from tests.test_voice import MadeUpVoiceWorker

SCRIPT = ("**DOCTOR:** Tell me one two three four five six seven eight nine ten.\n"
          "**PATIENT:** Yes doctor I will.\n"
          "**DOCTOR:** Alpha beta gamma delta epsilon zeta eta.\n"
          "**DOCTOR:** Theta iota kappa lambda.\n"
          "**PATIENT:** Fine.\n")
REF = build(SCRIPT)


def page(text_and_gaps: list) -> dict:
    """A page at Stop from words; a number in the list is a pause in seconds.
    Each word is 0.2 s long with 0.1 s after it."""
    spoken, t = [], 1.0
    for item in text_and_gaps:
        if isinstance(item, (int, float)):
            t += item
            continue
        for word in item.split():
            spoken.append({"word": word, "start": round(t, 2), "end": round(t + 0.2, 2)})
            t += 0.3
    return {"stop": {"raw": [{"start": 1.0, "end": t, "text": "x", "words": spoken}]}}


def stretches(text_and_gaps):
    return voicecut.stretches_of(voicecut.timed_tokens(page(text_and_gaps), REF), REF)


def test_ruling_33_a_stretch_is_eight_matched_words_inside_one_speech_of_the_doctor():
    # The first speech has eleven words, all matched, and the patient's first word comes 0.8 s after its last.
    found = stretches(["Tell me one two three four five six seven eight nine ten.", 0.7, "Yes doctor I will."])
    assert len(found) == 1 and found[0]["speech"] == 1 and found[0]["words"] == 12
    assert (found[0]["start"], found[0]["end"]) == (1.0, 4.5)                 # first word's start to last word's end
    # Seven matched words are not enough: the third speech has only seven.
    assert stretches(["Alpha beta gamma delta epsilon zeta eta."]) == []
    # A stretch never runs across two speeches of the doctor, though the words follow each other: 7 and 4, neither enough.
    assert stretches(["Alpha beta gamma delta epsilon zeta eta.", "Theta iota kappa lambda."]) == []
    # A word that is not the script's breaks the run: 4 matched, one other, 7 matched.
    assert stretches(["Tell me one two tree four five six seven eight nine ten."]) == []
    # A word with no time breaks it too: it cannot be cut by its times.
    untimed = page(["Tell me one two three four five six seven eight nine ten."])
    del untimed["stop"]["raw"][0]["words"][5]["start"]             # five matched before it, six after
    assert voicecut.stretches_of(voicecut.timed_tokens(untimed, REF), REF) == []


def test_ruling_33_a_stretch_within_half_a_second_of_a_patients_word_is_dropped_and_no_label_is_read():
    # The patient's word starts 0.3 s after the stretch ends (0.1 s after the word and 0.2 s more): dropped.
    assert stretches(["Tell me one two three four five six seven eight nine ten.", 0.2, "Yes doctor I will."]) == []
    # 0.5 s clear: kept.
    assert len(stretches(["Tell me one two three four five six seven eight nine ten.", 0.4, "Yes doctor I will."])) == 1
    # A word standing where nothing was spoken is kept away from as a patient's word is.
    assert stretches(["Tell me one two three four five six seven eight nine ten.", 0.2, "hmm"]) == []
    # The page's own speaker labels are never read: a page that labels everything wrongly gives the same stretches.
    labelled = page(["Tell me one two three four five six seven eight nine ten.", 0.7, "Yes doctor I will."])
    labelled["stop"]["raw"][0]["speaker"] = "SPEAKER_01"
    for word in labelled["stop"]["raw"][0]["words"]:
        word["speaker"] = "SPEAKER_01"
    assert len(voicecut.stretches_of(voicecut.timed_tokens(labelled, REF), REF)) == 1


def test_ruling_33_the_stretches_are_taken_in_the_order_spoken_and_cut_from_the_samples_untouched():
    found = [{"speech": n, "words": 9, "start": float(10 * n), "end": float(10 * n + 8)} for n in range(1, 12)]
    kept = voicecut.taken(found)
    assert [s["speech"] for s in kept] == [1, 2, 3, 4, 5, 6, 7, 8] and voicecut.seconds_of(kept) == 64.0   # stops once past a minute
    assert voicecut.taken(found[:2]) == found[:2] and voicecut.seconds_of(found[:2]) < voicecut.THIN_S     # less than a minute: all of it
    rate = 16000
    pcm = made_sound(3.0, rate)
    data = voicecut.cut(pcm, rate, [{"start": 0.5, "end": 1.0}, {"start": 2.0, "end": 2.25}])
    import io
    with wave.open(io.BytesIO(data), "rb") as made:
        assert (made.getnchannels(), made.getsampwidth(), made.getframerate()) == (1, 2, rate)
        frames = made.readframes(made.getnframes())
    edge = b"\0\0" * rate
    assert frames == edge + pcm[2 * 8000:2 * 16000] + pcm[2 * 32000:2 * 36000] + edge


@pytest.fixture
def bench(tmp_path, recordings_kept, monkeypatch):
    """Two recordings with a page of WhisperX at Stop each, and two voices listed as cut from them."""
    monkeypatch.setattr(paths, "default_data_folder", lambda: tmp_path / "owner-data")
    folder = recordings_kept.folder
    voices = []
    for name, source in (("voice_a", "one"), ("voice_b", "two")):
        sha = write_wav(folder / f"{name}.wav", made_sound(2.0))
        voices.append(entry(name, f"{name}.wav", sha, speakers=1, length_s=2.0, voice_only=True, doctor_voice=None, cut_of=source))
    made_up_recordings(folder, extra=voices)
    recordings_kept.settle()
    out = tmp_path / "out"
    stop = {"lines": [], "last_live": [], "refused": [], "revisions": [],
            "raw": [{"start": 0.2, "end": 1.4, "text": "One two three.", "speaker": "SPEAKER_00"},
                    {"start": 1.6, "end": 2.8, "text": "Four five six.", "speaker": "SPEAKER_01"}]}
    for name in ("one", "two"):
        for arm in ("whisperx_pyannote", "whisperx_v1_line"):
            ResultWriter(out).write(arm, name, {"arm": arm, "recording": name, "failure": None, "pieces": [], "stop": stop})
    data = tmp_path / "data"
    python = environment.python(data, WHISPERX_PYANNOTE)
    python.parent.mkdir(parents=True)
    python.write_bytes(b"")
    workers, said = [], []

    def make_worker(data_folder):
        workers.append(MadeUpVoiceWorker())
        return workers[-1]

    def run(voice_name, names=None):
        return commands2.speech_voice(out, folder, data, names, ["whisperx_pyannote"], say=said.append, make_worker=make_worker,
                                      voice_name=voice_name)

    return {"folder": folder, "out": out, "workers": workers, "said": said, "run": run, "tmp": tmp_path}


def test_ruling_33_the_voice_is_never_learnt_from_the_pages_own_recording(bench):
    out, workers, said, run = bench["out"], bench["workers"], bench["said"], bench["run"]
    assert run("voice_a") == 0
    results = ResultWriter(out / "voice").read_all()
    # voice_a was cut from one: only the page of two is read with it, and the result names its source.
    assert sorted(results) == [("whisperx_pyannote", "two--from-voice_a")]
    assert results[("whisperx_pyannote", "two--from-voice_a")]["doctor_voice"] == "voice_a"
    assert words.BENCH_VOICE_OWN.format(voice="voice_a", name="one") in said
    assert [h["type"] for h, _, _ in workers[0].requests] == ["learn", "score"]
    # Asked for its own recording alone: nothing is learnt, no worker is started.
    assert run("voice_a", names=["one"]) == 0 and len(workers) == 1


def test_ruling_33_a_page_has_one_result_for_each_source_and_neither_is_written_over(bench):
    out, workers, run = bench["out"], bench["workers"], bench["run"]
    third = entry("voice_c", "voice_a.wav", banked.sha256_of(bench["folder"] / "voice_a.wav"), speakers=1, length_s=2.0,
                  voice_only=True, doctor_voice=None, cut_of="elsewhere")
    assert third["voice_only"] and voice.chain_of("two", None) == "two" and voice.chain_of("two", "voice_a") == "two--from-voice_a"
    assert run("voice_a") == 0 and run("voice_b") == 0
    results = ResultWriter(out / "voice").read_all()
    assert sorted(results) == [("whisperx_pyannote", "one--from-voice_b"), ("whisperx_pyannote", "two--from-voice_a")]
    before = {key: json.dumps(value) for key, value in results.items()}
    started = len(workers)
    assert run("voice_a") == 0 and run("voice_b") == 0 and len(workers) == started        # kept: nothing asked again
    assert {key: json.dumps(value) for key, value in ResultWriter(out / "voice").read_all().items()} == before
    # A recording that is not a voice alone is never learnt from.
    assert run("two") == 4


def test_ruling_33_a_voice_alone_is_never_replayed_and_goes_to_no_service(bench, tmp_path):
    listed = banked.load_list(bench["folder"])
    cut = banked.named(listed, "voice_a")
    assert cut.voice_only and not cut.cloud_allowed("speechmatics") and not cut.cloud_whole_allowed("speechmatics")
    # The list refuses a voice alone whose consent names a service, for the stream or for the whole recording.
    other = made_up_recordings(tmp_path / "other")
    for consent in ({"cloud": ["assemblyai"]}, {"cloud": [], "cloud_whole": ["assemblyai"]}):
        listing = json.loads((other / "recordings.json").read_text(encoding="utf-8"))
        listing["recordings"][0].update(voice_only=True, speakers=1,
                                        consent={"recording": True, "tests_on_this_computer": True, **consent})
        (other / "recordings.json").write_text(json.dumps(listing), encoding="utf-8")
        with pytest.raises(banked.BadList):
            banked.load_list(other)


def test_ruling_33_the_cut_command_writes_voices_and_counts_and_never_where_recordings_are_kept(bench, tmp_path):
    out, folder, said = bench["out"], bench["folder"], bench["said"]
    scripts = scripts_folder(tmp_path)
    for place in (folder / "voices", commands2.REPO / "x", tmp_path / "owner-data" / "v"):
        assert commands2.speech_voice_cut(out, folder, [scripts], place, say=said.append) == 6
    write = tmp_path / "voices"
    assert commands2.speech_voice_cut(out, folder, [scripts], write, say=said.append) == 0
    cuts = json.loads((write / "voice_cuts.json").read_text(encoding="utf-8"))["voices"]
    assert sorted(cuts) == ["voice_one", "voice_two"]
    for name, made in cuts.items():
        assert (write / made["file"]).is_file() and made["sha256"] == banked.sha256_of(write / made["file"])
        assert made["cut_of"] in ("one", "two") and "seconds_of_voice" in made and isinstance(made["thin"], bool)
        # Times and counts only: no word of the page is kept with a cut.
        assert all(set(stretch) == {"speech", "words", "start", "end"} for stretch in made["stretches"])
    assert commands2.speech_voice_cut(out, folder, [scripts], write, say=said.append) == 6       # never written over
