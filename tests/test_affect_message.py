"""The affect call's user message: whole transcript, recent turns LAST.

String assembly only — no model, no database, no skip. It runs on a
machine with no MedGemma, which is the point: this is the half of the
consultation-467 fix that can be checked without asking a model
anything.

467: a patient opened with an all-clear after colon cancer surgery and
turned sad about his wife's illness. The affect call read the whole
transcript from zero seconds with no reason to weight the last minute
above the first, and returned "happy" on a transcript that already
contained "I'm sad about that". The prompt now asks a NOW question
(app/cds.py::AFFECT_PROMPT); this puts the now where the model attends.
"""

from app.cds import AFFECT_RECENT_TURNS, affect_message

TURNS = [
    "Good news doctor, the scan was clear.",
    "That is wonderful, I am delighted for you.",
    "It has been a long two years since the surgery.",
    "And how have you been in yourself?",
    "There is a bit of sadness in the story though.",
    "My wife's arthritis has been very bad this year.",
    "She is quite miserable with the pain, and I am sad about that.",
    "Do you think she might need antidepressants?",
]

BLOCK_MARKER = "THE MOST RECENT TURNS"


def _long_transcript() -> str:
    assert len(TURNS) > AFFECT_RECENT_TURNS, "fixture must exceed the window"
    return "\n".join(TURNS)


def test_the_block_holds_exactly_the_last_n_turns():
    message = affect_message(_long_transcript())
    block = message.split(BLOCK_MARKER, 1)[1]
    for turn in TURNS[-AFFECT_RECENT_TURNS:]:
        assert turn in block, turn
    # ...and nothing older leaks into it. The turn that made 467 wrong is
    # the all-clear at the top: it belongs in the context, not the moment.
    for turn in TURNS[:-AFFECT_RECENT_TURNS]:
        assert turn not in block, turn


def test_the_block_comes_after_the_whole_transcript():
    """The end of the message is what the model attends to most, so the
    thing being judged goes last. If this ever inverts, the fix is
    undone while every other assertion still passes."""
    message = affect_message(_long_transcript())
    assert message.index("LIVE TRANSCRIPT SO FAR") < message.index(BLOCK_MARKER)
    # The full transcript survives in full — the block is added context,
    # not a replacement for it.
    assert _long_transcript() in message
    # The last turn appears twice: once in the transcript, once in the block.
    assert message.count(TURNS[-1]) == 2


def test_a_short_transcript_is_not_repeated_twice():
    """A transcript shorter than the window IS the recent turns."""
    short = "\n".join(TURNS[:AFFECT_RECENT_TURNS])
    message = affect_message(short)
    assert BLOCK_MARKER not in message
    for turn in TURNS[:AFFECT_RECENT_TURNS]:
        assert message.count(turn) == 1


def test_a_transcript_exactly_the_window_long_is_not_repeated_either():
    message = affect_message("\n".join(TURNS[:AFFECT_RECENT_TURNS]))
    assert BLOCK_MARKER not in message


def test_blank_lines_do_not_consume_the_window():
    """Turn counting is on content, not on newlines: a transcript padded
    with blank lines must still surface real turns in the block."""
    padded = "\n\n".join(TURNS) + "\n\n"
    block = affect_message(padded).split(BLOCK_MARKER, 1)[1]
    for turn in TURNS[-AFFECT_RECENT_TURNS:]:
        assert turn in block, turn
