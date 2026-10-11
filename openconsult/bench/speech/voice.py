"""The voice method, the bench's side (spec 15.9, ruling 4; D53; the details
of part two of 5c). The worker in the WhisperX environment learns the
doctor's voice from the listed recording that holds it alone, and gives
each line of a page its distance from that voice. The reading of a line,
doctor, not doctor or unsure, is made here from the distance and the two
figures, so it can be made again from the stored distances when the
figures are set again (5e). Where the list names no recording of the
doctor's voice, the method is not run and the result says so."""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
from typing import Callable

from openconsult import words
from openconsult.bench.speech import banked, model_lines, pages, sound
from openconsult.bench.writer import ResultWriter
from openconsult.speech import environment
from openconsult.speech.choices import WHISPERX_PYANNOTE
from openconsult.speech.loudness import QUIET_DBFS, WINDOW_S
from openconsult.speech.worker import Worker, WorkerGone

WORKER = Path(__file__).resolve().parent / "voice" / "worker.py"
# The figure by which the WhisperX choice's own speaker step tells two
# voices apart: params.clustering.threshold of pyannote/speaker-diarization-3.1
# at the pinned revision 84fd2591 (its config.yaml: cosine distance, centroid
# linkage). A line's distance from the doctor's voice is measured the same way.
CLUSTER_THRESHOLD = 0.7045654963945799
# A band on each side of it, because one line's embedding is noisier than
# the centroid of many segments. A draft (the plan of part two): the result
# keeps every distance, so the band can be set again from the stored results.
BAND = 0.1
DOCTOR_DISTANCE_AT = CLUSTER_THRESHOLD - BAND          # below this: the doctor
NOT_DOCTOR_DISTANCE_AT = CLUSTER_THRESHOLD + BAND      # above this: not the doctor
# A line shorter than this by its own times is unsure whatever its distance.
LEAST_LINE_S = 1.0
# The worker scores a whole page in one request: the models' own time.
REQUEST_TIMEOUT_S = 600.0
# The pages the method reads: the page at Stop of every arm but the one that
# shares its pass at Stop with WhisperX (ruling 3; the details).
SHARES_STOP = ("whisperx_v1_line",)
NOT_RUN = "the list names no recording of the doctor's voice alone"


def reading_of(distance: float | None, length_s: float) -> str:
    if distance is None or length_s < LEAST_LINE_S:
        return "unsure"
    if distance < DOCTOR_DISTANCE_AT:
        return "doctor"
    if distance > NOT_DOCTOR_DISTANCE_AT:
        return "not_doctor"
    return "unsure"


def figures() -> dict:
    return {"cluster_threshold": CLUSTER_THRESHOLD, "band": BAND, "doctor_distance_at": DOCTOR_DISTANCE_AT,
            "not_doctor_distance_at": NOT_DOCTOR_DISTANCE_AT, "least_line_s": LEAST_LINE_S}


def make_worker(data_folder: Path, environ=os.environ) -> Worker:
    """The voice worker, run by the WhisperX environment's Python with the
    environment every worker gets (the hub's network off)."""
    command = [str(environment.python(data_folder, WHISPERX_PYANNOTE)), str(WORKER)]
    log = environment.log_path(data_folder, WHISPERX_PYANNOTE).with_name("voice.log")
    return Worker(command, log_path=log, env=environment.worker_env(environ))


class VoiceRun:
    """One command's worker, started at the first page that needs it, with
    the voice it has learnt."""

    def __init__(self, start: Callable[[], Worker]):
        self._start = start
        self.worker: Worker | None = None
        self.learnt: str | None = None
        self.info: dict = {}

    def _ready(self) -> Worker:
        if self.worker is None:
            self.worker = self._start()
            self.worker.start()
            if not self.worker.wait_ready():
                raise WorkerGone(self.worker.kind or "died", self.worker.reason or words.WORKER_NOT_READY)
            self.info = dict(self.worker.info)
        return self.worker

    def learn(self, recording: banked.Recording) -> dict:
        worker = self._ready()
        pcm = sound.read_wav(recording.path, recording.rate)
        reply = worker.request({"type": "learn", "rate": recording.rate, "quiet_dbfs": QUIET_DBFS, "window_s": WINDOW_S},
                               pcm, timeout_s=REQUEST_TIMEOUT_S)
        if reply.get("type") != "learnt":
            raise WorkerGone("worker_error", str(reply.get("message") or words.WORKER_SAID_NOTHING))
        self.learnt = recording.name
        return {k: reply.get(k) for k in ("seconds", "seconds_used", "seconds_trimmed")}

    def score(self, recording: banked.Recording, lines: list[dict]) -> dict:
        worker = self._ready()
        pcm = sound.read_wav(recording.path, recording.rate)
        asked = [{"n": line["n"], "start": line["start"], "end": line["end"]} for line in lines]
        reply = worker.request({"type": "score", "rate": recording.rate, "lines": asked}, pcm, timeout_s=REQUEST_TIMEOUT_S)
        if reply.get("type") != "scored":
            raise WorkerGone("worker_error", str(reply.get("message") or words.WORKER_SAID_NOTHING))
        return reply

    def stop(self) -> None:
        if self.worker is not None:
            self.worker.stop()


def result_of(arm: str, recording: banked.Recording, voice: banked.Recording | None, lines: list[dict],
              scored: dict | None, learnt: dict | None, info: dict, now: dt.datetime, not_run: str | None = None,
              failure: dict | None = None) -> dict:
    """The result file: the distance of every line and its reading, the
    figures, and the stamp of the model."""
    by_n = {entry["n"]: entry for entry in (scored or {}).get("lines", [])}
    rows = []
    for line in lines:
        distance = by_n.get(line["n"], {}).get("distance")
        rows.append({"n": line["n"], "start": line["start"], "end": line["end"], "length_s": round(line["end"] - line["start"], 3),
                     "words": len(line["text"].split()), "distance": distance,
                     "reading": reading_of(distance, line["end"] - line["start"]),
                     "seconds": by_n.get(line["n"], {}).get("seconds")})
    return {"arm": arm, "recording": recording.name, "recording_sha256": recording.sha256,
            "doctor_voice": voice.name if voice else None, "doctor_voice_sha256": voice.sha256 if voice else None,
            "model": info.get("models"), "versions": info.get("versions"), "device": info.get("device"),
            "least_s": info.get("least_s"), "figures": figures(), "learnt": learnt, "lines": rows,
            "seconds": (scored or {}).get("seconds"), "started_at": now.isoformat(timespec="seconds"),
            "not_run": not_run, "failure": failure}


def pages_to_run(results: dict, names: list[str] | None, arms: list[str] | None) -> list[tuple[str, str, dict]]:
    found = []
    for (arm, name), result in sorted(results.items()):
        if arm in SHARES_STOP or result.get("failure") or (names and name not in names) or (arms and arm not in arms):
            continue
        found.append((arm, name, result))
    return found


def run_pages(listed: list[banked.Recording], chosen: list[tuple[str, str, dict]], writer: ResultWriter,
              run: VoiceRun, say: Callable = print, now: Callable = dt.datetime.now) -> dict:
    """Each page: the voice learnt once per listed voice, the lines scored,
    the result written; the plain not-run record where the list names no
    voice. A failure is kept as failed and the next page runs."""
    done, kept, not_run, failed = [], [], [], []
    for arm, name, result in chosen:
        if writer.exists(arm, name):
            say(words.BENCH_RESULT_EXISTS.format(arm=arm, name=name))
            kept.append((arm, name))
            continue
        recording = banked.named(listed, name)
        lines = model_lines.lines_of(pages.stop_pieces(result))
        if recording.doctor_voice is None:
            say(words.BENCH_VOICE_NOT_RUN.format(name=name))
            writer.write(arm, name, result_of(arm, recording, None, lines, None, None, {}, now(), not_run=NOT_RUN))
            not_run.append((arm, name))
            continue
        voice = banked.named(listed, recording.doctor_voice)
        try:
            banked.check_file(voice)
            banked.check_file(recording)
            learnt = None
            if run.learnt != voice.name:
                say(words.BENCH_VOICE_LEARNING.format(name=voice.name))
                learnt = run.learn(voice)
            say(words.BENCH_VOICE_SCORING.format(arm=arm, name=name))
            scored = run.score(recording, lines)
            writer.write(arm, name, result_of(arm, recording, voice, lines, scored, learnt, run.info, now()))
            done.append((arm, name))
        except WorkerGone as gone:
            say(words.BENCH_FAILED.format(arm=arm, name=name, at="voice", detail=gone.detail))
            writer.write(arm, name, result_of(arm, recording, voice, lines, None, None, run.info, now(),
                                              failure={"failure": gone.kind, "detail": gone.detail}))
            failed.append((arm, name))
    return {"run": done, "kept": kept, "not_run": not_run, "failed": failed}
