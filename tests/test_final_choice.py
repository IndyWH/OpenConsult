"""The gate judges by the speech choice that made the final transcript
(spec 15.13, the details of run 9c: The line on confidence; Cowork's
review of the plan, point b; 15.10 ruling 8; 11.5 rule 5). In the room
check of 17 Nov 2026, with the tick for better accuracy, the page said
that confidence was not measured and named this computer's speech
choice, though the transcript shown was the service's, made from the
whole recording, and carried scores. And the model line at the foot of
the page named that choice alone. A made upload service inside the
suite; nothing here opens a connection."""

from __future__ import annotations

from openconsult import words
from openconsult.consult.live import FINAL
from openconsult.consult.whole import WholeRecording
from openconsult.settings.path import SPEECHMATICS
from tests.conftest import text_of
from tests.test_lost_connection import lost_and_found
from tests.test_recording_after_stop import LongPage, consult, ticked_app
from tests.test_stop import until

NOT_MEASURED = "Confidence was not measured: Nemotron gives no score."
WHOLE_LINE = "Speech: Nemotron during the consultation, Speechmatics for the final transcript. Language model: "


class OneLowLine(LongPage):
    """The made service's page with its second speaker's words scored low."""

    def transcript(self) -> dict:
        made = super().transcript()
        for item in made["results"]:
            if item["type"] == "word" and item["alternatives"][0]["speaker"] == "S2":
                item["alternatives"][0]["confidence"] = 0.4
        return made


def kinds(p) -> list[tuple]:
    return [(w["kind"], w["line_n"], w["detail"]) for w in p.consultations.warnings(1) if "confidence" in w["kind"]]


def test_details_of_9c_with_the_transcript_from_the_whole_recording_the_services_scores_are_judged_and_no_line_says_not_measured(tmp_path, clock, server):
    app, client, local = ticked_app(tmp_path, clock, server, OneLowLine())
    consult(app, client)
    p = app.state.parts
    assert p.consultations.get(1)["speech_choice"] == "nemotron"                           # the live lines were this computer's
    assert kinds(p) == [("low_confidence", 2, "0.40")]                                     # judged as a cloud consultation's are
    page = text_of(client.get("/consultations/1"))
    assert NOT_MEASURED not in page and "Confidence was not measured" not in page
    assert words.WARN_LOW_CONFIDENCE.format(n=2, score="0.40") in page and words.LOW_CONFIDENCE_MARK.format(score="0.40") in page
    # The model line names both: this computer's choice for the consultation, the service for the final transcript.
    assert WHOLE_LINE in page and "Speech: Nemotron. " not in page


def test_details_of_9c_where_the_upload_failed_the_live_lines_stay_and_the_line_names_the_choice_that_made_them(tmp_path, clock, server):
    app, client, local = ticked_app(tmp_path, clock, server, LongPage("submit 500"))
    consult(app, client)
    p = app.state.parts
    assert kinds(p) == [("confidence_not_measured", None, "Nemotron")]
    page = text_of(client.get("/consultations/1"))
    assert NOT_MEASURED in page and WHOLE_LINE not in page and "Speech: Nemotron. Language model: " in page   # as before this run


def test_details_of_9c_after_the_one_press_in_cloud_transcription_the_model_line_is_as_it_was(tmp_path, clock, server, monkeypatch):
    app, client, c, worker, now = lost_and_found(tmp_path, clock, server, monkeypatch)
    p = app.state.parts
    p.whole = c.whole = WholeRecording(lambda: p.connections.key(SPEECHMATICS), LongPage(), sleep=lambda s: None)
    client.post("/consultations/1/stop")
    assert until(lambda: c.stop_stage == "lost")
    client.post("/consultations/1/whole", data={"send": "yes"})
    assert until(lambda: c.stop_stage == "who_spoke")
    client.post("/consultations/1/speakers", data={"speaker": "S1"})
    assert until(lambda: c.state == FINAL)
    page = text_of(client.get("/consultations/1"))
    assert "Speech: Speechmatics. Language model: " in page and "during the consultation" not in page
    assert "Confidence was not measured" not in page
