"""The banked list (spec 13.2 item 6; 13.4 rule 3; 15.9, the details of
5c; V1_LESSONS 9.5). The bench takes its recordings from the list and
from nowhere else: never by searching a folder. For each recording the
list gives the file and its checksum, the script and its checksum, when
and how it was made, the sound's rate, the speakers, the length, how much
of the script was read, what was read differently, whether the voices are
machine voices, and what the consent covers. What is not known of an old
recording is written as not known. Consent is held by code (ruling 14):
the bench asks the list before any sound goes anywhere."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

LIST_NAME = "recordings.json"
NOT_KNOWN = "not known"
RATES = (16000, 48000)
REQUIRED = ("name", "file", "sha256", "script", "script_key", "script_sha256", "date", "room", "microphone",
            "capture", "rate", "channels", "sample_bits", "length_s", "speakers", "parts", "whole", "last_speech",
            "read_differently", "machine_voices", "cut_of", "consent", "notes")


class BadList(Exception):
    """The list cannot be used as it stands."""


class NotListed(Exception):
    """A recording the list does not name."""


class RecordingChanged(Exception):
    """A file whose checksum differs from the list."""


@dataclass(frozen=True)
class Recording:
    name: str
    path: Path
    sha256: str
    script: str
    script_key: str
    script_sha256: str
    rate: int
    speakers: int
    length_s: float
    whole: bool
    last_speech: int | None
    read_differently: tuple[dict, ...]
    machine_voices: bool
    consent: dict
    entry: dict = field(repr=False)        # every field of the list, as written
    # Part two of 5c: the listed recording that holds the doctor's voice
    # alone, or none; and whether this entry is such a voice, which the bench
    # learns from and never replays as a consultation.
    doctor_voice: str | None = None
    voice_only: bool = False

    def cloud_allowed(self, service: str) -> bool:
        """Whether the list says this recording's sound may go to the service."""
        return service in self.consent.get("cloud", [])

    @property
    def folder(self) -> Path:
        return self.path.parent


def _check_entry(entry: dict) -> None:
    missing = [key for key in REQUIRED if key not in entry]
    if missing:
        raise BadList(f"{entry.get('name', '?')}: the fields {', '.join(missing)} are missing")
    if entry["rate"] not in RATES:
        raise BadList(f"{entry['name']}: the rate is {entry['rate']}, not one of {RATES}")
    if entry["channels"] != 1 or entry["sample_bits"] != 16:
        raise BadList(f"{entry['name']}: the sound must be one channel of 16 bits")
    if not entry["whole"] and not isinstance(entry["last_speech"], int):
        raise BadList(f"{entry['name']}: a reading that is not whole names its last speech")
    if entry["whole"] and entry["last_speech"] is not None:
        raise BadList(f"{entry['name']}: a whole reading has no last speech")
    consent = entry["consent"]
    if not isinstance(consent, dict) or not isinstance(consent.get("cloud"), list) \
            or consent.get("tests_on_this_computer") is not True:
        raise BadList(f"{entry['name']}: consent must say tests_on_this_computer true and list the cloud services")
    if int(entry["speakers"]) < 1:
        raise BadList(f"{entry['name']}: the number of speakers is 1 or more")
    if entry.get("voice_only") and (int(entry["speakers"]) != 1 or consent.get("cloud")):
        raise BadList(f"{entry['name']}: a recording of the doctor's voice alone has one speaker and goes to no cloud service")
    if entry.get("doctor_voice") is not None and not isinstance(entry["doctor_voice"], str):
        raise BadList(f"{entry['name']}: doctor_voice names a listed recording, or is null")


def load_list(folder: Path, list_name: str = LIST_NAME) -> list[Recording]:
    """The list, checked field by field. No file is opened here but the list."""
    folder = Path(folder)
    try:
        listed = json.loads((folder / list_name).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise BadList(f"no {list_name} in {folder}") from None
    except ValueError as exc:
        raise BadList(f"{list_name} is not JSON: {exc}") from None
    recordings, names = [], set()
    for entry in listed.get("recordings") or []:
        _check_entry(entry)
        if entry["name"] in names:
            raise BadList(f"{entry['name']} is listed twice")
        names.add(entry["name"])
        recordings.append(Recording(
            entry["name"], folder / entry["file"], entry["sha256"], entry["script"], entry["script_key"],
            entry["script_sha256"], int(entry["rate"]), int(entry["speakers"]), float(entry["length_s"]),
            bool(entry["whole"]), entry["last_speech"], tuple(entry["read_differently"]),
            bool(entry["machine_voices"]), dict(entry["consent"]), dict(entry),
            entry.get("doctor_voice"), bool(entry.get("voice_only", False))))
    return recordings


def named(recordings: list[Recording], name: str) -> Recording:
    for recording in recordings:
        if recording.name == name:
            return recording
    raise NotListed(name)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_file(recording: Recording) -> None:
    """The file is the one the list describes, or nothing goes further.
    The file is opened for reading only."""
    if not recording.path.is_file():
        raise RecordingChanged(f"{recording.name}: {recording.path.name} is missing")
    found = sha256_of(recording.path)
    if found != recording.sha256:
        raise RecordingChanged(f"{recording.name}: {recording.path.name} has sha256 {found}, not {recording.sha256}")


def folders_of(recordings: list[Recording]) -> list[Path]:
    """Where recordings are kept: nothing is ever written there (R18)."""
    return sorted({r.folder.resolve() for r in recordings})
