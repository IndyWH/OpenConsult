"""The second ask after a delete (spec 15.13, ruling 49, with rulings 41 and
44; the details of run 9c). At the room check of 17 Nov 2026 the ask for
the job failed on the line and brought no answer at all, so there was
nothing to judge and the page said not proven. A failed request is not
an answer: such an ask is made once more, 5 seconds later, and never a
third time; an ask that brought any answer is never made again. Made
services inside the suite; nothing here opens a connection or waits."""

from __future__ import annotations

import pytest

from openconsult import words
from openconsult.bench.speech import assemblyai_upload
from openconsult.speech import speechmatics_upload, upload
from openconsult.speech.upload import Answer, Http
from tests.conftest import text_of
from tests.made_up_recordings import made_sound
from tests.made_up_upload_services import MADE_UP_KEY, MadeUpAssemblyAI, MadeUpSpeechmatics
from tests.test_recording_after_stop import LongPage, consult, ticked_app

JOB, TRANSCRIPT = "/jobs/job-1", "/jobs/job-1/transcript"
OWNERS = ("OpenConsult asked Speechmatics to delete the recording and could not confirm that it is gone. "
          "Its own pages say that it deletes such a recording itself after 7 days.")


def silent(made_class, quiet: dict):
    """A made service whose asks after the delete bring no answer at all:
    quiet names, for the end of an address, how many tries get none. Each
    ask after the delete is kept with the limit it was given."""

    class Silent(made_class):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.left, self.asks = dict(quiet), []

        def __call__(self, method, url, headers, body, timeout_s=None):
            path = url.split("/v2", 1)[1].split("?")[0]
            if method == "GET" and self.deleted and not path.endswith("/jobs") and not path.endswith("/transcript?"):
                self.asks.append((path, timeout_s))
                if self.left.get(path, 0) > 0:
                    self.left[path] -= 1
                    self.requests.append({"method": method, "url": url, "headers": dict(headers), "body": body})
                    return Answer(0, b"", "URLError")
            return super().__call__(method, url, headers, body)

    return Silent


class Slept:
    """The clock of an upload and its sleeps, kept: no test waits."""

    def __init__(self):
        self.t, self.sleeps = 0.0, []

    def __call__(self):
        return self.t

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.t += seconds


def one(service, made, clock):
    return upload.run_upload(service, Http(service.EU_HOST, made), MADE_UP_KEY, b"RIFFmade-up", "sound-1.wav", {"recording": "one"},
                             made_sound(1.0), 16000, clock=clock, sleep=clock.sleep)["upload"]


def tries(up) -> list[tuple]:
    return [(a["what"], a["status"], a["gone"], a.get("try", 1)) for a in up["asked_again"]]


def test_15_13_ruling_49_an_ask_with_no_answer_is_made_once_more_5_seconds_later_and_its_answer_is_judged():
    clock = Slept()
    made = silent(MadeUpSpeechmatics, {JOB: 1})()
    up = one(speechmatics_upload, made, clock)
    assert tries(up) == [("the job", 0, False, 1), ("its transcript", 404, True, 1), ("the job", 404, True, 2)]   # both tries, in order
    assert up["gone"] is True and up["proof"] == "the job: no answer came; its transcript: HTTP 404; the job, asked again after 5 s: HTTP 404"
    assert clock.sleeps[-1] == 5.0 == upload.SECOND_ASK_WAIT_S                              # the wait, between the first asks and the second try
    # The first asks keep the upload's own limit; the second try has the limit of 10 s. The answered ask was not made again.
    assert made.asks == [(JOB, None), (TRANSCRIPT, None), (JOB, 10.0)] and upload.SECOND_ASK_LIMIT_S == 10.0


def test_15_13_ruling_49_no_answer_twice_proves_nothing_and_there_is_never_a_third_try():
    clock = Slept()
    made = silent(MadeUpSpeechmatics, {JOB: 9, TRANSCRIPT: 9})()
    up = one(speechmatics_upload, made, clock)
    assert tries(up) == [("the job", 0, False, 1), ("its transcript", 0, False, 1), ("the job", 0, False, 2), ("its transcript", 0, False, 2)]
    assert up["gone"] is False and up["proof"].endswith("the job, asked again after 5 s: no answer came; its transcript, asked again after 5 s: no answer came")
    assert [path for path, _ in made.asks] == [JOB, TRANSCRIPT, JOB, TRANSCRIPT]            # four asks and no fifth
    assert clock.sleeps.count(5.0) == 1                                                     # one wait for both second tries


@pytest.mark.parametrize("after_delete, gone", [("gone", True), ("tombstone", True), ("words", False), ("error", False)])
def test_15_13_ruling_49_an_ask_that_brought_any_answer_is_never_made_again(after_delete, gone):
    clock = Slept()
    made = silent(MadeUpSpeechmatics, {})(after_delete=after_delete)
    up = one(speechmatics_upload, made, clock)
    assert [path for path, _ in made.asks] == [JOB, TRANSCRIPT] and all(t[3] == 1 for t in tries(up))   # a 500 is an answer too
    assert up["gone"] is gone and 5.0 not in clock.sleeps


def test_15_13_ruling_49_the_second_try_is_judged_by_the_rule_of_ruling_44_words_of_the_result_still_prove_nothing():
    clock = Slept()
    made = silent(MadeUpSpeechmatics, {TRANSCRIPT: 1})(after_delete="words")
    up = one(speechmatics_upload, made, clock)
    assert tries(up)[-1] == ("its transcript", 200, False, 2) and up["gone"] is False
    assert up["proof"].endswith("its transcript, asked again after 5 s: the answer still holds words of the result")


def test_15_13_ruling_49_the_benchs_upload_reads_the_same_code_for_the_second_service():
    clock = Slept()
    made = silent(MadeUpAssemblyAI, {"/transcript/tr-1": 1})(after_delete="gone")
    up = one(assemblyai_upload, made, clock)
    assert tries(up) == [("the transcript", 0, False, 1), ("the transcript", 404, True, 2)] and up["gone"] is True
    assert made.asks == [("/transcript/tr-1", None), ("/transcript/tr-1", 10.0)]


def test_15_13_rulings_41_and_49_in_the_app_a_second_try_that_answers_confirms_and_two_with_no_answer_say_not_proven(tmp_path, clock, server):
    # The room's case, mended: the ask for the job fails once on the line, the second try answers gone.
    made = silent(LongPage, {JOB: 1})()
    app, client, local = ticked_app(tmp_path / "a", clock, server, made)
    consult(app, client)
    sent = app.state.parts.consultations.upload(1)
    assert sent["gone"] == 1 and [(a["what"], a["status"], a.get("try", 1)) for a in sent["asked_again"]] == [
        ("the job", 0, 1), ("its transcript", 404, 1), ("the job", 404, 2)]
    page = text_of(client.get("/consultations/1"))
    assert words.UPLOAD_MADE in page and OWNERS not in page
    # No answer at either try: nothing to judge, so the page says not proven in the owner's sentence, with both tries in the record.
    made = silent(LongPage, {JOB: 2})()
    app, client, local = ticked_app(tmp_path / "b", clock, server, made)
    consult(app, client)
    p = app.state.parts
    sent = p.consultations.upload(1)
    assert sent["gone"] == 0 and [(a["what"], a["status"], a.get("try", 1)) for a in sent["asked_again"]] == [
        ("the job", 0, 1), ("its transcript", 404, 1), ("the job", 0, 2)]
    page = text_of(client.get("/consultations/1"))
    assert OWNERS in page and words.UPLOAD_MADE_ONLY in page and words.UPLOAD_MADE not in page
    assert next(l.detail for l in p.audit.lines() if l.event == "recording.delete_not_proven") == (
        "consultation 1: the job: no answer came; its transcript: HTTP 404; the job, asked again after 5 s: no answer came")
