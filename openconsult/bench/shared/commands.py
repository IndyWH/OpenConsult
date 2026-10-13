"""The commands of the test of 5d (spec 15.9, the details of 5d), run by
openconsult-bench: shared-install, shared-search, shared-index,
shared-watch and shared-judge. Each refuses, before anything is loaded
or written, a results folder in the repo, in the owner's data folder, in
the data folder it was given for its workers or where recordings are
kept (R18; V1_LESSONS 9.4), and never writes over a result. The driver,
the starts of the engines and the sampler are private files outside the
repo; these commands are what they run."""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable, Mapping

import openconsult
from openconsult import words
from openconsult.bench.shared import embed, judge, pieces, runner, tables, watch
from openconsult.bench.shared.searches import read_lists
from openconsult.bench.writer import Refused, ResultWriter
from openconsult.llm.ollama import DEFAULT_ADDRESS
from openconsult.settings import paths
from openconsult.speech import environment

REPO = Path(openconsult.__file__).resolve().parents[1]
PYTHON = environment.PYTHON
# Exit codes: 6 a folder refused or a result written over, 7 an environment or a worker, 8 a fetch.


def forbidden_for(data_folder: Path | None, recordings: Path | None) -> tuple[Path, ...]:
    found = [REPO, paths.default_data_folder()]
    if data_folder is not None:
        found.append(Path(data_folder))
    if recordings is not None:
        found.append(Path(recordings))
    return tuple(found)


def _check_out(out: Path, data_folder: Path | None, recordings: Path | None, say: Callable) -> bool:
    try:
        ResultWriter(out, forbidden=forbidden_for(data_folder, recordings))
    except Refused as refused:
        say(words.BENCH_FOLDER_REFUSED.format(place=str(refused).split("under ")[-1]))
        return False
    return True


def _write_once(path: Path, data: dict, say: Callable) -> bool:
    path = Path(path)
    if path.exists():
        say(words.BENCH_WRITE_EXISTS.format(path=path))
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    say(words.BENCH_RESULT_WRITTEN.format(path=path))
    return True


# --------------------------------------------------------------- install

def shared_install(data_folder: Path, say: Callable = print, run: Callable = subprocess.run,
                   which: Callable = shutil.which, environ: Mapping[str, str] = os.environ) -> int:
    """The environment of the EmbeddingGemma 2 worker from the lock file,
    then the one fetch of the model, with no token, into the data folder."""
    uv = which(environment.UV)
    if uv is None:
        say(words.UV_MISSING)
        return 7
    target = embed.venv(data_folder)
    target.parent.mkdir(parents=True, exist_ok=True)
    say(words.EMBED_BUILDING.format(folder=target.parent))
    done = run([uv, "sync", "--locked", "--project", str(embed.WORKER_FOLDER), "--python", PYTHON],
               env={**environ, "UV_PROJECT_ENVIRONMENT": str(target)}, capture_output=True, text=True)
    if done.returncode != 0:
        say(words.EMBED_BUILD_FAILED.format(reason=environment._last_line(done.stderr) or environment._last_line(done.stdout)))
        return 7
    say(words.EMBED_BUILT if "Installed" in (done.stderr or "") else words.EMBED_ALREADY_BUILT)
    model = embed.model_folder(data_folder)
    say(words.EMBED_FETCHING.format(revision="pinned", folder=model))
    env = {k: v for k, v in environ.items() if k not in environment.KEY_NAMES and k != "HF_HUB_OFFLINE"}
    env.update(HF_HUB_DISABLE_IMPLICIT_TOKEN="1", HF_HOME=str(embed.folder(data_folder) / "hub"))
    fetched = run([str(embed.python(data_folder)), str(embed.WORKER_FOLDER / "fetch.py"), "--folder", str(model)],
                  env=env, capture_output=True, text=True)
    reports = [json.loads(line) for line in (fetched.stdout or "").splitlines() if line.startswith("{")]
    if not reports:
        say(words.EMBED_FETCH_FAILED.format(reason=environment._last_line(fetched.stderr) or f"exit code {fetched.returncode}"))
        return 8
    report = reports[-1]
    if not report["ok"]:
        say(words.EMBED_GATED if "account" in (report["error"] or "") else words.EMBED_FETCH_FAILED.format(reason=report["error"]))
        return 8
    size = environment.plain_size(int(report["bytes"]))
    say((words.EMBED_FETCHED if report["fetched"] else words.EMBED_FOUND).format(revision=report["revision"], size=size))
    return 0


# --------------------------------------------------------------- search

def embedder_for(embedding: str, where: str, data_folder: Path | None, service: str, say: Callable):
    """The embedder a setup names, started; or None with the reason said."""
    if embedding == "first":
        return embed.OllamaEmbedder(where, service)
    if data_folder is None or not embed.installed(data_folder):
        say(words.EMBED_NOT_INSTALLED.format(folder=embed.folder(data_folder) if data_folder else "(no data folder)"))
        return None
    worker = embed.WorkerEmbedder(where, data_folder)
    reason = worker.start()
    if reason is not None:
        say(words.EMBED_WORKER_FAILED.format(reason=reason))
        worker.close()
        return None
    info = worker.info()
    say(words.EMBED_WORKER_SAYS.format(device=info.get("device"), dtype=info.get("dtype"), model=info.get("model"),
                                       revision=info.get("revision")))
    return worker


def _until(path: Path | None) -> Callable[[], bool] | None:
    return (lambda: Path(path).exists()) if path else None


def _placed(embedder, embedding: str, where: str, out: Path, say: Callable, wall: Callable) -> bool:
    """One call with the first name, so the model is placed where the
    setup asked; what it says of itself goes to placed.json. Not a search."""
    found = embedder.embed([runner.search_text(read_lists()[0][0])])
    placed = {"embedding": embedding, "where": where, "ok": found.ok, "error": found.error,
              "wall_s": round(found.wall_s, 4), "info": embedder.info(), "at_epoch": wall()}
    say(words.EMBED_PLACED.format(embedding=embedding, where=where, info=json.dumps(placed["info"], sort_keys=True)))
    return _write_once(out / "placed.json", placed, say) and found.ok


def _wait_for_feed(after: Path, delay_s: float, sleep: Callable, wall: Callable, limit_s: float = 900.0) -> float | None:
    """Wait for the file the speech replay writes when its feed begins,
    then until delay_s after the moment it names; None if it never came."""
    started = wall()
    while not Path(after).exists():
        if wall() - started > limit_s:
            return None
        sleep(0.2)
    t0 = json.loads(Path(after).read_text(encoding="utf-8"))["t0_epoch"]
    while wall() < t0 + delay_s:
        sleep(min(0.05, max(0.0, t0 + delay_s - wall())))
    return t0


def shared_search(out: Path, embedding: str, where: str, data_folder: Path | None = None, service: str = DEFAULT_ADDRESS,
                  every_s: float = runner.EVERY_S, searches: int | None = None, until: Path | None = None,
                  load_only: bool = False, recordings: Path | None = None, say: Callable = print,
                  make_embedder: Callable = embedder_for, sleep=None, clock=None, wall=None,
                  after: Path | None = None, delay_s: float = 15.0) -> int:
    """The searches of a setup or a base line. With --after, the model is
    placed first, then the searches begin delay_s after the feed began,
    which is the moment the driver starts the chains (the details of 5d)."""
    out = Path(out)
    if not _check_out(out, data_folder, recordings, say):
        return 6
    target = out / ("placed.json" if load_only else "searches.json")
    if target.exists():
        say(words.BENCH_WRITE_EXISTS.format(path=target))
        return 6
    embedder = make_embedder(embedding, where, data_folder, service, say)
    if embedder is None:
        return 7
    try:
        if load_only:
            return 0 if _placed(embedder, embedding, where, out, say, wall or dt.datetime.now().timestamp) else 7
        if after is not None:
            _placed(embedder, embedding, where, out, say, wall or dt.datetime.now().timestamp)
            if _wait_for_feed(after, delay_s, sleep or time.sleep, wall or time.time) is None:
                say(words.EMBED_NO_FEED.format(file=after))
                return 7
        extra = {k: v for k, v in (("sleep", sleep), ("clock", clock), ("wall", wall)) if v is not None}
        found = runner.run_searches(embedder, read_lists(), every_s=every_s, limit=searches, until=_until(until),
                                    say=lambda s: say(words.EMBED_SEARCH.format(
                                        embedding=embedding, where=where, n=s["k"], names=len(s["names"]), seconds=s["seconds"])
                                        + (" " + words.EMBED_LATE.format(n=s["k"], late=s["late_s"]) if s["late"] else "")
                                        + (" " + words.EMBED_EMPTY.format(n=s["k"]) if s["empty"] else "")
                                        + (" " + words.EMBED_FAILED.format(n=s["k"], reason=s["error"]) if not s["ok"] else "")),
                                    **extra)
    finally:
        embedder.close()
    return 0 if _write_once(target, found, say) else 6


def shared_index(out: Path, embedding: str, where: str, data_folder: Path | None = None, service: str = DEFAULT_ADDRESS,
                 recordings: Path | None = None, say: Callable = print, make_embedder: Callable = embedder_for,
                 sources: list[Path] | None = None, allowed: tuple[Path, Path] = (pieces.LESSONS, pieces.CASES)) -> int:
    out = Path(out)
    if not _check_out(out, data_folder, recordings, say):
        return 6
    if (out / "index.json").exists():
        say(words.BENCH_WRITE_EXISTS.format(path=out / "index.json"))
        return 6
    cut, used = pieces.cut(sources or pieces.public_files(*allowed), lessons=allowed[0], cases=allowed[1])
    embedder = make_embedder(embedding, where, data_folder, service, say)
    if embedder is None:
        return 7
    try:
        found = runner.run_index(embedder, cut, pieces.BATCH)
    finally:
        embedder.close()
    found["files"] = used
    say(words.EMBED_INDEX.format(pieces=len(cut), words=pieces.WORDS, files=len(used), batch=pieces.BATCH, seconds=found["seconds"]))
    return 0 if _write_once(out / "index.json", found, say) else 6


# ---------------------------------------------------------------- watch

def shared_watch(out: Path, until: Path, service: str = DEFAULT_ADDRESS, private: str | None = None,
                 vllm: str | None = None, every_s: float = watch.EVERY_S, data_folder: Path | None = None,
                 recordings: Path | None = None, say: Callable = print, readers: dict | None = None,
                 sleep=None, clock=None, wall=None) -> int:
    out = Path(out)
    if not _check_out(out, data_folder, recordings, say):
        return 6
    if (out / "watch.json").exists():
        say(words.BENCH_WRITE_EXISTS.format(path=out / "watch.json"))
        return 6
    if readers is None:
        readers = {"service": lambda: watch.read_ollama(service), "card": watch.read_card}
        if private:
            readers["private"] = lambda: watch.read_ollama(private)
        if vllm:
            readers["vllm"] = lambda: watch.read_vllm(vllm)
    say(words.EMBED_WATCHING.format(engine="vLLM" if vllm else "Ollama", every=every_s, file=until))
    extra = {k: v for k, v in (("sleep", sleep), ("clock", clock), ("wall", wall)) if v is not None}
    found = watch.watch(readers, lambda: Path(until).exists(), every_s=every_s, **extra)
    say(words.EMBED_WATCHED.format(readings=len(found["readings"]), path=out / "watch.json"))
    return 0 if _write_once(out / "watch.json", found, say) else 6


# ---------------------------------------------------------------- judge

def read_sampler(card: Path | None, apps: Path | None) -> dict | None:
    """The sampler's two files, as the judge reads them: each sample with
    its moment on the machine's clock. nvidia-smi writes its own local
    time stamp; the figures are MiB."""
    if card is None:
        return None
    found = {"samples": [], "programs": []}
    for line in Path(card).read_text(encoding="utf-8").splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 3 and parts[1].isdigit():
            found["samples"].append({"epoch": _stamp(parts[0]), "used": int(parts[1]), "total": int(parts[2])})
    for line in Path(apps).read_text(encoding="utf-8").splitlines() if apps else []:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 4 and parts[1].isdigit():
            found["programs"].append({"epoch": _stamp(parts[0]), "pid": int(parts[1]), "name": ",".join(parts[2:-1]),
                                      "mib": int(parts[-1]) if parts[-1].isdigit() else None})
    return found


def _stamp(text: str) -> float:
    for form in ("%Y/%m/%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            return dt.datetime.strptime(text, form).timestamp()
        except ValueError:
            continue
    return float(text)


def wayround_asked(found: dict) -> list[str]:
    """The engines on which a setup with the WhisperX choice did not work."""
    engines = sorted({s["way"].split("-")[0] for s in found["setups"] if s["speech"] == "whisperx" and s["works"] is False})
    return engines


def shared_judge(run: Path, write: Path | None, card: Path | None = None, apps: Path | None = None,
                 ask_wayround: bool = False, say: Callable = print, data_folder: Path | None = None,
                 recordings: Path | None = None) -> int:
    found = judge.judge_run(Path(run), read_sampler(card, apps))
    if ask_wayround:
        for engine in wayround_asked(found):
            say(engine)
        return 0
    if write is None:
        say(words.EMBED_JUDGE_NEEDS_WRITE)
        return 2
    if not _check_out(Path(write), data_folder, recordings, say):
        return 6
    try:
        written = tables.write(Path(write), found)
    except Refused as refused:
        say(words.BENCH_WRITE_EXISTS.format(path=str(refused).split(" exists")[0]))
        return 6
    say(words.EMBED_JUDGED.format(setups=len(found["setups"]), base=sum(1 for v in found["base_before"]["lm"].values() if v is not None)
                                  + sum(1 for v in found["base_after"]["lm"].values() if v is not None),
                                  wayround=len(found["wayrounds"]), folder=written[0].parent))
    return 0
