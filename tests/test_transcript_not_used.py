"""A transcript that came back from the service and could not be used (the
owner's word A of 20 Nov 2026, 10:57; mail 6 of run 9c). Since mail 5 the
line above the note said, for every recording the service took that gave
no final transcript, that no transcript came back: also where one came
back and the app did not use it, because the settings asked for were not
used or because it held no words. That case has two sentences of its own,
his, letter for letter: while the answer to the delete is awaited, and
when the delete is proven. When it is not proven, no line there and his
sentence of ruling 41 among the warnings, as in every case. His sentence
no transcript came back stays for the case where none came back. Made
services, no model, no internet."""

from __future__ import annotations

import pytest

from openconsult import words
from openconsult.consult import whole
from tests.conftest import text_of
from tests.test_delete_beside_stop import ASKING, NOT_PROVEN, SLOT, Held, to_final
from tests.test_recording_after_stop import LongPage, consult, ticked_app
from tests.test_sent_no_transcript import AWAITED as NONE_AWAITED, MADE_LINES, PROVEN as NONE_PROVEN, line_of

# THE OWNER'S, letter for letter.
AWAITED = ("The recording went to Speechmatics, and the transcript that came back could not be used. OpenConsult has asked "
           "Speechmatics to delete it there and is waiting for the answer.")
PROVEN = ("The recording went to Speechmatics, and the transcript that came back could not be used. It was deleted there, and "
          "Speechmatics confirmed that it is gone.")


class NoWords(Held):
    """The made service whose transcript comes back with the settings asked for and holds no word."""

    def transcript(self) -> dict:
        return {**super().transcript(), "results": []}


def test_his_word_of_20_nov_1057_the_two_lines_for_a_transcript_that_came_back_and_could_not_be_used_letter_for_letter():
    assert (words.UPLOAD_UNUSED_AWAITED, words.UPLOAD_UNUSED) == (AWAITED, PROVEN)
    # Each ends as his line for a transcript that was made ends, in the same state; his two of mail 5 stand as they were.
    assert AWAITED.endswith(words.UPLOAD_MADE_AWAITED.split(". ", 1)[1]) and PROVEN.endswith(words.UPLOAD_MADE.split(". ", 1)[1])
    assert (words.UPLOAD_NONE_AWAITED, words.UPLOAD_NONE) == (NONE_AWAITED, NONE_PROVEN)


@pytest.mark.parametrize("case, made, reason", [
    ("the settings asked for were not used", lambda: Held(model="standard"), "Speechmatics did not use the settings that were asked for."),
    # Restated on the owner's word A of 21 Nov 2026, 08:35 (step 9f; a flag of run 9c): the service answered, and its
    # transcript was empty, so the reason is one of its own. OLD: "Speechmatics is not answering. Try again later.",
    # which is not true there. NEW, his sentence, letter for letter:
    ("it held no words", lambda: NoWords(), "Speechmatics sent back a transcript with no words in it."),
])
def test_his_word_of_20_nov_1057_a_transcript_that_came_back_and_was_not_used_has_his_line_awaited_and_then_proven(tmp_path, clock, server, case, made, reason):
    made = made()
    app, client, local = ticked_app(tmp_path, clock, server, made)
    p = app.state.parts
    try:
        to_final(app, client)
        assert made.reached.wait(10)
        sent = p.consultations.upload(1)
        # The service took the recording, its reply was read, and no final transcript was made from it.
        assert sent["job_id"] == "job-1" and sent["result_at"] is None and sent["failure"] == reason
        assert whole.came_back(sent) and whole.proof_state(sent) == whole.AWAITED
        assert [r["text"] for r in p.consultations.transcript_lines(1)] == [l["text"] for l in p.consultations.live_lines(1)]
        page = text_of(client.get("/consultations/1"))
        assert line_of(page) == AWAITED and SLOT + ASKING in page
        assert client.get("/consultations/1/sent").json() == {"state": "awaited", "line": AWAITED}
        # Never his sentence that none came back, and never a line that says the final transcript was made.
        assert "no transcript came back" not in page and not any(line in page for line in MADE_LINES)
        assert "The better transcript could not be made: " + reason in page             # the warning under it stays as it is
    finally:
        made.go.set()
    assert p.whole.wait() and whole.proof_state(p.consultations.upload(1)) == whole.PROVEN
    assert client.get("/consultations/1/sent").json() == {"state": "proven", "line": PROVEN}
    for address in ("/consultations/1", "/consultations/1/sent/page"):
        page = text_of(client.get(address))
        assert line_of(page) == PROVEN and AWAITED not in page and "no transcript came back" not in page
        assert not any(line in page for line in MADE_LINES) and NOT_PROVEN not in page


def test_his_word_of_20_nov_1057_when_the_delete_is_not_proven_no_line_stands_there_and_his_warning_of_ruling_41_says_it(tmp_path, clock, server):
    made = LongPage(model="standard", after_delete="error")    # it came back with other settings; deleted, and each ask after it is answered 500
    app, client, local = ticked_app(tmp_path, clock, server, made)
    p = app.state.parts
    consult(app, client)
    sent = p.consultations.upload(1)
    assert whole.came_back(sent) and whole.proof_state(sent) == whole.UNPROVEN
    assert client.get("/consultations/1/sent").json() == {"state": "not_proven", "line": None}
    page = text_of(client.get("/consultations/1"))
    assert line_of(page) is None and "could not be used" not in page and "no transcript came back" not in page
    warnings = page.split('<div id="other-warnings" data-part>', 1)[1].split("</div>", 1)[0]
    assert NOT_PROVEN in warnings and "The better transcript could not be made: " in warnings


@pytest.mark.parametrize("mode", ["rejected", "never"])
def test_his_word_of_20_nov_0811_where_none_came_back_his_sentence_no_transcript_came_back_stays(tmp_path, clock, server, mode):
    app, client, local = ticked_app(tmp_path, clock, server, LongPage(mode))
    p = app.state.parts
    consult(app, client)
    sent = p.consultations.upload(1)
    assert sent["job_id"] == "job-1" and sent["result_at"] is None and not whole.came_back(sent)
    page = text_of(client.get("/consultations/1"))
    assert line_of(page) == NONE_PROVEN and "could not be used" not in page


def test_his_word_of_20_nov_1057_a_transcript_that_was_used_keeps_his_line_that_the_final_transcript_was_made(tmp_path, clock, server):
    app, client, local = ticked_app(tmp_path, clock, server, LongPage())
    p = app.state.parts
    consult(app, client)
    sent = p.consultations.upload(1)
    assert sent["result_at"] is not None and whole.came_back(sent)
    page = text_of(client.get("/consultations/1"))
    assert line_of(page) == words.UPLOAD_MADE and "could not be used" not in page and "no transcript came back" not in page
