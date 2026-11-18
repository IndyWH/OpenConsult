"""The recording sent after Stop (spec 15.9, rulings 9, 28, 36 and 42;
15.10 ruling 21; 15.13, rulings 29 and 33 and the details of run 9b): by
the tick for better accuracy or by the one press after a lost connection,
never by itself; the delete asked and its proof kept. A made upload
service inside the suite; nothing here opens a connection."""

from __future__ import annotations

import json

import pytest

from openconsult import words
from openconsult.consult import stop, whole
from openconsult.consult.live import FINAL
from openconsult.consult.whole import WholeRecording
from openconsult.settings.path import CLAUDE, SPEECHMATICS, THIS_COMPUTER, ChosenPath
from openconsult.settings.statement import statement_for
from openconsult.speech import upload
from openconsult.speech.upload import Answer
from openconsult.web.live import capture_from
from tests.conftest import refusal_on, text_of
from tests.made_up_store import MadeStore
from tests.made_up_upload_services import MadeUpSpeechmatics
from tests.test_cloud_consultation import BOTH_KEYS, cloud_app
from tests.test_connect_screens import GOOD, SUITABLE, everything_written
from tests.test_lost_connection import lost_and_found
from tests.test_review_page import CAPTURE, LOUD
from tests.test_start import TICKS
from tests.test_stop import until

TICKED = ChosenPath(THIS_COMPUTER, THIS_COMPUTER, better_accuracy=True)
FIRST_WORDS = " ".join(f"first{n}" for n in range(40))
SECOND_WORDS = " ".join(f"second{n}" for n in range(40))


class LongPage(MadeUpSpeechmatics):
    """The made service with a page long enough for a note: 40 words of one speaker, then 40 of the other.
    mode: submit STATUS (the job is not taken), rejected (the job ends as rejected), never (the job never ends)."""

    def __init__(self, mode: str = "", **kwargs):
        super().__init__(**kwargs)
        self.mode = mode.split()

    def transcript(self) -> dict:
        made = super().transcript()
        results, t = [], 1.0
        for speaker, text in (("S1", FIRST_WORDS), ("S2", SECOND_WORDS)):
            for word in text.split():
                results.append({"type": "word", "start_time": t, "end_time": t + 0.2, "alternatives": [{"content": word, "confidence": 0.9, "speaker": speaker}]})
                t += 0.3
            results.append({"type": "punctuation", "start_time": t, "end_time": t, "is_eos": True, "alternatives": [{"content": ".", "speaker": speaker}]})
        return {**made, "results": results}

    def __call__(self, method, url, headers, body):
        path = url.split("/v2", 1)[1]
        if self.mode[:1] == ["submit"] and method == "POST":
            self.requests.append({"method": method, "url": url, "headers": dict(headers), "body": body})
            return Answer(int(self.mode[1]), b"{}") if self.mode[1] != "0" else Answer(0, b"", "URLError")
        answer = super().__call__(method, url, headers, body)
        if method == "GET" and path == "/jobs/job-1" and not self.deleted and self.mode in (["rejected"], ["never"]):
            status = "rejected" if self.mode == ["rejected"] else "running"
            return Answer(200, json.dumps({"job": {"id": "job-1", "status": status}}).encode())
        return answer


def ticked_app(tmp_path, clock, server, made, path=TICKED, held=BOTH_KEYS):
    """An app on a suitable card whose path holds the tick, ticked; its sender is the made service, and it never sleeps."""
    app, client, local, workers, testers = cloud_app(tmp_path, clock, server, machine=SUITABLE, held=held)
    p = app.state.parts
    p.stored.set_path("suitable", path)
    if statement_for(path) is not None:
        p.stored.tick_statement(statement_for(path).sha256, path)
    ticks = {"t": 0.0}

    def clock_s():
        ticks["t"] += 1.0                                      # each look at the clock is a second later: no test waits
        return ticks["t"]

    p.whole = WholeRecording(lambda: p.connections.key(SPEECHMATICS), made, sleep=lambda s: None, clock=clock_s)
    return app, client, local


def consult(app, client, cid=1, answer="S1", pieces=8):
    client.post("/consultations/start/1", data=TICKS)
    c = app.state.parts.running[cid]
    c.begin_sound(capture_from(CAPTURE))
    for _ in range(pieces):
        c.sound(LOUD)
        c.wait_for_pass()
    client.post(f"/consultations/{cid}/stop")
    assert until(lambda: c.stop_stage == "who_spoke")
    client.post(f"/consultations/{cid}/speakers", data={"speaker": answer})
    assert until(lambda: c.state == FINAL)
    return c


def test_15_9_ruling_36_with_the_tick_the_recording_is_sent_once_after_stop_and_the_services_lines_become_the_final_transcript(tmp_path, clock, server):
    made = LongPage()
    app, client, local = ticked_app(tmp_path, clock, server, made)
    p = app.state.parts
    c = consult(app, client)
    row = p.consultations.get(1)
    assert (row["transcription_path"], row["better_accuracy"], row["speech_choice"]) == (THIS_COMPUTER, 1, "nemotron")
    # One upload, to the EU address, under a plain name, with the request the bench sent: no number of speakers.
    posts = [r for r in made.requests if r["method"] == "POST"]
    assert len(posts) == 1 and posts[0]["url"] == "https://eu1.asr.api.speechmatics.com/v2/jobs"
    body = posts[0]["body"]
    assert b'filename="recording.wav"' in body and json.dumps({"type": "transcription", "transcription_config": {
        "language": "en", "model": "enhanced", "domain": "medical", "diarization": "speaker"}}).encode() in body
    assert b"speakers" not in body.split(b"RIFF")[0] and (tmp_path / "recordings" / row["recording_file"]).read_bytes() in body
    assert all(r["headers"]["Authorization"] == f"Bearer {GOOD}" for r in made.requests)
    # The service's lines are the final transcript, words and speakers; the live lines stay as what was heard live.
    final = p.consultations.transcript_lines(1)
    assert [(r["n"], r["raw_speaker"], r["text"], r["label"]) for r in final] == [(1, "S1", FIRST_WORDS + ".", "doctor"), (2, "S2", SECOND_WORDS + ".", "patient")]
    assert [l["text"] for l in p.consultations.live_lines(1)] != [r["text"] for r in final] and len(p.consultations.live_lines(1)) == 2
    # 15.9 ruling 28: the delete asked as soon as the result was held, the job asked for again, each answer kept.
    sent = p.consultations.upload(1)
    assert (sent["way"], sent["file_name"], sent["job_id"], sent["gone"], sent["failure"]) == ("tick", "recording.wav", "job-1", 1, None)
    assert sent["delete_answer"]["status"] == 200 and [(a["what"], a["status"], a["gone"]) for a in sent["asked_again"]] == [
        ("the job", 404, True), ("its transcript", 404, True)]
    assert sent["proof"] == "the job: HTTP 404; its transcript: HTTP 404" and sent["result_at"] and sent["applied"]["domain"] == "medical"
    methods = [r["method"] for r in made.requests]
    assert methods.index("DELETE") > methods.index("POST") and methods[-2:] == ["GET", "GET"]
    # 15.10 ruling 21: the drug-name call read the lines that became final.
    drug_call = [call for call in local.calls if call.job == "drug_name"]
    assert len(drug_call) == 1 and "first0" in drug_call[0].user and "second39" in drug_call[0].user
    # The review page says where the transcript came from; the mark's third line says that the recording went (15.13,
    # ruling 52: by then it has gone, so goes would be untrue); the log holds the sending, never the key.
    page = text_of(client.get("/consultations/1"))
    assert words.UPLOAD_MADE in page and words.CLOUD_MARK_RECORDING_SENT in page and words.CLOUD_MARK_RECORDING not in page
    assert words.CLOUD_MARK_SOUND not in page
    assert not any(w["kind"] == "delete_not_proven" for w in p.consultations.warnings(1))
    assert next(l.detail for l in p.audit.lines() if l.event == "recording.sent") == (
        "consultation 1: by the tick; the transcript made from it; deleted and proven gone")
    assert GOOD not in everything_written(p)


def test_15_9_ruling_36_the_recording_is_never_sent_without_the_tick_or_the_press(tmp_path, clock, server):
    made = LongPage()
    app, client, local = ticked_app(tmp_path / "a", clock, server, made, path=ChosenPath(THIS_COMPUTER, THIS_COMPUTER))
    consult(app, client)
    assert made.requests == [] and app.state.parts.consultations.upload(1) is None            # no tick: nothing leaves


def test_15_9_ruling_36_the_tick_does_not_count_where_the_transcription_runs_in_the_cloud_nothing_is_sent_a_second_time(tmp_path, clock, server):
    made = LongPage()
    app, client, local = ticked_app(tmp_path / "b", clock, server, made, path=ChosenPath(THIS_COMPUTER, SPEECHMATICS, better_accuracy=True))
    consult(app, client)
    assert made.requests == [] and app.state.parts.consultations.get(1)["better_accuracy"] == 0


def test_7_3_the_tick_is_read_at_start_and_held_taken_off_during_the_consultation_its_recording_is_still_sent(tmp_path, clock, server):
    made = LongPage()
    app, client, local = ticked_app(tmp_path / "c", clock, server, made)
    p = app.state.parts
    client.post("/consultations/start/1", data=TICKS)
    p.stored.set_path("suitable", ChosenPath(THIS_COMPUTER, THIS_COMPUTER))
    c = p.running[1]
    c.begin_sound(capture_from(CAPTURE))
    c.sound(LOUD)
    client.post("/consultations/1/stop")
    assert until(lambda: c.stop_stage == "who_spoke") and len([r for r in made.requests if r["method"] == "POST"]) == 1
    client.post("/consultations/1/speakers", data={"speaker": "S1"})
    assert until(lambda: c.state == FINAL)


def test_15_13_ruling_33_the_tick_is_saved_only_with_speechmatics_connected_and_its_lines_ticked_and_is_not_offered_in_cloud_transcription(tmp_path, clock, server):
    app, client, local, workers, testers = cloud_app(tmp_path, clock, server, machine=SUITABLE, held={})
    p = app.state.parts
    page = client.get("/settings").text
    assert 'id="better-accuracy"' in page and words.BETTER_ACCURACY in text_of(client.get("/settings")) and 'name="better_accuracy" value="yes">' in page
    refused = client.post("/settings/better-accuracy", data={"better_accuracy": "yes"})
    assert refused.status_code == 400 and refusal_on(refused.text, "save-better-accuracy") == "Connect Speechmatics first."
    client.post("/connect/speechmatics", data={"key": GOOD})
    shown = client.post("/settings/better-accuracy", data={"better_accuracy": "yes"})
    made = statement_for(TICKED)
    said = text_of(shown)
    assert refusal_on(shown.text, "save-better-accuracy") == words.STATEMENT_TICK_FIRST and not p.stored.path("suitable").better_accuracy
    assert "Sending the recording after Stop" in said and "I understand that this recording leaves this computer after Stop." in said
    assert words.CLOUD_SENT_RECORDING in said and words.CLOUD_SPEECHMATICS_WHOLE_KEPT in said and "19 US cents" in said and "20 US cents" not in said
    saved = client.post("/settings/better-accuracy", data={"better_accuracy": "yes", "understand": "yes", "sha256": made.sha256})
    assert saved.status_code == 303 and p.stored.path("suitable") == TICKED and p.stored.ticked(made)
    assert [l.detail for l in p.audit.lines() if l.event == "setting.changed"] == ["better_accuracy from off to on"]
    assert 'name="better_accuracy" value="yes" checked>' in client.get("/settings").text
    # Taken off again: nothing leaves this computer, so it is saved at once.
    assert client.post("/settings/better-accuracy", data={}).status_code == 303 and not p.stored.path("suitable").better_accuracy
    # In cloud transcription the tick is not offered, and a post made anyway changes nothing.
    both = statement_for(ChosenPath(THIS_COMPUTER, SPEECHMATICS))
    client.post("/settings/path/transcription", data={"transcription": SPEECHMATICS, "understand": "yes", "sha256": both.sha256})
    assert 'id="better-accuracy"' not in client.get("/settings").text
    assert client.post("/settings/better-accuracy", data={"better_accuracy": "yes"}).headers["location"] == "/settings#transcription"
    assert not p.stored.path("suitable").better_accuracy


@pytest.mark.parametrize("after_delete, delete_status", [("words", 200), ("error", 200), ("gone", 500)])
def test_details_of_9b_a_delete_that_is_not_proven_is_said_on_the_review_page_in_the_owners_words_and_written_to_the_log(tmp_path, clock, server, after_delete, delete_status):
    made = LongPage(after_delete=after_delete, delete_status=delete_status)
    app, client, local = ticked_app(tmp_path, clock, server, made)
    p = app.state.parts
    consult(app, client)
    sent = p.consultations.upload(1)
    assert sent["gone"] == 0 and sent["result_at"] and sent["delete_answer"]["status"] == delete_status
    assert [r["text"] for r in p.consultations.transcript_lines(1)] == [FIRST_WORDS + ".", SECOND_WORDS + "."]    # the transcript is still used
    page = text_of(client.get("/consultations/1"))
    owners = ("OpenConsult asked Speechmatics to delete the recording and could not confirm that it is gone. "
              "Its own pages say that it deletes such a recording itself after 7 days.")
    assert owners in page and words.UPLOAD_MADE_ONLY in page and words.UPLOAD_MADE not in page
    events = {l.event: l.detail for l in p.audit.lines()}
    assert events["recording.delete_not_proven"].startswith("consultation 1: ") and events["recording.sent"].endswith("the delete not proven")
    assert FIRST_WORDS.split()[0] not in events["recording.delete_not_proven"]                # counts and states, never a word of the page


FAILURES = [
    ("submit 401", "Speechmatics refused the key. Check the key and try again.", False),
    ("submit 402", "Speechmatics refused to start: the account has no credit left.", False),
    ("submit 0", "Speechmatics could not be reached. Check the internet connection and try again.", False),
    ("submit 500", "Speechmatics is not answering. Try again later.", False),
    ("rejected", "Speechmatics is not answering. Try again later.", True),
    ("never", "Speechmatics did not answer in 120 seconds.", True),       # the limit for two seconds of sound: 120.5 s
]


@pytest.mark.parametrize("mode, reason, job_taken", FAILURES)
def test_details_of_9b_each_failure_leaves_the_live_lines_final_says_why_sends_nothing_again_and_leaves_no_job_without_a_delete(tmp_path, clock, server, mode, reason, job_taken):
    made = LongPage(mode)
    app, client, local = ticked_app(tmp_path, clock, server, made)
    p = app.state.parts
    c = consult(app, client)
    assert [r["text"] for r in p.consultations.transcript_lines(1)] == [l["text"] for l in p.consultations.live_lines(1)]   # the live lines stay final
    sent = p.consultations.upload(1)
    assert sent["failure"] == reason and sent["result_at"] is None
    assert words.UPLOAD_FAILED.format(detail=reason) in text_of(client.get("/consultations/1"))
    assert len([r for r in made.requests if r["method"] == "POST"]) == 1                       # sent once, and never again by itself
    # Review point 13: whenever the service took a job, a delete was asked and its answer kept; where it took none, none is owed.
    deletes = [r for r in made.requests if r["method"] == "DELETE"]
    assert len(deletes) == (1 if job_taken else 0)
    if job_taken:
        assert sent["job_id"] == "job-1" and sent["delete_answer"]["status"] == 200 and sent["gone"] == 1 and len(sent["asked_again"]) == 2
    else:
        assert sent["job_id"] is None and sent["proof"] == "nothing was taken by the service"
    assert c.state == FINAL and GOOD not in everything_written(p)


def test_details_of_9b_no_key_at_stop_leaves_the_live_lines_final_and_sends_nothing(tmp_path, clock, server):
    made = LongPage()
    app, client, local = ticked_app(tmp_path / "a", clock, server, made)
    p = app.state.parts
    client.post("/consultations/start/1", data=TICKS)
    p.connections.remove(SPEECHMATICS)                                                         # the key taken out during the consultation
    c = p.running[1]
    c.begin_sound(capture_from(CAPTURE))
    c.sound(LOUD)
    client.post("/consultations/1/stop")
    assert until(lambda: c.stop_stage == "who_spoke")
    assert made.requests == [] and p.consultations.upload(1)["failure"] == "Speechmatics is not connected."
    client.post("/consultations/1/speakers", data={"speaker": "none"})
    assert until(lambda: c.state == FINAL)


def test_details_of_9b_a_result_that_names_another_model_than_asked_leaves_the_live_lines_final_and_its_job_is_deleted(tmp_path, clock, server):
    wrong = LongPage(model="standard")
    app, client, local = ticked_app(tmp_path / "b", clock, server, wrong)
    consult(app, client)
    sent = app.state.parts.consultations.upload(1)
    assert sent["failure"] == "Speechmatics did not use the settings that were asked for." and sent["gone"] == 1
    assert [r["text"] for r in app.state.parts.consultations.transcript_lines(1)] != [FIRST_WORDS + ".", SECOND_WORDS + "."]
    assert whole.limit_s(900) == 345.0 and whole.limit_s(8.0) == 122.0                         # two minutes and a quarter of the recording


def test_15_9_ruling_9_the_upload_goes_to_the_eu_address_and_any_other_is_refused_before_a_connection():
    made = LongPage()
    sender = WholeRecording(lambda: GOOD, made)
    for url in ("https://asr.api.speechmatics.com/v2/jobs", "https://us1.asr.api.speechmatics.com/v2/jobs",
                "http://eu1.asr.api.speechmatics.com/v2/jobs", "https://eu1.asr.api.speechmatics.com.example/v2/jobs"):
        with pytest.raises(upload.AddressRefused):
            sender.http().request("POST", url, {}, b"")
    assert made.requests == [] and sender.http().eu_host == "eu1.asr.api.speechmatics.com"


def test_15_13_ruling_29_after_a_lost_connection_the_question_at_stop_waits_and_each_press_does_what_it_says(tmp_path, clock, server, monkeypatch):
    # Go on without: nothing is sent.
    made = LongPage()
    app, client, c, worker, now = lost_and_found(tmp_path / "a", clock, server, monkeypatch)
    p = app.state.parts
    p.whole = c.whole = WholeRecording(lambda: p.connections.key(SPEECHMATICS), made, sleep=lambda s: None)
    client.post("/consultations/1/stop")
    assert until(lambda: c.stop_stage == "lost")
    page = client.get("/consultations/1")
    said = text_of(page)
    at_the_press = statement_for(ChosenPath(CLAUDE, SPEECHMATICS), at_the_press=True)
    assert words.LOST_TITLE in said and "The connection was lost from 0.8 to 0.8 s, so that part has no transcript." in said
    assert words.CLOUD_SENT_RECORDING in said and words.CLOUD_SPEECHMATICS_WHOLE_KEPT in said and "19 US cents" in said and "20 US cents" in said
    assert 'id="send-whole" name="send" value="yes"' in page.text and 'id="go-on-without" name="send" value="no"' in page.text
    assert 'http-equiv="refresh"' not in page.text and made.requests == []                     # it waits: nothing moves and nothing is sent
    refused = client.post("/consultations/1/whole", data={})
    assert refused.status_code == 400 and refusal_on(refused.text, "send-whole") == words.PICK_ONE and c.send_after_loss is None
    client.post("/consultations/1/whole", data={"send": "no"})
    assert until(lambda: c.stop_stage == "who_spoke") and made.requests == [] and p.consultations.upload(1) is None
    assert next(l.detail for l in p.audit.lines() if l.event == "recording.pressed") == "consultation 1: go on without"
    client.post("/consultations/1/speakers", data={"speaker": "S1"})
    assert until(lambda: c.state == FINAL)


def test_15_13_ruling_29_the_one_press_sends_the_recording_once_for_the_whole_transcript_with_one_set_of_speakers(tmp_path, clock, server, monkeypatch):
    made = LongPage()
    at_the_press = statement_for(ChosenPath(CLAUDE, SPEECHMATICS), at_the_press=True)
    app, client, c, worker, now = lost_and_found(tmp_path / "b", clock, server, monkeypatch)
    p = app.state.parts
    p.whole = c.whole = WholeRecording(lambda: p.connections.key(SPEECHMATICS), made, sleep=lambda s: None)
    client.post("/consultations/1/stop")
    assert until(lambda: c.stop_stage == "lost")
    client.post("/consultations/1/whole", data={"send": "yes", "sha256": at_the_press.sha256})
    assert until(lambda: c.stop_stage == "who_spoke")
    assert len([r for r in made.requests if r["method"] == "POST"]) == 1 and p.consultations.upload(1)["way"] == "press"
    assert next(l.detail for l in p.audit.lines() if l.event == "recording.pressed") == (
        f"consultation 1: send the recording once; the statement shown, sha256 {at_the_press.sha256}")
    question = client.get("/consultations/1")
    assert 'name="speaker" value="S1"' in question.text and 'name="speaker_1"' not in question.text
    client.post("/consultations/1/speakers", data={"speaker": "S1"})
    assert until(lambda: c.state == FINAL)
    assert [r["text"] for r in p.consultations.transcript_lines(1)] == [FIRST_WORDS + ".", SECOND_WORDS + "."]
    assert not any(w["kind"] == "no_transcript" for w in p.consultations.warnings(1))          # the whole transcript has no such stretch
    review = text_of(client.get("/consultations/1"))
    assert words.CLOUD_MARK_RECORDING_SENT in review and words.UPLOAD_MADE in review and words.CLOUD_MARK_SOUND in review
    assert not stop.press(c, True)                                                             # a press after its time changes nothing


def test_review_point_13_a_consultation_found_at_the_upload_after_a_restart_is_not_sent_again_and_the_delete_owed_is_asked(tmp_path, clock, server):
    made = LongPage()
    app, client, local = ticked_app(tmp_path, clock, server, made)
    p = app.state.parts
    client.post("/consultations/start/1", data=TICKS)
    c = p.running[1]
    c.begin_sound(capture_from(CAPTURE))
    c.sound(LOUD)
    # As a restart would find it: the row of the upload with the job's name, written the moment the service took it, and no end.
    p.consultations.add_upload(1, "tick", "recording.wav", 1234)
    p.consultations.note_upload_job(1, "job-1")
    client.post("/consultations/1/stop")
    assert until(lambda: c.stop_stage == "who_spoke")
    assert [r["method"] for r in made.requests] == ["DELETE", "GET", "GET"]                    # no upload: the delete, and the job asked for again
    sent = p.consultations.upload(1)
    assert sent["failure"] == words.UPLOAD_APP_CLOSED and sent["gone"] == 1 and sent["delete_answer"]["status"] == 200


def test_review_point_8_start_is_offered_with_the_tick_set_and_speechmatics_down_and_the_screen_says_so_plainly(tmp_path, clock, server):
    app, client, local, workers, testers = cloud_app(tmp_path, clock, server, machine=SUITABLE)
    p = app.state.parts
    p.stored.set_path("suitable", TICKED)
    p.stored.tick_statement(statement_for(TICKED).sha256, TICKED)
    testers.fail[SPEECHMATICS] = "no_internet"
    page = client.get("/consultations/start/1")
    assert 'id="start" aria-describedby="start-refusal" disabled' not in page.text and refusal_on(page.text, "start") == ""
    assert ("Speechmatics cannot be reached now: Speechmatics could not be reached. Check the internet connection and try again. "
            "The consultation can start. The better transcript may not be made after Stop.") in text_of(page)
    assert client.post("/consultations/start/1", data=TICKS).status_code == 303 and p.consultations.get(1)["better_accuracy"] == 1
