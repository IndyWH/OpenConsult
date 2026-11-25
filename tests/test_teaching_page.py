"""The teaching page and its tab (spec 12.5; 15.14, rulings 1, 3 and 22,
and the details of run 10b: Where teaching lives, The teaching page;
R24). A made bank stands behind most tests; the app's own bank is read
where the page's eight rows are pinned. No model is asked."""

import json

from openconsult.app import build_app
from openconsult.settings import store
from openconsult.teaching import bank as bank_module, words as t
from openconsult import words
from openconsult.web import teaching as teaching_web
from tests import made_teaching
from tests.conftest import PORT, browser, log_in, set_up, text_of
from tests.fakes import FakeEngine


def teaching_app(tmp_path, clock, machine, engine=None, bank="made", **more):
    """An app with a user logged in; a made bank unless the app's own is asked for with bank=None."""
    app = build_app(store.build(tmp_path, PORT), machine=machine, clock=clock,
                    engines={"vllm": FakeEngine(version=None), "ollama": engine or FakeEngine()},
                    bank=made_teaching.made_bank() if bank == "made" else bank, **more)
    client = browser(app)
    set_up(client)
    log_in(client)
    return app, client


def bar_of(raw: str) -> str:
    return raw.split('<nav class="tabs">', 1)[1].split("</nav>", 1)[0]


def test_15_14_the_tab_teaching_stands_after_new_patient_on_every_page_behind_the_login(tmp_path, clock, machine):
    app, client = teaching_app(tmp_path, clock, machine)
    for address in ("/", "/patients/new", "/settings", "/log", "/teaching"):
        bar = bar_of(client.get(address).text)
        found = [bar.find(f'href="{to}"') for to in ("/", "/patients/new", "/teaching", "/settings", "/log")]
        assert all(f >= 0 for f in found) and found == sorted(found), address
        assert f">{words.NAV_TEACHING}</a>" in bar
    assert '<a href="/teaching" class="active">' in bar_of(client.get("/teaching").text)
    assert '<a href="/teaching" class="active">' not in bar_of(client.get("/settings").text)


def test_15_14_rulings_1_and_22_the_page_says_no_affiliation_and_no_real_patient_before_anything_else(tmp_path, clock, machine):
    app, client = teaching_app(tmp_path, clock, machine)
    raw = client.get("/teaching").text
    page = text_of(client.get("/teaching"))
    assert "OpenConsult is not affiliated with or endorsed by the RCGP." in page          # 12.5; ruling 1
    assert t.NOT_AFFILIATED in page and t.NO_REAL_PATIENT in page and "real patient" in t.NO_REAL_PATIENT
    found = [raw.find('id="not-affiliated"'), raw.find('id="no-real-patient"'), raw.find('id="bank"')]
    assert all(f >= 0 for f in found) and found == sorted(found)                          # in the order of the details
    assert words.STATEMENT in page                                                        # the prototype's own statement, as on every page


def test_15_14_ruling_3_each_case_of_the_bank_is_a_row_with_its_number_topic_level_and_label_and_nothing_names_a_diagnosis(tmp_path, clock, machine):
    app, client = teaching_app(tmp_path, clock, machine, bank=None)                       # the app's own bank
    raw = client.get("/teaching").text
    page = text_of(client.get("/teaching"))
    rows = raw.split('id="bank-cases"', 1)[1].split("</table>", 1)[0].split("<tr data-case=")[1:]
    assert len(rows) == 8 and 'id="bank-unread"' not in raw
    for n, (row, case) in enumerate(zip(rows, app.state.parts.teaching.bank.cases), 1):
        assert row.startswith(f'"{n}">') and f"<td>Case {n}</td>" in row
        assert f"<td>{case.topic}</td>" in row and f"<td>{t.LEVEL_NAMES[case.level]}</td>" in row and t.LABELS[case.label] in text_of_row(row)
    assert page.count("Made from a clinician's script. The scenario is not yet reviewed.") == 8   # ruling 3: none is approved yet
    # The name of a file and the id inside it name the diagnosis: neither is on the page, nor any longer word of them.
    for path in sorted(bank_module.FOLDER.glob("card_*.json")):
        held = json.loads(path.read_text(encoding="utf-8"))
        assert held["id"] not in raw and path.stem not in raw and held["source"] not in raw
        for word in (w for w in path.stem.split("_")[2:] if len(w) >= 5):
            assert word not in raw.lower(), word
        # Nothing of the scenario stands on the page either: not the patient's name, not a diagnosis.
        assert held["scenario"]["patient"]["name"] not in page
        assert not [d for d in held["scenario"]["differential"] if d["diagnosis"] in page]


def text_of_row(row: str) -> str:
    import html
    return html.unescape(row)


def test_15_14_the_page_says_when_a_file_of_the_bank_could_not_be_read(tmp_path, clock, machine):
    app, client = teaching_app(tmp_path / "one", clock, machine, bank=made_teaching.made_bank(unread=1))
    assert "One case could not be read and is not offered." in text_of(client.get("/teaching"))
    app, client = teaching_app(tmp_path / "three", clock, machine, bank=made_teaching.made_bank(unread=3))
    assert "3 cases could not be read and are not offered." in text_of(client.get("/teaching"))
    assert client.get("/teaching").text.count("<tr data-case=") == 2                      # the cases that were read are offered
    app, client = teaching_app(tmp_path / "none", clock, machine)
    assert 'id="bank-unread"' not in client.get("/teaching").text


def test_15_6_R24_the_teaching_page_is_behind_the_login_and_every_address_of_teaching_is_its_own(tmp_path, clock, machine):
    app = build_app(store.build(tmp_path, PORT), machine=machine, clock=clock,
                    engines={"vllm": FakeEngine(version=None), "ollama": FakeEngine()}, bank=made_teaching.made_bank())
    client = browser(app)
    assert client.get("/teaching").headers["location"] == "/first-run"                    # the first run comes first
    set_up(client)
    assert client.get("/teaching").headers["location"] == "/login"
    log_in(client)
    assert client.get("/teaching").status_code == 200
    # Teaching's pages have addresses of their own (R24): every route of its module begins /teaching or /settings/teaching.
    own = {route.path for route in teaching_web.router.routes}
    assert own and all(path == "/teaching" or path.startswith(("/teaching/", "/settings/teaching")) for path in own)
    # And no other module of pages has an address of teaching: the app's addresses that name it are exactly these.
    assert {path for path in app.openapi()["paths"] if "teach" in path.lower()} == own
