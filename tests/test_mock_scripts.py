from pathlib import Path

from app.mock_scripts import as_live_transcript, parse_script

SCRIPTS_DIR = Path(__file__).parent.parent / "mock_consultations"


def test_all_scripts_parse_into_dialogue():
    scripts = sorted(SCRIPTS_DIR.glob("0*_en.md"))
    assert len(scripts) == 9  # 5 routine/original + 4 red-flag variants
    for script in scripts:
        turns = parse_script(script)
        assert len(turns) > 20, f"{script.name} parsed suspiciously few turns"
        assert {t.speaker for t in turns} <= {"DOCTOR", "PATIENT", "MOTHER"}
        # Alternating conversation, not a monologue
        assert any(t.speaker != turns[0].speaker for t in turns)


def test_stage_directions_are_stripped():
    turns = parse_script(SCRIPTS_DIR / "03_diabetes_review_en.md")
    text = as_live_transcript(turns)
    assert "(laughs)" not in text
    assert "*" not in text
