"""A browser never runs a script or a style older than the app that
served the page (spec 15.10, the details of the mend run of step 6d,
Three more mends, one). In the room check of 15 Nov 2026 the page was
the new one and the browser ran its own stored copies of older scripts,
because the app served them with nothing that tells a browser when its
copy is too old: two mends never ran. Now every address of a script or
a style carries a mark worked out from the file's own bytes, and the
static files are served so that a browser asks each time."""

import hashlib
import re

from openconsult.app import build_app
from openconsult.settings import store
from openconsult.speech.choices import NEMOTRON
from openconsult.speech.door import Door as SpeechDoor
from openconsult.web import pages
from tests.conftest import PORT, browser, log_in, set_up
from tests.fakes import FakeEngine, MadeUpWorker
from tests.test_letters_page import drafted
from tests.test_live import live_seg
from tests.test_start import PATIENT, TICKS
from tests.test_stop import until

NAMED = re.compile(r'<(?:script src|link rel="stylesheet" href)="([^"]*)"')


def marks_hold(client, raw: str) -> list[str]:
    """Every script and style the page names, each proven to carry the
    mark of the file as the app serves it now; the names, in order."""
    names = []
    for address in NAMED.findall(raw):
        found = re.fullmatch(r"/static/([A-Za-z._-]+)\?v=([0-9a-f]{12})", address)
        assert found, f"an address with no mark: {address}"
        served = client.get(f"/static/{found.group(1)}")
        assert served.status_code == 200 and hashlib.sha256(served.content).hexdigest()[:12] == found.group(2), address
        assert client.get(address).content == served.content            # the marked address gives the same file
        names.append(found.group(1))
    assert "/static/" not in NAMED.sub("", raw)                          # and the page names no other
    return names


def test_6d2_every_script_and_style_address_on_every_page_carries_the_mark_of_the_file_as_it_stands(tmp_path, clock, machine):
    seen = {}
    # The first run and the login page, on an app nobody has set up.
    fresh = build_app(store.build(tmp_path / "fresh", PORT), machine=machine, clock=clock,
                      engines={"vllm": FakeEngine(version=None), "ollama": FakeEngine()})
    visitor = browser(fresh)
    seen["first run: the statement"] = marks_hold(visitor, visitor.get("/first-run").text)
    visitor.post("/first-run/statement", data={"agree": "yes"})
    seen["first run: this machine"] = marks_hold(visitor, visitor.get("/first-run").text)
    visitor.post("/first-run/machine", data={})
    seen["first run: you"] = marks_hold(visitor, visitor.get("/first-run").text)
    set_up(visitor)
    seen["login"] = marks_hold(visitor, visitor.get("/login").text)
    # A consultation: the new-patient form, Start, the live page, and Stop waiting for its answer.
    worker = MadeUpWorker(live=[[live_seg(1, 0.0, 0.2, "made up words")], [], [live_seg(2, 0.3, 0.5, "more", "S2")]])
    doors = {NEMOTRON.name: SpeechDoor(NEMOTRON, make_worker=lambda: worker, installed=lambda: True)}
    live_app = build_app(store.build(tmp_path / "live", PORT), machine=machine, clock=clock,
                         engines={"vllm": FakeEngine(version=None), "ollama": FakeEngine()}, doors=doors)
    client = browser(live_app)
    set_up(client)
    log_in(client)
    seen["new patient"] = marks_hold(client, client.get("/patients/new").text)
    client.post("/patients", data=PATIENT)
    seen["Start"] = marks_hold(client, client.get("/consultations/start/1").text)
    assert client.post("/consultations/start/1", data=TICKS).status_code == 303
    live = client.get("/consultations/1").text
    seen["live"] = marks_hold(client, live)
    # The recorder worklet is named by the live script, not by the page: the page hands the script its mark.
    worklet = client.get("/static/recorder-worklet.js").content
    assert f'data-worklet-mark="{hashlib.sha256(worklet).hexdigest()[:12]}"' in live
    assert "'/static/recorder-worklet.js?v=' + page.dataset.workletMark" in client.get("/static/live.js").text
    client.post("/consultations/1/stop")
    assert until(lambda: live_app.state.parts.running[1].stop_stage == "who_spoke")
    seen["stopping"] = marks_hold(client, client.get("/consultations/1").text)
    live_app.state.parts.running[1].close()
    # A consultation with an approved note and a letter: every other page behind the login.
    app, client, engine, item = drafted(tmp_path / "drafted", clock, machine)
    for name, address in (("the Patients page", "/"), ("a patient", "/patients/1"), ("review, approved, with its letters", "/consultations/1"),
                          ("a letter", "/consultations/1/letters/1"), ("the calls", "/consultations/1/calls"), ("Settings", "/settings"),
                          ("the Log", "/log")):
        page = client.get(address)
        assert page.status_code == 200, name
        seen[name] = marks_hold(client, page.text)
    # Every page names the style sheet; the pages with scripts name each of them, marked.
    assert all(names[0] == "theme.css" for names in seen.values()) and len(seen) == 15
    assert seen["live"][1:] == ["alarmdialog.js", "panels.js", "guidelines.js", "earlier.js", "live.js"]
    assert seen["review, approved, with its letters"][1:] == ["print.css", "use.js", "alarmdialog.js", "review.js", "fresh.js", "rows.js", "place.js",
                                                             "letters.js", "player.js"]
    assert seen["a letter"][1:] == ["use.js", "letters.js"] and seen["new patient"][1:] == ["use.js"]


def test_6d2_the_mark_changes_when_the_files_bytes_do_and_not_otherwise(tmp_path):
    (tmp_path / "a.js").write_text("made up script, as first written\n")
    first = pages.static_mark("a.js", tmp_path)
    assert re.fullmatch(r"[0-9a-f]{12}", first) and pages.static_address("a.js", tmp_path) == f"/static/a.js?v={first}"
    assert pages.static_mark("a.js", tmp_path) == first                                # the same bytes: the same mark, read again
    (tmp_path / "a.js").write_text("made up script, as first written\n")                # written again with the same bytes: the same
    assert pages.static_mark("a.js", tmp_path) == first
    (tmp_path / "a.js").write_text("made up script, mended\n")
    second = pages.static_mark("a.js", tmp_path)
    assert second != first and pages.static_address("a.js", tmp_path) == f"/static/a.js?v={second}"
    (tmp_path / "b.css").write_text("made up script, mended\n")                         # the mark is of the bytes, not of the name
    assert pages.static_mark("b.css", tmp_path) == second


def test_6d2_a_static_file_is_served_so_that_a_browser_asks_each_time_and_is_told_when_its_copy_is_still_good(logged_in):
    for name in ("player.js", "use.js", "theme.css", "recorder-worklet.js"):
        served = logged_in.get(f"/static/{name}")
        assert served.status_code == 200 and served.headers["cache-control"] == "no-cache" and served.headers["etag"]
        # The browser's question, with the name of the copy it holds: still good, and nothing is sent again.
        again = logged_in.get(f"/static/{name}", headers={"If-None-Match": served.headers["etag"]})
        assert again.status_code == 304 and again.content == b"" and again.headers["cache-control"] == "no-cache"
        # A copy of other bytes: the file is sent.
        other = logged_in.get(f"/static/{name}", headers={"If-None-Match": '"another-copy"'})
        assert other.status_code == 200 and other.content == served.content
