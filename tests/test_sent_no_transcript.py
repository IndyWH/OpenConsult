"""A recording that was sent after Stop and gave no transcript (the owner's
word A of 20 Nov 2026, 08:11; mail 5 of run 9c). Until then no line stood
above the note while its delete at the service was awaited: his three
lines all say that the final transcript was made. Where the service took
the recording and named a job, and no transcript from it was made, the
line above the note is one of two, his, letter for letter: while the
answer is awaited, and when the delete is proven. When it is not proven,
no line there and his sentence of ruling 41 among the warnings, as in
every case. Made services, no model, no internet."""

from __future__ import annotations

import pytest

from openconsult import words
from openconsult.consult import whole
from openconsult.web import pages
from tests.conftest import text_of
from tests.test_delete_beside_stop import ASKING, NOT_PROVEN, SLOT, Held, to_final
from tests.test_recording_after_stop import LongPage, consult, ticked_app

# THE OWNER'S, letter for letter.
AWAITED = ("The recording went to Speechmatics, and no transcript came back. OpenConsult has asked Speechmatics to delete it there "
           "and is waiting for the answer.")
PROVEN = ("The recording went to Speechmatics, and no transcript came back. It was deleted there, and Speechmatics confirmed that "
          "it is gone.")
MADE_LINES = (words.UPLOAD_MADE, words.UPLOAD_MADE_ONLY, words.UPLOAD_MADE_AWAITED)


def line_of(page: str) -> str | None:
    slot = page.split(SLOT, 1)[1].split("</div>", 1)[0]
    return slot.split('<p class="mark no-print" id="recording-sent">', 1)[1].split("</p>", 1)[0] if 'id="recording-sent"' in slot else None


def test_his_word_of_20_nov_the_two_lines_for_a_recording_that_gave_no_transcript_letter_for_letter():
    assert (words.UPLOAD_NONE_AWAITED, words.UPLOAD_NONE) == (AWAITED, PROVEN)
    # Each ends as his line for a transcript that was made ends, in the same state.
    assert AWAITED.endswith(words.UPLOAD_MADE_AWAITED.split(". ", 1)[1]) and PROVEN.endswith(words.UPLOAD_MADE.split(". ", 1)[1])


@pytest.mark.parametrize("mode", ["rejected", "never"])
def test_his_word_of_20_nov_while_the_answer_is_awaited_and_when_the_delete_is_proven_the_page_says_so_in_his_line(tmp_path, clock, server, mode):
    made = Held(mode=mode)                                     # the service takes the recording and names a job; no transcript comes of it
    app, client, local = ticked_app(tmp_path, clock, server, made)
    p = app.state.parts
    try:
        to_final(app, client)
        assert made.reached.wait(10)
        sent = p.consultations.upload(1)
        assert sent["job_id"] == "job-1" and sent["result_at"] is None and whole.proof_state(sent) == whole.AWAITED
        page = text_of(client.get("/consultations/1"))
        # Awaited: his line, where until now there was none; the page asks the app by itself, as for the other three.
        assert line_of(page) == AWAITED and SLOT + ASKING in page and pages.static_address("sent.js") in page
        assert client.get("/consultations/1/sent").json() == {"state": "awaited", "line": AWAITED}
        assert not any(line in page for line in MADE_LINES)                        # never a line that says a transcript was made
        # What stands as it did: the mark's line of ruling 52, and the warning that the better transcript could not be made.
        assert words.CLOUD_MARK_RECORDING_SENT in page and "The better transcript could not be made: " in page
        assert [w["kind"] for w in p.consultations.warnings(1)].count("better_transcript_failed") == 1
    finally:
        made.go.set()
    # Proven: his second line, on a load and in the app's own page that the page's script takes its parts from.
    assert p.whole.wait() and whole.proof_state(p.consultations.upload(1)) == whole.PROVEN
    assert client.get("/consultations/1/sent").json() == {"state": "proven", "line": PROVEN}
    for address in ("/consultations/1", "/consultations/1/sent/page"):
        page = text_of(client.get(address))
        assert line_of(page) == PROVEN and "data-awaited" not in page and "sent.js" not in page and AWAITED not in page
        assert not any(line in page for line in MADE_LINES) and NOT_PROVEN not in page


def test_his_word_of_20_nov_when_the_delete_is_not_proven_no_line_stands_there_and_his_warning_of_ruling_41_says_it(tmp_path, clock, server):
    made = LongPage(mode="rejected", after_delete="error")     # deleted, and each ask after it is answered 500
    app, client, local = ticked_app(tmp_path, clock, server, made)
    p = app.state.parts
    consult(app, client)
    assert whole.proof_state(p.consultations.upload(1)) == whole.UNPROVEN
    assert client.get("/consultations/1/sent").json() == {"state": "not_proven", "line": None}
    page = text_of(client.get("/consultations/1"))
    assert line_of(page) is None and AWAITED not in page and PROVEN not in page and not any(line in page for line in MADE_LINES)
    warnings = page.split('<div id="other-warnings" data-part>', 1)[1].split("</div>", 1)[0]
    assert NOT_PROVEN in warnings and "The better transcript could not be made: " in warnings


def test_his_word_of_20_nov_no_line_where_the_service_took_nothing(tmp_path, clock, server):
    app, client, local = ticked_app(tmp_path, clock, server, LongPage(mode="submit 500"))
    p = app.state.parts
    consult(app, client)
    assert p.consultations.upload(1)["job_id"] is None
    assert client.get("/consultations/1/sent").json() == {"state": "none", "line": None}
    assert line_of(text_of(client.get("/consultations/1"))) is None
