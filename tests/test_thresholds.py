"""The two thresholds of the gate (spec 7.3; 15.13, the details of run 9c;
the owner's bounds of 18 Nov 2026): the fewest words a note is drafted
from, 30 to 300, default 60; the score under which a line is marked as low
confidence, 0.40 to 0.80, default 0.60. Each a typed field with its Save.
A consultation holds the two values it started with in its own row, and
its gate and its review page read them there. Made services, no model."""

from __future__ import annotations

import pytest

from openconsult import words
from openconsult.consult.gate import judge
from openconsult.settings import thresholds
from openconsult.settings.thresholds import fewest_words_of, low_score_of, of_row
from openconsult.speech.choices import SPEECHMATICS
from tests.conftest import refusal_on, text_of
from tests.made_up_store import MadeStore
from tests.test_connect_screens import SUITABLE, made_app
from tests.test_gate import row
from tests.test_recording_after_stop import LongPage, consult, ticked_app
from tests.test_saves_by_itself import BOTH_KEYS, changes
from tests.test_start import TICKS

FEWEST = ("The fewest words a note is drafted from. With fewer, no note is drafted. From 30 to 300; default 60.")
LOW = "The score under which a line is marked as low confidence. From 0.40 to 0.80; default 0.60."
FEWEST_BAD = "Enter a whole number from 30 to 300."
LOW_BAD = "Enter a number from 0.40 to 0.80, such as 0.60."
SAVED = "Saved. A consultation started from now on uses it. One already started keeps the value it started with."


class SecondSpeakerAt(LongPage):
    """The made service's page with its second speaker's words at one score."""

    def __init__(self, score: float, **kwargs):
        super().__init__(**kwargs)
        self.score = score

    def transcript(self) -> dict:
        made = super().transcript()
        for item in made["results"]:
            if item["type"] == "word" and item["alternatives"][0]["speaker"] == "S2":
                item["alternatives"][0]["confidence"] = self.score
        return made


def field_of(page: str, action: str) -> str:
    return page.split(f'action="{action}"', 1)[1].split("</form>", 1)[0]


def test_the_owners_bounds_of_18_nov_the_two_thresholds_with_their_defaults():
    # Pins the owner's word of 18 Nov 2026 (mail 2 of run 9c): the bounds are his, never the code's own choice.
    t = thresholds
    assert (t.FEWEST_WORDS_LOW, t.FEWEST_WORDS_DEFAULT, t.FEWEST_WORDS_HIGH) == (30, 60, 300)
    assert (t.LOW_SCORE_LOW, t.LOW_SCORE_DEFAULT, t.LOW_SCORE_HIGH) == (0.40, 0.60, 0.80)
    # Each bound itself is inside; one step outside is not.
    assert [fewest_words_of(text) for text in ("30", "300", " 60 ", "29", "301")] == [30, 300, 60, None, None]
    assert [low_score_of(text) for text in ("0.40", "0.80", "0.4", ".8", " 0.55 ", "0.39", "0.81")] == [0.40, 0.80, 0.40, 0.80, 0.55, None, None]
    # Not a whole number; not a number; more places than a score is ever shown with.
    assert [fewest_words_of(text) for text in ("", "sixty", "60.5", "-60", "6e1", "٦٠", "00000060")] == [None] * 7
    assert [low_score_of(text) for text in ("", "low", "0.555", "0,6", "60", "-0.6", "1", "0", "6e-1")] == [None] * 9


def test_7_3_each_threshold_is_a_typed_field_with_its_save_showing_its_default_and_its_bounds(tmp_path, clock):
    app, client, store, testers = made_app(tmp_path, clock, machine=SUITABLE, store=MadeStore(BOTH_KEYS))
    page = client.get("/settings").text
    section = text_of(client.get("/settings")).split('id="thresholds"', 1)[1].split("</section>", 1)[0]
    assert FEWEST in section and LOW in section and section.index("/settings/retention") < section.index(FEWEST) < section.index(LOW)
    assert words.FIELD_FEWEST_WORDS.format(low=30, high=300, default=60) == FEWEST
    assert words.FIELD_LOW_SCORE.format(low="0.40", high="0.80", default="0.60") == LOW
    for action, name, value, save in (("/settings/fewest-words", "words", "60", "save-fewest-words"),
                                      ("/settings/low-score", "score", "0.60", "save-low-score")):
        form = field_of(page, action)
        assert f'<input name="{name}" value="{value}"' in form                    # never set: the default stands in the field
        # Its own Save, never taken away by the page's script; and a typed field does not save by itself (ruling 47).
        assert f'id="{save}"' in form and "data-save" not in form
        assert "data-saves" not in page.split(f'action="{action}"', 1)[0].rsplit("<form", 1)[1] and "data-saves" not in form.split(">", 1)[0]


def test_7_3_a_threshold_is_saved_by_its_save_audited_from_what_to_what_and_says_so_beside_its_field(tmp_path, clock):
    app, client, store, testers = made_app(tmp_path, clock, machine=SUITABLE, store=MadeStore(BOTH_KEYS))
    p = app.state.parts
    assert (p.stored.fewest_words, p.stored.low_score) == (60, 0.60) and changes(p) == []
    saved = client.post("/settings/fewest-words", data={"words": "45"})
    assert saved.status_code == 303 and saved.headers["location"] == "/settings?done=fewest-words#fewest-words"
    assert p.stored.fewest_words == 45 and changes(p) == ["gate_fewest_words from the default to 45"]
    page = text_of(client.get("/settings?done=fewest-words"))
    assert SAVED in field_of(page, "/settings/fewest-words") and page.count(SAVED) == 1 and '<input name="words" value="45"' in page
    # The page's script keeps the window's place itself and asks for no anchor.
    saved = client.post("/settings/low-score", data={"score": "0.7", "place": "keep"})
    assert saved.status_code == 303 and saved.headers["location"] == "/settings?done=low-score"
    assert p.stored.low_score == 0.70 and changes(p)[-1] == "gate_low_score from the default to 0.70"
    page = text_of(client.get("/settings?done=low-score"))
    assert SAVED in field_of(page, "/settings/low-score") and page.count(SAVED) == 1 and '<input name="score" value="0.70"' in page
    # Each bound itself is taken; a later change is audited from the value before; the same value again writes no line.
    for text, value in (("30", 30), ("300", 300)):
        assert client.post("/settings/fewest-words", data={"words": text}).status_code == 303 and p.stored.fewest_words == value
    for text, value in (("0.40", 0.40), ("0.80", 0.80)):
        assert client.post("/settings/low-score", data={"score": text}).status_code == 303 and p.stored.low_score == value
    assert changes(p)[2:] == ["gate_fewest_words from 45 to 30", "gate_fewest_words from 30 to 300",
                              "gate_low_score from 0.70 to 0.40", "gate_low_score from 0.40 to 0.80"]
    client.post("/settings/fewest-words", data={"words": "300"})
    client.post("/settings/low-score", data={"score": ".8"})
    assert len(changes(p)) == 6
    # The other typed field of the section is untouched by either.
    assert p.stored.audio_retention_days == 90


@pytest.mark.parametrize("action,name,control,sentence,outside", [
    ("/settings/fewest-words", "words", "save-fewest-words", FEWEST_BAD, ("29", "301", "0", "", "sixty", "60.5", "-60")),
    ("/settings/low-score", "score", "save-low-score", LOW_BAD, ("0.39", "0.81", "0", "1", "", "low", "0.555", "0,6", "60")),
])
def test_7_3_rule_1_a_value_outside_the_bounds_is_refused_on_the_control_and_nothing_is_saved(tmp_path, clock, action, name, control, sentence, outside):
    app, client, store, testers = made_app(tmp_path, clock, machine=SUITABLE, store=MadeStore(BOTH_KEYS))
    p = app.state.parts
    for text in outside:
        refused = client.post(action, data={name: text})
        assert refused.status_code == 400 and refusal_on(text_of(refused), control) == sentence, text
        assert SAVED not in text_of(refused)
    assert (p.stored.fewest_words, p.stored.low_score) == (60, 0.60) and changes(p) == []
    # The setting's own door refuses what the form's check would have refused.
    for wrong in (29, 301, True, 60.5):
        with pytest.raises(ValueError):
            p.stored.set_fewest_words(wrong)
    for wrong in (0.39, 0.81, 0.555, True):
        with pytest.raises(ValueError):
            p.stored.set_low_score(wrong)
    assert changes(p) == []


def test_ruling_8_the_gate_judges_by_the_two_values_it_is_given_and_by_the_defaults_when_given_none():
    eighty = [row(1, "word " * 40, confidence=0.9), row(2, "word " * 40, confidence=0.7)]
    as_before = judge(eighty, SPEECHMATICS.declares, "Speechmatics")
    assert not as_before.refused and as_before.warnings == []
    longer = judge(eighty, SPEECHMATICS.declares, "Speechmatics", fewest_words=81)
    assert longer.refused and longer.warnings[0] == {"kind": "too_short", "detail": words.WARN_TOO_SHORT.format(words=80, least=81)}
    assert not judge(eighty, SPEECHMATICS.declares, "Speechmatics", fewest_words=80).refused
    stricter = judge(eighty, SPEECHMATICS.declares, "Speechmatics", low_score=0.80)
    assert not stricter.refused and stricter.warnings == [{"kind": "low_confidence", "line_n": 2, "detail": "0.70"}]
    assert judge(eighty, SPEECHMATICS.declares, "Speechmatics", low_score=0.70).warnings == []        # under the score, not at it
    # A row from before the thresholds could be set holds none and reads the defaults.
    assert of_row({"fewest_words": None, "low_score": None}) == (60, 0.60) and of_row({}) == (60, 0.60)
    assert of_row({"fewest_words": 45, "low_score": 0.7}) == (45, 0.70)


def test_7_3_a_consultation_holds_the_two_values_it_started_with_whatever_settings_becomes(tmp_path, clock, server):
    app, client, local = ticked_app(tmp_path, clock, server, LongPage())
    p = app.state.parts
    client.post("/settings/fewest-words", data={"words": "100"})
    client.post("/settings/low-score", data={"score": "0.45"})
    client.post("/consultations/start/1", data=TICKS)
    began = p.consultations.get(1)
    assert (began["fewest_words"], began["low_score"]) == (100, 0.45)
    # The setting changes after Start: the consultation is not touched, and is judged at Stop by what it started with.
    client.post("/settings/fewest-words", data={"words": "30"})
    client.post("/settings/low-score", data={"score": "0.80"})
    assert (p.stored.fewest_words, p.stored.low_score) == (30, 0.80)
    assert (p.consultations.get(1)["fewest_words"], p.consultations.get(1)["low_score"]) == (100, 0.45)


def test_7_3_a_consultation_started_with_nothing_set_holds_the_defaults_and_is_judged_as_before(tmp_path, clock, server):
    app, client, local = ticked_app(tmp_path, clock, server, LongPage())
    p = app.state.parts
    consult(app, client)                                           # the made page holds 80 words, each scored 0.9
    assert (p.consultations.get(1)["fewest_words"], p.consultations.get(1)["low_score"]) == (60, 0.60)
    assert not [w for w in p.consultations.warnings(1) if w["kind"] in ("too_short", "low_confidence")]
    assert "No note will be drafted." not in text_of(client.get("/consultations/1"))


def test_7_3_with_more_words_asked_for_than_the_transcript_holds_no_note_is_drafted_and_the_page_names_the_value_it_started_with(tmp_path, clock, server):
    app, client, local = ticked_app(tmp_path, clock, server, LongPage())
    p = app.state.parts
    client.post("/settings/fewest-words", data={"words": "100"})
    client.post("/consultations/start/1", data=TICKS)
    client.post("/settings/fewest-words", data={"words": "30"})    # after Start: too late for this consultation
    c = p.running[1]
    finish_it(app, client, c)
    refused = [w for w in p.consultations.warnings(1) if w["kind"] == "too_short"]
    assert [w["detail"] for w in refused] == [words.WARN_TOO_SHORT.format(words=80, least=100)]
    assert words.WARN_TOO_SHORT.format(words=80, least=100) in text_of(client.get("/consultations/1"))
    assert p.notes.drafts(1) == []


def finish_it(app, client, c, cid=1):
    """The rest of a consultation that the test itself started: sound, Stop, the answer."""
    from openconsult.consult.live import FINAL
    from openconsult.web.live import capture_from
    from tests.test_review_page import CAPTURE, LOUD
    from tests.test_stop import until
    c.begin_sound(capture_from(CAPTURE))
    for _ in range(8):
        c.sound(LOUD)
        c.wait_for_pass()
    client.post(f"/consultations/{cid}/stop")
    assert until(lambda: c.stop_stage == "who_spoke" or c.state == FINAL)
    if c.state != FINAL:
        client.post(f"/consultations/{cid}/speakers", data={"speaker": "S1"})
    assert until(lambda: c.state == FINAL)
    assert app.state.parts.whole.wait()          # the delete and its proof run beside Stop: no thread outlives the test


def test_7_3_the_gate_and_the_review_page_mark_a_line_by_the_score_the_consultation_started_with(tmp_path, clock, server):
    app, client, local = ticked_app(tmp_path, clock, server, SecondSpeakerAt(0.70))
    p = app.state.parts
    client.post("/settings/low-score", data={"score": "0.80"})
    client.post("/consultations/start/1", data=TICKS)
    client.post("/settings/low-score", data={"score": "0.40"})     # after Start
    finish_it(app, client, p.running[1])
    assert p.consultations.get(1)["low_score"] == 0.80 and p.stored.low_score == 0.40
    marked = [(w["line_n"], w["detail"]) for w in p.consultations.warnings(1) if w["kind"] == "low_confidence"]
    assert marked == [(2, "0.70")]                                 # by its own 0.80, not by the default and not by Settings' 0.40
    page = text_of(client.get("/consultations/1"))
    mark = words.LOW_CONFIDENCE_MARK.format(score="0.70")
    assert mark in page and words.WARN_LOW_CONFIDENCE.format(n=2, score="0.70") in page
    # A row from before the thresholds could be set reads the default: 0.70 is not under 0.60, so its line has no mark.
    p.db.execute("UPDATE consultation SET fewest_words = NULL, low_score = NULL WHERE id = 1")
    assert mark not in text_of(client.get("/consultations/1"))


def test_7_3_an_older_row_is_judged_by_the_defaults_whatever_settings_holds(tmp_path, clock, server):
    app, client, local = ticked_app(tmp_path, clock, server, SecondSpeakerAt(0.70))
    p = app.state.parts
    client.post("/settings/fewest-words", data={"words": "100"})
    client.post("/settings/low-score", data={"score": "0.80"})
    client.post("/consultations/start/1", data=TICKS)
    # As a consultation begun before version 12 and stopped after it: its row holds neither value.
    p.db.execute("UPDATE consultation SET fewest_words = NULL, low_score = NULL WHERE id = 1")
    finish_it(app, client, p.running[1])
    kinds = [w["kind"] for w in p.consultations.warnings(1)]
    assert "too_short" not in kinds and "low_confidence" not in kinds        # 80 words are 60 or more; 0.70 is not under 0.60
