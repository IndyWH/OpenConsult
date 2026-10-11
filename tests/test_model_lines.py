"""The lines a model reads, the turns, and the words placed around a
transcript (spec 15.9, the details of part two of 5c; rulings 17 and 22).
Every word here is made up."""

import random

from openconsult.bench.speech import model_lines
from openconsult.bench.speech.reference import build

PAGE = [("S1", 0.0, 0.4, "Any"), ("S1", 0.4, 0.9, "chest pain"), ("S1", 0.9, 1.3, "at rest?"),
        ("S2", 1.6, 2.9, "No. Not at rest."), (None, 3.1, 3.6, "Only on"), (None, 3.6, 4.0, "the stairs."),
        ("S2", 5.5, 6.0, "Is that bad?")]


def pieces_of(rows):
    return [{"speaker": s, "start": a, "end": b, "text": t} for s, a, b, t in rows]


def test_the_words_that_come_out_are_the_words_that_went_in():
    for seed in range(60):
        rnd = random.Random(seed)
        rows, at = [], 0.0
        for _ in range(rnd.randint(0, 25)):
            words = " ".join(rnd.choice(["ask", "not", "what", "rest.", "pain?", "now!", "a,"]) for _ in range(rnd.randint(1, 6)))
            length = rnd.uniform(0.1, 3.0)
            rows.append((rnd.choice(["S1", "S2", None]), round(at, 3), round(at + length, 3), words))
            at += length + rnd.choice([0.0, 0.3, 0.99, 1.0, 2.5])
        pieces = pieces_of(rows)
        lines = model_lines.lines_of(pieces)
        assert " ".join(line["text"] for line in lines) == " ".join(p["text"] for p in pieces), seed
        assert [i for line in lines for i in line["pieces"]] == list(range(len(pieces)))   # each piece in one line, in order
        assert [line["n"] for line in lines] == list(range(1, len(lines) + 1))
        turns = model_lines.turns_of(lines)
        assert " ".join(turn["text"] for turn in turns) == " ".join(p["text"] for p in pieces), seed
        assert [n for turn in turns for n in turn["lines"]] == [line["n"] for line in lines]
        assert [turn["n"] for turn in turns] == list(range(len(turns)))
        for line in lines:
            assert line["start"] == pieces[line["pieces"][0]]["start"]
            assert line["end"] == max(pieces[i]["end"] for i in line["pieces"])


def test_the_three_conditions_of_the_join_and_that_a_piece_is_never_split():
    one = lambda rows: [line["text"] for line in model_lines.lines_of(pieces_of(rows))]   # noqa: E731
    assert one([("S1", 0, 1, "ask not"), ("S1", 1, 2, "what you")]) == ["ask not what you"]
    assert one([("S1", 0, 1, "ask not."), ("S1", 1, 2, "what you")]) == ["ask not.", "what you"]      # a sentence's end
    assert one([("S1", 0, 1, "ask not?"), ("S1", 1, 2, "what")]) == ["ask not?", "what"]
    assert one([("S1", 0, 1, "ask not!"), ("S1", 1, 2, "what")]) == ["ask not!", "what"]
    assert one([("S1", 0, 1, "ask not"), ("S2", 1, 2, "what you")]) == ["ask not", "what you"]       # a different label
    assert one([(None, 0, 1, "ask not"), (None, 1, 2, "what you")]) == ["ask not what you"]        # no speaker twice: the same label
    assert one([("S1", 0, 1, "ask not"), (None, 1, 2, "what you")]) == ["ask not", "what you"]
    assert one([("S1", 0, 1, "ask not"), ("S1", 1.99, 3, "what you")]) == ["ask not what you"]     # under 1.0 s between
    assert one([("S1", 0, 1, "ask not"), ("S1", 2.0, 3, "what you")]) == ["ask not", "what you"]   # 1.0 s: a pause
    assert one([("S1", 0, 1, "No. Not at rest. Is that bad?")]) == ["No. Not at rest. Is that bad?"]   # never split
    assert one([("S1", 0, 1, "   "), ("S1", 1, 2, "what")]) == ["what"]                            # an empty piece is no line


def test_the_worked_page_gives_its_four_lines_and_four_turns_and_the_exact_texts():
    lines = model_lines.lines_of(pieces_of(PAGE))
    assert [(line["n"], line["speaker"], line["text"], line["start"], line["end"]) for line in lines] == [
        (1, "S1", "Any chest pain at rest?", 0.0, 1.3), (2, "S2", "No. Not at rest.", 1.6, 2.9),
        (3, None, "Only on the stairs.", 3.1, 4.0), (4, "S2", "Is that bad?", 5.5, 6.0)]
    turns = model_lines.turns_of(lines)
    assert [(turn["n"], turn["speaker"], turn["text"]) for turn in turns] == [
        (0, "S1", "Any chest pain at rest?"), (1, "S2", "No. Not at rest."), (2, None, "Only on the stairs."), (3, "S2", "Is that bad?")]
    assert model_lines.lines_text(lines) == ("TRANSCRIPT:\n[1] Any chest pain at rest?\n[2] No. Not at rest.\n"
                                             "[3] Only on the stairs.\n[4] Is that bad?")
    roles = {"S1": "DOCTOR", "S2": "PATIENT"}
    assert model_lines.turns_text(turns, roles) == ("TRANSCRIPT:\n[0] Doctor: Any chest pain at rest?\n[1] Patient: No. Not at rest.\n"
                                                    "[2] Unknown: Only on the stairs.\n[3] Patient: Is that bad?")
    # A label beyond the two of the best fit is Unknown too (ruling 22; the plan review).
    assert model_lines.turns_text(model_lines.turns_of(model_lines.lines_of(pieces_of([("S3", 0, 1, "Hm.")]))), roles) == "TRANSCRIPT:\n[0] Unknown: Hm."
    # Neighbouring lines of one label are one turn; two with no speaker too.
    joined = model_lines.turns_of(model_lines.lines_of(pieces_of([("S1", 0, 1, "Ask."), ("S1", 1, 2, "Not."), (None, 2, 3, "What."), (None, 3, 4, "You.")])))
    assert [(t["speaker"], t["text"], t["lines"]) for t in joined] == [("S1", "Ask. Not.", [1, 2]), (None, "What. You.", [3, 4])]
    # A note from the script: each speech of the reference as cut is one turn, from 0.
    reference = build("**DOCTOR:** Ask not.\n**PATIENT:** What you.\n**DOCTOR:** Can do.\n", last_speech=2)
    script = model_lines.script_turns(reference)
    assert model_lines.turns_text(script, {}) == "TRANSCRIPT:\n[0] Doctor: Ask not.\n[1] Patient: What you."
