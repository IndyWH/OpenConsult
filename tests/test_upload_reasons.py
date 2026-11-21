"""Two flags of run 9c, mended in step 9f (spec 15.13, the details of step
9f, Two flags of run 9c). One: where the recording was sent after Stop
and the transcript that came back held no words, the warning said that
Speechmatics is not answering, which is not true there: the service
answered. That case has a reason of its own, the owner's sentence, and no
other reason changes. Two: the lines and the key of the picture of This
machine are hidden from a screen reader, which cannot meet a drawing; the
picture is tied to the lines above it as its description, so that a
reader is given in words what the lines draw. No service, no model."""

from __future__ import annotations

import re

import pytest

from openconsult import words
from openconsult.consult import whole
from tests.conftest import text_of
from tests.test_less_no_tick import PATHS
from tests.test_panel import BOTH_KEYS, made
from tests.test_where_it_runs import picture_lines

# Every reason the better transcript could not be made, by what the sending's own record says of the failure.
REASONS = [
    ({"at": "key", "detail": "no key in use"}, "Speechmatics is not connected."),
    ({"at": "send", "detail": "the upload was refused: HTTP 401"}, words.KEY_REFUSED.format(service="Speechmatics")),
    ({"at": "send", "detail": "HTTP 403"}, words.KEY_REFUSED.format(service="Speechmatics")),
    ({"at": "send", "detail": "HTTP 402"}, words.NO_CREDIT.format(service="Speechmatics")),
    ({"at": "send", "detail": "no answer: HTTP 0"}, words.NO_INTERNET.format(service="Speechmatics")),
    ({"at": "send", "detail": "HTTP 500"}, "Speechmatics is not answering. Try again later."),
    ({"at": "result", "detail": "no result within 150 s"}, "Speechmatics did not answer in 150 seconds."),
    ({"at": "model", "detail": "standard"}, "Speechmatics did not use the settings that were asked for."),
    ({"at": "restart", "detail": ""}, "OpenConsult was closed while the recording was being sent."),
    ({"at": "result", "detail": "HTTP 500"}, "Speechmatics is not answering. Try again later."),
    (None, "Speechmatics is not answering. Try again later."),
]


@pytest.mark.parametrize("failure, sentence", REASONS)
def test_9f_no_other_reason_of_a_better_transcript_that_could_not_be_made_changes(failure, sentence):
    assert whole.reason_of(failure, 150.0) == sentence


def test_9f_a_transcript_that_came_back_with_no_words_has_a_reason_of_its_own_in_the_owners_sentence():
    # THE OWNER'S, letter for letter (his word A of 21 Nov 2026, 08:35).
    said = whole.reason_of({"at": "result", "detail": whole.NO_WORDS}, 150.0)
    assert said == "Speechmatics sent back a transcript with no words in it." == words.UPLOAD_NO_WORDS.format(service="Speechmatics")
    assert "not answering" not in said
    # As the warning shows it under the line above the note.
    assert words.UPLOAD_FAILED.format(detail=said) == ("The better transcript could not be made: Speechmatics sent back a transcript with no "
                                                       "words in it. The transcript is the one made during the consultation. Nothing is sent again.")


@pytest.mark.parametrize("name", ["L", "CR", "CS"])
def test_9f_the_picture_of_this_machine_is_described_to_a_screen_reader_by_the_lines_above_it_and_its_drawing_stays_hidden(tmp_path, clock, name):
    app, client, *_ = made(tmp_path, clock, held=BOTH_KEYS, path=PATHS[name])
    page = text_of(client.get("/settings"))
    # The picture is a group with a name, and the lines above it are its description: one element of that name, which
    # holds the lines the picture's own function gives and nothing else.
    assert f'<div class="control-panel" id="control-panel" role="group" aria-label="{words.SECTION_MACHINE}" aria-describedby="panel-path">' in page
    assert page.count('id="panel-path"') == 1 and len(picture_lines(page)) >= 2
    described = page.split('<div class="panel-where" id="panel-path">', 1)[1].split("</div>", 1)[0]
    assert re.sub(r"<[^>]+>", "", described).count("In the cloud:") == len([line for line in picture_lines(page) if line.startswith("In the cloud:")])
    assert "aria-hidden" not in described
    # Every drawn line and the key stay hidden from a reader, as since run 9c.
    arrows = re.findall(r'<span class="panel-arrow [^>]*>', page)
    assert arrows and all('aria-hidden="true"' in arrow for arrow in arrows)
    assert '<p class="panel-key" id="panel-key" aria-hidden="true">' in page
