"""The pass at Stop of a cloud service, the bench's alone (spec 15.9,
rulings 3, 9, 28 and 31; the details of 5e). A made-up service stands for
each upload service inside the suite: no connection is opened, and every
key, word and id is made up. What a service hears is never asserted."""

import json
from pathlib import Path

import pytest

import openconsult
from openconsult import words
from openconsult.bench.speech import assemblyai_upload, speechmatics_upload, upload, upload_commands
from openconsult.bench.speech.arms import ARMS
from openconsult.bench.speech.upload import Answer, Http
from openconsult.bench.writer import ResultWriter
from openconsult.settings import paths
from openconsult.speech.choices import CHOICES
from tests.made_up_recordings import entry, made_sound, made_up_recordings, write_wav
from tests.made_up_upload_services import MADE_UP_KEY, WORDS, MadeUpAssemblyAI, MadeUpSpeechmatics

REPO = Path(openconsult.__file__).resolve().parents[1]
BOTH = {"recording": True, "tests_on_this_computer": True, "cloud": ["speechmatics", "assemblyai"],
        "cloud_whole": ["speechmatics", "assemblyai"]}


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds


def one(service, made, wav=b"RIFFmade-up", file_name="sound-1.wav", **more):
    clock = Clock()
    return upload.run_upload(service, Http(service.EU_HOST, made), MADE_UP_KEY, wav, file_name, {"recording": "one"},
                             made_sound(1.0), 16000, clock=clock, sleep=clock.sleep, **more)


@pytest.fixture
def bench(tmp_path, recordings_kept, monkeypatch):
    monkeypatch.setattr(paths, "default_data_folder", lambda: tmp_path / "owner-data")
    sha = write_wav(recordings_kept.folder / "three.wav", made_sound(2.0))
    folder = made_up_recordings(recordings_kept.folder, extra=[entry("three", "three.wav", sha, consent=BOTH)])
    recordings_kept.settle()
    key_folder = tmp_path / "keys"
    key_folder.mkdir()
    (key_folder / ".env").write_bytes(f"SPEECHMATICS_API_KEY={MADE_UP_KEY}\nASSEMBLYAI_API_KEY={MADE_UP_KEY}\n".encode())
    said, clock = [], Clock()

    def run(service, made, out="out", names=("three",), **more):
        return upload_commands.speech_upload(service, key_folder, tmp_path / out, folder, list(names) if names else None,
                                             say=said.append, send=made, clock=clock, sleep=clock.sleep, **more)

    return {"folder": folder, "keys": key_folder, "said": said, "run": run, "tmp": tmp_path}


def test_ruling_28_the_opening_request_to_speechmatics_byte_for_byte():
    made = MadeUpSpeechmatics()
    job, problem = speechmatics_upload.submit(Http(speechmatics_upload.EU_HOST, made), MADE_UP_KEY, b"WAVBYTES", "sound-1.wav",
                                              boundary="b0")
    sent = made.requests[0]
    assert (job, problem) == ({"id": "job-1"}, None)
    assert (sent["method"], sent["url"]) == ("POST", "https://eu1.asr.api.speechmatics.com/v2/jobs")
    assert sent["headers"] == {"Authorization": f"Bearer {MADE_UP_KEY}", "Content-Type": "multipart/form-data; boundary=b0"}
    assert sent["body"] == (
        b'--b0\r\nContent-Disposition: form-data; name="config"\r\n\r\n'
        b'{"type": "transcription", "transcription_config": {"language": "en", "model": "enhanced", '
        b'"domain": "medical", "diarization": "speaker"}}\r\n'
        b'--b0\r\nContent-Disposition: form-data; name="data_file"; filename="sound-1.wav"\r\n'
        b'Content-Type: audio/wav\r\n\r\nWAVBYTES\r\n--b0--\r\n')


def test_ruling_28_the_two_opening_requests_to_assemblyai_and_one_model_named_alone():
    made = MadeUpAssemblyAI()
    job, problem = assemblyai_upload.submit(Http(assemblyai_upload.EU_HOST, made), MADE_UP_KEY, b"WAVBYTES", "sound-1.wav")
    first, second = made.requests
    assert (first["method"], first["url"], first["body"]) == ("POST", "https://api.eu.assemblyai.com/v2/upload", b"WAVBYTES")
    assert first["headers"] == {"Authorization": MADE_UP_KEY, "Content-Type": "application/octet-stream"}
    assert (second["method"], second["url"]) == ("POST", "https://api.eu.assemblyai.com/v2/transcript")
    assert json.loads(second["body"]) == {
        "audio_url": MadeUpAssemblyAI.UPLOAD_URL, "speech_models": ["universal-3-5-pro"], "language_code": "en",
        "speaker_labels": True, "speakers_expected": 2, "domain": "medical-v1"}
    # The file's name never travels: the upload call has no place for it. The host the service names is kept as a state.
    assert all(b"sound-1" not in (r["body"] or b"") and "sound-1" not in r["url"] for r in made.requests)
    assert problem is None and job["id"] == "tr-1" and job["upload_host"] == "cdn.made-up.example"


def test_ruling_3_no_word_list_no_prompt_and_no_key_terms_go_to_either_service():
    for text in (json.dumps(speechmatics_upload.config()), json.dumps(assemblyai_upload.body_for("u"))):
        for name in ("additional_vocab", "keyterms", "word_boost", "prompt", "custom_spelling", "custom_dictionary"):
            assert name not in text
    assert speechmatics_upload.stamp()["options"]["additional_vocab"] is None
    assert assemblyai_upload.stamp()["options"]["keyterms_prompt"] is None


@pytest.mark.parametrize("url", ["https://asr.api.speechmatics.com/v2/jobs", "http://eu1.asr.api.speechmatics.com/v2/jobs",
                                 "https://us1.asr.api.speechmatics.com/v2/jobs", "https://api.assemblyai.com/v2/upload",
                                 "https://eu1.asr.api.speechmatics.com.example.org/v2/jobs",
                                 "https://eu1.asr.api.speechmatics.com:8443/v2/jobs", "https://cdn.assemblyai.com/upload/x"])
def test_ruling_9_any_other_address_is_refused_before_a_connection_is_opened(url):
    opened = []
    for service in (speechmatics_upload, assemblyai_upload):
        if service.EU_HOST in url and url.startswith("https://" + service.EU_HOST + "/"):
            continue
        with pytest.raises(upload.AddressRefused):
            Http(service.EU_HOST, lambda *a: opened.append(a)).request("GET", url, {})
    assert opened == []
    assert speechmatics_upload.BASE == "https://eu1.asr.api.speechmatics.com/v2" and assemblyai_upload.BASE == "https://api.eu.assemblyai.com/v2"


def test_ruling_9_no_redirect_is_followed_to_another_host():
    handler = upload._NoRedirect()
    assert handler.redirect_request(None, None, 302, "Found", {}, "https://elsewhere.example/") is None


@pytest.mark.parametrize("service, make", [(speechmatics_upload, MadeUpSpeechmatics), (assemblyai_upload, MadeUpAssemblyAI)])
def test_ruling_28_the_result_is_kept_then_the_job_is_deleted_and_asked_for_again(service, make):
    made = make()
    result = one(service, made)
    methods = [r["method"] for r in made.requests]
    assert methods.index("DELETE") > max(i for i, r in enumerate(made.requests) if r["method"] == "POST")
    assert methods[methods.index("DELETE") + 1:] and set(methods[methods.index("DELETE") + 1:]) == {"GET"}
    up = result["upload"]
    assert result["failure"] is None and up["gone"] is True and up["delete"]["status"] == 200
    assert up["counted_s"] == 7.0 and up["seconds_to_result"] is not None and up["reply"] is not None
    assert all(answer["gone"] for answer in up["asked_again"]) and up["asked_again"]
    # The lines are a page at Stop: the words unchanged and in order, with times and the two speakers.
    lines = result["stop"]["lines"]
    assert " ".join(line["text"] for line in lines) == WORDS and result["pieces"] == [] and result["stop"]["raw"] == []
    assert [line["speaker"] for line in lines] == (["S1", "S2"] if service is speechmatics_upload else ["A", "B"])
    assert lines[0]["start"] == 1.0 and lines[0]["end"] < lines[1]["start"] and lines[0]["confidence"] == 0.9
    assert result["arm"] == service.ARM and result["stamp"]["model"] == service.MODEL and result["loudness"]["dbfs"]
    # The key is in no part of the result (the keys).
    assert MADE_UP_KEY not in json.dumps(result)


def test_ruling_28_a_delete_that_fails_is_never_passed_over(bench):
    made = MadeUpSpeechmatics(delete_status=500)
    assert bench["run"]("speechmatics", made) == upload_commands.NOT_PROVEN
    result = ResultWriter(bench["tmp"] / "out").read("speechmatics_upload", "three")
    assert result["upload"]["gone"] is False and "500" in result["upload"]["proof"]
    assert any(line.startswith("STOP: the upload of three") for line in bench["said"])
    # Nothing more is sent: a second recording of the same command never reaches the service.
    made = MadeUpAssemblyAI(delete_status=500)
    assert bench["run"]("assemblyai", made, out="out2", names=("three", "two")) == upload_commands.NOT_PROVEN
    assert sum(1 for r in made.requests if r["url"].endswith("/upload")) == 1
    # An upload the service took with no transcript made cannot be deleted by any call: not proven.
    made = MadeUpAssemblyAI(transcript_status=500)
    result = one(assemblyai_upload, made)
    assert result["failure"]["at"] == "send" and result["upload"]["gone"] is False
    assert all(r["method"] != "DELETE" for r in made.requests)


def test_ruling_28_the_proof_that_an_upload_is_gone():
    result_words = upload.words_of(WORDS)
    body = lambda status, value: Answer(status, json.dumps(value).encode())           # noqa: E731
    assert upload.proves_gone(body(404, {}), result_words)[0] and upload.proves_gone(body(410, {}), result_words)[0]
    # An answer that still holds the words: not proven, wherever they stand.
    assert not upload.proves_gone(body(200, {"text": WORDS}), result_words)[0]
    assert not upload.proves_gone(body(200, {"a": [{"b": "x made up page y"}]}), result_words)[0]
    # Empty fields: proven. Fields replaced by the service's own words for deleted: proven.
    assert upload.proves_gone(body(200, {"text": "", "words": None}), result_words)[0]
    assert upload.proves_gone(body(200, {"text": "Deleted by user.", "audio_url": "http://deleted_by_user"}), result_words)[0]
    # The address of the uploaded file still there: not proven. An error is no proof either, nor is no answer.
    assert not upload.proves_gone(body(200, {"text": "", "audio_url": "https://cdn/x"}), result_words, "https://cdn/x")[0]
    assert not upload.proves_gone(body(500, {}), result_words)[0] and not upload.proves_gone(body(401, {}), result_words)[0]
    assert not upload.proves_gone(Answer(0, b"", "URLError"), result_words)[0]
    assert not upload.proves_gone(Answer(200, WORDS.encode()), result_words)[0]       # not JSON: read as one text
    # A service that gives each word a field of its own: read as its result is read, the words are still found.
    whole = Answer(200, json.dumps(MadeUpSpeechmatics().transcript()).encode())
    assert upload.proves_gone(whole, result_words)[0] is True and not upload.proves_gone(whole, result_words, None, speechmatics_upload.lines_of)[0]
    # Each made-up service, each way it can answer after a delete.
    for after, gone in (("gone", True), ("tombstone", True), ("words", False), ("error", False)):
        assert one(speechmatics_upload, MadeUpSpeechmatics(after_delete=after))["upload"]["gone"] is gone
    for after, gone in (("replaced", True), ("empty", True), ("gone", True), ("words", False), ("url", False)):
        assert one(assemblyai_upload, MadeUpAssemblyAI(after_delete=after))["upload"]["gone"] is gone


def test_ruling_28_another_model_in_the_reply_is_a_failed_result_and_the_job_is_still_deleted():
    for service, made in ((assemblyai_upload, MadeUpAssemblyAI(model="universal-2")),
                          (assemblyai_upload, MadeUpAssemblyAI(domain=None)),
                          (speechmatics_upload, MadeUpSpeechmatics(model="standard")),
                          (speechmatics_upload, MadeUpSpeechmatics(domain=None))):
        result = one(service, made)
        assert result["failure"]["at"] == "model" and result["upload"]["gone"] is True
        assert any(r["method"] == "DELETE" for r in made.requests)


def test_ruling_28_a_result_that_never_comes_is_failed_and_the_job_is_still_deleted():
    made = MadeUpSpeechmatics(runs=10 ** 6)
    result = one(speechmatics_upload, made, timeout_s=30.0)
    assert result["failure"]["at"] == "result" and "30 s" in result["failure"]["detail"]
    assert any(r["method"] == "DELETE" for r in made.requests) and result["upload"]["gone"] is True


def test_rulings_28_and_31_consent_for_the_whole_recording_is_held_by_code(bench):
    made = MadeUpSpeechmatics()
    # "two" may go live to both services, and its list says nothing of the whole recording: refused, nothing sent.
    assert bench["run"]("speechmatics", made, names=("two",)) == 4 and made.requests == []
    assert words.BENCH_NO_WHOLE_CONSENT.format(name="two", service="Speechmatics, whole recording") in bench["said"]
    assert bench["run"]("speechmatics", made, names=("not-listed",)) == 3 and made.requests == []
    for place in (REPO / "x", bench["tmp"] / "owner-data" / "o", bench["keys"] / "o", bench["folder"] / "o"):
        assert upload_commands.speech_upload("speechmatics", bench["keys"], place, bench["folder"], ["three"],
                                             say=bench["said"].append, send=made) == 6
    assert made.requests == []
    # No key in the key folder: said, and nothing sent.
    empty = bench["tmp"] / "no-keys"
    empty.mkdir()
    assert upload_commands.speech_upload("speechmatics", empty, bench["tmp"] / "o9", bench["folder"], ["three"],
                                         say=bench["said"].append, send=made) == 2 and made.requests == []


def test_the_keys_and_the_file_name_of_an_upload(bench):
    made = MadeUpSpeechmatics()
    assert bench["run"]("speechmatics", made) == 0
    text = (bench["tmp"] / "out" / "results" / "speechmatics_upload" / "three.json").read_text(encoding="utf-8")
    assert MADE_UP_KEY not in text and MADE_UP_KEY not in "\n".join(bench["said"])
    assert all(r["headers"]["Authorization"] == f"Bearer {MADE_UP_KEY}" for r in made.requests)
    # A plain word and a number: the recording's own name is never sent.
    assert b'filename="sound-3.wav"' in made.requests[0]["body"] and b"three" not in made.requests[0]["body"][:400]
    assert all("three" not in r["url"] for r in made.requests)
    assert upload_commands.file_name_for(1) == "sound-1.wav"
    # A result is never written over, and nothing is sent for it again.
    before = len(made.requests)
    assert bench["run"]("speechmatics", made) == 0 and len(made.requests) == before


def test_ruling_28_the_gate_call_sends_the_clip_deletes_it_and_proves_it_gone(bench):
    made = MadeUpAssemblyAI()
    code = upload_commands.speech_upload("assemblyai", bench["keys"], bench["tmp"] / "gate", gate=True,
                                         say=bench["said"].append, send=made, clock=Clock(), sleep=lambda s: None)
    result = ResultWriter(bench["tmp"] / "gate").read("assemblyai_upload", "gate")
    # The made-up service answers with made-up words, so the clip's words are not heard: deleted all the same.
    assert code == 5 and result["upload"]["gone"] is True and result["gate"]["heard"] < result["gate"]["needed"]
    assert made.requests[0]["body"][:4] == b"RIFF" and any(r["method"] == "DELETE" for r in made.requests)
    made = MadeUpAssemblyAI(after_delete="words")
    assert upload_commands.speech_upload("assemblyai", bench["keys"], bench["tmp"] / "gate2", gate=True,
                                         say=bench["said"].append, send=made, clock=Clock(), sleep=lambda s: None) == upload_commands.NOT_PROVEN


def test_ruling_28_what_a_service_still_holds_is_asked_once_more_and_counted(bench):
    made = MadeUpSpeechmatics(after_delete="tombstone")
    assert bench["run"]("speechmatics", made) == 0
    said = []
    assert upload_commands.speech_upload_held("speechmatics", bench["keys"], [bench["tmp"] / "out"], bench["tmp"] / "held.json",
                                              say=said.append, send=made) == 0
    held = json.loads((bench["tmp"] / "held.json").read_text(encoding="utf-8"))
    assert held["still_held"] == 0 and len(held["jobs"]) == 1 and held["listing"]["status"] == 200
    assert MADE_UP_KEY not in json.dumps(held)
    made.after_delete = "words"
    assert upload_commands.speech_upload_held("speechmatics", bench["keys"], [bench["tmp"] / "out"], bench["tmp"] / "held2.json",
                                              say=said.append, send=made) == upload_commands.NOT_PROVEN


def test_ruling_9_and_R31_the_app_cannot_reach_the_pass_at_stop():
    # Not a speech choice, not an arm the replay can feed, and nothing outside the bench imports it.
    for name in ("speechmatics_upload", "assemblyai_upload"):
        assert name not in CHOICES and name not in ARMS
    for path in (REPO / "openconsult").rglob("*.py"):
        if "bench" in path.relative_to(REPO).parts:
            continue
        text = path.read_text(encoding="utf-8")
        assert "upload_commands" not in text and "speechmatics_upload" not in text and "assemblyai_upload" not in text
        assert "eu1.asr.api.speechmatics.com" not in text and "api.eu.assemblyai.com" not in text
