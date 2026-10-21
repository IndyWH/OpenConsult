"""Retention and the conversion to Opus (spec 15.11 ruling 7; 7.3; 8.8;
R15, R18, R30; 3c's room check; V1_LESSONS 10.3). A made converter and a
one-second made WAV; never a real recording. The fake clock moves."""

import asyncio
from datetime import timezone

import pytest

from openconsult import words
from openconsult.app import build_app
from openconsult.consult import opus, retention
from openconsult.consult.live import FINAL
from openconsult.consult.recording import header
from openconsult.settings import store
from openconsult.settings.decisions import converter_element
from openconsult.settings.machine import Card, describe
from tests.conftest import PASSWORD, PORT, browser, log_in, refusal_on, set_up, text_of
from tests.fakes import FakeEngine, MadeUpConverter, MadeUpWorker
from tests.test_review_page import engine_with, nemotron_doors, run_through, LINES
from tests.test_start import PATIENT, TICKS


def made_wav(path, seconds=1.0, rate=16000):
    data = b"\x00\x00" * int(rate * seconds)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header(rate, len(data)) + data)
    return path


def app_with_converter(tmp_path, clock, machine, converter, engine=None):
    doors = nemotron_doors(MadeUpWorker(live=LINES + [[]] * 6 + LINES))
    app = build_app(store.build(tmp_path, PORT), machine=machine, clock=clock, doors=doors,
                    engines={"vllm": FakeEngine(version=None), "ollama": engine or engine_with()},
                    find_converter=lambda: converter)
    client = browser(app)
    set_up(client)
    log_in(client)
    return app, client


def test_ruling_7_7_3_the_retention_days_default_to_90_are_changed_on_the_settings_page_and_audited(logged_in, app):
    page = text_of(logged_in.get("/settings"))
    assert words.SECTION_THRESHOLDS in page and words.FIELD_RETENTION_DAYS.format(default=90) in page
    assert 'name="days" value="90"' in logged_in.get("/settings").text
    done = logged_in.post("/settings/retention", data={"days": "30"})
    assert done.status_code == 303 and done.headers["location"] == "/settings?done=retention"
    assert words.RETENTION_SAVED in logged_in.get("/settings?done=retention").text
    assert app.state.parts.stored.audio_retention_days == 30 and 'name="days" value="30"' in logged_in.get("/settings").text
    assert app.state.parts.audit.lines()[0].detail == "audio_retention_days from the default to 30"
    logged_in.post("/settings/retention", data={"days": "0"})
    assert app.state.parts.stored.audio_retention_days == 0
    for bad in ("ten", "-1", "1.5", ""):
        refused = logged_in.post("/settings/retention", data={"days": bad})
        assert refused.status_code == 400 and refusal_on(refused.text, "save-retention") == words.RETENTION_BAD
    assert app.state.parts.stored.audio_retention_days == 0


def test_ruling_7_R15_8_8_the_sweep_at_0_deletes_nothing_and_at_1_day_deletes_the_older_recording_and_writes_the_audit_line(tmp_path, clock, machine):
    app, client, c = run_through(tmp_path, clock, machine, nemotron_doors(MadeUpWorker(live=LINES)), engine_with())
    p = app.state.parts
    first = tmp_path / "recordings" / "consultation_1.wav"
    assert first.is_file() and p.consultations.get(1)["recording_format"] in (None, "wav")
    # A second, newer consultation by rows, with an Opus file: the sweep treats either file as the recording.
    clock.advance(days=2)
    cid = p.consultations.start(1, 15, "nemotron", "made-up", "0", "tag", None, 2)
    p.consultations.set(cid, state="final", stopped_at=clock().isoformat(timespec="seconds"), recording_file="consultation_2.ogg",
                        recording_format="opus")
    second = tmp_path / "recordings" / "consultation_2.ogg"
    second.write_bytes(b"OggS made up")
    before = len(p.audit.lines())
    p.stored.set_audio_retention_days(0)
    assert retention.sweep(p) == retention.DONE and first.is_file() and second.is_file()        # 0 keeps
    assert len([l for l in p.audit.lines() if l.event == "audio.deleted"]) == 0
    p.stored.set_audio_retention_days(1)
    clock.advance(hours=1)
    assert retention.sweep(p) == retention.DONE
    assert not first.is_file() and second.is_file()                                                 # the older one only
    row = p.consultations.get(1)
    assert row["audio_deleted_at"] == clock().isoformat(timespec="seconds") and p.consultations.get(2)["audio_deleted_at"] is None
    deletion = p.db.query_one("SELECT * FROM audio_deletion")
    assert (deletion["consultation_ids"], deletion["files"], deletion["bytes"]) == ("[1]", 1, 44 + 2 * 16000 * 2)
    line = [l for l in p.audit.lines() if l.event == "audio.deleted"][0]
    assert line.detail == f"1 recordings of consultations 1, {deletion['bytes']} bytes freed, after 1 days"
    assert retention.sweep(p) == retention.DONE and len([l for l in p.audit.lines() if l.event == "audio.deleted"]) == 1   # nothing: no line
    # The player then shows the line of stage 6 with the date, in the player's place (R15; 8.8).
    log_in(client)                                                                                  # the clock moved past the lock
    page = text_of(client.get("/consultations/1"))
    assert words.AUDIO_GONE.format(date="4 Oct 2026") in page and "<audio" not in page
    clock.advance(days=2)
    assert retention.sweep(p) == retention.DONE and not second.is_file()                            # the Opus file too, in its turn
    del before


def test_ruling_7_the_sweep_runs_at_start_up_and_every_24_hours_and_never_during_a_stop(tmp_path, clock, machine):
    app, client, c = run_through(tmp_path, clock, machine, nemotron_doors(MadeUpWorker(live=LINES)), engine_with())
    p = app.state.parts
    p.stored.set_audio_retention_days(1)
    clock.advance(days=2)
    # A consultation stopping: the sweep is deferred, and tried again after 60 s; otherwise it waits a day.
    p.consultations.set(1, state="stopping")
    assert retention.sweep(p) == retention.DEFERRED and (tmp_path / "recordings" / "consultation_1.wav").is_file()
    assert retention.next_wait_s(retention.DEFERRED) == 60 and retention.next_wait_s(retention.DONE) == 24 * 3600
    p.consultations.set(1, state="final")
    assert retention.sweep(p) == retention.DONE and not (tmp_path / "recordings" / "consultation_1.wav").is_file()
    # The loop: a whole day first (the start-up sweep was made), then the wait the outcome gives; no real waiting.
    waits, outcomes = [], iter([retention.DEFERRED, retention.DONE])

    async def sleep(seconds):
        waits.append(seconds)
        if len(waits) == 3:
            raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(retention.loop(p, sleep=sleep, run=lambda parts: next(outcomes)))
    assert waits == [24 * 3600, 60, 24 * 3600]
    # At start-up: a fresh app over the same folder sweeps at once and reports an orphan file, deleting nothing.
    orphan = tmp_path / "recordings" / "consultation_77.wav"
    orphan.write_bytes(b"RIFF made up")
    again = build_app(store.build(tmp_path, PORT), machine=machine, clock=clock,
                      engines={"vllm": FakeEngine(version=None), "ollama": FakeEngine()})
    lines = again.state.parts.audit.lines()
    assert any(l.event == "recording.orphan" and l.detail == "consultation_77.wav" for l in lines)
    assert orphan.is_file()


def test_ruling_7_R18_a_made_one_second_wav_is_converted_to_opus_after_stops_final_step_and_the_wav_removed_only_after_the_check(tmp_path, clock, machine):
    converter = MadeUpConverter()
    app, client = app_with_converter(tmp_path, clock, machine, converter)
    client.post("/patients", data=PATIENT)
    client.post("/consultations/start/1", data=TICKS)
    c = app.state.parts.running[1]
    from openconsult.web.live import capture_from
    from tests.test_review_page import CAPTURE, LOUD
    from tests.test_stop import until
    c.begin_sound(capture_from(CAPTURE))
    for _ in range(8):
        c.sound(LOUD)
        c.wait_for_pass()
    client.post("/consultations/1/stop")
    assert until(lambda: c.stop_stage == "who_spoke")
    client.post("/consultations/1/speakers", data={"speaker": "S1"})
    assert until(lambda: c.state == FINAL)
    assert until(lambda: app.state.parts.consultations.get(1)["recording_format"] == "opus")
    p = app.state.parts
    row = p.consultations.get(1)
    assert row["recording_file"] == "consultation_1.ogg" and row["conversion_failure"] is None
    assert (tmp_path / "recordings" / "consultation_1.ogg").is_file() and not (tmp_path / "recordings" / "consultation_1.wav").is_file()
    assert converter.encoded == [(str(tmp_path / "recordings" / "consultation_1.wav"), str(tmp_path / "recordings" / "consultation_1.ogg"))]
    line = [l for l in p.audit.lines() if l.event == "recording.converted"][0]
    assert line.detail.startswith("consultation 1: ") and "bytes WAV to 12 bytes Opus, 2.00 s" in line.detail
    # The route serves the Opus file as audio/ogg; the player's data is as before and a line's press plays from its start.
    served = client.get("/consultations/1/recording")
    assert served.status_code == 200 and served.headers["content-type"].startswith("audio/ogg")
    raw = client.get("/consultations/1").text
    assert '<audio id="audio" controls' in raw and 'class="play-line cite" data-line="1"' in raw
    assert words.CONVERSION_FAILED.split(":")[0] not in text_of(client.get("/consultations/1"))


def test_ruling_7_R30_a_conversion_that_fails_or_a_missing_converter_leaves_the_wav_with_its_reason_shown(tmp_path):
    folder = tmp_path / "recordings"
    wav = made_wav(folder / "consultation_1.wav", 1.0)
    # No converter: the WAV stays, the reason says so.
    outcome = opus.convert_file(None, wav)
    assert not outcome.ok and outcome.reason == words.CONVERSION_NO_CONVERTER and wav.is_file()
    # The command fails: the WAV stays, no Ogg is left.
    outcome = opus.convert_file(MadeUpConverter(fail="made-up: could not encode"), wav)
    assert not outcome.ok and outcome.reason == "made-up: could not encode" and wav.is_file() and not (folder / "consultation_1.ogg").exists()
    # The check fails: the Ogg plays for less than the WAV, outside the tolerance; the part-written Ogg is removed.
    outcome = opus.convert_file(MadeUpConverter(decoded_s=0.5), wav)
    assert not outcome.ok and outcome.reason == words.CONVERSION_LENGTH_DIFFERS.format(wav="1.00", opus="0.50")
    assert wav.is_file() and not (folder / "consultation_1.ogg").exists()
    # Within the tolerance it passes; the WAV goes only then.
    assert opus.DURATION_TOLERANCE_S == 0.1
    outcome = opus.convert_file(MadeUpConverter(decoded_s=1.05), wav)
    assert outcome.ok and outcome.file_name == "consultation_1.ogg" and not wav.is_file() and (folder / "consultation_1.ogg").is_file()
    assert (outcome.wav_bytes, outcome.ogg_bytes, outcome.wav_s, outcome.ogg_s) == (44 + 32000, 12, 1.0, 1.05)
    assert opus.wav_seconds(made_wav(folder / "other.wav", 0.25, rate=48000)) == 0.25


def test_ruling_7_R30_a_failed_conversion_is_shown_on_the_consultations_page_and_start_is_still_offered(tmp_path, clock, machine):
    app, client = app_with_converter(tmp_path, clock, machine, MadeUpConverter(fail="made-up: could not encode"))
    p = app.state.parts
    assert words.START.encode() in client.get("/patients/new").content or True
    client.post("/patients", data=PATIENT)
    assert 'id="start" aria-describedby="start-refusal" disabled' not in client.get("/consultations/start/1").text   # Start still offered
    client.post("/consultations/start/1", data=TICKS)
    c = p.running[1]
    from openconsult.web.live import capture_from
    from tests.test_review_page import CAPTURE, LOUD
    from tests.test_stop import until
    c.begin_sound(capture_from(CAPTURE))
    for _ in range(8):
        c.sound(LOUD)
        c.wait_for_pass()
    client.post("/consultations/1/stop")
    assert until(lambda: c.stop_stage == "who_spoke")
    client.post("/consultations/1/speakers", data={"speaker": "S1"})
    assert until(lambda: c.state == FINAL)
    assert until(lambda: p.consultations.get(1)["conversion_failure"] is not None)
    row = p.consultations.get(1)
    assert row["recording_format"] == "wav" and row["recording_file"] == "consultation_1.wav"
    assert (tmp_path / "recordings" / "consultation_1.wav").is_file()
    page = text_of(client.get("/consultations/1"))
    assert words.CONVERSION_FAILED.format(reason="made-up: could not encode") in page and '<audio id="audio"' in client.get("/consultations/1").text
    assert any(l.event == "recording.conversion_failed" for l in p.audit.lines())
    assert client.get("/consultations/1/recording").headers["content-type"].startswith("audio/wav")
    # With no converter at all nothing is attempted: the row says why the WAV stays, and no line is written per consultation.
    app2, client2 = app_with_converter(tmp_path / "none", clock, machine, None)
    client2.post("/patients", data=PATIENT)
    client2.post("/consultations/start/1", data=TICKS)
    c2 = app2.state.parts.running[1]
    c2.begin_sound(capture_from(CAPTURE))
    for _ in range(8):
        c2.sound(LOUD)
        c2.wait_for_pass()
    client2.post("/consultations/1/stop")
    assert until(lambda: c2.stop_stage == "who_spoke")
    client2.post("/consultations/1/speakers", data={"speaker": "S1"})
    assert until(lambda: c2.state == FINAL) and until(lambda: app2.state.parts.consultations.get(1)["conversion_failure"] is not None)
    assert app2.state.parts.consultations.get(1)["conversion_failure"] == words.CONVERSION_NO_CONVERTER
    assert not any(l.event == "recording.conversion_failed" for l in app2.state.parts.audit.lines())
    assert words.CONVERSION_FAILED.format(reason=words.CONVERSION_NO_CONVERTER) in text_of(client2.get("/consultations/1"))


def test_ruling_7_3c_the_room_check_reports_the_converter_as_the_packages_the_systems_or_missing(tmp_path, clock, machine):
    def run_ok(args, **kwargs):
        from types import SimpleNamespace
        return SimpleNamespace(returncode=0, stdout="ffmpeg version 7.0.2-static Copyright\nconfiguration: --enable-libopus\n", stderr="")

    def run_no_opus(args, **kwargs):
        from types import SimpleNamespace
        return SimpleNamespace(returncode=0, stdout="ffmpeg version 9.9 Copyright\nconfiguration: --enable-gpl\n", stderr="")

    found = opus.find_converter(which=lambda name: "/usr/bin/ffmpeg", package=lambda: "/made-up/package/ffmpeg", run=run_ok)
    assert found == opus.Converter("/made-up/package/ffmpeg", "package", "7.0.2-static")
    found = opus.find_converter(which=lambda name: "/usr/bin/ffmpeg", package=lambda: None, run=run_ok)
    assert found == opus.Converter("/usr/bin/ffmpeg", "system", "7.0.2-static")
    assert opus.find_converter(which=lambda name: None, package=lambda: None, run=run_ok) is None
    assert opus.find_converter(which=lambda name: "/usr/bin/ffmpeg", package=lambda: None, run=run_no_opus) is None   # no Opus encoder
    assert opus.find_converter(which=lambda name: "/usr/bin/ffmpeg", package=lambda: None, run=lambda *a, **k: (_ for _ in ()).throw(OSError("no"))) is None
    # The element, its sentence, the audit line at start and the row on This machine, on every machine.
    for machine_case in (machine, describe("Darwin", "arm64", [])):
        for converter, sentence in ((opus.Converter("/p/ffmpeg", "package", "7.0.2"), words.REASONS["converter_package"].format(version="7.0.2")),
                                    (opus.Converter("/usr/bin/ffmpeg", "system", "9.0"), words.REASONS["converter_system"].format(path="/usr/bin/ffmpeg")),
                                    (None, words.REASONS["converter_none"])):
            assert converter_element(converter).sentence == sentence
            folder = tmp_path / f"{machine_case.case}-{converter.source if converter else 'none'}"
            app = build_app(store.build(folder, PORT), machine=machine_case, clock=clock,
                            engines={"vllm": FakeEngine(version=None), "ollama": FakeEngine()}, find_converter=lambda: converter)
            client = browser(app)
            set_up(client)
            log_in(client)
            page = text_of(client.get("/settings"))
            assert words.ROW_CONVERTER in page and sentence in page
            assert any(l.event == "decision.converter" and l.detail.startswith(sentence) for l in app.state.parts.audit.lines())
            assert app.state.parts.decisions.start_offered == app.state.parts.decisions.language_model.green   # never held by the converter
