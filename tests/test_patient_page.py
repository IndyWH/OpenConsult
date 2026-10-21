"""The patient's page (spec 15.11 ruling 2; R2, R11, R15, R17; D44): the
three corrections, each audited with what stood before; every earlier
consultation keeps the details it ran with; the consultations newest
first with their state. Made-up patients, made-up doors."""

from openconsult import words
from openconsult.web.live import capture_from
from tests.conftest import refusal_on, text_of
from tests.test_review_page import CAPTURE, LOUD, reviewed
from tests.test_start import PATIENT, TICKS, app_with


def test_ruling_2_R2_R11_each_detail_is_corrected_on_its_own_control_and_audited_with_what_stood_before(tmp_path, clock, machine):
    app, client = app_with(tmp_path, clock, machine)
    client.post("/patients", data=PATIENT)
    page = text_of(client.get("/patients/1"))
    assert "Made-up Patient" in page and words.NUMBER_LINE.format(id=1) in page and 'value="1990-10-21"' in client.get("/patients/1").text
    done = client.post("/patients/1/name", data={"value": "Corrected Patient"})
    assert done.status_code == 303 and done.headers["location"] == "/patients/1"
    client.post("/patients/1/date_of_birth", data={"value": "1991-01-02"})
    client.post("/patients/1/sex", data={"value": "M"})
    p = app.state.parts
    assert (p.patients.get(1).name, p.patients.get(1).date_of_birth.isoformat(), p.patients.get(1).sex) == ("Corrected Patient", "1991-01-02", "M")
    assert [(c["field"], c["before"], c["after"], c["by_whom"]) for c in p.patients.changes(1)] == [
        ("name", "Made-up Patient", "Corrected Patient", "Dr Example"), ("date_of_birth", "1990-10-21", "1991-01-02", "Dr Example"),
        ("sex", "F", "M", "Dr Example")]
    assert all(c["at"] for c in p.patients.changes(1))
    events = [(l.event, l.detail) for l in p.audit.lines()[:3]]
    assert ("patient.changed", "patient 1: name from Made-up Patient to Corrected Patient") in events
    assert ("patient.changed", "patient 1: sex from F to M") in events
    # A bad value is refused on its control (R11, R15); an unchanged value writes nothing.
    refused = client.post("/patients/1/date_of_birth", data={"value": "2030-01-01"})
    assert refused.status_code == 400 and refusal_on(refused.text, "save-date") == words.DATE_OF_BIRTH_BAD
    refused = client.post("/patients/1/name", data={"value": " "})
    assert refusal_on(refused.text, "save-name") == words.PATIENT_NAME_MISSING
    same = client.post("/patients/1/sex", data={"value": "M"})
    assert refusal_on(same.text, "save-sex") == words.DETAIL_UNCHANGED and len(p.patients.changes(1)) == 3
    assert client.post("/patients/1/age", data={"value": "x"}).headers["location"] == "/patients/1"
    assert client.get("/patients/99").headers["location"] == "/"


def test_ruling_2_R11_a_consultation_keeps_the_details_it_ran_with_and_says_when_they_changed_later(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine)
    p = app.state.parts
    row = p.consultations.get(1)
    assert (row["patient_name"], row["patient_date_of_birth"], row["patient_sex"]) == ("Made-up Patient", "1990-10-21", "F")
    page = text_of(client.get("/consultations/1"))
    assert f"{words.RAN_WITH} Made-up Patient, 21 Oct 1990, Female." in page and words.DETAILS_CORRECTED.split("{")[0] not in page
    clock.advance(minutes=5)                    # within the lock's 30 minutes
    client.post("/patients/1/date_of_birth", data={"value": "1980-10-21"})
    client.post("/patients/1/name", data={"value": "Corrected Patient"})
    page = text_of(client.get("/consultations/1"))
    assert f"{words.RAN_WITH} Made-up Patient, 21 Oct 1990, Female." in page              # never rewritten
    assert words.DETAILS_CORRECTED.format(date="4 Oct 2026") in page
    assert p.consultations.get(1)["patient_name"] == "Made-up Patient"
    # A new consultation runs with the corrected details: the patient line of its passes reads the
    # details copied at its Start (R11), and a correction made while it runs leaves them as they stood.
    client.post("/consultations/start/1", data=TICKS)
    assert p.consultations.get(2)["patient_name"] == "Corrected Patient"
    live = p.running[2]
    assert live.patient.date_of_birth.isoformat() == "1980-10-21" and live.model_patient.age == 45
    client.post("/patients/1/date_of_birth", data={"value": "1970-10-21"})
    assert live.model_patient.age == 45 and p.patients.get(1).date_of_birth.isoformat() == "1970-10-21"
    assert words.DETAILS_CORRECTED.format(date="4 Oct 2026") in text_of(client.get("/consultations/1"))


def test_ruling_2_the_patients_page_lists_every_consultation_newest_first_with_its_state(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine)
    client.post("/consultations/1/note/approve")
    clock.advance(minutes=10)
    client.post("/consultations/start/1", data=TICKS)                 # 2, running
    raw = client.get("/patients/1").text
    page = text_of(client.get("/patients/1"))
    assert [part.split('"')[0] for part in raw.split('data-consultation="')[1:]] == ["2", "1"]
    assert f"4 Oct 2026 09:10</a>: {words.STATE_WORDS['running']}" in page
    assert f"4 Oct 2026 09:00</a>: {words.STATE_WORDS['approved']}" in page
    assert 'href="/consultations/1"' in raw and 'id="new-consultation"' in raw and 'href="/consultations/start/1"' in raw
    from openconsult.web.patients import consultation_state
    assert consultation_state({"state": "final"}, False, False) == "review"
    assert consultation_state({"state": "final"}, False, True) == "refused"
    assert consultation_state({"state": "stopping"}, False, False) == "at_stop"
