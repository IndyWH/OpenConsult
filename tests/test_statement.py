"""The cloud statement (spec 15.13, rulings 5, 31, 32 and 33; 7.3 rules 2
and 4; the details of run 9b): the owner's words proven against the
spec's own text, the statement of each path line by line, and the tick
with its checksum."""

from __future__ import annotations

from pathlib import Path

import pytest

from openconsult import words
from openconsult.db import open_database
from openconsult.patients.audit import Audit
from openconsult.settings.path import CLAUDE, SPEECHMATICS, THIS_COMPUTER, ChosenPath, beginning
from openconsult.settings import statement as statement_module
from openconsult.settings.statement import statement_for
from openconsult.settings.stored import Stored

SPEC = Path(__file__).resolve().parents[1] / "V2_SPEC.md"
BOTH = ChosenPath(CLAUDE, SPEECHMATICS)
MODEL_ALONE = ChosenPath(CLAUDE, THIS_COMPUTER)
SOUND_ALONE = ChosenPath(THIS_COMPUTER, SPEECHMATICS)
RECORDING_ALONE = ChosenPath(THIS_COMPUTER, THIS_COMPUTER, better_accuracy=True)
MODEL_AND_RECORDING = ChosenPath(CLAUDE, THIS_COMPUTER, better_accuracy=True)
LOCAL = ChosenPath(THIS_COMPUTER, THIS_COMPUTER)


def stage_9_of_the_spec() -> str:
    text = SPEC.read_text(encoding="utf-8")
    return text[text.index("### 15.13 Stage 9"):text.index("## 16. Decisions")]


def fenced() -> list[list[str]]:
    """The texts between fence lines in the section of stage 9, in order:
    rulings 5, 31, 32, 33 and 34."""
    blocks, current = [], None
    for line in stage_9_of_the_spec().splitlines():
        if line.strip() == "```":
            if current is None:
                current = []
            else:
                blocks.append(current)
                current = None
        elif current is not None:
            current.append(line)
    return blocks


def bullets(lines: list[str]) -> list[str]:
    return [line[2:] for line in lines if line.startswith("- ")]


def test_rule_4_of_run_9b_every_sentence_of_the_owner_in_the_file_of_words_is_the_specs_own_text_letter_for_letter():
    five, claude, speechmatics, after_stop, connect = fenced()
    # Ruling 5: the fixed part, as approved on 6 Nov 2026.
    assert five[0] == words.CLOUD_HEADING_BOTH and five[2] == words.CLOUD_INTRO and five[4] == words.CLOUD_SENT_HEADING
    # Restated in run 10b (15.14, ruling 15): the list gained the owner's line for teaching as its last, on 25 Nov 2026.
    # OLD: bullets(five[5:11]) == the six lines from the sound to the passages; five[12] the heading of What stays.
    assert bullets(five[5:12]) == [words.CLOUD_SENT_SOUND, words.CLOUD_SENT_WORDS, words.CLOUD_SENT_AGE, words.CLOUD_SENT_EARLIER,
                                   words.CLOUD_SENT_NOTE, words.CLOUD_SENT_PASSAGES, words.CLOUD_SENT_TEACHING]
    assert five[13] == words.CLOUD_STAYS_HEADING and bullets(five[14:16]) == [words.CLOUD_STAYS_NAME, words.CLOUD_STAYS_APPROVED]
    assert five[-3] == words.CLOUD_PROTOTYPE and five[-1] == f"[ ] {words.CLOUD_TICK_BOTH}"
    # Ruling 5's own paragraph gives the words for a path with transcription on this computer.
    ruling_5 = next(line for line in stage_9_of_the_spec().splitlines() if line.startswith("5. **The cloud statement"))
    for said in (f"the heading reads {words.CLOUD_HEADING_MODEL}", f"the tick reads {words.CLOUD_TICK_WORDS}",
                 f"the second list gains the line {words.CLOUD_STAYS_RECORDING} after its first line",
                 f"the words{words.CLOUD_SENT_WORDS_GO.rstrip('.')} are left out"):
        assert said in ruling_5, said
    assert words.CLOUD_SENT_WORDS.endswith(words.CLOUD_SENT_WORDS_GO)
    # Rulings 31 and 32: the part for each service.
    assert claude == [words.CLOUD_CLAUDE_HEADING, *(f"- {line}" for line in words.CLOUD_CLAUDE_LINES)]
    assert speechmatics == [words.CLOUD_SPEECHMATICS_HEADING, *(f"- {line}" for line in words.CLOUD_SPEECHMATICS_LINES)]
    # Ruling 33: what is added when the whole recording is sent after Stop.
    assert bullets(after_stop) == [words.CLOUD_SENT_RECORDING, words.CLOUD_SPEECHMATICS_WHOLE_KEPT, words.CLOUD_SPEECHMATICS_WHOLE_COST]
    # Ruling 34: the connect screen for Claude.
    assert connect == [words.CONNECT_CLAUDE_TITLE, *(f"- {line}" for line in words.CONNECT_CLAUDE_LINES)]


def test_15_13_rulings_5_31_and_32_the_statement_of_both_choices_in_the_cloud_is_the_specs_text_with_the_two_parts_in_place():
    five, claude, speechmatics, _, _ = fenced()
    start = five.index("The service: Ollama cloud")                 # the part that rulings 31 and 32 take the place of
    expected = five[:start] + speechmatics + [""] + claude + five[start + 4:]
    assert statement_for(BOTH).text == "\n".join(expected) + "\n"


def test_15_13_ruling_5_the_statement_of_a_cloud_language_model_alone_line_by_line():
    made = statement_for(MODEL_ALONE)
    assert (made.heading, made.tick) == ("Using a cloud language model", "I understand that these words leave this computer.")
    # Restated in run 10b (15.14, ruling 15). OLD: the five lines from the words to the passages. NEW: the five and
    # the owner's line for teaching, last and whole.
    assert made.sent == ("The words spoken in the consultation. A name spoken aloud is among them.", words.CLOUD_SENT_AGE,
                         words.CLOUD_SENT_EARLIER, words.CLOUD_SENT_NOTE, words.CLOUD_SENT_PASSAGES,
                         "What you type in a teaching case. It goes to the language model service.")
    assert made.stays == (words.CLOUD_STAYS_NAME, "The recording.", words.CLOUD_STAYS_APPROVED)
    assert made.parts == ((words.CLOUD_CLAUDE_HEADING, tuple(words.CLOUD_CLAUDE_LINES)),)
    assert "Speechmatics" not in made.text and "sound" not in made.text.lower()


def test_15_13_ruling_5_the_statement_of_cloud_transcription_alone_holds_the_owners_heading_and_tick_and_no_line_of_the_words():
    made = statement_for(SOUND_ALONE)
    # The owner's words of 16 Nov 2026, brought with the review of the plan (its point 6).
    assert (made.heading, made.tick) == ("Using a cloud transcription service", "I understand that this sound leaves this computer.")
    assert made.sent == (words.CLOUD_SENT_SOUND,) and made.stays == (words.CLOUD_STAYS_NAME, words.CLOUD_STAYS_APPROVED)
    assert made.parts == ((words.CLOUD_SPEECHMATICS_HEADING, tuple(words.CLOUD_SPEECHMATICS_LINES)),)
    assert "Claude" not in made.text and "age and sex" not in made.text


def test_15_13_ruling_33_the_statement_of_the_recording_after_stop_alone_and_the_last_line_without_the_price_of_live_sound():
    made = statement_for(RECORDING_ALONE)
    assert (made.heading, made.tick) == ("Sending the recording after Stop",
                                         "I understand that this recording leaves this computer after Stop.")
    assert made.sent == (words.CLOUD_SENT_RECORDING,) and made.stays == (words.CLOUD_STAYS_NAME, words.CLOUD_STAYS_APPROVED)
    where, live, training, cost = words.CLOUD_SPEECHMATICS_LINES
    # The owner's word of 16 Nov 2026: no live sound goes, so the last line stands without its third sentence;
    # its first two sentences stand letter for letter, and the line of 19 cents stands.
    assert made.parts == ((words.CLOUD_SPEECHMATICS_HEADING, (
        where, words.CLOUD_SPEECHMATICS_WHOLE_KEPT, training,
        "You pay Speechmatics for what you use. A new account starts with 100 US dollars of credit and needs no card.",
        words.CLOUD_SPEECHMATICS_WHOLE_COST)),)
    assert "20 US cents" not in made.text and live not in made.text and "19 US cents" in made.text
    assert cost.endswith(words.CLOUD_SPEECHMATICS_LIVE_COST) and cost in statement_for(BOTH).text       # whole where live sound is sent


def test_15_13_rulings_5_and_33_claude_with_the_tick_and_the_press_after_a_lost_connection():
    made = statement_for(MODEL_AND_RECORDING)
    assert (made.heading, made.tick) == (words.CLOUD_HEADING_BOTH, words.CLOUD_TICK_BOTH)
    assert made.sent[0] == words.CLOUD_SENT_RECORDING and made.sent[1] == "The words spoken in the consultation. A name spoken aloud is among them."
    assert words.CLOUD_STAYS_RECORDING not in made.stays                                   # the recording leaves: the line would not be true
    assert [heading for heading, _ in made.parts] == [words.CLOUD_SPEECHMATICS_HEADING, words.CLOUD_CLAUDE_HEADING]
    assert made.parts[0] == statement_for(RECORDING_ALONE).parts[0]
    # At the one press after a lost connection both sets show (ruling 33), in a path with live sound.
    press = statement_for(BOTH, at_the_press=True)
    assert press.sent[:2] == (words.CLOUD_SENT_SOUND, words.CLOUD_SENT_RECORDING)
    assert press.parts[0][1] == (*words.CLOUD_SPEECHMATICS_LINES, words.CLOUD_SPEECHMATICS_WHOLE_KEPT, words.CLOUD_SPEECHMATICS_WHOLE_COST)
    assert statement_for(SOUND_ALONE, at_the_press=True).heading == words.CLOUD_HEADING_TRANSCRIPTION


@pytest.mark.parametrize("path, sound, wordsline, recording", [
    (BOTH, True, True, False), (MODEL_ALONE, False, True, False), (SOUND_ALONE, True, False, False),
    (RECORDING_ALONE, False, False, True), (MODEL_AND_RECORDING, False, True, True),
    (ChosenPath(CLAUDE, SPEECHMATICS, better_accuracy=True), True, True, False),      # the tick does not count in cloud transcription
])
def test_15_13_ruling_5_a_line_shows_only_when_it_is_true_for_the_path(path, sound, wordsline, recording):
    made = statement_for(path)
    assert (words.CLOUD_SENT_SOUND in made.sent) is sound
    assert (words.CLOUD_SENT_AGE in made.sent) is wordsline and (words.CLOUD_CLAUDE_HEADING in made.text) is wordsline
    assert (words.CLOUD_SENT_RECORDING in made.sent) is recording and (words.CLOUD_SPEECHMATICS_WHOLE_COST in made.text) is recording
    assert (words.CLOUD_SPEECHMATICS_HEADING in made.text) is (sound or recording)
    assert (words.CLOUD_SPEECHMATICS_LINES[1] in made.text) is sound                       # the line on live sound
    assert made.text.endswith(f"{words.CLOUD_PROTOTYPE}\n\n[ ] {made.tick}\n")


def test_15_13_ruling_5_a_path_on_this_computer_has_no_statement_and_the_machine_decides_where_a_path_begins():
    assert statement_for(LOCAL) is None and not LOCAL.holds_cloud
    assert beginning("suitable") == LOCAL
    for case in ("smaller", "none", "mac", "unreadable"):                                 # 10.3
        assert beginning(case) == BOTH
    assert BOTH.services == (SPEECHMATICS, CLAUDE) and RECORDING_ALONE.services == (SPEECHMATICS,)
    # The owner's word of 16 Nov 2026: the recording after Stop needs its service only after Stop.
    assert RECORDING_ALONE.needed_while_it_runs == () and MODEL_AND_RECORDING.needed_while_it_runs == (CLAUDE,)
    assert BOTH.needed_while_it_runs == (SPEECHMATICS, CLAUDE)


def test_7_3_rule_4_the_path_is_audited_from_what_to_what_and_a_changed_choice_or_word_asks_for_the_tick_again(tmp_path, clock, monkeypatch):
    db = open_database(tmp_path / "openconsult.db")
    audit = Audit(db, clock)
    stored = Stored(db, audit, clock)
    assert stored.path("suitable") == LOCAL and stored.path("none") == BOTH and audit.lines() == []     # read, never written
    stored.set_path("suitable", MODEL_ALONE)
    assert stored.path("suitable") == MODEL_ALONE
    assert [(l.event, l.detail) for l in audit.lines()] == [("setting.changed", "language_model from this_computer to claude")]
    stored.set_path("suitable", MODEL_ALONE)                                               # the same path writes nothing
    assert len(audit.lines()) == 1
    stored.set_path("suitable", MODEL_AND_RECORDING)
    assert audit.lines()[0].detail == "better_accuracy from off to on"
    with pytest.raises(ValueError):
        stored.set_path("suitable", ChosenPath("another", THIS_COMPUTER))
    # The tick: the checksum of the text as shown, with the path, in the audit log.
    shown = statement_for(MODEL_ALONE)
    assert not stored.ticked(shown) and stored.ticked(None)
    stored.tick_statement(shown.sha256, MODEL_ALONE)
    assert stored.ticked(shown) and stored.ticked_sha256 == shown.sha256 and len(shown.sha256) == 64
    assert (audit.lines()[0].event, audit.lines()[0].detail) == (
        "statement.ticked", f"language model claude, transcription this_computer, recording after Stop no; sha256 {shown.sha256}")
    # Another choice has another text, so the tick no longer stands for it.
    assert not stored.ticked(statement_for(BOTH)) and not stored.ticked(statement_for(MODEL_AND_RECORDING))
    # A word changed by a later release: the same path, another checksum, so it is asked again.
    monkeypatch.setattr(words, "CLOUD_INTRO", words.CLOUD_INTRO + " Made-up change.")
    assert not stored.ticked(statement_for(MODEL_ALONE))
    db.close()


def test_rule_4_of_run_9b_no_place_of_the_owners_words_is_empty():
    for name in ("CLOUD_HEADING_TRANSCRIPTION", "CLOUD_TICK_SOUND", "CLOUD_HEADING_RECORDING", "CLOUD_TICK_RECORDING", "CLOUD_MARK",
                 "CLOUD_MARK_SOUND", "CLOUD_MARK_WORDS", "CLOUD_MARK_RECORDING", "UPLOAD_DELETE_NOT_PROVEN"):
        assert getattr(words, name).strip(), name


# ------------------------------------------------- the line for teaching (run 10b)

TEACHING_LINE = "What you type in a teaching case. It goes to the language model service."
# The statement as the code of 69135bb built it, before the line stood: the checksum of the text of three paths and the
# one checksum of every word, computed from that code on 25 Nov 2026. It is what a folder that ticked before holds.
BEFORE_THE_LINE = {"both": "f151c33d2a4499b0e17cb813be8dc98b1dbe0202dcae64d328631891582c8068",
                   "sound": "bb1594c226df64a1da081ec066e218171676b9f0c319349afff2f8a11e64f3d3",
                   "words": "b36f679fa2e49a1f94e2a34372ecb70c1dd3cadd56dbf69120aaec86edccfe97"}


def test_15_14_ruling_15_the_line_for_teaching_is_the_owners_and_the_last_of_what_is_sent_on_every_path_with_claude_and_on_no_other():
    assert words.CLOUD_SENT_TEACHING == TEACHING_LINE
    with_claude = (BOTH, MODEL_ALONE, MODEL_AND_RECORDING, ChosenPath(CLAUDE, SPEECHMATICS, better_accuracy=True))
    for made in (*(statement_for(path) for path in with_claude), statement_for(BOTH, at_the_press=True)):
        assert made.sent[-1] == TEACHING_LINE and made.text.count(TEACHING_LINE) == 1          # last, whole, once
    for made in (statement_for(SOUND_ALONE), statement_for(RECORDING_ALONE), statement_for(SOUND_ALONE, at_the_press=True)):
        assert "teaching" not in made.text                                                     # true of no path without Claude


def test_15_14_ruling_15_a_tick_given_before_the_line_stood_is_asked_for_once_more(tmp_path, clock, monkeypatch):
    db = open_database(tmp_path / "openconsult.db")
    stored = Stored(db, Audit(db, clock), clock)
    built = statement_module._sent
    with monkeypatch.context() as before:
        # The list as it stood before: the same function without the line. The checksums prove it is that statement.
        before.setattr(statement_module, "_sent", lambda path, recording: tuple(
            line for line in built(path, recording) if line != words.CLOUD_SENT_TEACHING))
        old = statement_for(BOTH)
        assert (old.sha256, statement_for(SOUND_ALONE).sha256, statement_module.words_checksum()) == (
            BEFORE_THE_LINE["both"], BEFORE_THE_LINE["sound"], BEFORE_THE_LINE["words"])
        stored.tick_statement(old.sha256, BOTH, old)
        assert all(stored.covers(statement_for(path)) for path in (BOTH, MODEL_ALONE, SOUND_ALONE))
    # The statement now holds more than was ticked: asked once more (ruling 15; 15.13, ruling 48, read the other way).
    assert not stored.ticked(statement_for(BOTH)) and not stored.covers(statement_for(BOTH))
    assert not stored.covers(statement_for(MODEL_ALONE))
    # A path under that wider tick whose own text has not changed is asked once more as well: a word of the
    # statements has changed since the tick, and the test of less is made only while none has (ruling 48).
    assert statement_for(SOUND_ALONE).sha256 == BEFORE_THE_LINE["sound"] and not stored.covers(statement_for(SOUND_ALONE))
    # A folder whose own tick was for the sound alone is not asked: its text is the text it ticked.
    stored.tick_statement(BEFORE_THE_LINE["sound"], SOUND_ALONE)
    assert stored.covers(statement_for(SOUND_ALONE))
    # Ticked once more, with the line, it stands, and so does every path that sends less.
    new = statement_for(BOTH)
    stored.tick_statement(new.sha256, BOTH, new)
    assert all(stored.covers(statement_for(path)) for path in (BOTH, MODEL_ALONE, SOUND_ALONE))
    db.close()
