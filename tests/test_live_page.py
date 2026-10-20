"""The live page and Stop through the pages (spec 15.10, The live page,
Stop in order; R15; V1_LESSONS 1.12, 5.3; 15.6: every sentence in one
file). Made-up everything."""

from openconsult import words
from openconsult.web.live import SCRIPT_WORDS, script_words
from tests.conftest import text_of
from tests.test_sound import started  # noqa: F401 - the fixture


def test_R15_1_12_stop_moves_to_the_stopping_page_and_a_second_stop_waits(started):
    app, client, worker = started
    first = client.post("/consultations/1/stop")
    assert first.status_code == 303 and first.headers["location"] == "/consultations/1"
    page = client.get("/consultations/1")
    assert page.status_code == 200
    text = text_of(page)
    assert words.STAGE_LINES["speech"] in text and 'class="spinner"' in text and 'hidden' not in text.split('class="spinner"')[1][:10]
    assert 'content="1;url=/consultations/1?quiet"' in page.text           # the quiet refresh each second
    stopped = [line for line in app.state.parts.audit.lines() if line.event == "consultation.stopped"]
    second = client.post("/consultations/1/stop")
    assert second.status_code == 303 and second.headers["location"] == "/consultations/1"
    assert [line for line in app.state.parts.audit.lines() if line.event == "consultation.stopped"] == stopped
    assert app.state.parts.running[1].state == "stopping"
    # Sound sent after Stop goes nowhere, and the lock is still held off while finalising.
    assert len(worker.requested("audio")) == 0


def test_15_6_every_sentence_the_page_script_renders_comes_from_the_one_file(started):
    app, client, worker = started
    handed = script_words()
    assert set(handed) == set(SCRIPT_WORDS)
    for name, sentence in handed.items():
        assert sentence == getattr(words, name) and isinstance(sentence, str) and sentence
    page = client.get("/consultations/1").text
    assert '<script id="words" type="application/json">' in page and words.ALARM_NO_ACTION in text_of(client.get("/consultations/1"))
    assert client.get("/static/panels.js").status_code == 200
