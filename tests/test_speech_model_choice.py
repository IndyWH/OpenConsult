"""The speech model of this computer (spec 7.3, rule 1; 15.13, the details
of run 9c, with rulings 47 and 57; 15.9, ruling 34; 10.4). Under
Transcription, where This computer is chosen: Nemotron, or WhisperX with
pyannote. Until run 9c the app took Nemotron when it was installed and
the WhisperX choice otherwise, and no page let the doctor choose. Made
workers behind the speech doors; nothing is installed or started."""

from __future__ import annotations

from openconsult import words
from openconsult.app import build_app
from openconsult.settings import store
from openconsult.settings.machine import Card, describe
from openconsult.settings.path import SPEECHMATICS, THIS_COMPUTER, ChosenPath
from openconsult.speech.choices import NEMOTRON, WHISPERX_PYANNOTE
from openconsult.speech.door import Door as SpeechDoor
from tests.conftest import PORT, browser, log_in, refusal_on, set_up, text_of
from tests.fakes import FakeEngine, MadeUpWorker
from tests.test_connect_screens import NO_CARD, SUITABLE
from tests.test_start import PATIENT, TICKS

ROOMY = describe("Linux", "x86_64", [Card("Made-up roomy card", 49140)])          # a card with room for the WhisperX pass at Stop
US_ENGLISH = "Nemotron's English model was trained on US English."
INSTALL = "Not installed. Install it with: uv run openconsult install-speech --choice {name}"


def app_with(tmp_path, clock, machine=ROOMY, nemotron=True, whisperx=True):
    installed = {NEMOTRON.name: nemotron, WHISPERX_PYANNOTE.name: whisperx}
    doors = {choice.name: SpeechDoor(choice, make_worker=MadeUpWorker, installed=lambda name=choice.name: installed[name])
             for choice in (NEMOTRON, WHISPERX_PYANNOTE)}
    app = build_app(store.build(tmp_path, PORT), machine=machine, clock=clock, doors=doors,
                    engines={"vllm": FakeEngine(version=None), "ollama": FakeEngine()})
    client = browser(app)
    set_up(client)
    log_in(client)
    client.post("/patients", data=PATIENT)
    return app, client, installed


def radio(name: str, more: str = "") -> str:
    return f'<input type="radio" name="speech_model" value="{name}"{more}>'


def changes(p) -> list[str]:
    return [l.detail for l in reversed(p.audit.lines()) if l.event == "setting.changed"]


def test_7_3_the_choice_stands_under_transcription_saves_by_itself_is_audited_and_the_next_consultation_runs_on_it(tmp_path, clock):
    app, client, installed = app_with(tmp_path, clock)
    p = app.state.parts
    page = client.get("/settings")
    section = page.text.split('<section class="pane" id="transcription">', 1)[1].split("</section>", 1)[0]
    assert '<form method="post" action="/settings/speech-model" id="speech-model" data-saves data-stay>' in section   # it saves by itself (ruling 47)
    assert 'id="save-speech-model" aria-describedby="save-speech-model-refusal" data-save>' in section               # and with no script by its Save
    assert words.SPEECH_MODEL_LEGEND in section and section.index('name="transcription"') < section.index('name="speech_model"')
    # Nemotron is the choice until the doctor changes it (15.9, ruling 34), with the line on its English beside it.
    assert radio("nemotron", " checked") in section and radio("whisperx_pyannote") in section
    assert f'id="speech-model-nemotron-note">{US_ENGLISH}</p>' in text_of(page) and US_ENGLISH == words.NEMOTRON_US_ENGLISH
    assert section.index(words.SPEECH_MODEL_LEGEND) < section.index(words.BETTER_ACCURACY)       # the tick for better accuracy is offered with either
    # A consultation on the choice as it stands, then the choice changed during it.
    client.post("/consultations/start/1", data=TICKS)
    saved = client.post("/settings/speech-model", data={"speech_model": "whisperx_pyannote", "place": "keep"})
    assert saved.status_code == 303 and saved.headers["location"] == "/settings?done=path&at=speech-model"
    assert p.stored.speech_model == "whisperx_pyannote" and changes(p) == ["speech_model from nemotron to whisperx_pyannote"]   # 7.3 rule 4
    after = client.get(saved.headers["location"]).text
    assert f'id="saved-speech-model" role="status">{words.PATH_SAVED}</p>' in after and radio("whisperx_pyannote", " checked") in after
    assert words.BETTER_ACCURACY in text_of(client.get("/settings"))
    # A change takes effect at the next consultation, never during one: each records the choice it ran with.
    assert p.consultations.get(1)["speech_choice"] == "nemotron" and p.running[1].speech_door.choice is NEMOTRON
    p.running[1].close()
    client.post("/consultations/start/1", data=TICKS)
    assert p.consultations.get(2)["speech_choice"] == "whisperx_pyannote"
    assert words.CHOICE_TITLE in text_of(client.get("/consultations/start/1"))                   # the Start screen names it
    p.running[2].close()
    # The same choice sent again writes nothing.
    client.post("/settings/speech-model", data={"speech_model": "whisperx_pyannote"})
    assert len(changes(p)) == 1


def test_7_3_rule_1_a_model_that_is_not_installed_or_that_the_room_check_does_not_allow_is_disabled_with_the_reason_on_the_control(tmp_path, clock):
    # A card of 24 GB: no room for the WhisperX pass at Stop beside the language model (15.8, ruling 33).
    app, client, installed = app_with(tmp_path / "room", clock, machine=SUITABLE)
    p = app.state.parts
    page = client.get("/settings")
    no_room = p.decisions.whisperx_choice.sentence
    assert not p.decisions.whisperx_choice.green and no_room == words.REASONS["whisperx_no_room"]
    assert radio("whisperx_pyannote", ' aria-describedby="speech-model-whisperx_pyannote-reason" disabled') in page.text
    assert f'id="speech-model-whisperx_pyannote-reason">{no_room}</p>' in text_of(page)
    refused = client.post("/settings/speech-model", data={"speech_model": "whisperx_pyannote"})    # a post made anyway
    assert refused.status_code == 400 and refusal_on(refused.text, "save-speech-model") == no_room
    assert p.stored.speech_model is None and changes(p) == []
    assert refusal_on(client.post("/settings/speech-model", data={"speech_model": "made-up"}).text, "save-speech-model") == words.PICK_ONE
    # Not installed: said with the command as it stands (ruling 57); nothing can be pressed to fetch it.
    app, client, installed = app_with(tmp_path / "bare", clock, nemotron=True, whisperx=False)
    page = client.get("/settings")
    reason = INSTALL.format(name="whisperx_pyannote")
    assert f'id="speech-model-whisperx_pyannote-reason">{reason}</p>' in text_of(page) and reason == words.SPEECH_MODEL_NOT_INSTALLED.format(name="whisperx_pyannote")
    refused = client.post("/settings/speech-model", data={"speech_model": "whisperx_pyannote"})
    assert refused.status_code == 400 and refusal_on(refused.text, "save-speech-model") == reason
    assert "Download" not in text_of(page)


def test_details_of_9c_a_choice_never_saved_reads_as_before_and_a_chosen_model_that_cannot_run_is_not_replaced(tmp_path, clock):
    # Never saved, Nemotron not installed, the WhisperX choice usable: the app takes it by itself, as since 6a.
    app, client, installed = app_with(tmp_path / "older", clock, nemotron=False, whisperx=True)
    p = app.state.parts
    page = client.get("/settings").text
    assert radio("whisperx_pyannote", " checked") in page and p.stored.speech_model is None
    assert client.post("/consultations/start/1", data=TICKS).status_code == 303 and p.consultations.get(1)["speech_choice"] == "whisperx_pyannote"
    p.running[1].close()
    # Chosen by the doctor, then gone from the disk: Start says why, and Nemotron is not taken in its place (10.4).
    app, client, installed = app_with(tmp_path / "chosen", clock)
    p = app.state.parts
    client.post("/settings/speech-model", data={"speech_model": "whisperx_pyannote"})
    installed[WHISPERX_PYANNOTE.name] = False
    start = client.get("/consultations/start/1")
    expected = words.START_NO_SPEECH.format(reason=words.SPEECH_REASONS["whisperx_not_installed"])
    assert refusal_on(start.text, "start") == expected
    refused = client.post("/consultations/start/1", data=TICKS)
    assert refused.status_code == 400 and refusal_on(refused.text, "start") == expected and p.consultations.get(1) is None
    assert radio("whisperx_pyannote", ' checked aria-describedby="speech-model-whisperx_pyannote-reason" disabled') in client.get("/settings").text
    # Back to Nemotron by the doctor's own choice: Start is offered.
    client.post("/settings/speech-model", data={"speech_model": "nemotron"})
    assert client.post("/consultations/start/1", data=TICKS).status_code == 303 and p.consultations.get(1)["speech_choice"] == "nemotron"
    p.running[1].close()


def test_7_3_the_choice_is_shown_only_where_this_computer_writes_the_transcript(tmp_path, clock):
    app, client, installed = app_with(tmp_path / "cloud", clock)
    p = app.state.parts
    p.stored.set_path("suitable", ChosenPath(THIS_COMPUTER, SPEECHMATICS))
    assert 'name="speech_model"' not in client.get("/settings").text
    assert client.post("/settings/speech-model", data={"speech_model": "nemotron"}).headers["location"] == "/settings#transcription"
    assert p.stored.speech_model is None
    app, client, installed = app_with(tmp_path / "no-card", clock, machine=NO_CARD)
    assert 'name="speech_model"' not in client.get("/settings").text
