"""The recordings guard (Task 16, 2026-10-04): no test run may create,
change or remove a file in the owner's data/recordings.

tests/test_live.py wrote the 11 s JFK fixture over 83 files there before
tests/conftest.py pointed RECORDINGS_DIR at a session temp directory;
consultations 68 and 161 lost their audio. conftest snapshots the folder at
session start and fails the run at session end if anything moved. These
tests pin that the redirect is real and that the guard can see what it
claims to see — every check of a change runs in tmp_path, never in the
real folder.
"""

import os
import time
from pathlib import Path

import pytest

import conftest
from app import main as appmain

REPO_RECORDINGS = (Path(__file__).parent.parent / "data" / "recordings").resolve()


def test_the_app_writes_recordings_to_the_session_temp_dir():
    bound = appmain.RECORDINGS_DIR.resolve()
    assert bound == Path(conftest._RECORDINGS_TMP).resolve()
    assert bound != REPO_RECORDINGS
    assert not bound.is_relative_to(REPO_RECORDINGS.parent.parent)


def test_the_guard_watches_the_repository_folder():
    assert conftest._REPO_RECORDINGS == REPO_RECORDINGS
    on_disk = set(os.listdir(REPO_RECORDINGS)) if REPO_RECORDINGS.is_dir() else set()
    if not on_disk:
        pytest.skip("no recordings on this machine; nothing for the guard to watch")
    # The session-start snapshot holds every file — the guard is not
    # comparing an empty listing with an empty listing.
    assert set(conftest._RECORDINGS_BEFORE) == on_disk


def test_the_comparison_sees_a_created_a_rewritten_and_a_removed_file(tmp_path):
    (tmp_path / "consultation_1.wav").write_bytes(b"RIFF one")
    (tmp_path / "consultation_2.wav").write_bytes(b"RIFF two")
    before = conftest.recordings_snapshot(tmp_path)
    assert conftest.recordings_changes(before, conftest.recordings_snapshot(tmp_path)) == []

    # File timestamps are coarse (a few ms); in a real run seconds pass
    # between the snapshot and any write.
    time.sleep(0.05)
    (tmp_path / "consultation_1.wav").write_bytes(b"RIFF one")  # same bytes, rewritten
    (tmp_path / "consultation_2.wav").unlink()
    (tmp_path / "consultation_3.wav").write_bytes(b"RIFF new")

    changes = conftest.recordings_changes(before, conftest.recordings_snapshot(tmp_path))
    assert changes == ["created consultation_3.wav",
                       "removed consultation_2.wav",
                       "changed consultation_1.wav"]


def test_the_guard_fails_the_run_and_names_the_file(tmp_path):
    class Session:
        exitstatus = pytest.ExitCode.OK

    (tmp_path / "consultation_66.wav").write_bytes(b"RIFF real")
    before = conftest.recordings_snapshot(tmp_path)

    quiet = Session()
    assert conftest.apply_recordings_guard(quiet, before, tmp_path) == []
    assert quiet.exitstatus == pytest.ExitCode.OK

    time.sleep(0.05)
    (tmp_path / "consultation_66.wav").write_bytes(b"RIFF fixture")
    caught = Session()
    changes = conftest.apply_recordings_guard(caught, before, tmp_path)
    assert changes == ["changed consultation_66.wav"]
    assert caught.exitstatus == pytest.ExitCode.TESTS_FAILED


def test_an_absent_folder_is_an_empty_snapshot(tmp_path):
    assert conftest.recordings_snapshot(tmp_path / "missing") == {}
