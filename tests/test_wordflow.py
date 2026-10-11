"""Fix one of part two of 5c (spec 15.9, the details of part two): the
English model's last word before a silence is passed on once the model has
moved past it. The grouping of tokens into words, loaded by path as the
worker loads it. Every token here is made up; no model is run."""

import importlib.util
import random
from pathlib import Path

FLOW = Path(__file__).resolve().parents[1] / "openconsult" / "speech" / "nemotron" / "wordflow.py"
spec = importlib.util.spec_from_file_location("nemotron_wordflow", FLOW)
wordflow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wordflow)
WordFlow, MARK = wordflow.WordFlow, wordflow.WORD_MARK
FRAME_S = 0.08


def text_of(ids):
    """A stand-in for the tokenizer: ids are the pieces themselves."""
    return "".join(ids).replace(MARK, " ")


def tokens_of(text, start=0, step=2, gap_inside=1):
    """Each word as a word-mark piece and one continuation piece per further
    letter pair, at rising frames."""
    found, frame = [], start
    for word in text.split():
        found.append((MARK + word[:2], frame))
        for i in range(2, len(word), 2):
            frame += gap_inside
            found.append((word[i:i + 2], frame))
        frame += step
    return found


def old_grouping(tokens):
    """Today's grouping: a word closes only on the next word mark or at the end."""
    words, open_word = [], None
    for piece, frame in tokens:
        if piece.startswith(MARK) or open_word is None:
            if open_word is not None:
                words.append(open_word)
            open_word = {"ids": [piece], "first": frame, "last": frame}
        else:
            open_word["ids"].append(piece)
            open_word["last"] = frame
    if open_word is not None:
        words.append(open_word)
    return [{"word": text_of(w["ids"]).strip(), "start": round(w["first"] * FRAME_S, 3),
             "end": round((w["last"] + 1) * FRAME_S, 3)} for w in words]


def test_fix_one_a_word_with_no_next_word_is_complete_once_the_model_has_moved_a_second_past_it():
    flow = WordFlow(text_of, FRAME_S)
    for piece, frame in tokens_of("ask not"):
        flow.take(piece, piece, frame)
    assert flow.complete == [{"word": "ask", "start": 0.0, "end": 0.16}] and flow.open_text() == "not"
    last = 4                                   # the frame of the last token of "not" (▁no at 3, t at 4)
    flow.moved_to(last + 12)                   # 12 frames: 0.96 s, not yet
    assert flow.open_text() == "not" and len(flow.complete) == 1
    flow.moved_to(last + 13)                   # 13 frames: 1.04 s past the word
    assert flow.open is None and flow.complete[-1] == {"word": "not", "start": 0.24, "end": 0.4}
    assert flow.tokens_after_close_by_time == 0
    # Silence after it: nothing more happens, and finish gives nothing new.
    flow.moved_to(last + 100)
    flow.finish()
    assert [w["word"] for w in flow.complete] == ["ask", "not"]


def test_fix_one_never_splits_a_word_and_never_changes_adds_or_loses_one():
    # A word whose tokens straddle a chunk of 13 frames is one word.
    flow = WordFlow(text_of, FRAME_S)
    flow.take(MARK + "co", MARK + "co", 12)
    flow.moved_to(13)                          # the chunk ended between its two tokens
    flow.take("da", "da", 13)
    flow.take("mol", "mol", 14)
    flow.moved_to(26)
    flow.finish()
    assert [w["word"] for w in flow.complete] == ["codamol"] and flow.largest_gap_frames == 1
    # Random token sequences with gaps inside a word under the figure: the
    # same words, with the same times, as today's grouping; every token in one word.
    for seed in range(40):
        rnd = random.Random(seed)
        tokens = tokens_of(" ".join(rnd.choice(["a", "ab", "abcd", "abcdef", "x"]) for _ in range(rnd.randint(1, 12))),
                           step=rnd.randint(1, 40), gap_inside=rnd.randint(1, 12))
        flow = WordFlow(text_of, FRAME_S)
        for i, (piece, frame) in enumerate(tokens):
            flow.take(piece, piece, frame)
            # The decoding runs on, never past the next token's frame: a token
            # is emitted while its frame is decoded.
            next_frame = tokens[i + 1][1] if i + 1 < len(tokens) else frame + 50
            flow.moved_to(rnd.randint(frame, next_frame))
            flow.moved_to(rnd.randint(frame, next_frame))
        flow.finish()
        assert flow.complete == old_grouping(tokens), seed
        assert flow.tokens_after_close_by_time == 0
        assert sum(len(text_of([p]).strip()) for p, _ in tokens) == sum(len(w["word"]) for w in flow.complete)


def test_ruling_8_the_grouping_of_5b_stays_a_word_mark_opens_a_word_and_stop_closes_the_open_one():
    flow = WordFlow(text_of, FRAME_S)
    flow.take("st", "st", 5)                   # no word open: a piece without the mark opens one
    flow.take("op", "op", 6)
    flow.take(MARK + "no", MARK + "no", 9)     # the mark closes "stop" and opens "no"
    assert flow.complete == [{"word": "stop", "start": 0.4, "end": 0.56}]
    flow.take("w", "w", 9)
    assert flow.open_text() == "now" and len(flow.complete) == 1
    flow.finish()                              # Stop closes the open word
    assert flow.complete[-1] == {"word": "now", "start": 0.72, "end": 0.8} and flow.open is None
    assert flow.open_text() == ""
    # The text comes from the callable given: an empty text makes no word.
    empty = WordFlow(lambda ids: "   ", FRAME_S)
    empty.take("x", MARK + "x", 0)
    empty.finish()
    assert empty.complete == []
