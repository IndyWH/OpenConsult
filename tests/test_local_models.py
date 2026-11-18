"""The section Local models (spec 7.3; 15.13, ruling 57 and the details of
run 9c; R31): a list that is read. Each thing the app has installed in
the data folder with its size on the disk, and the language model as
the engine chosen at start reports it. Nothing in it can be pressed:
every download on a click arrives with the installers, at stage 15.
Made folders of made files; nothing is installed or fetched."""

from __future__ import annotations

import threading

from openconsult import words
from openconsult.guidelines import environment as guidelines_environment
from openconsult.settings.installed import Sizes, folder_bytes
from openconsult.speech import environment as speech_environment
from openconsult.speech.choices import NEMOTRON, WHISPERX_PYANNOTE
from openconsult.web.settings_local import plain_size
from tests.conftest import text_of
from tests.test_panel import SMALLER, made


def section_of(page: str) -> str:
    return page.split('<section class="pane" id="local-models">', 1)[1].split("</section>", 1)[0]


def row_of(page: str, name: str) -> str:
    return section_of(page).split(f'<tr data-thing="{name}">', 1)[1].split("</tr>", 1)[0]


def fill(folder, name: str, size: int) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(b"\0" * size)


def test_ruling_57_each_thing_installed_in_the_data_folder_is_listed_with_its_size_on_the_disk(tmp_path, clock):
    app, client, *_ = made(tmp_path, clock, nemotron=True, whisperx=False)
    p = app.state.parts
    fill(speech_environment.folder(tmp_path, NEMOTRON) / ".venv" / "lib", "made-up-library.bin", 2_500_000)
    fill(speech_environment.folder(tmp_path, NEMOTRON), "made-up.cfg", 400_000)
    # The guideline search: its environment and its model, as its own module tells an install.
    python = guidelines_environment.python(tmp_path)
    fill(python.parent, python.name, 1000)
    fill(guidelines_environment.model_folder(tmp_path), guidelines_environment.WEIGHTS, 1_200_000_000)
    first = text_of(client.get("/settings"))
    assert p.sizes.wait(10)
    page = text_of(client.get("/settings"))
    assert f"<h2>{words.SECTION_LOCAL_MODELS}</h2>" in page and words.LOCAL_MODELS_INTRO in section_of(page)
    assert "<th>Nemotron, its environment</th><td>Installed, 3 MB on the disk. " + words.LOCAL_MODELS_ELSEWHERE + "</td>" in row_of(page, "nemotron")
    assert "<th>WhisperX with pyannote, its environment</th><td>Not installed.</td>" in row_of(page, "whisperx_pyannote")
    assert "<th>Guideline search model</th><td>Installed, 1.2 GB on the disk.</td>" in row_of(page, "guideline_search")
    # The language model as the engine chosen at start reports it; its files are the engine's, so no size is said.
    assert "Gemma 4 QAT on Ollama 0.0-made-up, as the engine reports it. Its files are the engine's own." in row_of(page, "language_model")
    # Before the sizes were there, the first view said so and did not wait.
    assert "<th>Nemotron, its environment</th>" in first and ("being measured" in row_of(first, "nemotron") or "3 MB" in row_of(first, "nemotron"))
    # A list that is read: nothing in it can be pressed, and no download is offered (R31).
    listed = section_of(client.get("/settings").text)
    assert not any(mark in listed for mark in ("<form", "<button", "<a ", "<input", "<details")) and "Download" not in listed


def test_ruling_57_a_view_does_not_wait_for_the_sizes_and_they_are_measured_once_in_a_run(tmp_path, clock):
    app, client, *_ = made(tmp_path, clock, nemotron=True, whisperx=True)
    p = app.state.parts
    go, measured = threading.Event(), []

    def slow(folder):
        measured.append(folder.name)
        go.wait(10)
        return 42_000_000

    p.sizes = Sizes(measure=slow)
    page = text_of(client.get("/settings"))                                               # it comes back while the measuring is held
    assert "Installed. The size is being measured. Load the page again to see it." in row_of(page, "nemotron")
    assert "Installed. The size is being measured." in row_of(page, "whisperx_pyannote") and p.sizes.of("nemotron") is None
    go.set()
    assert p.sizes.wait(10)
    for _ in range(3):
        page = text_of(client.get("/settings"))
    assert "Installed, 42 MB on the disk." in row_of(page, "nemotron") and "Installed, 42 MB on the disk." in row_of(page, "whisperx_pyannote")
    assert sorted(measured) == ["nemotron", "whisperx_pyannote"]                          # each folder once, whatever the views


def test_ruling_57_on_a_machine_with_no_suitable_card_no_language_model_is_listed_and_a_size_is_said_in_plain_units(tmp_path, clock):
    app, client, *_ = made(tmp_path, clock, machine=SMALLER, nemotron=False, whisperx=False)
    page = text_of(client.get("/settings"))
    assert 'data-thing="language_model"' not in section_of(page) and "Ollama" not in section_of(page)      # no engine was asked here (15.7)
    assert section_of(page).count("Not installed.") == 3
    assert (plain_size(999_999), plain_size(1_000_000), plain_size(8_949_000_000), plain_size(10 ** 9)) == (
        "less than 1 MB", "1 MB", "8.9 GB", "1.0 GB")
    # A link is counted as a link and never followed; a folder that is not there holds nothing.
    fill(tmp_path / "counted", "a.bin", 700)
    (tmp_path / "counted" / "link").symlink_to(tmp_path)
    assert folder_bytes(tmp_path / "counted") >= 700 and folder_bytes(tmp_path / "counted") < 5000 and folder_bytes(tmp_path / "absent") == 0
