"""The Patients page (spec 15.11 ruling 1; 8.1; R1, R15, R17): the home
page for a logged-in user, with the rows waiting at the top, the one
search box and the list, last seen first, every patient with a number.
Every patient here is made up."""

from datetime import date

from openconsult import words
from openconsult.patients.patients import Listed, PatientRow, fold, search
from tests.conftest import text_of
from tests.test_start import PATIENT, TICKS, app_with


def rows_on(page: str) -> list[str]:
    return [part.split('data-patient="')[1].split('"')[0] for part in page.split('<tr class="patient" ')[1:]]


def test_ruling_1_R17_the_patients_page_lists_last_seen_first_with_the_five_columns_and_the_number(tmp_path, clock, machine):
    app, client = app_with(tmp_path, clock, machine)
    client.post("/patients", data=PATIENT)                                          # 1, never seen
    client.post("/patients", data={**PATIENT, "name": "Other Patient"})             # 2
    client.post("/patients", data=PATIENT)                                          # 3, the same name and date of birth as 1
    client.post("/consultations/start/2", data=TICKS)
    clock.advance(hours=1)
    client.post("/consultations/start/3", data=TICKS)
    raw = client.get("/").text
    page = text_of(client.get("/"))
    assert rows_on(raw) == ["3", "2", "1"]                                           # last seen first; never seen after, newest first
    for column in (words.COL_NAME, words.COL_DATE_OF_BIRTH, words.COL_SEX, words.COL_LAST_SEEN, words.COL_NUMBER):
        assert column in page
    assert page.count("Made-up Patient") == 2 and "21 Oct 1990" in page and "Female" in page and words.NEVER_SEEN in page
    assert '<td class="number">3</td>' in raw and '<td class="number">1</td>' in raw   # the two told apart by their numbers
    assert 'href="/patients/3"' in raw and "4 Oct 2026" in page                      # the date last seen


def test_ruling_1_the_search_matches_part_of_a_name_folded_a_date_of_birth_and_the_number_exactly(tmp_path, clock, machine):
    listed = [Listed(PatientRow(1, "Zoë Made-up", date(1990, 10, 21), "F"), None),
              Listed(PatientRow(2, "Agent 7 Made-up", date(1985, 1, 2), "M"), None),
              Listed(PatientRow(12, "Twelve Made-up", date(1990, 10, 21), "M"), None)]
    assert [r.patient.id for r in search(listed, "zoe")] == [1]                      # accents and case folded
    assert [r.patient.id for r in search(listed, "MADE")] == [1, 2, 12]
    assert [r.patient.id for r in search(listed, "12")] == [12]                      # the number exactly
    assert [r.patient.id for r in search(listed, "7")] == [2]                        # no patient 7: tried as part of a name
    assert [r.patient.id for r in search(listed, "1990-10-21")] == [1, 12]           # a date typed as a date, three forms
    assert [r.patient.id for r in search(listed, "21/10/1990")] == [1, 12]
    assert [r.patient.id for r in search(listed, "2.1.1985")] == [2]
    assert search(listed, "nobody") == [] and search(listed, "  ") == listed
    assert fold("Élodie-Ñ") == "elodie-n"
    # Through the page: the same rows, and nothing matching says so.
    app, client = app_with(tmp_path, clock, machine)
    client.post("/patients", data=PATIENT)
    client.post("/patients", data={**PATIENT, "name": "Zoë Other"})
    assert rows_on(client.get("/?q=zoe").text) == ["2"]
    assert rows_on(client.get("/?q=1990-10-21").text) == ["2", "1"]
    assert rows_on(client.get("/?q=1").text) == ["1"]
    page = text_of(client.get("/?q=nobody"))
    assert words.SEARCH_NONE.format(query="nobody") in page and rows_on(page) == []
    assert 'value="nobody"' in client.get("/?q=nobody").text                          # the query stays in the box


def test_ruling_1_R1_R15_the_patients_page_is_the_home_page_with_the_waiting_rows_at_the_top(tmp_path, clock, machine):
    app, client = app_with(tmp_path, clock, machine)
    raw = client.get("/").text
    page = text_of(client.get("/"))
    assert words.STATEMENT in page and words.NO_PATIENTS in page and words.NAV_NEW_PATIENT in page
    assert 'href="/patients/new"' in raw and words.PATIENTS_TITLE in page
    client.post("/patients", data=PATIENT)
    assert rows_on(client.get("/").text) == ["1"]                                     # read from the tables: shows at once
    client.post("/consultations/start/1", data=TICKS)
    app.state.parts.running[1].on_stop = None                                         # hold the finaliser: the row waits at Stop
    client.post("/consultations/1/stop")
    raw = client.get("/").text
    found = [raw.find(words.HOME_WAITING), raw.find('id="search-form"'), raw.find('id="patients"')]
    assert all(f >= 0 for f in found) and found == sorted(found)                       # the waiting rows above the box, the box above the list
    assert words.CONTINUE_CONSULTATION in text_of(client.get("/"))


def test_his_word_of_20_nov_1031_the_new_patient_button_stands_at_the_very_top_above_the_rows_waiting_and_the_list(tmp_path, clock, machine):
    # The owner, at his room check of 20 Nov 2026 (mail 6 of run 9c): The new patient button is at the very bottom of
    # for review patients and the patient list. ... What if there was 1000 patients in the database! New patient
    # button should be at the very top. OLD: the button under the list. NEW: above the rows waiting and the list.
    from tests.test_review_page import reviewed
    app, client, c = reviewed(tmp_path, clock, machine)                                # consultation 1 waits for review
    for n in range(30):
        client.post("/patients", data={**PATIENT, "name": f"Made-up Patient {n}"})
    client.post("/consultations/start/2", data=TICKS)
    app.state.parts.running[2].on_stop = None                                         # hold the finaliser: the row waits at Stop
    client.post("/consultations/2/stop")
    raw = client.get("/").text
    main = raw.split("<main", 1)[1].split("</main>", 1)[0]
    button = '<a class="button" id="new-patient" href="/patients/new">' + words.NAV_NEW_PATIENT + "</a>"
    found = [main.find(button), main.find(words.HOME_WAITING), main.find(words.HOME_REVIEW), main.find('id="search-form"'),
             main.find('id="patients"'), main.find('<tr class="patient" ')]
    assert all(f >= 0 for f in found) and found == sorted(found)                       # the button first, then all that was above it
    assert main.count('href="/patients/new"') == 1 and len(rows_on(raw)) == 31         # once, and not again under the list
    assert main.find(words.PATIENTS_TITLE) < main.find(button)                         # under the page's heading
    # The link in the top bar stays.
    bar = raw.split('<nav class="tabs">', 1)[1].split("</nav>", 1)[0]
    assert 'href="/patients/new"' in bar and words.NAV_NEW_PATIENT in bar
    # A folder with no patient: the button is there too, above the line that says none is there.
    empty, first = app_with(tmp_path / "empty", clock, machine)
    page = first.get("/").text
    assert 0 <= page.find(button) < page.find('id="none-found"')
