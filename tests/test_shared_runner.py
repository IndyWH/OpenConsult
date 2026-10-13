"""The searches every 5 seconds and the side reading of 5d (spec 15.9,
the details of 5d; rule 22 of the stage): with a clock the test moves, so
no test waits. Every vector here is made up."""

from pathlib import Path

import pytest

from openconsult.bench.shared import pieces, runner
from openconsult.bench.shared.embed import Vectors

VECTOR = [0.25] * 768


class MovedClock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


class MadeUpEmbedder:
    """Answers at once, taking `takes` seconds of the moved clock for each
    call; the texts it was given are kept."""
    name, where = "made-up", "card"

    def __init__(self, clock, takes=1.0, faults=None):
        self.clock, self.takes, self.texts = clock, takes, []
        self.faults = dict(faults or {})          # text -> a Vectors to answer instead

    def embed(self, texts):
        self.texts.append(list(texts))
        self.clock.sleep(self.takes)
        for text in texts:
            if text in self.faults:
                return self.faults[text]
        return Vectors(True, [VECTOR for _ in texts], self.takes, None, {"made": True})

    def info(self):
        return {"device": "made-up"}

    def close(self):
        pass


def searches(embedder, clock, lists, **kwargs):
    return runner.run_searches(embedder, lists, every_s=5.0, sleep=clock.sleep, clock=clock, wall=lambda: 1000.0 + clock.t,
                               **kwargs)


def test_15_9_5d_one_search_every_5_seconds_with_a_clock_the_test_moves():
    clock = MovedClock()
    found = searches(MadeUpEmbedder(clock), clock, [["Made-up A"], ["Made-up B"]], limit=3)
    assert [s["started"] for s in found["searches"]] == [0.0, 5.0, 10.0]
    assert [s["due"] for s in found["searches"]] == [0.0, 5.0, 10.0]
    assert [s["names"] for s in found["searches"]] == [["Made-up A"], ["Made-up B"], ["Made-up A"]]
    assert found["late_starts"] == 0 and found["failed"] == 0 and found["stopped_by"] == "limit"
    assert found["t0_epoch"] == 1100.0 and found["searches"][1]["started_epoch"] == 1105.0
    assert found["median_s"] == 1.0 and found["info"] == {"device": "made-up"}


def test_15_9_5d_a_second_search_never_begins_before_the_first_has_ended_and_the_late_start_is_counted():
    clock = MovedClock()
    found = searches(MadeUpEmbedder(clock, takes=7.0), clock, [["Made-up A"]], limit=3)
    assert [s["started"] for s in found["searches"]] == [0.0, 7.0, 14.0]
    assert [s["late"] for s in found["searches"]] == [False, True, True]
    assert [s["late_s"] for s in found["searches"]] == [0.0, 2.0, 4.0] and found["late_starts"] == 2


def test_15_9_5d_a_list_with_no_name_gives_no_search_and_is_counted():
    clock = MovedClock()
    embedder = MadeUpEmbedder(clock)
    found = searches(embedder, clock, [[], ["Made-up A"]], limit=2)
    assert found["empty"] == 1 and found["searches"][0]["empty"] and found["searches"][0]["calls"] == []
    assert embedder.texts == [["task: search result | query: Made-up A"]]
    assert found["median_s"] == 1.0                      # an empty search is not a search time


def test_15_9_5d_each_name_goes_in_a_call_of_its_own_and_a_failed_call_is_kept():
    clock = MovedClock()
    bad = Vectors(True, [VECTOR[:-1]], 1.0, None, {})
    embedder = MadeUpEmbedder(clock, faults={"task: search result | query: Made-up C": bad,
                                             "task: search result | query: Made-up E": Vectors(False, [], 1.0, "made-up: refused", {})})
    found = searches(embedder, clock, [["Made-up A", "Made-up B", "Made-up C", "Made-up D", "Made-up E"]], limit=1)
    search = found["searches"][0]
    assert embedder.texts == [[f"task: search result | query: Made-up {x}"] for x in "ABCDE"]
    assert search["seconds"] == 5.0 and [c["ok"] for c in search["calls"]] == [True, True, False, True, False]
    assert search["calls"][2]["fault"] == "767 numbers, not 768" and search["calls"][4]["error"] == "made-up: refused"
    assert not search["ok"] and found["failed"] == 1 and found["median_s"] is None


def test_15_9_5d_the_runner_stops_at_the_stop_condition_and_starts_no_search_after_it():
    clock = MovedClock()
    found = searches(MadeUpEmbedder(clock), clock, [["Made-up A"]], until=lambda: clock.t >= 107.0)
    assert len(found["searches"]) == 2 and found["stopped_by"] == "stop"


def made_up_sources(tmp_path):
    lessons = tmp_path / "LESSONS.md"
    lessons.write_text(" ".join(f"lesson{i}" for i in range(1000)), encoding="utf-8")
    cases = tmp_path / "cases"
    cases.mkdir()
    for n in range(30):
        (cases / f"case_{n:02d}.md").write_text(" ".join(f"word{n}_{i}" for i in range(2050)), encoding="utf-8")
    (cases / "not_a_case.txt").write_text("x " * 500, encoding="utf-8")
    return lessons, cases


def test_15_9_5d_the_pieces_come_from_the_public_files_only_in_v1s_form(tmp_path):
    lessons, cases = made_up_sources(tmp_path)
    files = pieces.public_files(lessons, cases)
    assert files[0] == lessons and len(files) == 31 and all(f.suffix == ".md" for f in files)
    cut, used = pieces.cut(files, lessons=lessons, cases=cases)
    assert len(cut) == 250 and all(100 <= len(p["text"].split()) <= 200 for p in cut)
    assert cut[0]["passage"] == "title: LESSONS.md | text: " + cut[0]["text"] and cut[0]["title"] == "LESSONS.md"
    assert used[0]["pieces"] == 5 and used[1]["file"] == "case_00.md" and len(used[1]["sha256"]) == 64
    assert sum(u["pieces"] for u in used) == 250
    with pytest.raises(pieces.NotPublic):
        pieces.cut([tmp_path / "private.md"], lessons=lessons, cases=cases)
    with pytest.raises(pieces.NotPublic):
        pieces.cut([cases / "not_a_case.txt"], lessons=lessons, cases=cases)
    assert pieces.allowed(pieces.LESSONS) and pieces.allowed(pieces.CASES / "495.jsonl") is False


def test_15_9_5d_the_side_reading_sends_16_at_a_time(tmp_path):
    lessons, cases = made_up_sources(tmp_path)
    cut, _ = pieces.cut(pieces.public_files(lessons, cases), lessons=lessons, cases=cases)
    clock = MovedClock()
    embedder = MadeUpEmbedder(clock, takes=0.5)
    found = runner.run_index(embedder, cut, 16, clock=clock, wall=lambda: 1.0)
    assert [len(t) for t in embedder.texts] == [16] * 15 + [10] and embedder.texts[0][0] == cut[0]["passage"]
    assert found["pieces"] == 250 and len(found["batches"]) == 16 and found["seconds"] == 8.0 and found["ok"]
    assert all(Path(p["title"]).suffix == ".md" for p in cut)
