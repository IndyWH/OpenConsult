"""A consultation deleted while the delete of its recording at the service
is awaited (the owner's ruling of 20 Nov 2026, 08:14; mail 5 of run 9c).
His word A to this: Delete is never refused. The app keeps the job's name
and the state of its delete apart from the consultation, and nothing else:
no patient, no consultation's number, no word, no time of the
consultation. The thread that is asking goes on; the next start finds what
is kept and finishes it by the same rule and limits; when it is proven
gone or judged, the kept name is dropped, and the audit log says so in one
line that names no patient. Made services, no model, no internet."""

from __future__ import annotations

import json

import pytest

from openconsult import schema, words
from openconsult.consult import whole
from openconsult.consult.session_rows import LEFT_TRY
from openconsult.db import open_database
from openconsult.speech import speechmatics_upload, upload
from openconsult.speech.upload import Http
from tests.conftest import text_of
from tests.made_up_upload_services import MADE_UP_KEY, MadeUpSpeechmatics
from tests.test_delete_beside_stop import Held, events, next_start, to_final
from tests.test_recording_after_stop import LongPage, ticked_app
from tests.test_second_ask import JOB, TRANSCRIPT, Slept, silent

DROPPED = "the job's name is no longer kept"
GONE = f"the job: HTTP 404; its transcript: HTTP 404; {DROPPED}"


def kept(p) -> list[dict]:
    return [dict(row) for row in p.db.query("SELECT * FROM recording_left")]


def delete(client, cid=1):
    """The doctor's two presses: Delete, then the answer to the one question."""
    asked = client.post(f"/consultations/{cid}/delete")
    assert asked.status_code == 200 and words.DELETE_CONSULTATION_QUESTION.split("{")[0] in text_of(asked)
    return client.post(f"/consultations/{cid}/delete", data={"confirm": "yes"})


def asked(made) -> list[tuple]:
    return [(r["method"], r["url"].split("/v2", 1)[1].split("?")[0]) for r in made.requests if r["method"] != "POST" and "/jobs?" not in r["url"]]


def after_the_upload(made) -> list[tuple]:
    """The requests from the delete on: what is asked of the service once the transcript is read."""
    found = asked(made)
    return found[found.index(("DELETE", JOB)):] if ("DELETE", JOB) in found else []


def test_ruling_of_20_nov_delete_is_not_refused_while_the_answer_is_awaited_and_only_the_jobs_name_and_its_state_are_kept(tmp_path, clock, server):
    made = Held()
    app, client, local = ticked_app(tmp_path, clock, server, made)
    p = app.state.parts
    try:
        to_final(app, client)
        assert made.reached.wait(10) and whole.proof_state(p.consultations.upload(1)) == whole.AWAITED
        patient = p.patients.get(1)
        gone = delete(client)
        # Delete goes through: the consultation and every row of it are gone, the record of the sending among them.
        assert gone.status_code == 303 and gone.headers["location"] == "/patients/1"
        assert p.consultations.get(1) is None and p.consultations.upload(1) is None and p.consultations.open_proofs() == []
        # Kept apart: the job's name and the state of its delete, and nothing else. No column could hold more.
        assert {c["name"] for c in p.db.query("PRAGMA table_info(recording_left)")} == {"job_id", "delete_status", "asks"}
        assert kept(p) == [{"job_id": "job-1", "delete_status": None, "asks": "[]"}] and p.consultations.left_jobs() == ["job-1"]
        assert patient.name and patient.name not in json.dumps(kept(p))
        # The thread that is asking goes on: no second thread and no second delete are started by the press.
        assert not made.go.is_set() and p.whole.wait(0.2) is False
        assert p.whole.prove_left(p.consultations, p.audit, "job-1", 1) is False
    finally:
        made.go.set()
    assert p.whole.wait()
    assert after_the_upload(made) == [("DELETE", JOB), ("GET", JOB), ("GET", TRANSCRIPT)]                 # deleted once, each ask once
    # Proven gone: the kept name is dropped, and the log says so in one line that names no patient.
    assert kept(p) == [] and p.consultations.left_jobs() == []
    said = [line for line in p.audit.lines() if line.event.startswith("recording.left")]
    assert [(line.event, line.detail) for line in said] == [("recording.left_deleted", GONE)]
    for word in ("patient", "consultation", "job-1", patient.name):
        assert word not in said[0].detail
    # The lines of a consultation that still stands are not written for one that is gone, and no warning is left behind.
    assert "recording.deleted" not in events(p) and "recording.delete_not_proven" not in events(p)
    assert p.db.query_one("SELECT COUNT(*) AS n FROM warning")["n"] == 0
    assert words.EVENTS["recording.left_deleted"] in text_of(client.get("/log"))


def test_ruling_of_20_nov_the_thread_that_is_asking_judges_by_the_words_it_holds_and_says_not_proven_in_the_log_alone(tmp_path, clock, server):
    made = Held(after_delete="words")                              # deleted, and the transcript still answers with its words
    app, client, local = ticked_app(tmp_path, clock, server, made)
    p = app.state.parts
    try:
        to_final(app, client)
        assert made.reached.wait(10)
        assert delete(client).status_code == 303 and kept(p) == [{"job_id": "job-1", "delete_status": None, "asks": "[]"}]
    finally:
        made.go.set()
    assert p.whole.wait() and kept(p) == []                        # judged not proven: the name is dropped all the same
    said = [(line.event, line.detail) for line in p.audit.lines() if line.event.startswith("recording.")]
    assert ("recording.left_not_proven",
            "the job: HTTP 200 with no words of the result; its transcript: the answer still holds words of the result; " + DROPPED) in said
    assert "recording.delete_not_proven" not in events(p) and p.db.query_one("SELECT COUNT(*) AS n FROM warning")["n"] == 0
    assert words.EVENTS["recording.left_not_proven"] in text_of(client.get("/log"))


def test_ruling_of_20_nov_where_no_thread_is_asking_the_delete_at_the_service_is_finished_at_the_press(tmp_path, clock, server):
    made = LongPage()
    app, client, local = ticked_app(tmp_path, clock, server, made)
    p = app.state.parts
    p.whole.prove = lambda *given, **named: False                  # as an app whose thread for this consultation never began
    to_final(app, client)
    assert p.consultations.open_proofs() == [1] and after_the_upload(made) == []
    assert delete(client).status_code == 303
    assert p.whole.wait() and kept(p) == []
    assert after_the_upload(made) == [("DELETE", JOB), ("GET", JOB), ("GET", TRANSCRIPT)]
    assert [limit for m, path, limit in made.limits[-3:]] == [30.0, 30.0, 30.0]                          # the same limits
    assert events(p)["recording.left_deleted"] == GONE


def closed_with_a_job_kept(tmp_path, clock, server, note=None):
    """An app closed with a consultation deleted and its job kept: neither thread ever ran."""
    app, client, local = ticked_app(tmp_path, clock, server, LongPage())
    p = app.state.parts
    p.whole.prove = lambda *given, **named: False
    p.whole.prove_left = lambda *given, **named: False
    to_final(app, client)
    if note is not None:
        p.consultations.note_proof(1, *note)
    assert delete(client).status_code == 303 and p.consultations.left_jobs() == ["job-1"]
    return p


def test_ruling_of_20_nov_the_next_start_finds_what_is_kept_and_finishes_it_and_a_start_after_that_asks_nothing(tmp_path, clock, server):
    first = closed_with_a_job_kept(tmp_path, clock, server)
    assert kept(first) == [{"job_id": "job-1", "delete_status": None, "asks": "[]"}]
    second = LongPage()
    app2, p2 = next_start(tmp_path, clock, second)
    assert p2.whole.wait()
    # The delete is sent, since none was answered, then the two asks, by the same limits; nothing is sent again.
    assert asked(second) == [("DELETE", JOB), ("GET", JOB), ("GET", TRANSCRIPT)] and [limit for m, path, limit in second.limits] == [30.0, 30.0, 30.0]
    assert kept(p2) == [] and events(p2)["recording.left_deleted"] == GONE
    third = LongPage()
    app3, p3 = next_start(tmp_path, clock, third)
    assert p3.whole.wait() and third.requests == [] and p3.consultations.left_jobs() == []
    assert len([line for line in p3.audit.lines() if line.event.startswith("recording.left")]) == 1      # one line, once


def test_ruling_of_20_nov_what_is_kept_holds_no_body_of_an_answer_and_an_answered_ask_is_never_made_again(tmp_path, clock, server):
    # As an app closed after the delete and the first ask were answered: each answer came with a body, and a body may
    # hold a word of the consultation or the time it was made.
    body = {"job": {"id": "job-1", "created_at": "2026-10-04T09:00:00Z", "data_name": "recording.wav"}, "text": "first1 first2 first3"}
    answered = {"status": 200, "error": None, "body": body}
    tried = {"what": "the job", "status": 404, "error": None, "body": body, "gone": True, "why": "HTTP 404"}
    first = closed_with_a_job_kept(tmp_path, clock, server, note=(answered, [tried]))
    row, = kept(first)
    assert (row["job_id"], row["delete_status"]) == ("job-1", 200)
    assert json.loads(row["asks"]) == [{"what": "the job", "status": 404, "gone": True, "why": "HTTP 404"}] and LEFT_TRY == ("what", "status", "gone", "why", "try")
    for word in ("first1", "2026", "recording.wav", "body", "created_at"):
        assert word not in json.dumps(row)
    # The next start takes it up where it stands: no delete, the answered ask not made again, the other asked once.
    second = LongPage()
    second.deleted = True
    app2, p2 = next_start(tmp_path, clock, second)
    assert p2.whole.wait() and asked(second) == [("GET", TRANSCRIPT)]
    assert kept(p2) == [] and events(p2)["recording.left_deleted"] == GONE


@pytest.mark.parametrize("after_delete, why", [
    # The transcript still answers, with its words: once the consultation is deleted the app holds no word to read the
    # answer against, so an answer of 200 proves nothing. Never called gone by an answer that cannot be read.
    ("words", "the job: HTTP 200: the words of the result are no longer held to read the answer against; "
              "its transcript: HTTP 200: the words of the result are no longer held to read the answer against"),
    ("tombstone", "the job: HTTP 200: the words of the result are no longer held to read the answer against; its transcript: HTTP 404"),
])
def test_ruling_of_20_nov_at_a_next_start_only_an_answer_that_the_job_is_gone_proves_it_for_no_word_is_kept(tmp_path, clock, server, after_delete, why):
    closed_with_a_job_kept(tmp_path, clock, server)
    second = LongPage(after_delete=after_delete)
    app2, p2 = next_start(tmp_path, clock, second)
    assert p2.whole.wait() and kept(p2) == []
    assert events(p2)["recording.left_not_proven"] == f"{why}; {DROPPED}" and "recording.left_deleted" not in events(p2)
    # The rule itself is unchanged where the words are held (ruling 44): there the same answers are read against them.
    made, stopwatch = silent(MadeUpSpeechmatics, {})(after_delete=after_delete), Slept()
    made.deleted = True
    up = {"delete": {"status": 200}, "asked_again": []}
    upload._delete_and_prove(speechmatics_upload, Http(speechmatics_upload.EU_HOST, made), MADE_UP_KEY, {"id": "job-1"},
                             [{"text": "the made up page says nine plain words here."}], up, stopwatch.sleep)
    assert up["gone"] is (after_delete == "tombstone")


def test_ruling_of_20_nov_with_no_key_in_use_at_the_next_start_what_is_kept_is_judged_and_dropped_never_left_for_ever(tmp_path, clock, server):
    closed_with_a_job_kept(tmp_path, clock, server)
    second = LongPage()
    app2, p2 = next_start(tmp_path, clock, second)
    assert p2.whole.wait()
    # Kept once more, by hand, and the start's own step run with no key in use.
    p2.db.execute("INSERT INTO recording_left (job_id) VALUES ('job-2')")
    p2.whole._key = lambda: None
    assert p2.whole.finish_open(p2.consultations, p2.audit) == [] and p2.whole.wait()
    assert kept(p2) == [] and len(second.requests) == 3
    assert events(p2)["recording.left_not_proven"] == f"no key in use: the service could not be asked; {DROPPED}"


def test_ruling_of_20_nov_nothing_is_kept_of_a_consultation_whose_delete_is_judged_or_that_sent_nothing(tmp_path, clock, server, machine):
    from tests.test_recording_after_stop import consult
    from tests.test_review_page import reviewed
    # Proven gone before the press.
    app, client, local = ticked_app(tmp_path / "proven", clock, server, LongPage())
    consult(app, client)
    assert whole.proof_state(app.state.parts.consultations.upload(1)) == whole.PROVEN
    assert delete(client).status_code == 303 and kept(app.state.parts) == [] and app.state.parts.whole.wait()
    # Judged not proven before the press: its full tries are made, and it is not asked about again.
    made = LongPage(after_delete="words")
    app, client, local = ticked_app(tmp_path / "not-proven", clock, server, made)
    consult(app, client)
    assert whole.proof_state(app.state.parts.consultations.upload(1)) == whole.UNPROVEN
    before = len(made.requests)
    assert delete(client).status_code == 303 and kept(app.state.parts) == [] and app.state.parts.whole.wait() and len(made.requests) == before
    # The service took nothing: no job, nothing owed.
    made = LongPage(mode="submit 401")
    app, client, local = ticked_app(tmp_path / "refused", clock, server, made)
    consult(app, client)
    assert app.state.parts.consultations.upload(1)["job_id"] is None
    assert delete(client).status_code == 303 and kept(app.state.parts) == []
    # A consultation whose recording was never sent.
    app, client, c = reviewed(tmp_path / "plain", clock, machine)
    assert delete(client).status_code == 303 and kept(app.state.parts) == []
    assert [line.event for line in app.state.parts.audit.lines() if line.event.startswith("recording.left")] == []


COLUMNS = [("job_id", "TEXT"), ("delete_status", "INTEGER"), ("asks", "TEXT")]
# The sha256 of version 12's script of the tables as it stood at 62e7c0a.
SCRIPT_12_AT_62E7C0A = "4df71f77b875f02759d69834ece67bd5ab53ab59e72de5b86485f4de8df2e171"


@pytest.mark.parametrize("met", [11, 12])
def test_6_5_version_13_holds_the_table_of_a_job_kept_apart_and_a_folder_of_version_11_or_12_comes_forward_with_it_empty(tmp_path, monkeypatch, clock, met):
    # The table is a version of its own. The app's command was started from the code of version 12 on 19 Nov 2026,
    # before this table was written: a folder that met version 12 then must come forward, and so must one of 11.
    from openconsult.consult.consultations import Consultations
    from openconsult.consult.session_rows import keep_left
    from tests.test_recording_after_stop import TICKED
    path = tmp_path / "openconsult.db"
    monkeypatch.setattr(schema, "VERSION", met)
    old = open_database(path)
    assert old.version() == met and "recording_left" not in old.tables()       # version 12 as a folder met it before 20 Nov
    old.execute("INSERT INTO patient (name, date_of_birth, sex, created_at) VALUES ('Made-up', '1990-01-01', 'F', 't')")
    cid = Consultations(old, clock).start(1, 15, "nemotron", "vllm", None, "tag", None, 2, path=TICKED)
    old.execute("INSERT INTO recording_upload (consultation_id, way, sent_at, file_name, bytes, job_id) VALUES (?, 'tick', 'sent', 'recording.wav', 1234, 'job-c')", (cid,))
    old.close()
    monkeypatch.setattr(schema, "VERSION", 13)
    new = open_database(path)
    rows = Consultations(new, clock)
    assert new.version() == 13 and "recording_left" in new.tables() and rows.left_jobs() == []
    assert [(c["name"], c["type"]) for c in new.query("PRAGMA table_info(recording_left)")] == COLUMNS
    # The upload that the older version left open is still found, and its job can be kept and dropped in the new table.
    assert rows.open_proofs() == [cid]
    with new.transaction() as con:
        assert keep_left(con, cid) == "job-c"
    assert rows.left("job-c") == {"job_id": "job-c", "delete": None, "asked_again": []} and rows.drop_left("job-c") and not rows.drop_left("job-c")
    new.close()


def test_6_5_a_folder_that_met_the_table_under_version_12_on_20_nov_comes_forward_to_13_with_what_it_keeps(tmp_path, monkeypatch, clock):
    # For some commits of 20 Nov 2026 the table stood in version 12's script, in this same shape. A folder opened
    # between them holds it already, perhaps with a job kept: version 13 makes the table only if it is not there.
    from openconsult.consult.consultations import Consultations
    path = tmp_path / "openconsult.db"
    monkeypatch.setattr(schema, "VERSION", 12)
    old = open_database(path)
    old.execute("CREATE TABLE recording_left (job_id TEXT PRIMARY KEY, delete_status INTEGER, asks TEXT NOT NULL DEFAULT '[]')")
    old.execute("INSERT INTO recording_left (job_id, delete_status) VALUES ('job-k', 200)")
    old.close()
    monkeypatch.setattr(schema, "VERSION", 13)
    new = open_database(path)
    rows = Consultations(new, clock)
    assert new.version() == 13 and [(c["name"], c["type"]) for c in new.query("PRAGMA table_info(recording_left)")] == COLUMNS
    assert rows.left("job-k") == {"job_id": "job-k", "delete": {"status": 200}, "asked_again": []}
    new.close()


def test_6_5_version_12_is_again_what_a_folder_met_before_20_nov_no_table_of_a_job_kept_apart(tmp_path, monkeypatch):
    # The script of version 12 is never changed again once a folder may have met it: it makes no recording_left.
    assert "recording_left" not in schema.MIGRATIONS[12] and "recording_left" in schema.MIGRATIONS[13] and max(schema.MIGRATIONS) == schema.VERSION == 13
    # Its bytes are those of 62e7c0a, the code the app was started from on 19 Nov 2026.
    import hashlib
    assert hashlib.sha256(schema.MIGRATIONS[12].encode("utf-8")).hexdigest() == SCRIPT_12_AT_62E7C0A
    monkeypatch.setattr(schema, "VERSION", 12)
    old = open_database(tmp_path / "openconsult.db")
    assert old.version() == 12 and "recording_left" not in old.tables()
    old.close()
