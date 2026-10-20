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
    "GP", "JSON", "ECG", "ACS", "TIA", "GI",                        # clinical and technical
    "LIVE", "TRANSCRIPT", "SO", "FAR", "FIRST", "NOT", "ANY", "DO",   # emphasis
    "NEVER", "NEW", "ONE", "TO", "COMMITTED", "SUSPICION", "TODAY",
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
    assert len(words) == 7      # two prompts and three frames of stage 3; the label check's prompt and frame of 6a
    for path in words:
        assert '"' not in _words(path), path.name
    assert '"' in 'a "quoted" word'   # the twin


def _words(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_R13_no_prompt_file_names_a_country():
    countries = [c.strip() for c in _words(Path(__file__).parent / "countries.txt").splitlines() if c.strip()]
    assert len(countries) > 150
    files = loader.every_prompt_file()
    assert len(files) == 10     # stage 3's seven, and the label check's prompt, frame and form of 6a
    for path in files:
        text = _words(path).lower()
        for country in countries:
            assert not re.search(rf"\b{re.escape(country.lower())}\b", text), f"{path.name} names {country}"


def test_R21_no_prompt_file_names_a_guideline_publisher():
    for path in loader.every_prompt_file():
        text = _words(path)
        for word in GUIDELINE_WORDS:
            assert word not in text.lower(), f"{path.name} holds {word}"
        unknown = set(re.findall(r"\b[A-Z][A-Z]+\b", text)) - KNOWN_CAPITALS
        assert not unknown, f"{path.name} has a capitalised word not on the list: {unknown}"
    # The twin: the check can fail.
    assert set(re.findall(r"\b[A-Z][A-Z]+\b", "as the ZZZZ advice says")) - KNOWN_CAPITALS
