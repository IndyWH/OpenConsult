"""The kept cases (spec 15.14, ruling 22 and the details of run 10b: Kept
cases, The teaching page; R24). Everything of a case is saved as it
happens, so a case that was left is listed as not finished and gone on
with from where it stood, and a finished one opens as it was. A made
bank and a made engine: no model is asked for real."""

import re

from openconsult.teaching import words as t
from tests import made_teaching
from tests.conftest import log_in, text_of
from tests.fakes import FakeEngine
from tests.test_teaching_examination import came
from tests.test_teaching_feedback import ANSWER
from tests.test_teaching_history import reply
from tests.test_teaching_page import teaching_app
from tests.test_teaching_start import start


def scripted() -> FakeEngine:
    return FakeEngine(script={"teaching_patient": [reply("A made-up reply.")] * 4, "teaching_examination": [came(asked=[1])] * 2,
                              "teaching_feedback": [ANSWER]})


def rows(raw: str) -> list[list[str]]:
    """The rows of Your cases as a reader meets them: the words of each cell."""
    table = raw.split('id="kept-cases"', 1)[1].split("</table>", 1)[0]
    found = []
    for row in table.split("<tr data-kept=")[1:]:
        found.append([text_of_cell(cell) for cell in re.findall(r"<td>(.*?)</td>", row, flags=re.S)])
    return found


def text_of_cell(cell: str) -> str:
    import html
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", cell)).split())


def finish(client, case: int = 1):
    client.post(f"/teaching/cases/{case}/say", data={"line": "1", "text": "A made-up line."})
    client.post(f"/teaching/cases/{case}/end-history", data={"text": ""})
    client.post(f"/teaching/cases/{case}/examine", data={"n": "1", "text": "Made-up one."})
    client.post(f"/teaching/cases/{case}/finish-examination", data={"text": ""})
    for question in (1, 2, 3):
        client.post(f"/teaching/cases/{case}/answer", data={"question": str(question), "text": f"A made-up answer {question}."})


def test_15_14_ruling_22_your_cases_lists_every_case_begun_on_this_computer_newest_first_finished_or_not(tmp_path, clock, machine):
    app, client = teaching_app(tmp_path, clock, machine, scripted())
    app.state.parts.teaching.run = lambda work: work()
    raw = client.get("/teaching").text
    assert '<p class="mark" id="no-cases">No case has been started on this computer.</p>' in raw and 'id="kept-cases"' not in raw
    found = [raw.find(f'id="{part}"') for part in ("new-case", "bank", "your-cases")]
    assert all(f >= 0 for f in found) and found == sorted(found)                       # the order of the details
    start(client, 1)
    finish(client, 1)
    clock.advance(days=2)
    log_in(client)                                                                     # two days on, the login had ended
    start(client, 2)
    raw = client.get("/teaching").text
    assert rows(raw) == [
        ["6 Oct 2026", "Another made-up topic", "Hidden", "Approved by a clinician", "Not finished", "Go on"],
        ["4 Oct 2026", "A made-up topic", "Straightforward", "Made from a clinician's script. The scenario is not yet reviewed.", "Finished", "Open"]]
    assert '<a class="button" id="open-2" href="/teaching/cases/2">Go on</a>' in raw and '<a class="button" id="open-1" href="/teaching/cases/1">Open</a>' in raw
    assert 'id="no-cases"' not in raw
    # Nothing of a scenario stands in the list: not the patient's name, nothing of either part.
    kept = raw.split('id="your-cases"', 1)[1]
    assert "Made Up" not in kept and "made-up ache" not in kept and "Qdiagone" not in kept and "A made-up line." not in kept


def test_15_14_ruling_22_a_case_that_was_left_is_gone_on_with_from_where_it_stood_after_the_app_was_closed(tmp_path, clock, machine):
    first = scripted()
    app, client = teaching_app(tmp_path, clock, machine, first)
    start(client, 1)
    client.post("/teaching/cases/1/say", data={"line": "1", "text": "A line before the app was closed."})
    client.post("/teaching/cases/1/end-history", data={"text": ""})
    client.post("/teaching/cases/1/examine", data={"n": "1", "text": "Made-up one."})
    client.post("/teaching/cases/1/finish-examination", data={"text": ""})
    client.post("/teaching/cases/1/answer", data={"question": "1", "text": "An answer before the app was closed."})
    start(client, 2)                                                                   # a second case, left at its very start
    app.state.parts.db.close()
    # The app started again on the same data folder: both cases are listed as not finished and stand where they stood.
    again = scripted()
    app, client = teaching_app(tmp_path, clock, machine, again)
    app.state.parts.teaching.run = lambda work: work()
    assert [row[4:] for row in rows(client.get("/teaching").text)] == [["Not finished", "Go on"], ["Not finished", "Go on"]]
    raw = client.get("/teaching/cases/1").text
    page = text_of(client.get("/teaching/cases/1"))
    assert "A line before the app was closed." in page and "A made-up reply." in page and "Qexamone: qfindone" in page
    assert "An answer before the app was closed." in page and f'id="question">{t.QUESTIONS[1]}</label>' in page
    assert 'name="question" value="2"' in raw and 'id="say-box"' not in raw and again.calls == []
    assert '<input type="hidden" name="line" value="1">' in client.get("/teaching/cases/2").text
    # Gone on with to its end, on the app as it runs now.
    for question in (2, 3):
        assert client.post("/teaching/cases/1/answer", data={"question": str(question), "text": f"A made-up answer {question}."}).status_code == 303
    assert app.state.parts.teaching.cases.get(1)["step"] == "done" and len(again.calls_for("teaching_feedback")) == 1
    asked = len(again.calls)
    opened = client.get("/teaching/cases/1").text
    assert 'id="feedback"' in opened and len(again.calls) == asked                      # a finished case opens as stored: no call
    assert rows(client.get("/teaching").text)[1][4:] == ["Finished", "Open"]


def test_R24_the_clinics_pages_list_nothing_of_a_teaching_case(tmp_path, clock, machine):
    app, client = teaching_app(tmp_path, clock, machine, scripted())
    app.state.parts.teaching.run = lambda work: work()
    start(client, 1)
    finish(client, 1)
    p = app.state.parts
    home = client.get("/").text
    assert "/teaching/cases" not in home and "Made Up" not in home and p.patients.listed() == []
    # No table of the clinic gained a row: no patient, no consultation, no note, no letter.
    for table in ("patient", "consultation", "note_draft", "letter", "transcript_line"):
        assert p.db.query(f"SELECT COUNT(*) AS n FROM {table}")[0]["n"] == 0, table
    assert made_teaching.SCENARIO["patient"]["name"] not in client.get("/log").text    # the log holds numbers, never a word of a case
