"""One referral letter: the call, the check and the rows, and the parts
code writes (spec 15.12, rulings 1 and 4; 15.11 ruling 2; R2, R5, R11,
R20, R30; 10.4). Made-up replies through a made-up engine; no model's
words asserted."""

from datetime import date

from openconsult import words
from openconsult.consult import letter, referral_note
from openconsult.consult.letter_rows import ItemRow
from openconsult.llm.door import Door
from openconsult.llm.engine import EngineTimeout
from openconsult.llm.record import ModelCalls
from openconsult.patients.users import User
from openconsult.prompts import loader
from tests.fakes import FakeEngine, reply
from tests.test_referral_note import TEXT
from tests.test_referrals import approved, rows  # noqa: F401  (the fixture)

ROW = {"patient_name": "Made-up Patient", "patient_date_of_birth": "1962-03-01", "patient_sex": "F", "started_at": "2026-10-04T09:00:00+00:00"}


def test_ruling_1_15_11_ruling_2_code_writes_the_salutation_the_re_line_and_the_sign_off_from_the_record():
    text = letter.assemble(["First made paragraph.", "", "Second made paragraph."], " ENT Surgeon ", ROW, User("Dr", "Example", 1))
    assert text == ("Dear Consultant ENT Surgeon,\n\nRe: Made-up Patient, born 1 Mar 1962, Female\n\n"
                    "First made paragraph.\n\nSecond made paragraph.\n\nYours faithfully,\nDr Example\n")
    assert words.LETTER_SALUTATION == "Dear Consultant {title}," and words.LETTER_SIGN_OFF == "Yours faithfully,"
    # The ran-with details, not the patient's current ones: a row corrected later keeps its own three.
    corrected = {**ROW, "patient_name": "Corrected Name", "patient_sex": "M"}
    assert "Re: Corrected Name, born 1 Mar 1962, Male" in letter.assemble([], "Physician", corrected, User("", "Example", 1))
    assert letter.assemble([], "Physician", ROW, User("", "Example", 1)).endswith("Yours faithfully,\nExample\n")   # no title: the name alone


def test_R20_R30_the_letter_draft_stores_both_bodies_the_counts_and_a_failed_call_plainly(rows, clock):  # noqa: F811
    good = {"reasoning": "made reasoning", "paragraphs": [
        {"text": "Thank you for seeing this 64-year-old woman with a made-up history. She hoped for a made-up wish.", "note_lines": [2, 3]},
        {"text": "Her BP was 120/80.", "note_lines": [5]},
        {"text": "The impression was made up.", "note_lines": [7]}]}
    under = {"reasoning": "x", "paragraphs": [{"text": "Made up. Made up again. Her BP was 120/80.", "note_lines": [99]}]}
    engine = FakeEngine({"letter": [good, under, reply({"reasoning": "cut"}, ended="cut"), EngineTimeout("no answer")]})
    door = Door(engine, ModelCalls(rows["db"], clock))
    cid = approved(rows)
    item_id = rows["letters"].add_item(ItemRow(cid, None, "named", "a made-up specialty", "Physician", None, None, [], None, 0))
    item = rows["letters"].item(item_id)
    drafted = letter.draft(door, rows["letters"], rows["notes"], rows["consultations"], rows["audit"], cid, item)
    # The stamp from the door, the prompt hash, the masked note sent, both bodies, the detail and the counts (R20; ruling 11).
    assert (drafted["engine"], drafted["engine_version"], drafted["model_tag"], drafted["model_digest"]) == ("made-up", "0.0-made-up", "gemma4:26b-a4b-it-qat", "made-up-digest")   # the engine's own name, as model_call names it
    assert drafted["prompt_sha256"] == loader.APPROVED_BYTES["letter"] and drafted["note_lines"] == referral_note.letter_text(referral_note.numbered_lines(TEXT))
    assert "[assessment withheld from referral letters]" in drafted["note_lines"] and "made up impression" not in drafted["note_lines"]
    assert drafted["model_body"] == good["paragraphs"] and drafted["reasoning"] == "made reasoning"
    assert drafted["paragraphs"] == ["Thank you for seeing this 64-year-old woman with a made-up history. She hoped for a made-up wish.",
                                     "Her BP was 120/80.", words.LETTER_PLACEHOLDER]
    assert (drafted["sentences_total"], drafted["sentences_grounded"], drafted["placeholders"], drafted["expectations_dropped"],
            drafted["refused"], drafted["failure"], drafted["n"]) == (4, 3, 1, 0, 0, None, 1)
    assert drafted["check_detail"]["paragraphs"][2]["assessment_cited"] == [7] and drafted["call_id"] is not None
    sent = engine.calls_for("letter")[0].user
    assert sent == referral_note.letter_message(TEXT, "a made-up specialty", referral_note.patient_of(rows["consultations"].get(cid)))
    assert sent.startswith("The patient is a 64-year-old woman.") and "BACKGROUND" not in sent
    line = rows["audit"].lines()[0]
    assert line.event == "letter.drafted" and "4 sentences, 3 grounded, 1 placeholders" in line.detail and "made-up history" not in line.detail
    assert "0 allergy sentences dropped" in line.detail and drafted["check_detail"]["allergies_dropped"] == 0   # ruling 16
    # A refused draft keeps both bodies and the counts, refused 1, and the audit line says so.
    refused = letter.draft(door, rows["letters"], rows["notes"], rows["consultations"], rows["audit"], cid, item)
    assert (refused["refused"], refused["sentences_total"], refused["sentences_grounded"], refused["n"]) == (1, 3, 0, 2)
    assert refused["model_body"] == under["paragraphs"] and refused["paragraphs"] == [words.LETTER_PLACEHOLDER]
    assert rows["audit"].lines()[0].event == "letter.refused_by_check" and "0 of 3" in rows["audit"].lines()[0].detail
    # A cut reply is too_long and a late one too_slow, each kept as a failed letter with no body; no second call by itself.
    cut = letter.draft(door, rows["letters"], rows["notes"], rows["consultations"], rows["audit"], cid, item)
    assert cut["failure"].startswith("too_long") and cut["body"] is None and cut["model_body"] is None and cut["sentences_total"] == 0
    slow = letter.draft(door, rows["letters"], rows["notes"], rows["consultations"], rows["audit"], cid, item)
    assert slow["failure"].startswith("too_slow") and rows["audit"].lines()[0].event == "letter.failed"
    assert len(engine.calls_for("letter")) == 4 and [l["n"] for l in rows["letters"].letters_of_item(item_id)] == [1, 2, 3, 4]
    assert rows["letters"].latest_letter(item_id)["id"] == slow["id"]
