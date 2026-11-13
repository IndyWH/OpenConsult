"""The lines a model reads and a long page in parts, one rule for the app
and the bench (spec 15.10, the details of step 6c; 15.9 ruling 37; spec
5.1). Every word here is made up."""

import random

from openconsult.bench.speech import model_lines
from openconsult.consult import joined, labels


def row(n, speaker, start, end, text):
    return {"n": n, "raw_speaker": speaker, "start_s": start, "end_s": end, "text": text, "label": "unsure"}


def made_rows(seed: int, count: int | None = None) -> list[dict]:
    rnd = random.Random(seed)
    rows, at = [], 0.0
    for n in range(1, (count if count is not None else rnd.randint(0, 30)) + 1):
        text = " ".join(rnd.choice(["ask", "not", "what", "rest.", "pain?", "now!", "a,"]) for _ in range(rnd.randint(1, 6)))
        length = rnd.uniform(0.1, 3.0)
        rows.append(row(n, rnd.choice(["S1", "S2", None]), round(at, 3), round(at + length, 3), text))
        at += length + rnd.choice([0.0, 0.3, 0.99, 1.0, 2.5])
    return rows


def test_6c_the_apps_joined_lines_are_the_benchs_on_the_same_pieces_and_the_label_checks_text_the_same_bytes():
    # Details, The lines a model reads; spec 5.1: one function, so the app sends what the bench of 5e read.
    assert model_lines.lines_of is joined.lines_of
    for seed in range(40):
        rows = made_rows(seed)
        pieces = [{"speaker": r["raw_speaker"], "start": r["start_s"], "end": r["end_s"], "text": r["text"]} for r in rows]
        lines = joined.of_rows(rows)
        assert [{k: v for k, v in line.items() if k != "page_lines"} for line in lines] == model_lines.lines_of(pieces), seed
        if lines:     # a page with no line is never sent: the gate refuses it and the check is not offered
            assert labels.lines_text(lines) == model_lines.lines_text(lines), seed      # the frame file gives the bench's bytes
    assert labels.lines_text(joined.of_rows(made_rows(3))).startswith("TRANSCRIPT:\n[1] ")


def test_6c_no_word_is_changed_added_or_lost_and_each_joined_line_remembers_its_lines():
    # Details: the proof is the hash the label check already uses, on the joined lines cut back into the page's lines.
    for seed in range(40):
        rows = made_rows(seed) + [{"n": None, "raw_speaker": "S1", "start_s": 0, "end_s": 1, "text": "refused words", "label": "unsure"}]
        lines = joined.of_rows(rows)
        numbered = [r for r in rows if r["n"] is not None]
        assert [n for line in lines for n in line["page_lines"]] == [r["n"] for r in numbered]      # every line once, in order
        assert labels.texts_hash(joined.unjoined(lines, rows)) == labels.texts_hash(numbered), seed
    rows = [row(1, "S1", 0, 1, "ask not"), row(2, "S1", 1.5, 2, "what you"), row(3, None, 2.1, 3, "can do"),
            row(4, None, 3.2, 4, "for it."), row(5, None, 4.1, 5, "Then"), row(6, "S2", 7.0, 8, "rest")]
    lines = joined.of_rows(rows)
    assert [(line["text"], line["page_lines"]) for line in lines] == [
        ("ask not what you", [1, 2]),          # the choice's own speaker, under a second between
        ("can do for it.", [3, 4]),            # two with no speaker count as the same
        ("Then", [5]), ("rest", [6])]          # a sentence's end; another speaker
    changed = [dict(r) for r in rows]
    changed[1]["text"] = "what he"
    assert labels.texts_hash(joined.unjoined(lines, rows)) != labels.texts_hash(changed)   # the twin: a changed word is seen


def lines_made(count: int) -> list[dict]:
    return [{"n": n, "text": f"line {n}"} for n in range(1, count + 1)]


def test_6c_a_page_of_160_lines_is_one_call_and_a_longer_one_the_fewest_equal_parts_of_at_most_120_new_lines():
    # WHOLE_LINES, PART_LINES: the named figures of the details, A page in parts.
    assert (joined.WHOLE_LINES, joined.PART_LINES, joined.OVERLAP_LINES) == (160, 120, 10)
    assert [len(p["lines"]) for p in joined.cut(lines_made(160))] == [160]
    assert joined.cut(lines_made(0)) == [{"k": 1, "lines": [], "overlap": 0}]
    for count, sizes in ((161, [81, 80]), (240, [120, 120]), (241, [81, 80, 80]), (400, [100, 100, 100, 100])):
        parts = joined.cut(lines_made(count))
        new = [[line["n"] for line in p["lines"][p["overlap"]:]] for p in parts]
        assert [len(n) for n in new] == sizes, count
        assert [n for part in new for n in part] == list(range(1, count + 1))      # every line a new line exactly once
        assert max(sizes) - min(sizes) <= 1 and max(sizes) <= joined.PART_LINES
        assert [p["k"] for p in parts] == list(range(1, len(parts) + 1))


def test_6c_each_later_part_begins_with_the_last_10_lines_of_the_part_before_and_is_numbered_from_1():
    parts = joined.cut(lines_made(300))
    assert [p["overlap"] for p in parts] == [0, 10, 10]
    for before, part in zip(parts, parts[1:]):
        assert part["lines"][:10] == before["lines"][-10:]
    assert [line["n"] for line in joined.numbered(parts[1])] == list(range(1, 111))
    assert joined.numbered(parts[1])[0]["text"] == "line 91" and joined.numbered(parts[1])[10]["text"] == "line 101"
    # The bench's halves: the part size half the page rounded up, the same overlap; a short first part carries what it has.
    halves = joined.cut(lines_made(43), whole=0, part=22, overlap=10)
    assert [(len(p["lines"]), p["overlap"]) for p in halves] == [(22, 0), (31, 10)]
    assert [(len(p["lines"]), p["overlap"]) for p in joined.cut(lines_made(6), whole=0, part=3, overlap=10)] == [(3, 0), (6, 3)]


def test_6c_the_overlaps_labels_come_from_the_part_before_never_the_later_part():
    parts = joined.cut(lines_made(170))             # 85 and 85, the second carrying lines 76 to 85
    first = {i: "doctor" for i in range(1, 86)}
    second = {i: "patient" for i in range(1, 96)}   # the later part calls the carried lines patient too
    merged = joined.merge(parts, [first, second])
    assert sorted(merged) == list(range(1, 171))
    assert all(merged[n] == "doctor" for n in range(1, 86)) and all(merged[n] == "patient" for n in range(86, 171))


def test_6c_all_or_nothing_one_part_without_labels_and_no_label_is_taken_from_any():
    parts = joined.cut(lines_made(170))
    first = {i: "doctor" for i in range(1, 86)}
    assert joined.merge(parts, [first, None]) is None
    assert joined.merge(parts, [None, {i: "patient" for i in range(1, 96)}]) is None
    assert joined.merge(parts, [first]) is None                                    # a part never asked
    assert joined.merge(joined.cut(lines_made(3)), [{1: "doctor", 2: "patient", 3: "unsure"}]) == {1: "doctor", 2: "patient", 3: "unsure"}
