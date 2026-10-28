"""The prompts as files: the spec's approved wording exactly (15.8,
rulings 41 to 43), and the checks of R13 and R21 over every prompt file
(spec 5.1, 15.7; stage 3 rule 7)."""

import re
from pathlib import Path

from openconsult.prompts import loader

# The hashes the spec gives for its approved wording of the two prompts
# (15.8, rulings 41 and 42), of the text as the loader reads it. A changed
# prompt is a bench of its own (V1_LESSONS 3.7): this fails first.
APPROVED_HASHES = {
    "assessment": "437d7f32b3b020f8757ce96fdcf31ae4b85aef0b949e56f81546b3e200e1c6bb",
    "alarm": "1e05ffc8634b4093897ec53cd590111fbb2bdeac0abbd4462c8298f5582c9451",
}

# R21 check, as HANDOVER (stage 3) records it: no publisher's name is listed
# here. Instead a prompt may hold no guideline words, and every capitalised
# word in a prompt must be on this list, so a new one fails and is looked at.
KNOWN_CAPITALS = {
    "GP", "JSON", "ECG", "ACS", "TIA", "GI", "SOAP", "ICE", "HTN", "SOB", "BP",   # clinical and technical
    "LIVE", "TRANSCRIPT", "SO", "FAR", "FIRST", "NOT", "ANY", "DO",   # emphasis
    "NEVER", "NEW", "ONE", "TO", "COMMITTED", "SUSPICION", "TODAY",
    "IF", "END", "THE", "DOCTOR", "PATIENT",                          # the note prompt's emphasis (6b)
    "BACKGROUND", "FROM", "EARLIER", "CONSULTATIONS",                 # the background frame's heading (7a)
    "APPROVED", "CONSULTATION", "NOTE", "SPECIALTY", "FOUR", "ONLY", "ENT", "MUST",   # the two letter prompts and their frames (8a; MUST from ruling 14)
    "QUERY", "PASSAGES", "NOTHING",                                   # the summary prompt and its frame (8b)
}
GUIDELINE_WORDS = ("guideline", "guidance")


def test_15_8_rulings_41_and_42_the_prompt_sent_is_the_specs_approved_wording():
    for name, expected in APPROVED_HASHES.items():
        assert loader.sha256(loader.prompt(name)) == expected, name
        assert loader.APPROVED[name] == expected, name   # the one table the word check reads
    # The forms and frames load, and a frame fills without touching braces in the words.
    assert loader.form("assessment")["required"] and loader.form("alarm")["required"]
    filled = loader.fill(loader.frame("alarm"), transcript="a {brace} stays")
    assert filled.endswith("\na {brace} stays") and "{transcript}" not in filled


def test_15_8_ruling_43_no_prompt_or_frame_holds_a_double_quote():
    # The model was shown the habit that cuts its reasoning (ruling 16); now it is not.
    words = [p for p in loader.every_prompt_file() if p.suffix == ".txt"]
    assert len(words) == 20     # two prompts and three frames of stage 3; the label check's and the note's prompt and frame (6a, 6b); the background's three (7a); the letters' two prompts, two frames and the withheld line (8a); the summary prompt, its frame and its passage layout (8b)
    for path in words:
        assert '"' not in _words(path), path.name
    assert '"' in 'a "quoted" word'   # the twin


def _words(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_ruling_3_the_note_prompt_file_is_the_approved_bytes():
    # 15.10 ruling 3: the block of the spec byte for byte, one line break after its last line.
    import hashlib
    assert hashlib.sha256(loader.prompt_bytes("note")).hexdigest() == loader.APPROVED_BYTES["note"]
    assert loader.APPROVED_BYTES["note"] == "0666c026d5ac8fa74f99434396709381214ee43cb70fe763a02c2bde2a284207"
    text = loader.prompt("note")
    assert text.endswith("The subjective section must hold at least one entry. Output JSON only.")
    assert not text.endswith("\n") and '"' not in text
    # The frame of ruling 5: the bench's words, the heading and the slot, nothing else.
    assert loader.frame("note") == "TRANSCRIPT:\n{transcript}"
    assert hashlib.sha256((loader.FOLDER / "note.frame.txt").read_bytes()).hexdigest() == (
        "44f10e089af2ab4b4df272002604d35b0a678df6472949b193ba183bac1e0637")


def test_ruling_3_3_5_the_form_needs_at_least_one_subjective_entry():
    from openconsult.llm import forms
    form = loader.form("note")
    empty = {"reasoning": "made up.", "subjective": [], "objective": [], "assessment": [], "plan": []}
    assert forms.misfit(empty, form) == "answer.subjective has fewer than 1 items"
    one = {**empty, "subjective": [{"text": "made up", "turns": [0]}]}
    assert forms.misfit(one, form) is None
    # The entry holds text and turns and nothing else: no field for a name the model thinks was meant (ruling 6).
    for section in ("subjective", "objective", "assessment", "plan"):
        assert sorted(form["properties"][section]["items"]["properties"]) == ["text", "turns"]
    assert form["properties"]["subjective"]["items"]["properties"]["turns"]["items"] == {"type": "integer"}


def test_R13_no_prompt_file_names_a_country():
    countries = [c.strip() for c in _words(Path(__file__).parent / "countries.txt").splitlines() if c.strip()]
    assert len(countries) > 150
    files = loader.every_prompt_file()
    assert len(files) == 27     # stage 3's seven, the label check's and the note's prompt, frame and form (6a, 6b), the background's three (7a), the letters' seven (8a), the summary's four (8b)
    for path in files:
        text = _words(path).lower()
        for country in countries:
            assert not re.search(rf"\b{re.escape(country.lower())}\b", text), f"{path.name} names {country}"


def test_R21_no_prompt_file_names_a_guideline_publisher():
    for path in loader.every_prompt_file():
        text = _words(path)
        # The summary prompt's own approved words (15.12 ruling 7) say guideline, as its job is; it names no publisher.
        for word in GUIDELINE_WORDS if not path.name.startswith("guideline.") else ():
            assert word not in text.lower(), f"{path.name} holds {word}"
        unknown = set(re.findall(r"\b[A-Z][A-Z]+\b", text)) - KNOWN_CAPITALS
        assert not unknown, f"{path.name} has a capitalised word not on the list: {unknown}"
    # The twin: the check can fail.
    assert set(re.findall(r"\b[A-Z][A-Z]+\b", "as the ZZZZ advice says")) - KNOWN_CAPITALS


def test_ruling_5_15_8_ruling_1_the_three_background_files_are_the_approved_bytes_and_hold_no_double_quote():
    # 15.11 ruling 5: each block followed by one line break, nothing else; the cut line the same (the plan review, point 1).
    import hashlib
    expected = {"background.frame": "48875847e78d1830e69a7bd4afccf0a975502af86dc4196189709470cdcf2fe3",
                "background.note": "79b41aaff3a95d4ae0b8c0d00e4e82f9fd6a9ce26f47ed711cf1d487dbfc08b7",
                "background.cut": "c00401b4a0a993c4f639ea9261517ac448106c6b84838e0711a98f26ae7c2b4e"}
    for name, digest in expected.items():
        assert hashlib.sha256(loader.file_bytes(name)).hexdigest() == digest == loader.APPROVED_BYTES[name], name
        assert loader.file_bytes(name).endswith(b"\n") and not loader.file_bytes(name).endswith(b"\n\n")
        assert '"' not in loader.file_text(name)
    assert loader.file_text("background.frame").startswith("BACKGROUND FROM EARLIER CONSULTATIONS, approved by the doctor:\n{notes}")
    assert loader.file_text("background.note").split("\n") == [
        "Consultation of {date}:", "Subjective: {subjective}", "Objective: {objective}", "Assessment: {assessment}", "Plan: {plan}"]
    assert loader.file_text("background.cut") == "The note is cut here"


def test_rulings_3_and_8_the_two_letter_prompts_are_the_approved_bytes_and_the_frames_the_fixed_words():
    # 15.12 rulings 3 and 8: each block followed by one line break, nothing else; the two frames and the withheld
    # line as the plan of 8a gives them byte for byte (the detail The two letter frames; item 2).
    import hashlib
    expected = {"letter": "220d61f00f0fc86cbb4f9010c0da7a38c9709724e6840bf19fa29167e9527332",
                "referrals": "5eab5bb56333fd5c4643dd482caa04afc9cb8a2c2ae922d69192ecaed5632962",
                "letter.frame": "727bf80252fcee71b5ee79b141a2264302afacc41d0c8414f80838fdb73475de",
                "referrals.frame": "af9401ac6241ef8dcdb665e5e49ac6279d444390002ba69442452d824359c4b8",
                "letter.withheld": "a0950641e45a39a87a8df02a5c3b4045c58a92fa7e7cd085c7a4e9766b5d6f26"}
    for name, digest in expected.items():
        data = loader.prompt_bytes(name) if name in ("letter", "referrals") else loader.file_bytes(name)
        assert hashlib.sha256(data).hexdigest() == digest == loader.APPROVED_BYTES[name], name
        assert data.endswith(b"\n") and not data.endswith(b"\n\n") and b'"' not in data
    assert loader.prompt("letter").startswith("You draft the body of a GP referral letter to the requested specialty.")
    assert loader.prompt("referrals").startswith("You read an APPROVED GP consultation note")
    assert loader.frame("referrals") == "APPROVED CONSULTATION NOTE:\n{note}"
    assert loader.frame("letter") == "SPECIALTY: {specialty}\n\nAPPROVED CONSULTATION NOTE:\n{note}"
    assert loader.file_text("letter.withheld") == "[assessment withheld from referral letters]"
    filled = loader.fill(loader.frame("letter"), specialty="a {brace} specialty", note="[1] a {note} line")
    assert filled == "SPECIALTY: a {brace} specialty\n\nAPPROVED CONSULTATION NOTE:\n[1] a {note} line"
    # The forms: the field names are the prompts' own words; at most four paragraphs (the letter prompt's FOUR).
    letter_form, list_form = loader.form("letter"), loader.form("referrals")
    assert sorted(letter_form["properties"]["paragraphs"]["items"]["properties"]) == ["note_lines", "text"]
    assert letter_form["properties"]["paragraphs"]["maxItems"] == 4
    assert sorted(list_form["properties"]["referrals"]["items"]["properties"]) == ["lines", "reason", "specialty", "suggestion", "title", "urgency"]
    assert list_form["properties"]["referrals"]["items"]["properties"]["urgency"]["enum"] == ["urgent", "routine"]


def test_ruling_4_the_placeholder_in_the_prompt_is_the_one_the_check_writes():
    from openconsult import words
    assert words.LETTER_PLACEHOLDER == "[to be completed by the referring doctor]"
    assert words.LETTER_PLACEHOLDER in loader.prompt("letter")


def test_ruling_7_the_summary_prompt_and_its_frames_are_the_approved_bytes():
    # 15.12 ruling 7: the block followed by one line break, nothing else; the frame and the layout of one
    # passage as the plan of 8b gives them byte for byte (item 5); the form v1's three fields.
    import hashlib
    expected = {"guideline": "7e07e0170f2f38ac06551fabd8cb67d66d9a0e21a2e4a507d82c20629975d94f",
                "guideline.frame": "4b07fd0dac1086c318c416c94a4fcebc1b41b857cb86bb1ff735fd15363f07e9",
                "guideline.passage": "c1bcff2265bdd94c9121c407fde08b33895e6d761167aa6630451f0ce5958227",
                "guideline.form": "a3fd2e5d0991fde7c0fcfcf6547bd68c9ff7d5c60bcce5fefd9930836872da9c"}
    for name, digest in expected.items():
        data = (loader.prompt_bytes(name) if name == "guideline" else
                loader.form_bytes("guideline") if name == "guideline.form" else loader.file_bytes(name))
        assert hashlib.sha256(data).hexdigest() == digest == loader.APPROVED_BYTES[name], name
        assert data.endswith(b"\n") and not data.endswith(b"\n\n")
        if name != "guideline.form":
            assert b'"' not in data
    assert loader.prompt("guideline").startswith("You are preparing a short guideline summary for a doctor during a consultation.")
    assert loader.prompt("guideline").endswith("Output JSON only.")
    assert loader.frame("guideline") == "QUERY: {query}\n\nPASSAGES:\n{passages}"
    assert loader.file_text("guideline.passage") == "[{n}] {source}\n{text}"
    form = loader.form("guideline")
    assert sorted(form["required"]) == ["covered", "passages_cited", "summary"] and form["properties"]["covered"]["type"] == "boolean"
    assert form["properties"]["passages_cited"]["items"] == {"type": "integer"}
    from openconsult.llm.jobs import job
    assert job("guideline").frames == ("guideline", "guideline.passage") and job("guideline").max_tokens == 1000
