"""The new-patient form and the Start screen (spec 8.2; 15.10 rulings 9
and 12; R1, R11, R15, R17; D38). Made-up patients, a made-up engine, a
made-up worker behind the speech door."""

import pytest

from openconsult import words
from openconsult.app import build_app
from openconsult.patients.logins import LOCK_AFTER
from openconsult.settings import store
from openconsult.speech.choices import NEMOTRON, WHISPERX_PYANNOTE
from openconsult.speech.door import Door as SpeechDoor
from openconsult.web.consult import INTENDED_MINUTES
from tests.conftest import PORT, browser, log_in, refusal_on, set_up, text_of
from tests.fakes import FakeEngine, MadeUpWorker

PATIENT = {"name": "Made-up Patient", "date_of_birth": "1990-10-21", "sex": "F"}
TICKS = {"right_patient": "yes", "acted": "yes", "intended": "15"}


def door(choice, installed=True):
    return SpeechDoor(choice, make_worker=MadeUpWorker, installed=lambda: installed)


def app_with(tmp_path, clock, machine, nemotron=True, whisperx=False, ollama=None, key=False):
    doors = {NEMOTRON.name: door(NEMOTRON, nemotron), WHISPERX_PYANNOTE.name: door(WHISPERX_PYANNOTE, whisperx)}
    if key:
        from openconsult.speech.choices import SPEECHMATICS
        doors[SPEECHMATICS.name] = SpeechDoor(SPEECHMATICS, make_worker=MadeUpWorker, installed=lambda: True,
                                              key_present=lambda: True)
    engines = {"vllm": FakeEngine(version=None), "ollama": ollama or FakeEngine()}
    app = build_app(store.build(tmp_path, PORT), machine=machine, clock=clock, engines=engines, doors=doors)
    client = browser(app)
    set_up(client)
    log_in(client)
    return app, client


@pytest.fixture
def ready(tmp_path, clock, machine):
    return app_with(tmp_path, clock, machine)


def saved(client, **fields):
    return client.post("/patients", data={**PATIENT, **fields})


def test_R11_a_patient_cannot_be_saved_without_a_name_a_date_of_birth_and_a_sex(ready):
    app, client = ready
    for fields, message in [({"name": " "}, words.PATIENT_NAME_MISSING), ({"date_of_birth": ""}, words.DATE_OF_BIRTH_MISSING),
                            ({"date_of_birth": "2030-01-01"}, words.DATE_OF_BIRTH_BAD), ({"sex": ""}, words.SEX_MISSING)]:
        refused = saved(client, **fields)
        assert refused.status_code == 400 and refusal_on(refused.text, "save-patient") == message
        assert app.state.parts.patients.get(1) is None
    done = saved(client)
    assert done.status_code == 303 and done.headers["location"] == "/consultations/start/1"
    assert app.state.parts.patients.get(1).name == "Made-up Patient"
    assert app.state.parts.audit.lines()[0].event == "patient.saved"


def test_8_1_the_form_says_patients_are_acted_and_is_timed_by_its_own_script(ready):
    app, client = ready
    page = client.get("/patients/new")
    assert words.PATIENT_ACTED_LINE in page.text and "/static/use.js" in page.text
    assert 'http-equiv="refresh"' not in page.text and 'data-seconds-left="1800"' in page.text
    assert client.get("/static/use.js").status_code == 200


def test_R17_the_start_screen_shows_the_three_in_large_type_and_needs_the_right_patient_tick(ready):
    app, client = ready
    saved(client)
    page = text_of(client.get("/consultations/start/1"))
    assert "Made-up Patient" in page and "21 Oct 1990" in page and "35 years old" in page and "Female" in page
    assert "reason for" not in page.lower()                            # no box for the reason for the visit
    refused = client.post("/consultations/start/1", data={**TICKS, "right_patient": ""})
    assert refused.status_code == 400 and refusal_on(refused.text, "start") == words.TICK_BOTH
    assert app.state.parts.consultations.get(1) is None


def test_R1_start_needs_the_acted_tick_and_is_audited(ready, clock):
    app, client = ready
    saved(client)
    refused = client.post("/consultations/start/1", data={**TICKS, "acted": ""})
    assert refusal_on(refused.text, "start") == words.TICK_BOTH and app.state.parts.consultations.get(1) is None
    done = client.post("/consultations/start/1", data=TICKS)
    assert done.status_code == 303 and done.headers["location"] == "/consultations/1"
    row = app.state.parts.consultations.get(1)
    assert row["state"] == "live" and row["speech_choice"] == "nemotron" and row["engine"] == "made-up"
    assert row["model_tag"] == "gemma4:26b-a4b-it-qat" and row["model_digest"] == "made-up-digest"
    assert app.state.parts.audit.lines()[0].event == "consultation.started"
    assert 1 in app.state.parts.running and app.state.parts.logins.consultation_running
    # A live consultation holds the lock off (15.6 ruling 5).
    clock.advance(hours=3)
    assert client.get("/?quiet").status_code == 200


def test_ruling_9_the_intended_time_opens_on_the_time_used_last_and_the_speech_choice_is_named(ready):
    app, client = ready
    saved(client)
    page = client.get("/consultations/start/1").text
    assert '<option value="15" selected>' in page and all(f'value="{m}"' in page for m in INTENDED_MINUTES)
    assert words.ROW_NEMOTRON in text_of(client.get("/consultations/start/1"))
    client.post("/consultations/start/1", data={**TICKS, "intended": "30"})
    assert app.state.parts.consultations.get(1)["intended_minutes"] == 30
    saved(client)
    assert '<option value="30" selected>' in client.get("/consultations/start/2").text
    refused = client.post("/consultations/start/2", data={**TICKS, "intended": "20"})
    assert refused.status_code == 400
    assert client.get("/consultations/start/99").headers["location"] == "/patients/new"


def disabled_on(page: str) -> bool:
    return 'id="start" aria-describedby="start-refusal" disabled' in page


def test_R15_start_is_disabled_with_its_reason_and_a_post_anyway_is_refused(tmp_path, clock, machine):
    cases = {
        "no_model": dict(ollama=FakeEngine(version=None)),
        "unreachable": dict(),
        "no_speech": dict(nemotron=False),
        "cloud_key_only": dict(nemotron=False, key=True),
    }
    for name, kwargs in cases.items():
        app, client = app_with(tmp_path / name, clock, machine, **kwargs)
        if name == "unreachable":
            app.state.parts.engine._version = None          # it answered at start; it does not answer now
        saved(client)
        page = text_of(client.get("/consultations/start/1"))
        assert disabled_on(page), name
        if name == "no_model":
            expected = words.START_NO_MODEL.format(reason=app.state.parts.decisions.language_model.sentence)
        elif name == "unreachable":
            expected = words.START_MODEL_UNREACHABLE.format(engine="made-up")
        else:
            expected = words.START_NO_SPEECH.format(reason=words.SPEECH_REASONS["nemotron_not_installed"] + " "
                                                    + words.SPEECH_REASONS["whisperx_no_room"])
        assert refusal_on(page, "start") == expected, name
        refused = client.post("/consultations/start/1", data=TICKS)
        assert refused.status_code == 400 and refusal_on(refused.text, "start") == expected, name
        assert app.state.parts.consultations.get(1) is None and app.state.parts.running == {}
    # The twin: all green, the control acts; and the WhisperX choice is used only where the room check offers it.
    app, client = app_with(tmp_path / "green", clock, machine)
    saved(client)
    assert not disabled_on(client.get("/consultations/start/1").text)
    assert client.post("/consultations/start/1", data=TICKS).status_code == 303


def test_ruling_12_typing_counts_as_use_and_a_quiet_check_does_not(ready, clock):
    app, client = ready
    seconds = int(LOCK_AFTER.total_seconds())
    clock.advance(minutes=20)
    assert client.post("/use").json() == {"seconds_left": seconds}        # use: the lock moves back
    clock.advance(minutes=20)
    assert client.get("/patients/new?quiet").status_code == 200           # not use
    clock.advance(minutes=10)
    assert client.get("/patients/new?quiet").headers["location"] == "/login?why=locked"
