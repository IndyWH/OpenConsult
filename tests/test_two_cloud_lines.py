"""Two lines for two things in the cloud, and the owner's sentences of step
9f (spec 15.13, ruling 76; rule 4 of the step's prompt). Run 9c wrote one
long line where both the transcription and the language model were in
the cloud. On 21 Nov 2026 the owner ruled that each thing in the cloud
has a line of its own that begins In the cloud:, in his words of 18 Nov;
and he took as his own, letter for letter, the drafts of run 9c that say
where words or sound go. Each stands here as the stage prompt gives it
and is proven against what the app says: none is changed without his
word. Made services, no model, no internet."""

from __future__ import annotations

import pytest

from openconsult import words
from openconsult.settings.statement import where_lines
from tests.conftest import text_of
from tests.test_less_no_tick import PATHS
from tests.test_panel import BOTH_KEYS, made
from tests.test_where_it_runs import picture_lines

HERE_BOTH = "On this computer: the language model and transcription."
SPEECH = "In the cloud: transcription, by Speechmatics. The sound of the consultation goes to it as it is spoken."
MODEL = "In the cloud: the language model, by Claude. The words of the consultation go to it."
AFTER_STOP = "In the cloud: after Stop, the recording goes to Speechmatics once. No sound goes to it during the consultation."
# The lines the one function gives for every path, in full. L: both on this computer. R: the recording sent after Stop.
# S: Speechmatics live. C: Claude. CR: Claude, and the recording after Stop. CS: Claude and Speechmatics live.
LINES = {"L": (HERE_BOTH, "In the cloud: nothing."), "R": (HERE_BOTH, AFTER_STOP),
         "S": ("On this computer: the language model. Nothing goes to Claude.", SPEECH),
         "C": ("On this computer: transcription. Nothing goes to Speechmatics.", MODEL),
         "CR": ("On this computer: transcription.", AFTER_STOP, MODEL), "CS": (SPEECH, MODEL)}


@pytest.mark.parametrize("name", list(LINES))
def test_ruling_76_each_thing_in_the_cloud_has_a_line_of_its_own_the_transcription_or_the_recording_first_for_every_path(name):
    lines = where_lines(PATHS[name])
    assert lines == LINES[name]
    # Each line of the cloud is the heading and then one thing, beginning with a small letter: never two things on a line.
    cloud = [line for line in lines if line.startswith("In the cloud: ")]
    assert all(line[len("In the cloud: ")].islower() for line in cloud)
    assert not any("Speechmatics" in line and "Claude" in line for line in lines)


def test_ruling_76_with_speechmatics_and_claude_both_chosen_settings_shows_two_lines_that_begin_in_the_cloud_one_for_each(tmp_path, clock):
    # Done when you see, for 9f: in Settings, with both chosen, two lines begin In the cloud. Above the picture.
    app, client, *_ = made(tmp_path / "live", clock, held=BOTH_KEYS, path=PATHS["CS"])
    page = text_of(client.get("/settings"))
    assert picture_lines(page) == [SPEECH, MODEL] and page.count("In the cloud:") == 2 and "On this computer:" not in page
    assert f'<p class="sentence">{SPEECH}</p><p class="sentence">{MODEL}</p>' in page
    # The one long line that run 9c built for both is gone: no sentence of the second thing follows the first on its line.
    assert "spoken. The language model, by Claude." not in page and "In the cloud: Transcription" not in page
    # The same where the recording is sent after Stop and Claude is the language model: the recording first.
    app, client, *_ = made(tmp_path / "after", clock, held=BOTH_KEYS, path=PATHS["CR"])
    page = text_of(client.get("/settings"))
    assert picture_lines(page) == ["On this computer: transcription.", AFTER_STOP, MODEL] and page.count("In the cloud:") == 2
    assert "consultation. The language model, by Claude." not in page and "In the cloud: After Stop" not in page


# THE OWNER'S, as the stage prompt of step 9f gives them, one to a line, with the place of each.
OWNERS = [
    ("one of the two presses at the top right of the note, and of the transcript", lambda: words.VIEW_WORDS["simple"], "Simple"),
    ("the other", lambda: words.VIEW_WORDS["advanced"], "Advanced"),
    ("ruling 76, one: Claude the language model, transcription on this computer, the tick for better accuracy not set",
     lambda: where_lines(PATHS["C"])[0], "On this computer: transcription. Nothing goes to Speechmatics."),
    ("ruling 76, two: the first of two lines where Speechmatics writes the live text and Claude is the language model",
     lambda: where_lines(PATHS["CS"])[0], "In the cloud: transcription, by Speechmatics. The sound of the consultation goes to it as it is spoken."),
    ("ruling 76, two: the second of the two", lambda: where_lines(PATHS["CS"])[1],
     "In the cloud: the language model, by Claude. The words of the consultation go to it."),
    ("ruling 76, two: the first of two lines where the recording is sent after Stop and Claude is the language model",
     lambda: where_lines(PATHS["CR"])[1],
     "In the cloud: after Stop, the recording goes to Speechmatics once. No sound goes to it during the consultation."),
    ("ruling 76, two: the second where the recording is sent after Stop and Claude is the language model",
     lambda: where_lines(PATHS["CR"])[2], "In the cloud: the language model, by Claude. The words of the consultation go to it."),
    ("ruling 76, three: the press under the notice of a path that sends less", lambda: words.LESS_FULL_STATEMENT,
     "Read the full statement for these choices"),
    ("ruling 76, four: the box of Speechmatics, opened, when it is ready",
     lambda: words.PANEL_REASONS["cloud_ready"].format(service=words.SERVICE_TITLES["speechmatics"], kind=words.PANEL_KINDS["speechmatics"]),
     "Speechmatics is connected. It is the cloud transcription service."),
    ("ruling 76, four: the box of Claude, opened, when it is ready",
     lambda: words.PANEL_REASONS["cloud_ready"].format(service=words.SERVICE_TITLES["claude"], kind=words.PANEL_KINDS["claude"]),
     "Claude is connected. It is the cloud language model."),
    # His by mail 1 of the step (his word A of 21 Nov 2026, 08:35): the reason where the recording was sent after Stop
    # and the transcript that came back held no words.
    ("the reason of a transcript that came back with no words", lambda: words.UPLOAD_NO_WORDS.format(service=words.SERVICE_TITLES["speechmatics"]),
     "Speechmatics sent back a transcript with no words in it."),
]


@pytest.mark.parametrize("place, said, sentence", OWNERS, ids=[place for place, _, _ in OWNERS])
def test_step_9f_each_of_the_owners_sentences_and_words_is_said_by_the_app_letter_for_letter(place, said, sentence):
    assert said() == sentence, place
