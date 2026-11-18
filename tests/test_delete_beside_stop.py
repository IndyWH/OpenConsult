"""Stop does not wait for the delete of a recording or for its proof (the
owner's ruling of 18 Nov 2026, 06:55; mail 3 of run 9c). His words:
doctors are under time pressure; the doctor wants to look at the note as
soon as they press Stop. The delete and each ask after it wait 30
seconds at most. As soon as the transcript from the whole recording is
stored, Stop goes on; the delete, the two asks and their second tries run
beside it and write to the record as they come. Above the note stands one
of three lines, by what the record holds at that moment, and the page
takes the new one with no load. An app closed before the service has
answered finishes the proof at its next start. Made services, no model,
no internet."""

from __future__ import annotations

import re
import threading
from pathlib import Path

from openconsult import schema, words
from openconsult.app import build_app
from openconsult.consult import whole
from openconsult.consult.live import FINAL
from openconsult.settings import store as settings_store
from openconsult.speech import speechmatics_upload, upload
from openconsult.speech.upload import Answer, Http
from openconsult.web import pages
from openconsult.web.live import capture_from
from tests.conftest import PORT, browser, log_in, refusal_on, text_of
from tests.fakes import FakeEngine
from tests.made_up_store import MadeStore
from tests.made_up_upload_services import MADE_UP_KEY, MadeUpSpeechmatics
from tests.test_cloud_consultation import BOTH_KEYS, MadeTesters
from tests.test_connect_screens import SUITABLE
from tests.test_recording_after_stop import LongPage, consult, ticked_app
from tests.test_review_page import CAPTURE, LOUD, NOTE, reviewed
from tests.test_second_ask import JOB, TRANSCRIPT, Slept, one, silent, tries
from tests.test_start import TICKS
from tests.test_stop import until

# THE OWNER'S SENTENCE, letter for letter (his word at 06:58 on 18 Nov 2026): above the note while the answer is awaited.
AWAITED = ("The final transcript was made by Speechmatics from the whole recording. OpenConsult has asked Speechmatics to delete "
           "it there and is waiting for the answer.")
# His line of ruling 53, when the delete is proven; and its first sentence alone, when it is not.
PROVEN = ("The final transcript was made by Speechmatics from the whole recording. It was deleted there, and Speechmatics "
          "confirmed that it is gone.")
FIRST_ALONE = "The final transcript was made by Speechmatics from the whole recording."
# His sentence of ruling 41, among the warnings, when the delete is not proven.
NOT_PROVEN = ("OpenConsult asked Speechmatics to delete the recording and could not confirm that it is gone. "
              "Its own pages say that it deletes such a recording itself after 7 days.")
SLOT = '<div id="recording-sent-slot" class="no-print" data-part'
ASKING = ' data-awaited data-address="/consultations/1/sent" data-page="/consultations/1/sent/page">'


class Held(LongPage):
    """The made service whose answer to the delete waits for the test's
    word. then: answer (the delete is then answered as the made service
    answers it) or none (no answer at all comes of it)."""

    def __init__(self, then="answer", **kwargs):
        super().__init__(**kwargs)
        self.then, self.go, self.reached = then, threading.Event(), threading.Event()

    def __call__(self, method, url, headers, body, timeout_s=None):
        if method == "DELETE":
            self.reached.set()
            self.go.wait(30)
            if self.then == "none":
                self.requests.append({"method": method, "url": url, "headers": dict(headers), "body": body})
                self.limits.append((method, url.split("/v2", 1)[1].split("?")[0], timeout_s))
                return Answer(0, b"", "TimeoutError")
        return super().__call__(method, url, headers, body, timeout_s)


def to_final(app, client, cid=1):
    """Start, sound, Stop and the answer, as the doctor does them; never a wait for the delete."""
    client.post("/consultations/start/1", data=TICKS)
    c = app.state.parts.running[cid]
    c.begin_sound(capture_from(CAPTURE))
    for _ in range(8):
        c.sound(LOUD)
        c.wait_for_pass()
    client.post(f"/consultations/{cid}/stop")
    assert until(lambda: c.stop_stage == "who_spoke")
    client.post(f"/consultations/{cid}/speakers", data={"speaker": "S1"})
    assert until(lambda: c.state == FINAL)
    return c


def events(p) -> dict:
    return {line.event: line.detail for line in p.audit.lines() if line.event.startswith("recording.")}


def count_on_approve(page: str) -> str:
    return re.search(r'id="warning-count"[^>]*>([^<]*)<', page).group(1)


def next_start(tmp_path, clock, made):
    """The app started again on the same data folder, with a made service behind it."""
    app = build_app(settings_store.build(tmp_path, PORT), machine=SUITABLE, clock=clock,
                    engines={"vllm": FakeEngine(version=None), "ollama": FakeEngine()}, secure_store=MadeStore(BOTH_KEYS), upload_send=made,
                    testers=MadeTesters().both())
    return app, app.state.parts


def test_the_owners_sentence_of_18_nov_for_an_answer_that_is_awaited_letter_for_letter():
    # Pins his word at 06:58 on 18 Nov 2026, and that his two older lines stand as they did.
    assert words.UPLOAD_MADE_AWAITED == AWAITED and words.UPLOAD_MADE == PROVEN and words.UPLOAD_MADE_ONLY == FIRST_ALONE
    assert words.UPLOAD_DELETE_NOT_PROVEN == NOT_PROVEN and AWAITED.startswith(FIRST_ALONE + " ") and PROVEN.startswith(FIRST_ALONE + " ")


def test_ruling_of_18_nov_stop_reaches_the_note_and_the_review_page_while_the_service_has_not_answered_the_delete(tmp_path, clock, server):
    made = Held(then="none")
    app, client, local = ticked_app(tmp_path, clock, server, made)
    local.script = {"note": [NOTE]}                                # the made engine drafts a note when it is asked
    p = app.state.parts
    try:
        c = to_final(app, client)                                  # Stop went on to its end: the delete is still in flight
        assert made.reached.wait(10) and not made.go.is_set() and p.whole.wait(0.2) is False
        # The note is there first: drafted from the transcript of the whole recording, and on the page.
        draft = p.notes.current_draft(1)
        assert c.state == FINAL and draft is not None and [e["text"] for e in p.notes.entries(draft["id"])][:1] == ["made up history [1]"]
        assert "made up history" in text_of(client.get("/consultations/1"))
        sent = p.consultations.upload(1)
        assert sent["result_at"] and sent["job_id"] == "job-1"                    # the transcript from the whole recording is stored
        assert (sent["delete_answer"], sent["gone"], sent["proof"], sent["judged_at"]) == (None, None, None, None)
        assert whole.proof_state(sent) == whole.AWAITED and p.consultations.open_proofs() == [1]
        page = client.get("/consultations/1")
        text = text_of(page)
        assert page.status_code == 200 and AWAITED in text and PROVEN not in text and NOT_PROVEN not in text
        assert words.CLOUD_MARK_RECORDING_SENT in text                            # the mark's line of ruling 52 does not change
        assert not any(w["kind"] == "delete_not_proven" for w in p.consultations.warnings(1))
        assert set(events(p)) == {"recording.sent"}                               # the sending is logged at once; of the delete nothing yet
        assert events(p)["recording.sent"] == "consultation 1: by the tick; the transcript made from it; the service asked to delete it, beside Stop"
    finally:
        made.go.set()
    # No answer at all came of the delete, within its limit of 30 s: not proven, said when it is known.
    assert p.whole.wait() and ("DELETE", JOB, 30.0) in made.limits and upload.DELETE_LIMIT_S == 30.0
    sent = p.consultations.upload(1)
    assert (sent["gone"], sent["proof"]) == (0, "the delete got no answer") and sent["judged_at"] and sent["delete_answer"]["status"] == 0
    assert whole.proof_state(sent) == whole.UNPROVEN and p.consultations.open_proofs() == []
    assert [r["method"] for r in made.requests if r["method"] != "GET"] == ["POST", "DELETE"]          # sent once, deleted once, no ask after no answer
    text = text_of(client.get("/consultations/1"))
    assert FIRST_ALONE in text and AWAITED not in text and PROVEN not in text and NOT_PROVEN in text
    assert events(p)["recording.delete_not_proven"] == "consultation 1: the delete got no answer" and "recording.deleted" not in events(p)


def test_ruling_of_18_nov_each_of_the_three_lines_stands_for_its_state_and_the_lines_address_gives_the_state(tmp_path, clock, server, machine):
    made = Held()
    app, client, local = ticked_app(tmp_path, clock, server, made)
    p = app.state.parts
    try:
        to_final(app, client)
        assert made.reached.wait(10)
        page = client.get("/consultations/1").text
        # Awaited: the owner's sentence; the page asks the app by itself; with no script, one line with a link that loads it again.
        assert SLOT + ASKING in page and f'<p class="mark no-print" id="recording-sent">{AWAITED}</p>' in text_of(client.get("/consultations/1"))
        assert pages.static_address("sent.js") in page
        assert (f'<p class="mark" id="sent-no-script">The page\'s script did not run. <a href="/consultations/1">'
                "Load the page again to see whether the answer has come</a></p>") in text_of(client.get("/consultations/1"))
        assert client.get("/consultations/1/sent").json() == {"state": "awaited", "line": AWAITED}
    finally:
        made.go.set()
    # Proven: his line of ruling 53; nothing is asked any more.
    assert p.whole.wait()
    answer = client.get("/consultations/1/sent")
    assert answer.json() == {"state": "proven", "line": PROVEN} and answer.headers["cache-control"] == "no-store"
    page = client.get("/consultations/1").text
    assert f'<p class="mark no-print" id="recording-sent">{PROVEN}</p>' in text_of(client.get("/consultations/1"))
    assert SLOT + ">" in page and "data-awaited" not in page and "sent.js" not in page and "sent-no-script" not in page
    assert events(p)["recording.deleted"] == "consultation 1: the job: HTTP 404; its transcript: HTTP 404"
    assert not any(w["kind"] == "delete_not_proven" for w in p.consultations.warnings(1))
    # Not proven: the first sentence alone (the warning is the next test's).
    held = Held(after_delete="words")
    app, client, local = ticked_app(tmp_path / "words", clock, server, held)
    held.go.set()
    consult(app, client)
    assert client.get("/consultations/1/sent").json() == {"state": "not_proven", "line": FIRST_ALONE}
    page = client.get("/consultations/1").text
    assert f'<p class="mark no-print" id="recording-sent">{FIRST_ALONE}</p>' in page and "data-awaited" not in page and "sent.js" not in page
    # A consultation whose recording was never sent: no line, no state, nothing asked.
    app, client, c = reviewed(tmp_path / "plain", clock, machine)
    assert client.get("/consultations/1/sent").json() == {"state": "none", "line": None}
    page = client.get("/consultations/1").text
    assert SLOT + ">" in page and 'id="recording-sent"' not in page and "sent.js" not in page


def test_ruling_of_18_nov_the_pages_script_holds_no_sentence_and_asks_two_addresses_that_are_never_use(tmp_path, clock, server):
    script = (Path(pages.__file__).parent / "static" / "sent.js").read_text(encoding="utf-8")
    code = "\n".join(line for line in script.splitlines() if not line.strip().startswith("//"))
    for sentence in (AWAITED, PROVEN, FIRST_ALONE, NOT_PROVEN, words.SENT_NO_SCRIPT, words.SENT_LOAD_AGAIN):
        assert sentence not in script
    # No quoted text in the code holds two words: every word the page shows is the app's.
    assert [quoted for quoted in re.findall(r"'([^'\n]*)'", code) if re.search(r"[A-Za-z]{2,} [A-Za-z]{2,}", quoted)] == []
    assert "dataset.address" in code and "dataset.page" in code and "freshPage.from" in code and "location" not in code      # no load
    # Neither ask is use (15.10 ruling 41): 29 minutes after the login each is answered, and 2 minutes later the lock has fallen.
    app, client, local = ticked_app(tmp_path, clock, server, LongPage())
    consult(app, client)
    for address in ("/consultations/1/sent", "/consultations/1/sent/page"):
        assert log_in(client).status_code == 303
        clock.advance(minutes=29)
        assert client.get(address).status_code == 200, address
        clock.advance(minutes=2)
        answer = client.get("/consultations/1")
        assert answer.status_code == 303 and "/login" in answer.headers["location"], address


def test_ruling_of_18_nov_the_warning_is_added_when_the_proof_fails_after_the_page_was_served_and_approve_is_not_held(tmp_path, clock, server):
    made = Held(after_delete="words")                              # deleted, and the asks still answer with words of the result
    app, client, local = ticked_app(tmp_path, clock, server, made)
    local.script = {"note": [NOTE]}
    p = app.state.parts
    try:
        to_final(app, client)
        assert made.reached.wait(10)
        served = text_of(client.get("/consultations/1"))           # the page the doctor has open
        assert AWAITED in served and NOT_PROVEN not in served
        before = count_on_approve(served)
        # Approve is not held by an answer that is awaited.
        approved = client.post("/consultations/1/note/approve")
        assert approved.status_code == 303 and p.notes.approval(1) is not None, refusal_on(text_of(approved), "approve")
    finally:
        made.go.set()
    assert p.whole.wait()
    assert [w["kind"] for w in p.consultations.warnings(1)].count("delete_not_proven") == 1
    assert client.get("/consultations/1/sent").json() == {"state": "not_proven", "line": FIRST_ALONE}
    # The app's own page, as the page's script asks for it: the warning in its part, the count on Approve read from
    # the record at this moment, the line above the note; and nothing is started for a page that asks by itself.
    listed = [line for line in p.audit.lines() if line.event == "referrals.listed"]
    asked = text_of(client.get("/consultations/1/sent/page"))
    warnings_part = asked.split('<div id="other-warnings" data-part>', 1)[1].split("</div>", 1)[0]
    assert NOT_PROVEN in warnings_part and f'id="recording-sent">{FIRST_ALONE}</p>' in asked and AWAITED not in asked
    number = lambda said: int(re.search(r"\d+", said).group()) if re.search(r"\d+", said) else 0      # noqa: E731
    assert number(count_on_approve(asked)) == number(before) + 1
    assert [line for line in p.audit.lines() if line.event == "referrals.listed"] == listed
    assert events(p)["recording.delete_not_proven"].startswith("consultation 1: the job: ")


def test_ruling_of_18_nov_the_delete_and_each_first_ask_wait_30_seconds_and_the_bench_reads_the_same_code(tmp_path, clock, server):
    made = LongPage()
    app, client, local = ticked_app(tmp_path, clock, server, made)
    consult(app, client)
    after = made.limits[[m for m, path, limit in made.limits].index("DELETE"):]
    assert after == [("DELETE", JOB, 30.0), ("GET", JOB, 30.0), ("GET", TRANSCRIPT, 30.0)]
    # The upload itself, the looks at the job and the read of the transcript keep the upload's own limit.
    assert {limit for m, path, limit in made.limits[:len(made.limits) - 3]} == {None}
    # The bench's upload waits for its proof, as it did, by the same code and the same limits.
    stopwatch, bench = Slept(), MadeUpSpeechmatics()
    up = one(speechmatics_upload, bench, stopwatch)
    assert up["gone"] is True and up["delete"]["status"] == 200 and [limit for m, path, limit in bench.limits if m == "DELETE"] == [30.0]
    assert [limit for m, path, limit in bench.limits[-2:]] == [30.0, 30.0]


def test_ruling_of_18_nov_a_proof_is_taken_up_where_its_record_stands_and_an_answered_ask_is_never_made_again():
    job = {"id": "job-1"}
    answered = {"status": 200, "error": None, "body": {}}
    said = lambda what, status, gone, why: {"what": what, "status": status, "error": None, "body": {}, "gone": gone, "why": why}      # noqa: E731
    # The record holds the delete's answer and the answer of the first ask: the second ask alone is made.
    made, clock = silent(MadeUpSpeechmatics, {})(), Slept()
    made.deleted = True
    up = {"delete": dict(answered), "asked_again": [said("the job", 404, True, "HTTP 404")]}
    upload._delete_and_prove(speechmatics_upload, Http(speechmatics_upload.EU_HOST, made), MADE_UP_KEY, job, [], up, clock.sleep)
    assert [r["method"] for r in made.requests] == ["GET"] and made.asks == [(TRANSCRIPT, 30.0)] and clock.sleeps == []
    assert tries(up) == [("the job", 404, True, 1), ("its transcript", 404, True, 1)] and up["gone"] is True
    assert up["proof"] == "the job: HTTP 404; its transcript: HTTP 404"
    # One try of an ask brought no answer before the app was closed: it gets its second try, with the limit of 10 s.
    made, clock = silent(MadeUpSpeechmatics, {})(), Slept()
    made.deleted = True
    up = {"delete": dict(answered), "asked_again": [said("the job", 0, False, "no answer came"), said("its transcript", 404, True, "HTTP 404")]}
    upload._delete_and_prove(speechmatics_upload, Http(speechmatics_upload.EU_HOST, made), MADE_UP_KEY, job, [], up, clock.sleep)
    assert made.asks == [(JOB, 10.0)] and clock.sleeps == [5.0] and up["gone"] is True
    assert tries(up) == [("the job", 0, False, 1), ("its transcript", 404, True, 1), ("the job", 404, True, 2)]
    # And never a third: with both tries in the record nothing is asked, and it is not proven.
    made, clock = silent(MadeUpSpeechmatics, {})(), Slept()
    made.deleted = True
    up = {"delete": dict(answered), "asked_again": [said("the job", 0, False, "no answer came"), said("its transcript", 404, True, "HTTP 404"),
                                                   {**said("the job", 0, False, "no answer came"), "try": 2}]}
    upload._delete_and_prove(speechmatics_upload, Http(speechmatics_upload.EU_HOST, made), MADE_UP_KEY, job, [], up, clock.sleep)
    assert made.requests == [] and clock.sleeps == [] and up["gone"] is False
    # Each step is told as it comes, so that the record can hold it: the delete, then each try.
    made, clock, told = silent(MadeUpSpeechmatics, {JOB: 1})(), Slept(), []
    up = {"asked_again": []}
    upload._delete_and_prove(speechmatics_upload, Http(speechmatics_upload.EU_HOST, made), MADE_UP_KEY, job, [], up, clock.sleep,
                             note=lambda: told.append((up["delete"]["status"], len(up["asked_again"]))))
    assert told == [(200, 0), (200, 1), (200, 2), (200, 3)] and up["gone"] is True


def test_ruling_of_18_nov_an_open_proof_is_found_and_finished_at_the_next_start_and_a_judged_one_is_not_asked_again(tmp_path, clock, server):
    first = LongPage()
    app, client, local = ticked_app(tmp_path, clock, server, first)
    p = app.state.parts
    p.whole.prove = lambda *given, **named: False                  # as an app closed the moment the transcript was stored
    to_final(app, client)
    assert p.consultations.open_proofs() == [1] and "DELETE" not in [r["method"] for r in first.requests]
    assert AWAITED in text_of(client.get("/consultations/1"))
    # The next start: the delete is sent, since none was answered, then the two asks; the recording is not sent again.
    second = LongPage()
    app2, p2 = next_start(tmp_path, clock, second)
    assert p2.whole.wait()
    assert [(r["method"], r["url"].split("/v2", 1)[1].split("?")[0]) for r in second.requests] == [("DELETE", JOB), ("GET", JOB), ("GET", TRANSCRIPT)]
    assert [limit for m, path, limit in second.limits] == [30.0, 30.0, 30.0]
    sent = p2.consultations.upload(1)
    assert sent["gone"] == 1 and sent["judged_at"] and sent["delete_answer"]["status"] == 200 and p2.consultations.open_proofs() == []
    assert events(p2)["recording.deleted"] == "consultation 1: the job: HTTP 404; its transcript: HTTP 404"
    again = browser(app2)
    log_in(again)
    assert PROVEN in text_of(again.get("/consultations/1")) and AWAITED not in text_of(again.get("/consultations/1"))
    # A start after that: the proof is judged, and nothing is asked.
    third = LongPage()
    app3, p3 = next_start(tmp_path, clock, third)
    assert p3.whole.wait() and third.requests == [] and p3.whole.finish_open(p3.consultations, p3.audit) == []


def test_ruling_of_18_nov_at_the_next_start_a_delete_that_was_answered_is_not_sent_again_and_one_judged_not_proven_is_left(tmp_path, clock, server):
    first = LongPage()
    app, client, local = ticked_app(tmp_path, clock, server, first)
    p = app.state.parts
    p.whole.prove = lambda *given, **named: False
    to_final(app, client)
    # As an app closed after the delete was answered and before the asks: the record holds the delete's answer.
    p.consultations.note_proof(1, {"status": 200, "error": None, "body": {}}, [])
    second = LongPage(after_delete="words")
    second.deleted = True
    app2, p2 = next_start(tmp_path, clock, second)
    assert p2.whole.wait()
    assert [r["method"] for r in second.requests] == ["GET", "GET"]                               # the two asks, and no delete
    sent = p2.consultations.upload(1)
    # The words of the result are read from the transcript the record holds: the asks still answer with them.
    assert sent["gone"] == 0 and sent["judged_at"] and "the answer still holds words of the result" in sent["proof"]
    assert [w["kind"] for w in p2.consultations.warnings(1)].count("delete_not_proven") == 1
    assert events(p2)["recording.delete_not_proven"].startswith("consultation 1: ")
    # Judged not proven after its full tries: the next start asks nothing and adds no second warning.
    third = LongPage()
    app3, p3 = next_start(tmp_path, clock, third)
    assert p3.whole.wait() and third.requests == []
    assert [w["kind"] for w in p3.consultations.warnings(1)].count("delete_not_proven") == 1


def test_ruling_of_18_nov_the_start_is_not_held_by_an_open_proof_and_a_recording_never_ended_is_deleted_too(tmp_path, clock, server):
    first = LongPage()
    app, client, local = ticked_app(tmp_path, clock, server, first)
    p = app.state.parts
    client.post("/consultations/start/1", data=TICKS)
    # As an app closed while the recording was at the service: the row of the upload with the job's name and no end.
    p.consultations.add_upload(1, "tick", "recording.wav", 1234)
    p.consultations.note_upload_job(1, "job-1")
    assert p.consultations.open_proofs() == [1]
    second = Held()
    try:
        app2, p2 = next_start(tmp_path, clock, second)             # the start returns while the service has not answered
        assert second.reached.wait(10) and p2.whole.wait(0.2) is False
        assert whole.proof_state(p2.consultations.upload(1)) == whole.AWAITED
    finally:
        second.go.set()
    assert p2.whole.wait()
    assert [r["method"] for r in second.requests] == ["DELETE", "GET", "GET"]                     # deleted and asked for; never sent again
    assert p2.consultations.upload(1)["gone"] == 1 and p2.consultations.open_proofs() == []
    # With no key in use the service cannot be asked: judged not proven and said, never left open for ever.
    p2.consultations.judge_upload(1, None, None)
    p2.whole._key = lambda: None
    assert p2.whole.finish_open(p2.consultations, p2.audit) == [1] and p2.whole.wait()
    sent = p2.consultations.upload(1)
    assert (sent["gone"], sent["proof"]) == (0, "no key in use: the service could not be asked") and len(second.requests) == 3
    # A consultation deleted while its answer was awaited: the proof never raises, writes no warning for a row that
    # is gone, and says what it found in the log.
    p2.whole._prove(p2.consultations, p2.audit, 99, None)
    assert p2.consultations.warnings(99) == []
    assert "consultation 99: the delete broke: TypeError" in [line.detail for line in p2.audit.lines() if line.event == "recording.delete_not_proven"]


def test_6_5_version_12_holds_the_moment_a_delete_was_judged_and_an_upload_of_version_11_that_ended_reads_as_judged(tmp_path, monkeypatch, clock):
    from openconsult.consult.consultations import Consultations
    from openconsult.db import open_database
    from tests.test_recording_after_stop import TICKED
    path = tmp_path / "openconsult.db"
    monkeypatch.setattr(schema, "VERSION", 11)
    old = open_database(path)
    old.execute("INSERT INTO patient (name, date_of_birth, sex, created_at) VALUES ('Made-up', '1990-01-01', 'F', 't')")
    rows = Consultations(old, clock)
    ids = [rows.start(1, 15, "nemotron", "vllm", None, "tag", None, 2, path=TICKED) for _ in range(4)]
    insert = ("INSERT INTO recording_upload (consultation_id, way, sent_at, file_name, bytes, job_id, result_at, gone, failure) "
              "VALUES (?, 'tick', 'sent', 'recording.wav', 1234, ?, ?, ?, ?)")
    old.execute(insert, (ids[0], "job-a", "result", 1, None))                   # ended, proven gone
    old.execute(insert, (ids[1], "job-b", None, 0, "made-up failure"))          # ended with a failure, the delete not proven
    old.execute(insert, (ids[2], "job-c", None, None, None))                    # the app was closed while it was at the service
    old.execute(insert, (ids[3], None, None, None, "made-up failure"))          # nothing was taken by the service
    old.close()
    monkeypatch.setattr(schema, "VERSION", 12)
    new = open_database(path)
    rows = Consultations(new, clock)
    assert new.version() == 12 and "judged_at" in {c["name"] for c in new.query("PRAGMA table_info(recording_upload)")}
    assert [whole.proof_state(rows.upload(cid)) for cid in ids] == [whole.PROVEN, whole.UNPROVEN, whole.AWAITED, None]
    assert [rows.upload(cid)["judged_at"] for cid in ids] == ["result", "sent", None, None]
    assert rows.open_proofs() == [ids[2]]                                       # the one a start has to finish
    new.close()
