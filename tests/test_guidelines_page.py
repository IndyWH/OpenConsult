"""The Guidelines section of Settings (spec 15.12, ruling 5; 7.3 rules 1
and 4; R15; R21): add with a file from this computer, the list, remove,
every refusal on the control, Add disabled with its reason when no worker
is installed, the corpus shipping empty. Made-up pages, a made-up
embedder; no document of any publisher."""

from openconsult import words
from openconsult.app import build_app
from openconsult.guidelines.loading import UPLOAD_LIMIT_BYTES
from openconsult.settings import store
from tests.conftest import PORT, browser, log_in, refusal_on, set_up, text_of
from tests.fakes import FakeEngine, MadeUpEmbedder
from tests.test_passages import PAGE, paragraph


def app_with_embedder(tmp_path, clock, machine, embedder):
    app = build_app(store.build(tmp_path, PORT), machine=machine, clock=clock,
                    engines={"vllm": FakeEngine(version=None), "ollama": FakeEngine()}, embedder=embedder)
    client = browser(app)
    set_up(client)
    log_in(client)
    return app, client


def add(client, data=PAGE.encode(), name="made.html", title="Made-up title", publisher="Made-up publisher", tick="yes", **more):
    fields = {"title": title, "publisher": publisher, **more}
    if tick:
        fields["statement"] = tick
    files = {"file": (name, data, "application/octet-stream")} if name is not None else None
    return client.post("/settings/guidelines/add", data=fields, files=files)


def test_ruling_5_the_corpus_ships_empty(tmp_path, clock, machine):
    app, client = app_with_embedder(tmp_path, clock, machine, MadeUpEmbedder())
    page = client.get("/settings")
    text = text_of(page)
    assert words.SECTION_GUIDELINES in text and words.NO_GUIDELINES in text and words.GUIDELINES_INTRO in text
    assert app.state.parts.sources.counts() == {"sources": 0, "passages": 0, "latest": None}
    assert 'id="guideline-sources"' not in page.text and 'id="add-guideline"' in page.text and "disabled" not in page.text.split('id="add-guideline"')[1][:20]
    assert words.GUIDELINE_WORKER_LINE.format(state="running on the graphics card, made-up/embedder@0") in text


def test_ruling_5_7_3_R15_the_guidelines_section_adds_lists_and_removes_with_every_refusal_on_the_control(tmp_path, clock, machine):
    embedder = MadeUpEmbedder()
    app, client = app_with_embedder(tmp_path, clock, machine, embedder)
    p = app.state.parts
    done = add(client)
    assert done.status_code == 303 and done.headers["location"].startswith("/settings?done=guideline_added&passages=")
    page = client.get(done.headers["location"])
    text = text_of(page)
    assert 'id="guideline-sources"' in page.text and "Made-up title" in text and "Made-up publisher" in text and "4 Oct 2026" in text
    assert words.GUIDELINE_ADDED.split(":")[0] in text and words.NO_GUIDELINES not in text
    sources = p.sources.loaded()
    assert len(sources) == 1 and sources[0]["passage_count"] == len(p.sources.passages_of(sources[0]["id"])) >= 5
    assert sources[0]["added_by"] == "page" and sources[0]["kind"] == "html" and sources[0]["model"] == "made-up/embedder@0"
    assert embedder.embedded and embedder.embedded[0][0].startswith("title: Made-up title | text: Intro") and any(t.startswith("title: Made-up title: Recommendations | text: ") for t in embedder.embedded[0])
    assert p.audit.lines()[0].event == "guideline.added" and "Made-up" not in p.audit.lines()[0].detail
    # Every refusal lands on Add (R15); nothing is added by a refused post.
    for response, expected in (
            (add(client, name=None), words.GUIDELINE_FILE_MISSING),
            (add(client, data=b""), words.GUIDELINE_FILE_MISSING),
            (add(client, title=" "), words.GUIDELINE_TITLE_MISSING),
            (add(client, publisher=""), words.GUIDELINE_PUBLISHER_MISSING),
            (add(client, tick=None), words.GUIDELINE_TICK_NEEDED),
            (add(client, data=b"PK...", name="letter.docx"), words.GUIDELINE_FILE_KIND),
            (add(client, data=b"%PDF-1.4 broken", name="x.pdf"), words.GUIDELINE_FILE_KIND),
            (add(client, data=b"too short", name="short.txt"), words.GUIDELINE_NO_PASSAGES),
            (add(client, data=b"x" * (UPLOAD_LIMIT_BYTES + 1), name="big.txt"), words.GUIDELINE_FILE_TOO_BIG.format(limit=50))):
        assert response.status_code == 400 and refusal_on(response.text, "add-guideline") == expected, expected
    assert len(p.sources.loaded()) == 1
    embedder.fail = "made-up: the worker died"
    refused = add(client, data=paragraph(80).encode(), name="other.txt")
    assert refusal_on(refused.text, "add-guideline") == words.GUIDELINE_EMBED_FAILED.format(reason="made-up: the worker died")
    assert len(p.sources.loaded()) == 1
    embedder.fail = None
    # A plain-text file and a title typed by the doctor; the list is newest first.
    clock.advance(minutes=1)                       # a day would lock the screen (15.6)
    assert add(client, data=f"Ignored title line\n\n{paragraph(80)}\n".encode(), name="notes.txt", title="Typed title").status_code == 303
    text = text_of(client.get("/settings"))
    assert text.index("Typed title") < text.index("Made-up title") and "Ignored title line" not in text.split("Typed title")[0]
    # Remove takes one out with its passages, audited; a second press is no control.
    first = sources[0]["id"]
    gone = client.post(f"/settings/guidelines/{first}/remove")
    assert gone.status_code == 303 and gone.headers["location"] == "/settings?done=guideline_removed"
    text = text_of(client.get("/settings?done=guideline_removed"))
    assert "Made-up title" not in text and "Typed title" in text and words.GUIDELINE_REMOVED in text
    assert p.sources.passages_of(first) == [] and p.audit.lines()[0].event == "guideline.removed"
    assert client.post(f"/settings/guidelines/{first}/remove").headers["location"] == "/settings"
    assert client.post("/settings/guidelines/999/remove").headers["location"] == "/settings"
    assert p.sources.counts()["sources"] == 1


def test_7_3_rule_1_with_no_worker_installed_add_is_disabled_with_the_reason_and_a_post_is_refused(tmp_path, clock, machine):
    app, client = app_with_embedder(tmp_path, clock, machine, MadeUpEmbedder(installed=False))
    page = client.get("/settings")
    text = text_of(page)
    assert 'id="add-guideline" aria-describedby="add-guideline-refusal" disabled' in page.text
    assert words.GUIDELINE_ADD_NEEDS_WORKER.format(reason=words.GUIDELINE_NOT_INSTALLED) in text
    assert words.GUIDELINE_WORKER_LINE.format(state=words.WORKER_STATES["not_installed"]) in text
    refused = add(client)
    assert refusal_on(refused.text, "add-guideline") == words.GUIDELINE_ADD_NEEDS_WORKER.format(reason=words.GUIDELINE_NOT_INSTALLED)
    assert app.state.parts.sources.loaded() == []
    # The app built with no embedder named gets the door with nothing behind it, and its shutdown closes it.
    from openconsult.app import build_app
    from openconsult.settings import store as store_module
    other = build_app(store_module.build(tmp_path / "other", PORT), machine=machine, clock=clock,
                      engines={"vllm": FakeEngine(version=None), "ollama": FakeEngine()})
    assert other.state.parts.embedder.installed is False and other.state.parts.embedder.where == "card"
