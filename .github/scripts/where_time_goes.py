"""GitHub's check, the step after the suite (spec 15.14, the details of
run 10a): where the time of the slowest tests goes. On GitHub's Windows
some tests take 13 to 26 seconds that take under a second elsewhere, and
why is not measured. This reads the times the suite wrote to its XML
file, takes the slowest tests, runs them once more, alone, and prints
for each: its set-up, its call and its tear-down; every process it
started, with the seconds the start took and the seconds until it was
waited for; and the functions that held most of the call.

It measures and mends nothing, and it always ends with 0: it can never
turn the check red. The profile sees the test's own thread alone, and a
test run alone may be quicker than in the suite; both times are shown.

usage: where_time_goes.py SUITE_XML HOW_MANY
"""

from __future__ import annotations

import cProfile
import multiprocessing.process
import pstats
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

FUNCTIONS = 12


def slowest(xml_path: Path, how_many: int) -> list[tuple[str, float]]:
    """The slowest tests of the suite's XML file, each as pytest names it, with its seconds there."""
    found = []
    for case in ET.parse(xml_path).iter("testcase"):
        parts = case.get("classname", "").split(".")
        for cut in range(len(parts), 0, -1):
            if Path(*parts[:cut]).with_suffix(".py").is_file():
                name = "::".join(["/".join(parts[:cut]) + ".py", *parts[cut:], case.get("name", "")])
                found.append((name, float(case.get("time", 0))))
                break
    return sorted(found, key=lambda pair: -pair[1])[:how_many]


class WhereTimeGoes:
    """A pytest plugin: for each test the seconds of its three phases, the processes it started and a profile of its call."""

    def __init__(self):
        self.tests: dict[str, dict] = {}
        self.now: tuple[dict, str] | None = None
        plugin, started, waited = self, subprocess.Popen.__init__, subprocess.Popen.wait
        process_start = multiprocessing.process.BaseProcess.start

        def popen(self, args, *more, **named):
            at = time.perf_counter()
            try:
                started(self, args, *more, **named)
            finally:
                words = args if isinstance(args, str) else " ".join(str(word) for word in list(args)[:4])
                self._where_time = plugin.note(words[:120], time.perf_counter() - at, at)

        def wait(self, *more, **named):
            try:
                return waited(self, *more, **named)
            finally:
                noted = getattr(self, "_where_time", None)
                if noted is not None and "ended_after_s" not in noted:
                    noted["ended_after_s"] = time.perf_counter() - noted["at"]

        def start(self):
            at = time.perf_counter()
            try:
                process_start(self)
            finally:
                plugin.note(f"multiprocessing: {self.name}", time.perf_counter() - at, at)

        subprocess.Popen.__init__, subprocess.Popen.wait, multiprocessing.process.BaseProcess.start = popen, wait, start

    def note(self, words: str, start_s: float, at: float) -> dict | None:
        if self.now is None:
            return None
        test, phase = self.now
        noted = {"phase": phase, "words": words, "start_s": start_s, "at": at}
        test["processes"].append(noted)
        return noted

    def phase(self, item, name: str):
        test = self.tests.setdefault(item.nodeid, {"phases": {}, "processes": [], "profile": None})
        self.now, at = (test, name), time.perf_counter()
        yield
        test["phases"][name] = time.perf_counter() - at
        self.now = None

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_setup(self, item):
        yield from self.phase(item, "set-up")

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_call(self, item):
        profile = cProfile.Profile()
        steps = self.phase(item, "call")
        next(steps)
        profile.enable()
        try:
            yield
        finally:
            profile.disable()
            next(steps, None)
            self.tests[item.nodeid]["profile"] = profile

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_teardown(self, item):
        yield from self.phase(item, "tear-down")


def held_most(profile: cProfile.Profile) -> list[str]:
    """The functions that held most of the call, by the seconds spent in each and in what it called."""
    stats = pstats.Stats(profile).stats
    # pytest's own frames around a test hold all of its time and say nothing: they are left out.
    own = [pair for pair in stats.items() if "_pytest" not in pair[0][0] and "pluggy" not in pair[0][0]]
    rows = sorted(own, key=lambda pair: -pair[1][3])[:FUNCTIONS]
    here = str(Path.cwd())
    return [f"    {cumulative:8.3f} s  {calls:7d} calls  {file.replace(here, '.')}:{line} {name}"
            for (file, line, name), (_, calls, _, cumulative, _) in rows]


def main(argv: list[str]) -> int:
    xml_path, how_many = Path(argv[1]), int(argv[2])
    if not xml_path.is_file():
        print(f"where the time goes: {xml_path} is not there, so nothing is measured")
        return 0
    tests = slowest(xml_path, how_many)
    in_suite = dict(tests)
    print(f"where the time goes: the {len(tests)} slowest tests of {xml_path}, run once more, alone", flush=True)
    plugin = WhereTimeGoes()
    code = pytest.main([name for name, _ in tests] + ["-q", "-p", "no:cacheprovider"], plugins=[plugin])
    print(f"\nwhere the time goes (pytest ended with {code}; this step measures and never fails the check)")
    for name, found in sorted(plugin.tests.items(), key=lambda pair: -in_suite.get(pair[0], 0)):
        phases = ", ".join(f"{phase} {found['phases'].get(phase, 0):.2f} s" for phase in ("set-up", "call", "tear-down"))
        print(f"\n{name}\n  in the suite {in_suite.get(name, 0):.2f} s; alone: {phases}")
        print(f"  processes started: {len(found['processes'])}")
        for process in found["processes"]:
            ended = f", waited for {process['ended_after_s']:.2f} s after its start" if "ended_after_s" in process else ", not waited for"
            print(f"    in the {process['phase']}: {process['words']}: {process['start_s']:.2f} s to start{ended}")
        if found["profile"] is not None:
            print(f"  the call, the {FUNCTIONS} functions that held most (seconds in each and in what it called):")
            print("\n".join(held_most(found["profile"])))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except Exception as failed:   # noqa: BLE001  (a measuring step: whatever goes wrong here must not turn the check red)
        print(f"where the time goes: stopped by {type(failed).__name__}: {failed}")
        sys.exit(0)
