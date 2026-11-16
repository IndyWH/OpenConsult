"""Speechmatics is the one cloud speech service a doctor can choose
(spec 15.13, ruling 28; the details of run 9b): the second service of the
bench is no choice of the app, and its worker stands under the bench.
And a worker's environment holds its own key alone (15.9, ruling 9)."""

from __future__ import annotations

from pathlib import Path

import openconsult
from openconsult.bench.speech.arms import ARMS, ASSEMBLYAI
from openconsult.settings import keys
from openconsult.speech import environment
from openconsult.speech.choices import CHOICES, SPEECHMATICS

APP = Path(openconsult.__file__).parent


def test_15_13_ruling_28_the_second_cloud_speech_service_is_the_benchs_alone_its_worker_folder_too():
    assert "assemblyai" not in CHOICES and ARMS["assemblyai"].choice is ASSEMBLYAI
    assert [name for name, choice in CHOICES.items() if choice.key] == ["speechmatics"]        # one service, one key
    assert ASSEMBLYAI.worker_folder == APP / "bench" / "speech" / "assemblyai" and (ASSEMBLYAI.worker_folder / "worker.py").is_file()
    assert not (APP / "speech" / "assemblyai").exists()                                         # nothing left in the app that nothing uses (R31)
    assert SPEECHMATICS.worker_folder == APP / "speech" / "speechmatics"
    # The bench still runs it as before: the app's own Python, its own key.
    command = environment.worker_command(Path("made-up-folder"), ASSEMBLYAI, "Linux")
    assert command[1] == str(APP / "bench" / "speech" / "assemblyai" / "worker.py")


def test_15_9_ruling_9_a_workers_environment_is_cleared_of_every_key_before_its_own_goes_in_claudes_included():
    every = {name: f"made-up-{name}" for name in keys.NAMES}
    assert set(keys.NAMES) == {"ANTHROPIC_API_KEY", "SPEECHMATICS_API_KEY", "ASSEMBLYAI_API_KEY", "DEEPINFRA_API_KEY"}
    example = keys.parse_env((APP.parent / ".env.example").read_text(encoding="utf-8"))
    assert set(example) == set(keys.NAMES)                                                      # the names the example settings hold
    env = environment.worker_env({**every, "PATH": "x"}, SPEECHMATICS.key, "made-up-own")
    assert {name: env.get(name) for name in keys.NAMES} == {"ANTHROPIC_API_KEY": None, "SPEECHMATICS_API_KEY": "made-up-own",
                                                           "ASSEMBLYAI_API_KEY": None, "DEEPINFRA_API_KEY": None}
    assert env["PATH"] == "x"
    assert not any(name in environment.worker_env(every) for name in keys.NAMES)                # a local worker holds none
