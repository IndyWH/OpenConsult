"""The cloud mark (spec 15.13, ruling 5; 7.3, rule 2; the owner's words of
16 Nov 2026, brought with the review of the plan of run 9b): on the live
page for the whole consultation and on the review page among the details
it ran with, whenever its path holds a cloud service, and on no other."""

from __future__ import annotations

import pytest

from openconsult.settings.path import CLAUDE, SPEECHMATICS, THIS_COMPUTER, ChosenPath
from openconsult.settings.statement import mark_lines, statement_for
from tests.conftest import text_of
from tests.test_cloud_consultation import cloud_app, through_stop
from tests.test_connect_screens import NO_CARD, SUITABLE
from tests.test_start import TICKS

SOUND = "Sound goes to Speechmatics as it is spoken."
WORDS = "Words go to Claude."
RECORDING = "After Stop the recording goes to Speechmatics."


@pytest.mark.parametrize("path, lines", [
    (ChosenPath(CLAUDE, SPEECHMATICS), (SOUND, WORDS)),
    (ChosenPath(CLAUDE, THIS_COMPUTER), (WORDS,)),
    (ChosenPath(THIS_COMPUTER, SPEECHMATICS), (SOUND,)),
    (ChosenPath(THIS_COMPUTER, THIS_COMPUTER, better_accuracy=True), (RECORDING,)),          # the tick alone: the third line alone, and true
    (ChosenPath(CLAUDE, THIS_COMPUTER, better_accuracy=True), (WORDS, RECORDING)),
    (ChosenPath(CLAUDE, SPEECHMATICS, better_accuracy=True), (SOUND, WORDS)),                # the tick does not count in cloud transcription
    (ChosenPath(THIS_COMPUTER, THIS_COMPUTER), ()),                                           # nothing in the cloud: no mark
])
def test_15_13_ruling_5_the_mark_holds_one_line_for_each_thing_that_is_true_of_the_path_in_the_owners_order(path, lines):
    assert mark_lines(path) == lines
    assert bool(lines) == path.holds_cloud == (statement_for(path) is not None)


def mark_of(page: str) -> str | None:
    if 'id="cloud-mark"' not in page:
        return None
    return page.split('id="cloud-mark"', 1)[1].split("</div>", 1)[0]


def test_15_13_ruling_5_the_mark_stands_on_the_live_page_for_the_whole_consultation_and_on_the_review_page_told_without_colour(tmp_path, clock, server):
    app, client, local, workers, testers = cloud_app(tmp_path, clock, server, machine=NO_CARD)
    start = mark_of(client.get("/consultations/start/1").text)
    assert start is not None and SOUND in start and WORDS in start                            # the path is said before Start, too
    client.post("/consultations/start/1", data=TICKS)
    live = client.get("/consultations/1")
    mark = mark_of(live.text)
    assert mark is not None and '<b class="cloud-word">Cloud</b>' in mark
    assert mark.index(SOUND) < mark.index(WORDS) and RECORDING not in mark
    assert "<svg" in mark and 'stroke="currentColor"' in mark and 'role="note"' in live.text  # a drawn cloud and words: not colour alone
    assert live.text.index('id="cloud-mark"') < live.text.index("<script src=")               # in the page as served, before any script that runs
    # The setting changes under the consultation: its mark is the mark of the path it started with.
    app.state.parts.stored.set_path("none", ChosenPath(CLAUDE, THIS_COMPUTER))
    assert SOUND in mark_of(client.get("/consultations/1").text)
    through_stop(app, client)
    review = mark_of(client.get("/consultations/1").text)
    assert review is not None and SOUND in review and WORDS in review
    assert SOUND in text_of(client.get("/consultations/1"))


def test_15_13_ruling_5_a_consultation_on_this_computer_has_no_mark_on_any_page(tmp_path, clock, server):
    app, client, local, workers, testers = cloud_app(tmp_path, clock, server, machine=SUITABLE)
    assert mark_of(client.get("/consultations/start/1").text) is None
    client.post("/consultations/start/1", data=TICKS)
    assert mark_of(client.get("/consultations/1").text) is None
    through_stop(app, client)
    assert mark_of(client.get("/consultations/1").text) is None and "Cloud" not in text_of(client.get("/consultations/1"))
