"""The what-the-model-saw page (spec 15.12, rulings 11 and 28; 15.8 ruling
1; R2, R18, R20). The app through the made doors, as the review page's
tests run it; no model's words asserted."""

from openconsult import words
from openconsult.consult.live import FINAL
from openconsult.guidelines.panel import Guidelines
from openconsult.guidelines.search import Index
from openconsult.prompts import loader
from openconsult.web.live import capture_from
from tests.conftest import log_in, set_up, text_of
from tests.fakes import MadeUpEmbedder
from tests.test_guideline_panel import covered, differentials, load_corpus, three_pass_worker
from tests.test_guideline_search import axis
from tests.test_letters_page import LETTER, LIST, NOTE
from tests.test_review_page import CAPTURE, LOUD, app_on, engine_with, nemotron_doors, reviewed
from tests.test_start import PATIENT, TICKS
from tests.test_stop import until

PROMPTS = ("alarm", "assessment", "label_check", "note", "referrals", "letter", "guideline")


def checked(app, client):
    """The check of who spoke asked for on the review page, as a doctor may (15.9 ruling 37), so that its call is on the page."""
    assert client.post("/consultations/1/who-check").status_code == 303
    app.state.parts.who_checks.wait(1, 20)


def approved(tmp_path, clock, machine):
    engine = engine_with(note=[NOTE], referrals=[LIST], letter=[LETTER])
    app, client, c = reviewed(tmp_path, clock, machine, engine)
    checked(app, client)
    client.post("/consultations/1/note/approve")
    return app, client, engine


def record_of(p) -> tuple:
    """Every table's row count, and the model_call and audit_log tables whole."""
    tables = sorted(r["name"] for r in p.db.query("SELECT name FROM sqlite_master WHERE type = 'table'"))
    counts = {t: p.db.query_one(f"SELECT COUNT(*) AS n FROM {t}")["n"] for t in tables}
    calls = [tuple(r) for r in p.db.query("SELECT * FROM model_call ORDER BY id")]
    audit = [tuple(r) for r in p.db.query("SELECT * FROM audit_log ORDER BY id")]
    return counts, calls, audit


def main_of(raw: str) -> str:
    return raw.split("<main", 1)[1].split("</main>", 1)[0]


def test_ruling_28_R2_R18_the_view_is_reached_from_the_review_and_patient_pages_lists_every_call_and_writes_nothing(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine)
    p = app.state.parts
    checked(app, client)
    # A call of the check made with no run to name it (as the bench of a later stage might leave one): shown as having no row.
    from openconsult.consult import labels
    labels.run(p.door, p.consultations.transcript_lines(1), 1)
    assert 'href="/consultations/1/calls"' in client.get("/consultations/1").text                  # the review page's link
    assert 'href="/consultations/1/calls"' in client.get("/patients/1").text and words.MODEL_SAW_LINK in text_of(client.get("/patients/1"))
    before = record_of(p)
    answer = client.get("/consultations/1/calls")
    page = text_of(answer)
    assert answer.status_code == 200 and words.MODEL_SAW_TITLE in page and words.MODEL_SAW_INTRO in page
    calls = p.consultations.model_calls(1)
    assert len(calls) >= 3 and answer.text.count('<details class="call"') == len(calls)
    assert [f'id="call-{row["id"]}"' in answer.text for row in calls] == [True] * len(calls)        # every call, by its row
    assert "pass 1, the alarm" in page and "pass 1, the assessment" in page and "the check of who spoke" in page
    assert "the check of drug names" in page and "the label check" not in page                      # the two calls of 6c, by their names
    assert "note draft 1, at Stop" in page and page.count(words.CALL_NO_ROW) == 1                   # the run names its call; the other has no row
    model = words.LETTER_MODEL_LINE.format(model=p.door.profile.tag, engine="made-up", version="0.0-made-up")
    assert page.count(model) == len(calls)                                                           # R20, each call's own row
    main = main_of(answer.text)
    assert "<form" not in main and "<button" not in main and "<script" not in main                   # read only: nothing acts
    assert record_of(p) == before                                                                    # R2, R18: nothing written
    # A consultation not final yet has no view (ruling 28); an unknown one leads home.
    p.consultations.set(1, state="stopping")
    assert client.get("/consultations/1/calls").headers["location"] == "/consultations/1"
    p.consultations.set(1, state="final")
    assert client.get("/consultations/9/calls").headers["location"] == "/"


def test_ruling_28_15_8_ruling_1_a_call_opens_to_its_parts_by_source_and_the_reply_and_no_prompt_text_is_on_the_page(tmp_path, clock, machine):
    app, client, engine = approved(tmp_path, clock, machine)
    p = app.state.parts
    clock.advance(seconds=45)
    client.get("/consultations/1")                                        # the list call, at the first opening after Approve
    item = [i for i in p.letters.items(1) if i["kind"] == "stated"][0]
    clock.advance(minutes=5)
    assert client.post(f"/consultations/1/referrals/{item['id']}/draft").status_code == 303
    answer = client.get("/consultations/1/calls")
    page, raw = text_of(answer), answer.text
    # The pass calls: the patient line, the frame by file name, the transcript as sent; the note's turns; the list's and the letter's lines.
    for source in ("patient_line", "transcript", "turns", "lines", "note_lines", "specialty"):
        assert f'data-source="{source}"' in raw and words.SOURCE_LABELS[source] in page
    assert words.SOURCE_LABELS["frame"].format(file="alarm.frame.txt") in page and words.SOURCE_LABELS["frame"].format(file="note.frame.txt") in page
    assert 'data-source="background"' not in raw                                                     # no switch, no block (R25)
    assert "word word word" in page and "[0] Doctor: word" in page and "[1] Subjective" in page
    assert "the referral list" in page and f"letter 1, {item['specialty']}" in page and item["specialty"] in page
    assert 'data-source="whole"' not in raw and words.NOT_TAKEN_APART.split(":")[0] not in page     # every call taken apart
    assert words.CAME_BACK_HEADING in page and "Made-up condition A" in page                         # the reply, word for word
    # The prompt by name and hash, never its text (15.8 ruling 1).
    for name in PROMPTS:
        assert loader.prompt(name).split("\n")[0] not in page
    assert words.PROMPT_LINE_SAME.format(name="alarm.prompt.txt", hash=loader.sha256(loader.prompt("alarm"))) in page
    assert words.PROMPT_LINE_SAME.format(name="letter.prompt.txt", hash=loader.sha256(loader.prompt("letter"))) in page
    # The band: the passes ticked, the rows, the averages, the final line's figures, the calls after final.
    assert 'data-pass="1"' in raw and 'data-kind="alarm"' in raw and 'data-kind="note"' in raw
    assert words.TIMELINE_TYPICAL.split("{")[0] in page and words.AVERAGES_HEADING in page
    assert words.AVERAGE_LINE.format(kind="alarm", count=1, mean=0.0, slowest=0.0, failed="") in page
    assert words.FINAL_FIGURES.format(line="").rstrip() in page and "Word to page" in page
    assert words.AFTER_FINAL_HEADING in page
    assert words.AFTER_FINAL_LINE.format(kind="referral list", when="09:00:45", lead="45 seconds") in page
    assert words.AFTER_FINAL_LINE.format(kind="letter", when="09:05:45", lead="5 minutes") in page


def test_ruling_28_the_guideline_call_opens_to_its_passages_with_their_sources(tmp_path, clock, machine):
    engine = engine_with(assessment=[differentials("Made-up A", "Made-up B")], guideline=[covered()])
    app, client = app_on(tmp_path, clock, machine, nemotron_doors(three_pass_worker()), engine)
    p = app.state.parts
    load_corpus(p.sources)
    p.guidelines = Guidelines(p.sources, Index(p.sources), MadeUpEmbedder(vector_for=lambda t: axis(0)), p.door, p.audit)
    set_up(client)
    log_in(client)
    client.post("/patients", data=PATIENT)
    client.post("/consultations/start/1", data=TICKS)
    c = p.running[1]
    c.begin_sound(capture_from(CAPTURE))
    for _ in range(6):
        c.sound(LOUD)
        c.wait_for_pass()
        c.wait_for_guideline()
    client.post("/consultations/1/stop")
    assert until(lambda: c.stop_stage == "who_spoke")
    client.post("/consultations/1/speakers", data={"speaker": "S2"})
    assert until(lambda: c.state == FINAL)
    assert len(p.sources.answers(1)) >= 1
    answer = client.get("/consultations/1/calls")
    page, raw = text_of(answer), answer.text
    assert 'data-kind="guideline"' in raw and "guideline summary after pass 1" in page
    assert words.SOURCE_LABELS["query"] in page and words.SOURCE_LABELS["passages"] in page and "Made-up A; Made-up B" in page
    assert words.PASSAGE_SENT.format(n=1, title="Title A", publisher="Made-up publisher", trail=words.PASSAGE_TRAIL.format(trail="Heading A0"),
                                     similarity="1.00", cited=words.PASSAGE_CITED) in page
    first = p.sources.answers(1)[0]
    assert words.CALL_SEARCH_MS.format(ms=first["search_ms"]) in page                               # the review's point 1
    assert words.AVERAGE_LINE.format(kind="guideline summary", count=len(p.sources.answers(1)), mean=0.0, slowest=0.0, failed="") in page
    assert 'data-source="whole"' not in raw


def test_6c_the_page_lists_each_call_of_the_check_a_part_by_its_number(tmp_path, clock, machine):
    # The details of step 6c, The record: the page of the calls lists each call of the check, a part by its number.
    from openconsult.consult import labels
    app, client, c = reviewed(tmp_path, clock, machine)
    p = app.state.parts
    made = []
    for _ in range(2):                       # two calls, as a long page read in two parts leaves them
        _, outcome = labels.run(p.door, p.consultations.transcript_lines(1), 1)
        made += outcome["call_ids"]
    run = p.consultations.add_check_run(1, 2, 200)
    p.consultations.end_check_run(run, "failed", reason="made up.", call_ids=made, named_twice=0, dropped=0)
    answer = client.get("/consultations/1/calls")
    page = text_of(answer)
    assert words.CALL_CHECK_PART.format(n=1, parts=2) in page and words.CALL_CHECK_PART.format(n=2, parts=2) in page
    assert words.CALL_NO_ROW not in page and answer.text.count('data-kind="label_check"') >= 2
    first = answer.text.split(f'id="call-{made[0]}"')[1].split("</details>")[0]
    assert 'data-source="lines"' in first and "label_check.frame.txt" in first                   # each read back from its frame
    assert words.AVERAGE_LINE.format(kind="check of who spoke", count=2, mean=0.0, slowest=0.0, failed="") in page    # its seconds, by its name
    assert "label check" not in page
    c.close()
