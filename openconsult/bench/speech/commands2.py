"""The commands of part two of the speech bench (spec 15.9, the details of
part two of 5c): speech-voice, speech-drugs and speech-calls, run by
openconsult-bench. Each refuses before anything is fetched, started or
written: a result folder in the repo, in the owner's data folder, in the
data folder given for the workers or where recordings are kept; a list
that cannot be used; a recording whose checksum differs; a result that
exists. A failure is kept as failed and counted; nothing is tried again."""

from __future__ import annotations

import datetime as dt
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

from openconsult import words
from openconsult.bench.speech import banked, calls, druglist, tables, voice
from openconsult.bench.speech.commands import REPO, forbidden_for
from openconsult.settings import paths
from openconsult.bench.writer import Refused, ResultWriter
from openconsult.db import open_database
from openconsult.llm.door import Door
from openconsult.llm.ollama import DEFAULT_ADDRESS, OllamaEngine
from openconsult.llm.profile import GEMMA_4_QAT
from openconsult.llm.record import ModelCalls
from openconsult.speech import environment
from openconsult.speech.choices import WHISPERX_PYANNOTE

# Exit codes, as part one's: 3 the list or a file, 4 consent or a voice not marked, 5 a failed result,
# 6 a folder, 7 an environment.


def speech_voice(out: Path, recordings_folder: Path, data_folder: Path, names: list[str] | None,
                 arms: list[str] | None, say: Callable = print, make_worker: Callable | None = None,
                 now: Callable = dt.datetime.now) -> int:
    """The voice method on the stored pages at Stop under out/results; the
    results under out/voice."""
    try:
        listed = banked.load_list(recordings_folder)
    except banked.BadList as bad:
        say(words.BENCH_BAD_LIST.format(reason=bad))
        return 3
    try:
        writer = ResultWriter(Path(out) / "voice", forbidden=forbidden_for(data_folder, listed))
    except Refused as refused:
        say(words.BENCH_FOLDER_REFUSED.format(place=str(refused).split("under ")[-1]))
        return 6
    chosen = voice.pages_to_run(ResultWriter(out).read_all(), names, arms)
    needs_worker = False
    try:
        for arm, name, _ in chosen:
            recording = banked.named(listed, name)
            if recording.doctor_voice is None or writer.exists(arm, name):
                continue
            heard = banked.named(listed, recording.doctor_voice)
            if not heard.voice_only:
                say(words.BENCH_VOICE_NEEDS_VOICE_ONLY.format(name=name, voice=heard.name))
                return 4
            needs_worker = True
    except banked.NotListed as missing:
        say(words.BENCH_NOT_LISTED.format(name=missing))
        return 3
    if needs_worker and not environment.installed(data_folder, WHISPERX_PYANNOTE):
        say(words.BENCH_ARM_NEEDS_ENVIRONMENT.format(arm="the voice method", choice=WHISPERX_PYANNOTE.name))
        return 7
    start = make_worker or voice.make_worker
    run = voice.VoiceRun(lambda: start(data_folder))
    try:
        summary = voice.run_pages(listed, chosen, writer, run, say=say, now=now)
    except (banked.RecordingChanged, banked.NotListed) as changed:
        say(words.BENCH_RECORDING_CHANGED.format(name=str(changed).split(":")[0], reason=changed))
        return 3
    finally:
        run.stop()
    say(words.BENCH_VOICE_DONE.format(run=len(summary["run"]), not_run=len(summary["not_run"]),
                                      failed=len(summary["failed"]), kept=len(summary["kept"])))
    return 5 if summary["failed"] else 0


def speech_drugs(month: str, url: str, out: Path, say: Callable = print,
                 urlopen: Callable = urllib.request.urlopen, recordings_folder: Path | None = None,
                 data_folder: Path | None = None) -> int:
    """One month of the drug file fetched to out, and the list made from it;
    neither over a file that exists. The one fetch from outside in part two.
    With a recordings folder given, its list's folders are refused too, and
    with a data folder given, that folder."""
    out = Path(out)
    forbidden = [REPO, paths.default_data_folder()] + ([Path(data_folder)] if data_folder else [])
    if recordings_folder is not None:
        try:
            forbidden += banked.folders_of(banked.load_list(recordings_folder))
        except banked.BadList as bad:
            say(words.BENCH_BAD_LIST.format(reason=bad))
            return 3
    try:
        ResultWriter(out, forbidden=forbidden)     # a check of the folder only
    except Refused as refused:
        say(words.BENCH_FOLDER_REFUSED.format(place=str(refused).split("under ")[-1]))
        return 6
    target, listing = out / f"pca_{month}.csv", out / "drug_list.json"
    for existing in (target, listing):
        if existing.exists():
            say(words.BENCH_WRITE_EXISTS.format(path=existing))
            return 6
    say(words.BENCH_DRUGS_FETCHING.format(month=month, url=url))
    try:
        fetched = druglist.fetch(url, target, urlopen=urlopen)
    except (OSError, urllib.error.URLError, ValueError) as failed:
        say(words.BENCH_DRUGS_BAD_FILE.format(reason=failed))
        return 3
    say(words.BENCH_DRUGS_FETCHED.format(size=environment.plain_size(fetched["bytes"]), sha256=fetched["sha256"], path=target))
    try:
        listed = druglist.make_list(target, month)
    except (druglist.BadFile, UnicodeDecodeError, csv_error()) as bad:
        say(words.BENCH_DRUGS_BAD_FILE.format(reason=bad))
        return 3
    druglist.write_list(listing, listed)
    say(words.BENCH_DRUGS_MADE.format(names=listed["names_count"], rows=listed["rows"], month=month, path=listing))
    return 0


def csv_error():
    import csv
    return csv.Error


def speech_calls(out: Path, recordings_folder: Path, script_folders: list[Path], job: str, round_n: int | None,
                 data_folder: Path | None = None, names: list[str] | None = None, arms: list[str] | None = None,
                 engine_address: str = DEFAULT_ADDRESS, say: Callable = print,
                 make_door: Callable[[Path], Door] | None = None, now: Callable = dt.datetime.now) -> int:
    """The calls of one job (and round) on the stored pages under out/results;
    the results under out/calls, the record in out/calls/calls.db."""
    if job not in calls.JOB_KINDS:
        say(words.BENCH_BAD_JOB.format(job=job, jobs=", ".join(calls.JOB_KINDS)))
        return 2
    try:
        listed = banked.load_list(recordings_folder)
    except banked.BadList as bad:
        say(words.BENCH_BAD_LIST.format(reason=bad))
        return 3
    out = Path(out)
    try:
        writer = ResultWriter(out / "calls", forbidden=forbidden_for(data_folder or out, listed))
    except Refused as refused:
        say(words.BENCH_FOLDER_REFUSED.format(place=str(refused).split("under ")[-1]))
        return 6
    results = ResultWriter(out).read_all()
    (out / "calls").mkdir(parents=True, exist_ok=True)
    door = make_door(out / "calls") if make_door else Door(OllamaEngine(engine_address),
                                                          ModelCalls(open_database(out / "calls" / "calls.db")), GEMMA_4_QAT)
    version, digest = door.identity()
    if version is None or digest is None:
        say(words.BENCH_ENGINE_ABSENT.format(address=engine_address, model=door.profile.tag))
        return 2
    say(words.BENCH_ENGINE_FOUND.format(version=version, model=door.profile.tag, digest=digest))
    try:
        summary = calls.run_calls(door, job, round_n, listed, results, [Path(f) for f in script_folders], writer,
                                  names, arms, say=say, now=now)
    except (banked.NotListed, banked.RecordingChanged) as missing:
        say(words.BENCH_NOT_LISTED.format(name=missing))
        return 3
    except tables.ScriptNotFound as missing:
        say(words.BENCH_BAD_LIST.format(reason=missing))
        return 8
    say(words.BENCH_CALLS_DONE.format(made=len(summary["run"]) + len(summary["failed"]), failed=len(summary["failed"]),
                                      kept=len(summary["kept"])))
    return 5 if summary["failed"] else 0
