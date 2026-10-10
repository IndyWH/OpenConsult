"""The prompts as files: v1's words exactly, and the checks of R13 and
R21 over every prompt file (spec 5.1, 15.7; stage 3 rule 7)."""

import re
from pathlib import Path

from openconsult.prompts import loader

# v1's recorded hashes of the two prompts (stage 3 prompt, rule 7). A
# changed prompt is a bench of its own (V1_LESSONS 3.7): this fails first.
V1_HASHES = {
    "assessment": "6cc315afcf2c8570a7486bb8adb84885a8c043612e54bd2da158fa7814ad9308",
    "alarm": "c98ef427c4e26609e5e6f88c4401e2b3fd851d33ded3f1a03d32b5f2dc533d41",
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


def test_15_7_the_prompt_sent_is_v1s_word_for_word():
    for name, expected in V1_HASHES.items():
        assert loader.sha256(loader.prompt(name)) == expected, name
    # The forms and frames load, and a frame fills without touching braces in the words.
    assert loader.form("assessment")["required"] and loader.form("alarm")["required"]
    filled = loader.fill(loader.frame("alarm"), transcript="a {brace} stays")
    assert filled.endswith("\na {brace} stays") and "{transcript}" not in filled


def _words(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_R13_no_prompt_file_names_a_country():
    countries = [c.strip() for c in _words(Path(__file__).parent / "countries.txt").splitlines() if c.strip()]
    assert len(countries) > 150
    files = loader.every_prompt_file()
    assert len(files) == 7
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
