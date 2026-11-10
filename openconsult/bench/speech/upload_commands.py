"""speech-upload, run by openconsult-bench (spec 15.9, rulings 28 and 31;
the details of 5e): the pass at Stop of a cloud service on listed
recordings, one at a time, each deleted and proven gone before the next;
the gate call with the self-test's clip; and the count at the end of what
each service still holds. Refused before any connection is opened: a
result folder in a forbidden place, a recording not listed or changed, a
voice alone, a recording whose consent does not cover the whole recording
going to that service, and no key. A delete that is not proven ends the
command at once with its own exit code, and nothing more is sent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from openconsult import words
from openconsult.bench.speech import assemblyai_upload, banked, sound, speechmatics_upload, upload
from openconsult.bench.speech.commands import REPO
from openconsult.bench.writer import Refused, ResultWriter
from openconsult.settings import keys, paths
from openconsult.speech import selftest

SERVICES = {"speechmatics": speechmatics_upload, "assemblyai": assemblyai_upload}
GATE_NAME, GATE_FILE = "gate", "clip-0.wav"
NOT_PROVEN = 10        # the exit code of a delete that failed or was not proven


def file_name_for(index: int) -> str:
    """A plain word and a number: never a script, a person, a place or a
    date, because a service may handle file names outside the EU."""
    return f"sound-{index}.wav"


def _key(service, key_folder: Path, say: Callable) -> str | None:
    key = keys.read_key(service.KEY_NAME, Path(key_folder), {})
    if key is None:
        say(words.BENCH_UPLOAD_NO_KEY.format(service=service.TITLE, name=service.KEY_NAME))
    return key


def _said(say: Callable, service, name: str, result: dict) -> None:
    up = result["upload"]
    if up["seconds_to_result"] is not None and up["reply"] is not None:
        say(words.BENCH_UPLOAD_RESULT.format(service=service.TITLE, seconds=up["seconds_to_result"], counted=up["counted_s"]))
    if result["failure"]:
        say(words.BENCH_FAILED.format(arm=service.ARM, name=name, at=result["failure"]["at"], detail=result["failure"]["detail"]))
    if up["gone"]:
        say(words.BENCH_UPLOAD_GONE.format(service=service.TITLE, answer=up["proof"]))
    else:
        say(words.BENCH_UPLOAD_NOT_PROVEN.format(name=name, service=service.TITLE, answer=up["proof"]))


def speech_upload(service_name: str, key_folder: Path, out: Path, recordings_folder: Path | None = None,
                  names: list[str] | None = None, gate: bool = False, say: Callable = print,
                  send: Callable | None = None, **timing) -> int:
    service = SERVICES[service_name]
    listed: list[banked.Recording] = []
    if not gate:
        try:
            listed = banked.load_list(Path(recordings_folder))
            chosen = [banked.named(listed, n) for n in names] if names else [r for r in listed if not r.voice_only]
        except banked.BadList as bad:
            say(words.BENCH_BAD_LIST.format(reason=bad))
            return 3
        except banked.NotListed as missing:
            say(words.BENCH_NOT_LISTED.format(name=missing))
            return 3
    try:
        writer = ResultWriter(out, forbidden=(REPO, paths.default_data_folder(), Path(key_folder), *banked.folders_of(listed)))
    except Refused as refused:
        say(words.BENCH_FOLDER_REFUSED.format(place=str(refused).split("under ")[-1]))
        return 6
    if gate:
        return _gate(service, key_folder, writer, say, send, timing)
    code = 0
    for recording in chosen:
        if recording.voice_only:
            say(words.BENCH_VOICE_ONLY_REFUSED.format(name=recording.name))
            return 3
        if writer.exists(service.ARM, recording.name):
            say(words.BENCH_RESULT_EXISTS.format(arm=service.ARM, name=recording.name))
            continue
        if not recording.cloud_whole_allowed(service.NAME):
            say(words.BENCH_NO_WHOLE_CONSENT.format(name=recording.name, service=service.TITLE))
            code = code or 4
            continue
        key = _key(service, key_folder, say)
        if key is None:
            return 2
        try:
            banked.check_file(recording)
            pcm = sound.read_wav(recording.path, recording.rate)
        except banked.RecordingChanged as changed:
            say(words.BENCH_RECORDING_CHANGED.format(name=recording.name, reason=changed))
            return 3
        index = 1 + [r.name for r in listed].index(recording.name)
        say(words.BENCH_UPLOAD_SENDING.format(name=recording.name, service=service.TITLE, address=service.BASE))
        described = {"recording": recording.name, "recording_sha256": recording.sha256, "script": recording.script,
                     "script_key": recording.script_key, "script_sha256": recording.script_sha256,
                     "speakers": recording.speakers, "machine_voices": recording.machine_voices,
                     "consent": dict(recording.consent)}
        result = upload.run_upload(service, upload.Http(service.EU_HOST, send), key, recording.path.read_bytes(),
                                   file_name_for(index), described, pcm, recording.rate, **timing)
        say(words.BENCH_RESULT_WRITTEN.format(path=writer.write(service.ARM, recording.name, result)))
        _said(say, service, recording.name, result)
        if not result["upload"]["gone"]:
            return NOT_PROVEN
        code = code or (5 if result["failure"] else 0)
    return code


def _gate(service, key_folder: Path, writer: ResultWriter, say: Callable, send, timing: dict) -> int:
    """The first act on an upload route: the self-test's clip sent whole,
    read, deleted and proven gone, before any recording is sent."""
    if writer.exists(service.ARM, GATE_NAME):
        say(words.BENCH_RESULT_EXISTS.format(arm=service.ARM, name=GATE_NAME))
        return 6
    key = _key(service, key_folder, say)
    if key is None:
        return 2
    rate, pcm = selftest.read_clip()
    say(words.BENCH_UPLOAD_SENDING.format(name="the self-test's clip", service=service.TITLE, address=service.BASE))
    described = {"recording": GATE_NAME, "recording_sha256": selftest.CLIP_SHA256, "script": None, "script_key": None,
                 "script_sha256": None, "speakers": selftest.SPEAKERS, "machine_voices": False, "consent": {}}
    timing = {"timeout_s": upload.GATE_TIMEOUT_S, **timing}
    result = upload.run_upload(service, upload.Http(service.EU_HOST, send), key, selftest.CLIP.read_bytes(), GATE_FILE,
                               described, pcm, rate, **timing)
    heard = selftest.words_of(" ".join(line["text"] for line in (result["stop"] or {}).get("lines", [])))
    result["gate"] = {"heard": selftest.in_order(list(selftest.EXPECTED), heard), "of": len(selftest.EXPECTED),
                      "needed": selftest.NEEDED}
    say(words.BENCH_RESULT_WRITTEN.format(path=writer.write(service.ARM, GATE_NAME, result)))
    _said(say, service, GATE_NAME, result)
    if not result["upload"]["gone"]:
        return NOT_PROVEN
    if result["failure"] or result["gate"]["heard"] < selftest.NEEDED:
        say(words.BENCH_UPLOAD_GATE_FAILED.format(service=service.TITLE, heard=result["gate"]["heard"], of=result["gate"]["of"]))
        return 5
    say(words.BENCH_UPLOAD_GATE_PASSED.format(service=service.TITLE))
    return 0


def speech_upload_held(service_name: str, key_folder: Path, outs: list[Path], write: Path, say: Callable = print,
                       send: Callable | None = None) -> int:
    """Each job of the given result folders asked for once more, and the
    service's own list read: what is still held, as counts and states. The
    answers are kept whole in the file written; nothing is deleted here."""
    service = SERVICES[service_name]
    write = Path(write)
    if write.exists():
        say(words.BENCH_WRITE_EXISTS.format(path=write))
        return 6
    key = _key(service, key_folder, say)
    if key is None:
        return 2
    http = upload.Http(service.EU_HOST, send)
    jobs, held = [], 0
    for out in outs:
        for (arm, name), result in sorted(ResultWriter(out).read_all().items()):
            job = (result.get("upload") or {}).get("job")
            if arm != service.ARM or not job or not job.get("id"):
                continue
            result_words = upload.words_of(" ".join(line["text"] for line in result["stop"]["lines"]))
            answers = []
            for what, answer in service.ask_again(http, key, job):
                ok, why = upload.proves_gone(answer, result_words, service.must_not_hold(job), service.lines_of)
                answers.append({"what": what, **answer.kept(), "gone": ok, "why": why})
                held += not ok
            jobs.append({"result": f"{out.name}/{name}", "id": job["id"], "answers": answers})
    listing = service.listing(http, key)
    report = {"service": service.NAME, "jobs": jobs, "still_held": held, "listing": listing.kept()}
    write.parent.mkdir(parents=True, exist_ok=True)
    write.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    say(words.BENCH_UPLOAD_HELD.format(service=service.TITLE, jobs=len(jobs), held=held, path=write))
    return NOT_PROVEN if held else 0
