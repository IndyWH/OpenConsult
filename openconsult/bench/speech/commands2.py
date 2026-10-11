"""The commands of part two of the speech bench (spec 15.9, the details of
part two of 5c): speech-voice, speech-drugs and speech-calls, run by
openconsult-bench. Each refuses before anything is fetched, started or
written: a result folder in the repo, in the owner's data folder, in the
data folder given for the workers or where recordings are kept; a list
that cannot be used; a recording whose checksum differs; a result that
exists. A failure is kept as failed and counted; nothing is tried again."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Callable

from openconsult import words
from openconsult.bench.speech import banked, voice
from openconsult.bench.speech.commands import forbidden_for
from openconsult.bench.writer import Refused, ResultWriter
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
