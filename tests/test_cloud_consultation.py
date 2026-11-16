"""A consultation in cloud mode (spec 7.2, 7.3, 10.3, 10.4; 15.13, rulings
5, 15 and 21 and the details of run 9b; 15.10 ruling 36): Start by the
path, the doors of that path held to the end, and no call ever answered
by another path. A made Claude service on this machine, a made speech
worker, a made store, made keys. What a model writes is never asserted."""

from __future__ import annotations

import json

import pytest

from openconsult import words
from openconsult.app import build_app
from openconsult.consult.live import FINAL
from openconsult.llm import claude
from openconsult.llm.claude import ClaudeEngine
from openconsult.settings import connections, store as settings_store
from openconsult.settings.path import CLAUDE, SPEECHMATICS, THIS_COMPUTER, ChosenPath
from openconsult.settings.statement import statement_for
from openconsult.speech.choices import NEMOTRON, SPEECHMATICS as SPEECHMATICS_CHOICE
from openconsult.speech.door import Door as SpeechDoor
from openconsult.web.live import capture_from
from tests.conftest import PORT, browser, log_in, refusal_on, set_up, text_of
from tests.fakes import ALARM_FIRES, ASSESSMENT, NO_DOUBT, FakeEngine, MadeUpWorker
from tests.made_up_store import MadeStore
from tests.test_connect_screens import GOOD, NO_CARD, SUITABLE, MadeTesters, everything_written
from tests.test_review_page import CAPTURE, CHECK, LINES, LOUD, NOTE
from tests.test_start import PATIENT, TICKS
from tests.test_stop import until

HAIKU, SONNET = "claude-haiku-5-5", "claude-sonnet-5-5"
LIST_PATH = "/v1/models?limit=1000"
BOTH_KEYS = {"ANTHROPIC_API_KEY": GOOD, "SPEECHMATICS_API_KEY": GOOD}
BY_FORM = {"time_critical_possible": ALARM_FIRES, "differentials": ASSESSMENT, "doubtful": NO_DOUBT, "subjective": NOTE, "lines": CHECK}


def made_claude(server):
    """A made Claude on this machine: the list of models, and a reply that
    fits whichever form the request carries, named by the model asked."""
    def answer(body):
        if "output_config" not in body:                          # the test of a connection: no form
            text = "made up"
        else:
            properties = body["output_config"]["format"]["schema"]["properties"]
            text = json.dumps(next(reply for name, reply in BY_FORM.items() if name in properties))
        return 200, {"id": "msg_made_up", "type": "message", "role": "assistant", "model": body["model"],
                     "content": [{"type": "text", "text": text}], "stop_reason": "end_turn", "usage": {"input_tokens": 100, "output_tokens": 20}}

    server.routes[LIST_PATH] = (200, {"data": [{"id": tag, "type": "model", "max_input_tokens": 1000000} for tag in (HAIKU, SONNET)]})
    server.routes["/v1/messages"] = answer
    return lambda key: ClaudeEngine(server.address, key, expected=server.address)


def sent(server, job_model=None):
    return [body for path, body in server.received if path == "/v1/messages" and (job_model is None or body["model"] == job_model)]


def cloud_app(tmp_path, clock, server, machine=NO_CARD, held=BOTH_KEYS, tick=True, testers=None):
    store, testers, local = MadeStore(held), testers or MadeTesters(), FakeEngine()
    # The local worker hears the made lines twice, eight pieces apart: a test may run two consultations on it.
    workers = {"speechmatics": MadeUpWorker(live=LINES), "nemotron": MadeUpWorker(live=LINES + [[]] * 6 + LINES)}
    doors = {SPEECHMATICS_CHOICE.name: SpeechDoor(SPEECHMATICS_CHOICE, make_worker=lambda: workers["speechmatics"], installed=lambda: True,
                                                  key_present=lambda: store.held.get("SPEECHMATICS_API_KEY") is not None),
             NEMOTRON.name: SpeechDoor(NEMOTRON, make_worker=lambda: workers["nemotron"], installed=lambda: True)}
    app = build_app(settings_store.build(tmp_path, PORT), machine=machine, clock=clock, engines={"vllm": FakeEngine(version=None), "ollama": local},
                    doors=doors, secure_store=store, testers=testers.both(), claude_engine=made_claude(server))
    client = browser(app)
    set_up(client)
    log_in(client)
    p = app.state.parts
    made = statement_for(p.stored.path(machine.case))
    if tick and made is not None:
        client.post("/statement/tick", data={"sha256": made.sha256, "understand": "yes", "back": "/settings"})
    client.post("/patients", data=PATIENT)
    return app, client, local, workers, testers


def through_stop(app, client, cid=1, pieces=8, answer="S1"):
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


def test_7_3_a_consultation_in_cloud_mode_runs_on_the_doors_of_its_path_and_records_it(tmp_path, clock, server):
    app, client, local, workers, testers = cloud_app(tmp_path, clock, server)
    p = app.state.parts
    page = text_of(client.get("/consultations/start/1"))
    assert f"<th>{words.ROW_SPEECH_IN_USE}</th><td>{words.CHOICE_SPEECHMATICS}</td>" in page          # the path, named in two rows
    assert f"<th>{words.ROW_MODEL_IN_USE}</th><td>{words.CHOICE_CLAUDE}</td>" in page
    started = client.post("/consultations/start/1", data=TICKS)
    assert started.status_code == 303 and started.headers["location"] == "/consultations/1"
    row = p.consultations.get(1)
    assert (row["language_model_path"], row["transcription_path"], row["better_accuracy"]) == (CLAUDE, SPEECHMATICS, 0)
    assert row["statement_sha256"] == statement_for(ChosenPath(CLAUDE, SPEECHMATICS)).sha256           # the text that stood ticked
    assert (row["speech_choice"], row["engine"], row["model_tag"], row["engine_version"], row["model_digest"]) == (
        "speechmatics", "claude", HAIKU, claude.ENGINE_VERSION, claude.NO_DIGEST)                       # R20
    c = through_stop(app, client)
    assert workers["speechmatics"].starts == 1 and workers["nemotron"].starts == 0                     # the speech choice of the path
    # Claude Haiku for the passes and the note, Claude Sonnet for the drug-name call alone (15.10, ruling 36).
    by_job = {call["job"]: call["model_tag"] for call in p.consultations.model_calls(1)}
    assert by_job == {"alarm": HAIKU, "assessment": HAIKU, "drug_name": SONNET, "note": HAIKU}
    assert len(sent(server, SONNET)) == 1 and len(sent(server)) == len(p.consultations.model_calls(1))
    assert local.calls == [] and all(call["engine"] == "claude" for call in p.consultations.model_calls(1))   # 10.4
    final = text_of(client.get("/consultations/1"))
    assert words.MODEL_LINE.format(speech="Speechmatics", model=HAIKU, engine="Claude", version=claude.ENGINE_VERSION) in final
    assert GOOD not in everything_written(p) and GOOD not in client.get("/consultations/1/calls").text  # the key in no table and on no page
    assert all(headers["x-api-key"] == GOOD for headers in server.headers)                             # and in every call's own header alone


def test_7_3_a_consultation_holds_its_path_when_the_setting_changes_under_it(tmp_path, clock, server):
    app, client, local, workers, testers = cloud_app(tmp_path, clock, server, machine=SUITABLE)
    p = app.state.parts
    made = statement_for(ChosenPath(CLAUDE, THIS_COMPUTER))
    client.post("/settings/path/language-model", data={"language_model": CLAUDE, "understand": "yes", "sha256": made.sha256})
    client.post("/consultations/start/1", data=TICKS)
    through_stop(app, client)
    assert p.consultations.get(1)["language_model_path"] == CLAUDE and p.consultations.get(1)["speech_choice"] == "nemotron"
    # The setting goes back to this computer on the page. The next consultation starts there and records it ...
    client.post("/settings/path/language-model", data={"language_model": THIS_COMPUTER})
    client.post("/consultations/start/1", data=TICKS)
    through_stop(app, client, cid=2, answer="none")          # the made worker's lines are spent: I cannot tell
    second = p.consultations.get(2)
    assert (second["language_model_path"], second["engine"], second["statement_sha256"]) == (THIS_COMPUTER, "made-up", None)
    assert {call["engine"] for call in p.consultations.model_calls(2)} == {"made-up"}
    # ... and every later call of the first one still goes by the path it started with: the note drafted again,
    # the check of who spoke, the referral list and a letter.
    before, local_before = len(sent(server)), len(local.calls)
    assert client.post("/consultations/1/lines/2", data={"label": "unsure", "text": "Yes, doctor."}).status_code == 303   # an edit: the note may be drafted again
    assert client.post("/consultations/1/note/draft").status_code == 303
    assert client.post("/consultations/1/who-check").status_code == 303
    p.who_checks.wait(1, 20)
    client.post("/consultations/1/note/approve")
    client.get("/consultations/1")                                                           # the referral list is made at the first view after Approve
    later = [call for call in p.consultations.model_calls(1) if call["job"] in ("note", "label_check", "referrals")]
    assert {call["job"] for call in later} >= {"note", "label_check"} and all(call["engine"] == "claude" for call in later)
    assert len(sent(server)) > before and len(local.calls) == local_before                    # none of them reached this computer's model
    # And the other way: a consultation that started on this computer never calls Claude afterwards.
    made = statement_for(ChosenPath(CLAUDE, THIS_COMPUTER))
    client.post("/settings/path/language-model", data={"language_model": CLAUDE, "understand": "yes", "sha256": made.sha256})
    before, calls_before = len(sent(server)), len(p.consultations.model_calls(2))
    client.post("/consultations/2/lines/2", data={"label": "unsure", "text": "Yes, doctor."})
    assert client.post("/consultations/2/note/draft").status_code == 303
    assert len(p.consultations.model_calls(2)) == calls_before + 1 and p.consultations.model_calls(2)[-1]["engine"] == "made-up"
    assert len(sent(server)) == before


def test_10_4_a_failed_call_to_claude_is_a_failed_call_and_no_local_engine_is_tried(tmp_path, clock, server):
    app, client, local, workers, testers = cloud_app(tmp_path, clock, server)
    p = app.state.parts
    server.routes["/v1/messages"] = (500, {"type": "error", "error": {"type": "api_error", "message": "made up"}})
    client.post("/consultations/start/1", data=TICKS)
    c = through_stop(app, client)
    calls = p.consultations.model_calls(1)
    assert calls and all(call["outcome"] == "unreachable" and call["engine"] == "claude" for call in calls)
    assert local.calls == [] and c.state == FINAL                                             # R30: the consultation went on to its end
    # The key taken out while the app runs: the next call fails plainly, and nothing is sent anywhere.
    p.connections.remove(CLAUDE)
    before = len(server.received)
    client.post("/consultations/1/note/draft")
    last = p.consultations.model_calls(1)[-1]
    assert last["outcome"] == "unreachable" and "Claude is not connected" in last["detail"] and len(server.received) == before
    assert local.calls == []


def disabled_on(page: str) -> bool:
    return 'id="start" aria-describedby="start-refusal" disabled' in page


def test_R15_and_7_2_start_says_on_its_control_why_a_cloud_path_cannot_start_and_no_consultation_begins(tmp_path, clock, server):
    # Not connected: no key in use for the service of the path.
    app, client, local, workers, testers = cloud_app(tmp_path / "a", clock, server, held={})
    page = client.get("/consultations/start/1")
    expected = "Start is not offered: Claude is not connected. Connect it in Settings."
    assert disabled_on(page.text) and refusal_on(page.text, "start") == expected and 'id="start-lead"><a href="/connect/claude">' in page.text
    refused = client.post("/consultations/start/1", data=TICKS)
    assert refused.status_code == 400 and refusal_on(refused.text, "start") == expected and app.state.parts.consultations.get(1) is None
    app, client, local, workers, testers = cloud_app(tmp_path / "b", clock, server, held={"ANTHROPIC_API_KEY": GOOD})
    assert refusal_on(client.get("/consultations/start/1").text, "start") == "Start is not offered: Speechmatics is not connected. Connect it in Settings."
    # Connected, and the statement of the path not ticked.
    app, client, local, workers, testers = cloud_app(tmp_path / "c", clock, server, tick=False)
    page = client.get("/consultations/start/1")
    assert refusal_on(page.text, "start") == words.START_STATEMENT and testers.asked.count((CLAUDE, GOOD)) == 1   # tested at start, not at this view
    # Ticked, and a connection the consultation needs is down now: said with its exact reason, at the view and at Start.
    app, client, local, workers, testers = cloud_app(tmp_path / "d", clock, server)
    tested_before = len(testers.asked)
    assert not disabled_on(client.get("/consultations/start/1").text)
    assert len(testers.asked) == tested_before + 2                                            # each view tests both connections (7.2)
    testers.fail[SPEECHMATICS] = "no_internet"
    page = client.get("/consultations/start/1")
    expected = "Start is not offered: Speechmatics could not be reached. Check the internet connection and try again."
    assert disabled_on(page.text) and refusal_on(page.text, "start") == expected
    refused = client.post("/consultations/start/1", data=TICKS)
    assert refused.status_code == 400 and refusal_on(refused.text, "start") == expected
    assert app.state.parts.consultations.get(1) is None and app.state.parts.running == {}     # a consultation never begins on a connection that is down
    # A word of the statement changed by a later release: the tick no longer stands, and Start says so.
    del testers.fail[SPEECHMATICS]
    app.state.parts.stored.tick_statement("0" * 64, ChosenPath(CLAUDE, SPEECHMATICS))
    assert refusal_on(client.get("/consultations/start/1").text, "start") == words.START_STATEMENT


def test_15_8_ruling_1_the_test_of_the_connection_made_at_start_is_on_the_page_of_calls_of_the_consultation_it_began(tmp_path, clock, server):
    holder = {}
    testers = MadeTesters()
    real = lambda key: connections.test_claude(key, holder.get("record"), made_claude(server)(key))    # noqa: E731 - the app's own test, on the made service
    testers.both = lambda: {CLAUDE: real, SPEECHMATICS: testers.tester(SPEECHMATICS)}
    app, client, local, workers, _ = cloud_app(tmp_path, clock, server, testers=testers)
    p = app.state.parts
    holder["record"] = p.calls
    client.post("/consultations/start/1", data=TICKS)
    through_stop(app, client)
    tests = [call for call in p.consultations.model_calls(1) if call["job"] == "connection_test"]
    assert len(tests) == 2 and sorted(json.loads(call["request"])["model"] for call in tests) == [HAIKU, SONNET]
    page = text_of(client.get("/consultations/1/calls"))
    assert page.count("the test of the connection to Claude, at Start") == 2 and "Connection test. Reply with OK." in page
    # A test made at a view of the Start screen began no consultation, so it is tied to none.
    client.get("/consultations/start/1")
    untied = [row for row in p.calls.rows() if row["job"] == "connection_test" and row["consultation_id"] is None]
    assert len(untied) >= 2 and len([c for c in p.consultations.model_calls(1) if c["job"] == "connection_test"]) == 2
