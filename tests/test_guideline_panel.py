"""The guideline panel of the live page (spec 15.12, rulings 5 and 6; R3,
R4, R5, R15, R30; 10.4): called when the top two differentials differ
and not otherwise, one at a time, never during Stop, a failed call
touching nothing of the pass or the alarm, no corpus meaning no call,
and nothing of the panel in any other call. A made-up corpus, a made-up
embedder, made-up replies; no model speaks."""

import threading
from pathlib import Path

import pytest

from openconsult import words
from openconsult.app import build_app
from openconsult.consult.live import FINAL
from openconsult.guidelines.panel import Guidelines, PanelState
from openconsult.guidelines.search import Index
from openconsult.guidelines.sources import Passage, SourceRow, Sources
from openconsult.llm.engine import EngineTimeout
from openconsult.settings import store
from openconsult.speech.door import Door as SpeechDoor
from openconsult.speech.choices import NEMOTRON
from openconsult.web.live import capture_from
from tests.conftest import PORT, browser, log_in, set_up, text_of
from tests.test_stop import until
from tests.fakes import ALARM_FIRES, FakeEngine, MadeUpEmbedder, MadeUpWorker
from tests.test_guideline_search import axis
from tests.test_letters_page import LETTER, LIST, NOTE
from tests.test_live import CAPTURE, LOUD, Room, live_seg
from tests.test_review_page import CHECK, LINES
from tests.test_start import PATIENT, TICKS

SENTINEL = "MADEUPSENTINEL"


def differentials(*names):
    return {"reasoning": "made up", "differentials": [{"condition": n, "likelihood": "high", "rationale": "made up"} for n in names],
            "questions_to_ask": [], "signs_to_check": []}


def covered(text=f"{SENTINEL} summary [1]."):
    return {"covered": True, "summary": text, "passages_cited": [1]}


def load_corpus(sources: Sources):
    """Three sources, five passages each, on axes 0 to 14; a query on axis 0 finds source A's first passage."""
    for name, first in (("A", 0), ("B", 5), ("C", 10)):
        passages = [Passage(i, f"Heading {name}{i}", f"MADEUPPASSAGE {name} {i} " * 8, 40, axis(first + i)) for i in range(5)]
        sources.add_source(SourceRow(f"Title {name}", "Made-up publisher", f"{name}.html", "html", "h" * 64, 1, "command", "made-up/embedder@0"), passages)


def three_pass_worker():
    return MadeUpWorker(live=[[live_seg(1, 0.0, 0.2, "First made-up line.")], [], [live_seg(2, 0.3, 0.5, "x" * 160, "S2")], [],
                              [live_seg(3, 0.6, 0.9, "y" * 160)], []])


@pytest.fixture
def room(clock):
    """Rooms built by the test, each closed at its end so no thread outlives it."""
    built = []

    def build(folder, worker, engine):
        made = Room(folder, clock, worker=worker, engine=engine)
        built.append(made)
        return made
    yield build
    for made in built:
        made.close()


def panel_room(room, tmp_path, clock, engine, embedder=None, corpus=True, worker=None):
    r = room(tmp_path, worker or three_pass_worker(), engine)
    sources = Sources(r.db, r.audit, clock)
    if corpus:
        load_corpus(sources)
    service = Guidelines(sources, Index(sources), embedder or MadeUpEmbedder(vector_for=lambda t: axis(0)), r.llm, r.audit)
    r.consultation.guideline = PanelState(service, r.consultation)
    return r, sources, service


def run_passes(c, pieces):
    c.begin_sound(CAPTURE)
    for _ in range(pieces):
        c.sound(LOUD)
        c.wait_for_pass()
        c.wait_for_guideline()


def test_ruling_6_the_panel_is_called_when_the_top_two_differ_and_not_otherwise(room, tmp_path, clock):
    engine = FakeEngine({"assessment": [differentials("Made-up A", "Made-up B", "Made-up Z"), differentials("Made-up B", "Made-up A"),
                                        differentials("Made-up A", "Made-up C")],
                         "guideline": [covered(), covered("second [1][2]")]})
    r, sources, service = panel_room(room, tmp_path, clock, engine)
    c = r.consultation
    assert c.page_state()["guidelines"]["state"] == "waiting"
    run_passes(c, 6)
    assert c.passes.n == 3 and len(engine.calls_for("guideline")) == 2            # pass 1 (A, B); pass 2 (B, A) the same pair; pass 3 (A, C)
    calls = engine.calls_for("guideline")
    assert calls[0].user.startswith("The patient is a 35-year-old woman.\n\nQUERY: Made-up A; Made-up B\n\nPASSAGES:\n[1] Title A: Heading A0\n")
    assert "Made-up Z" not in calls[0].user and calls[1].user.split("QUERY: ")[1].startswith("Made-up A; Made-up C\n")
    rows = sources.answers(c.id)
    assert [(a["pass_n"], a["names"], a["outcome"], a["shown"]) for a in rows] == [(1, ["Made-up A", "Made-up B"], "covered", 1),
                                                                                  (3, ["Made-up A", "Made-up C"], "covered", 1)]
    first = rows[0]
    assert first["query"] == "Made-up A; Made-up B" and first["summary"].startswith(SENTINEL) and first["passages_cited"] == [1]
    assert len(first["passages"]) == 6 and first["passages"][0]["cited"] and not first["passages"][1]["cited"]
    assert first["passages"][0]["title"] == "Title A" and first["passages"][0]["similarity"] == 1.0 and first["top_similarity"] == 1.0
    assert first["candidates"] >= 12 and first["floor"] == 0.45 and first["call_id"] and first["wall_ms"] >= 0
    # Ruling 25: the app's search never asks the worker to rerank, the row says so, and the page has no line for it.
    assert first["reranker_ran"] == 0 and service.embedder.reranked == [] and "reranker_ran" not in c.page_state()["guidelines"]["result"]
    script = (Path(__file__).resolve().parents[1] / "openconsult" / "web" / "static" / "guidelines.js").read_text()
    assert not hasattr(words, "GUIDELINE_RERANKED") and "rerank" not in script
    state = c.page_state()["guidelines"]
    assert state["state"] == "result" and state["searching"] is None and state["result"]["state"] == "covered"
    assert state["result"]["names_text"] == "Made-up A; Made-up C" and state["result"]["cited"] == [1, 2] and state["result"]["pass_n"] == 3
    assert state["result"]["passages"][0]["text"].startswith("MADEUPPASSAGE A 0") and state["provenance"]["sources"] == 3
    assert state["provenance"]["passages"] == 15 and state["provenance"]["date"] == "4 Oct 2026"
    lines = [line for line in r.audit.lines() if line.event in ("guideline.summary", "guideline.not_covered", "guideline.failed")]
    assert len(lines) == 2 and all(line.event == "guideline.summary" and SENTINEL not in line.detail and "MADEUPPASSAGE" not in line.detail for line in lines)
    assert "6 passages sent, 1 cited" in lines[-1].detail
    # A single differential queries one name; a kept list (an empty reply) asks nothing.
    engine2 = FakeEngine({"assessment": [differentials("Made-up D"), {"reasoning": "x", "differentials": [], "questions_to_ask": [], "signs_to_check": []}],
                          "guideline": [{"covered": False, "summary": "the made corpus lacks it.", "passages_cited": []}]})
    r2, sources2, _ = panel_room(room, tmp_path / "two", clock, engine2, worker=three_pass_worker())
    run_passes(r2.consultation, 4)
    assert [call.user.split("QUERY: ")[1].split("\n")[0] for call in engine2.calls_for("guideline")] == ["Made-up D"]
    answer = sources2.answers(r2.consultation.id)[0]
    assert answer["outcome"] == "not_covered" and answer["covered"] == 0 and answer["summary"] == "the made corpus lacks it."
    result = r2.consultation.page_state()["guidelines"]["result"]
    assert result["state"] == "not_covered" and result["model_sentence"] == "the made corpus lacks it." and result["summary"] is None


def test_R30_a_failed_or_slow_summary_call_leaves_the_pass_and_the_alarm_untouched_and_the_next_pass_runs(room, tmp_path, clock):
    engine = FakeEngine({"alarm": [ALARM_FIRES], "assessment": [differentials("Made-up A", "Made-up B"), differentials("Made-up C", "Made-up D")],
                         "guideline": [EngineTimeout("no answer"), covered()]})
    r, sources, _ = panel_room(room, tmp_path, clock, engine)
    c = r.consultation
    run_passes(c, 2)
    stored_pass = r.rows.passes(c.id)[0]
    alarm_before = [a.__dict__ for a in c.passes.history]
    first = sources.answers(c.id)[0]
    assert first["outcome"] == "failed" and first["failure"].startswith("too_slow") and first["call_id"] and first["covered"] is None
    result = c.page_state()["guidelines"]["result"]
    assert result["state"] == "failed" and result["failure"].startswith("too_slow")
    assert r.rows.passes(c.id)[0] == stored_pass and [a.__dict__ for a in c.passes.history] == alarm_before
    assert c.passes.history[-1].state == "fired" and c.page_state()["passes"]["alarm"]["state"] == "fired"
    assert [line.event for line in r.audit.lines() if line.event in ("guideline.summary", "guideline.not_covered", "guideline.failed")] == ["guideline.failed"]
    run_passes(c, 2)                                                           # the next pass runs, and its new pair is searched
    assert c.passes.n == 2 and len(engine.calls_for("guideline")) == 2 and sources.answers(c.id)[1]["outcome"] == "covered"
    # The floor refuses with no call (R3), below the floor on every passage.
    far = FakeEngine({"assessment": [differentials("Made-up far")], "guideline": [covered()]})
    r3, sources3, _ = panel_room(room, tmp_path / "three", clock, far, embedder=MadeUpEmbedder(vector_for=lambda t: axis(700)))
    run_passes(r3.consultation, 2)
    row = sources3.answers(r3.consultation.id)[0]
    assert row["outcome"] == "below_floor" and row["call_id"] is None and far.calls_for("guideline") == [] and row["top_similarity"] == 0.0
    assert r3.consultation.page_state()["guidelines"]["result"]["state"] == "not_covered"


def test_ruling_6_never_during_stop_and_a_late_result_is_recorded_not_shown(room, tmp_path, clock):
    hold = threading.Event()

    def slow_vector(text):
        hold.wait(10)
        return axis(0)
    engine = FakeEngine({"assessment": [differentials("Made-up A", "Made-up B")], "guideline": [covered()]})
    r, sources, service = panel_room(room, tmp_path, clock, engine, embedder=MadeUpEmbedder(vector_for=slow_vector))
    c = r.consultation
    c.begin_sound(CAPTURE)
    c.sound(LOUD)
    c.wait_for_pass()
    assert c.guideline.running and c.page_state()["guidelines"]["searching"] == ["Made-up A", "Made-up B"]
    assert c.page_state()["guidelines"]["state"] == "searching" and c.page_state()["guidelines"]["result"] is None
    c.on_stop = None
    assert c.stop()
    hold.set()
    c.wait_for_guideline()
    row = sources.answers(c.id)[0]
    assert row["outcome"] == "covered" and row["shown"] == 0 and c.guideline.shown is None
    # Once stopping, a pass that lands is not shown and asks the panel nothing.
    from openconsult.consult.cds_pass import Assessment
    c.guideline.after_pass(2, Assessment(True, [{"condition": "Made-up Q"}], [], [], None, None, None, 1))
    assert not c.guideline.running and len(engine.calls_for("guideline")) == 1


def test_ruling_5_R3_with_no_corpus_the_panel_says_so_and_no_call_is_made(room, tmp_path, clock):
    engine = FakeEngine({"assessment": [differentials("Made-up A", "Made-up B")]})
    embedder = MadeUpEmbedder(vector_for=lambda t: axis(0))
    r, sources, service = panel_room(room, tmp_path, clock, engine, embedder=embedder, corpus=False)
    c = r.consultation
    run_passes(c, 2)
    assert c.passes.n == 1 and engine.calls_for("guideline") == [] and embedder.embedded == [] and sources.answers(c.id) == []
    state = c.page_state()["guidelines"]
    assert state["state"] == "no_corpus" and state["result"] is None and state["provenance"] == {"sources": 0, "passages": 0, "date": ""}
    # The worker not installed: the panel says so, no search.
    r2, _, _ = panel_room(room, tmp_path / "two", clock, FakeEngine({"assessment": [differentials("Made-up A")]}), embedder=MadeUpEmbedder(installed=False))
    run_passes(r2.consultation, 2)
    assert r2.consultation.page_state()["guidelines"]["state"] == "not_installed" and r2.engine.calls_for("guideline") == []


def test_R4_R5_nothing_from_the_panel_reaches_the_note_the_list_or_the_letter_call(tmp_path, clock, machine):
    engine = FakeEngine({"alarm": [ALARM_FIRES], "label_check": [CHECK], "note": [NOTE], "referrals": [LIST], "letter": [LETTER],
                         "guideline": [covered()]})
    worker = MadeUpWorker(live=LINES)
    doors = {NEMOTRON.name: SpeechDoor(NEMOTRON, make_worker=lambda: worker, installed=lambda: True)}
    app = build_app(store.build(tmp_path, PORT), machine=machine, clock=clock,
                    engines={"vllm": FakeEngine(version=None), "ollama": engine}, doors=doors,
                    embedder=MadeUpEmbedder(vector_for=lambda t: axis(0)))
    p = app.state.parts
    load_corpus(p.sources)
    p.guidelines.index.refresh()
    client = browser(app)
    set_up(client)
    log_in(client)
    client.post("/patients", data=PATIENT)
    client.post("/consultations/start/1", data=TICKS)
    c = p.running[1]
    c.begin_sound(capture_from({"type": "capture", "echo_cancellation": False, "noise_suppression": False, "auto_gain": False, "rate": 48000}))
    for _ in range(8):
        c.sound(LOUD)
        c.wait_for_pass()
        c.wait_for_guideline()
    page = client.get("/consultations/1")
    assert 'id="guidelines-pane"' in page.text and "/static/guidelines.js" in page.text and client.get("/static/guidelines.js").status_code == 200
    assert SENTINEL in page.text                                                  # the state the script renders holds the summary
    assert len(engine.calls_for("guideline")) == 1 and p.sources.answers(1)[0]["outcome"] == "covered"
    client.post("/consultations/1/stop")
    assert until(lambda: c.stop_stage == "who_spoke")
    client.post("/consultations/1/speakers", data={"speaker": "S1"})
    assert until(lambda: c.state == FINAL)
    client.post("/consultations/1/note/approve")
    client.get("/consultations/1")
    item = [i for i in p.letters.items(1) if i["kind"] == "stated"][0]
    client.post(f"/consultations/1/referrals/{item['id']}/draft")
    assert engine.calls_for("note") and engine.calls_for("referrals") and engine.calls_for("letter")
    for job in ("alarm", "assessment", "label_check", "note", "referrals", "letter"):
        for call in engine.calls_for(job):
            assert SENTINEL not in call.user and "MADEUPPASSAGE" not in call.user and "PASSAGES:" not in call.user, job
    assert SENTINEL not in client.get("/consultations/1/note.txt").text
    review = text_of(client.get("/consultations/1"))
    assert SENTINEL not in review and words.PANEL_GUIDELINES not in review        # the panel lives on the live page alone
