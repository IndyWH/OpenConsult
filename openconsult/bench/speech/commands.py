"""The three commands of the speech bench (spec 15.9, the details of 5c),
run by openconsult-bench: speech-fetch, speech-run and speech-score. Each
refuses before anything is fed or written: a result folder in the repo,
in the owner's data folder, in the data folder given for the workers or
where recordings are kept; a file not listed or whose checksum differs; a
cloud arm without consent."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Callable

import openconsult
from openconsult import words
from openconsult.bench.speech import banked, replay, sound, tables
from openconsult.bench.speech.arms import ARMS, Arm, door_for
from openconsult.bench.writer import Refused, ResultWriter
from openconsult.settings import paths
from openconsult.speech import environment

REPO = Path(openconsult.__file__).resolve().parents[1]
# Exit codes: 3 the list or a file, 4 consent, 5 a failed result, 6 a folder, 7 an environment, 8 a script.


def forbidden_for(data_folder: Path, recordings: list[banked.Recording]) -> tuple[Path, ...]:
    return (REPO, paths.default_data_folder(), Path(data_folder), *banked.folders_of(recordings))


def speech_fetch(data_folder: Path, say: Callable = print, run: Callable = subprocess.run) -> int:
    """The models of the tied pair, found or fetched with the Nemotron
    environment's Python, as install-speech finds a choice's."""
    arm = ARMS["nemotron_tied_pair"]
    if not environment.installed(data_folder, arm.environment_of):
        say(words.BENCH_ARM_NEEDS_ENVIRONMENT.format(arm=arm.name, choice=arm.environment_of.name))
        return 7
    say(words.BENCH_MODEL_FETCH.format(arm=arm.name, choice=arm.environment_of.name))
    fetched = run([str(environment.python(data_folder, arm.environment_of)), str(arm.worker_script.with_name("fetch.py"))],
                  capture_output=True, text=True)
    models = [json.loads(line) for line in (fetched.stdout or "").splitlines() if line.startswith("{")]
    for model in models:
        say(environment._model_sentence(model))
    ok = fetched.returncode == 0 and bool(models) and all(m.get("ok") for m in models)
    if not ok and not models:
        say(words.SPEECH_BUILD_FAILED.format(reason=environment._last_line(fetched.stderr)))
    return 0 if ok else 1


def speech_run(recordings_folder: Path, arm_name: str, data_folder: Path, out: Path, names: list[str] | None,
               say: Callable = print, make_door: Callable[[Arm, Path], object] = door_for,
               sleep=None, clock=None) -> int:
    arm = ARMS[arm_name]
    try:
        listed = banked.load_list(recordings_folder)
        chosen = [banked.named(listed, n) for n in names] if names else [r for r in listed if not r.voice_only]
    except banked.BadList as bad:
        say(words.BENCH_BAD_LIST.format(reason=bad))
        return 3
    except banked.NotListed as missing:
        say(words.BENCH_NOT_LISTED.format(name=missing))
        return 3
    for recording in chosen:
        if recording.voice_only:
            # The doctor's voice alone is learnt from, never fed as a consultation.
            say(words.BENCH_VOICE_ONLY_REFUSED.format(name=recording.name))
            return 3
    try:
        writer = ResultWriter(out, forbidden=forbidden_for(data_folder, listed))
    except Refused as refused:
        say(words.BENCH_FOLDER_REFUSED.format(place=str(refused).split("under ")[-1]))
        return 6
    if not environment.installed(data_folder, arm.environment_of):
        say(words.BENCH_ARM_NEEDS_ENVIRONMENT.format(arm=arm.name, choice=arm.environment_of.name))
        return 7
    extra = {k: v for k, v in (("sleep", sleep), ("clock", clock)) if v is not None}
    try:
        summary = replay.run_many(arm, chosen, lambda: make_door(arm, data_folder), writer, say=say, **extra)
    except banked.RecordingChanged as changed:
        say(words.BENCH_RECORDING_CHANGED.format(name=str(changed).split(":")[0], reason=changed))
        return 3
    except sound.BadSound as bad:
        say(words.BENCH_BAD_WAV.format(name=str(bad).split(":")[0], reason=bad))
        return 3
    return 5 if summary["failed"] else 0


def speech_score(out: Path, recordings_folder: Path, script_folders: list[Path], marks_path: Path, write: Path,
                 say: Callable = print, key_facts_path: Path | None = None, drug_list_path: Path | None = None) -> int:
    """The one command: the stored results scored and the tables written,
    never over an existing file. The marks of part one always; the tables
    of part two where its results are there, which then need the key-fact
    file and the drug list."""
    try:
        listed = banked.load_list(recordings_folder)
    except banked.BadList as bad:
        say(words.BENCH_BAD_LIST.format(reason=bad))
        return 3
    out = Path(out)
    results = ResultWriter(out).read_all()
    marks_file = json.loads(Path(marks_path).read_text(encoding="utf-8"))
    voice_results = ResultWriter(out / "voice").read_all() if (out / "voice" / "results").is_dir() else {}
    call_results = ResultWriter(out / "calls").read_all() if (out / "calls" / "results").is_dir() else {}
    part_two = bool(voice_results or call_results)
    if part_two and key_facts_path is None:
        say(words.BENCH_NEEDS_FILE.format(option="--key-facts", what="the key-fact file"))
        return 9
    if part_two and drug_list_path is None:
        say(words.BENCH_NEEDS_FILE.format(option="--drug-list", what="the drug list"))
        return 9
    try:
        scored = tables.score_all(results, listed, [Path(f) for f in script_folders], marks_file)
        text = tables.as_markdown(scored)
        if part_two:
            from openconsult.bench.speech import druglist, keyfacts, tables2
            facts, drugs = keyfacts.KeyFacts.read(key_facts_path), druglist.DrugList.read(drug_list_path)
            scored["part_two"] = tables2.score_all(results, voice_results, call_results, listed, [Path(f) for f in script_folders],
                                                   marks_file, facts, drugs)
            scored["part_two"]["kinds"] = list(facts.kinds)
            text += tables2.as_markdown(scored["part_two"])
        written = tables.write(write, scored, text)
    except tables.ScriptNotFound as missing:
        say(words.BENCH_BAD_LIST.format(reason=missing))
        return 8
    except Refused as refused:
        say(words.BENCH_WRITE_EXISTS.format(path=str(refused).split(" exists")[0]))
        return 6
    say(words.BENCH_SCORED.format(results=len(results), arms=len(scored["arms"]), folder=written[0].parent))
    if part_two:
        say(words.BENCH_SCORED_TWO.format(pages=sum(len(r["arms"]) for r in scored["part_two"]["recordings"].values()),
                                          calls=len(call_results), voice=len(voice_results)))
    return 0
