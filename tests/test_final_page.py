"""The final transcript page with its warnings (spec 15.10, 6a; ruling 8;
11.5 rules 2 and 5; R9, R20). Made-up doors; made sound; no model's
words asserted."""

import json

from openconsult import words
from openconsult.app import build_app
from openconsult.consult.live import FINAL
from openconsult.settings import store
from openconsult.settings.machine import Card, describe
from openconsult.speech.choices import NEMOTRON, WHISPERX_PYANNOTE
from openconsult.speech.door import Door as SpeechDoor
from tests.conftest import PORT, browser, log_in, set_up, text_of
from tests.fakes import ALARM_FIRES, ASSESSMENT, FakeEngine, MadeUpWorker
from tests.test_loudness import sine
from tests.test_speech_door import seg
from tests.test_start import PATIENT, TICKS
from tests.test_stop import CHECK, until

RATE = 16000
LOUD = sine(0.25, -20.0)
CAPTURE = {"type": "capture", "echo_cancellation": False, "noise_suppression": False, "auto_gain": False, "rate": RATE}
LONG = " ".join(["word"] * 70)


def run_through(tmp_path, clock, machine, doors, engine, answer="S1", pieces=8):
    app = build_app(store.build(tmp_path, PORT), machine=machine, clock=clock,
                    engines={"vllm": FakeEngine(version=None), "ollama": engine}, doors=doors)
    client = browser(app)
    set_up(client)
    log_in(client)
    client.post("/patients", data=PATIENT)
    client.post("/consultations/start/1", data=TICKS)
    c = app.state.parts.running[1]
    from openconsult.web.live import capture_from
    c.begin_sound(capture_from(CAPTURE))
    for _ in range(pieces):
        c.sound(LOUD)
        c.wait_for_pass()
    client.post("/consultations/1/stop")
    assert until(lambda: c.stop_stage == "who_spoke")
    client.post("/consultations/1/speakers", data={"speaker": answer})
    assert until(lambda: c.state == FINAL)
    return app, client, c


def test_ruling_8_the_final_page_shows_the_warnings_the_labels_and_the_last_pass(tmp_path, clock, machine):
    lines = [[{"id": 1, "start": 0.0, "end": 0.5, "text": LONG, "speaker": "S1", "confidence": None}],
             [{"id": 2, "start": 0.6, "end": 1.0, "text": "Yes.", "speaker": None, "confidence": None}]]
    worker = MadeUpWorker(live=lines)
    doors = {NEMOTRON.name: SpeechDoor(NEMOTRON, make_worker=lambda: worker, installed=lambda: True)}
    engine = FakeEngine({"alarm": [ALARM_FIRES], "label_check": [{"lines": [{"line": 1, "label": "doctor"}, {"line": 2, "label": "patient"}]}]})
    app, client, c = run_through(tmp_path, clock, machine, doors, engine)
    page = text_of(client.get("/consultations/1"))
    assert words.FINAL_TITLE in page
    assert words.WARN_NO_SPEAKER.format(n=2) in page                                  # a line with no speaker: flagged
    assert words.WARN_CONFIDENCE_NOT_MEASURED.format(choice=words.ROW_NEMOTRON) in page   # Nemotron gives no score
    assert words.WARN_TOO_SHORT.split("{")[0] not in page                              # 71 words: not too short
    assert "[1] Doctor" in page and "[2] Patient" in page and words.LABEL_UNSURE in page
    assert words.ALARM_FIRED in page and "Made-up step" in page                        # the last pass's alarm, as shown live
    assert "Made-up condition A" in page and "A made-up question?" in page
    assert words.MODEL_LINE.format(speech=words.ROW_NEMOTRON, model="gemma4:26b-a4b-it-qat", engine="made-up",
                                   version="0.0-made-up") in page
    assert not c.final.refused
    # Nothing plays yet: the player is 6b's (R31).
    assert "<audio" not in page and "play" not in page.lower()


def test_11_5_rule_2_missing_speech_is_shown_at_its_place_on_the_final_page(tmp_path, clock):
    # A made-up card large enough for the WhisperX choice beside the language model.
    big = describe("Linux", "x86_64", [Card("Made-up card", 49140)])
    live_text = "go straight to the hospital now please"
    worker = MadeUpWorker(live=[[{"start": 0.0, "end": 1.0, "text": live_text}]] + [[]] * 11,
                          final={"last_live": [], "segments": [seg(0.0, 1.0, "now please", "S0", 0.9)], "seconds": {}})
    doors = {NEMOTRON.name: SpeechDoor(NEMOTRON, make_worker=MadeUpWorker, installed=lambda: False),
             WHISPERX_PYANNOTE.name: SpeechDoor(WHISPERX_PYANNOTE, make_worker=lambda: worker, installed=lambda: True)}
    engine = FakeEngine({"label_check": [{"lines": [{"line": 1, "label": "patient"}]}]})
    app, client, c = run_through(tmp_path, clock, big, doors, engine, answer="S0", pieces=12)
    page = text_of(client.get("/consultations/1"))
    assert words.WARN_MISSING_PASSAGE.format(start=0.0, end=1.0, words="go straight to the hospital") in page
    assert words.WARN_UNCOVERED.format(start=1.0, end=3.0) in page           # three seconds of sound, one covered
    assert words.WARN_TOO_SHORT.format(words=2, least=60) in page and c.final.refused
    assert words.WARN_CONFIDENCE_NOT_MEASURED.split(":")[0] not in page      # WhisperX gives a score
    assert c.final.figures["stop_s"] is not None and "Stop to final" in app.state.parts.audit.lines()[0].detail
    assert app.state.parts.consultations.get(1)["speech_choice"] == "whisperx_pyannote"
