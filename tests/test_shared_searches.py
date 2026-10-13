"""The searches of the test of 5d (spec 15.9, the details of 5d; 15.8
ruling 1): the 11 lists are what the public bench holds, a search is sent
in v1's form byte for byte, and a vector is checked. Nothing here is what
a model said: the lists are read from the public data as data."""

import gzip
import hashlib
import json
import math
from pathlib import Path

import pytest

from openconsult.bench.shared import searches

REPO = Path(__file__).resolve().parents[1]
PUBLIC = REPO / "engine-bench" / "arms" / "ollama-google-file" / "replies.jsonl.gz"
LISTS_SHA256 = "6f1ceb6a1ef490de03ed56311266105b0e8e21d73e63d6e2c67580db2256c314"


def test_15_9_5d_the_11_lists_are_what_the_public_bench_holds():
    with gzip.open(PUBLIC, "rt", encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    chain = [r for r in rows if r["case"] == "495" and r["chain"] == "A1"]
    assert searches.lists_from_replies(chain) == searches.read_lists()
    assert len(searches.read_lists()) == 11 and all(names for names in searches.read_lists())
    assert hashlib.sha256(searches.LISTS_FILE.read_bytes()).hexdigest() == LISTS_SHA256


def test_15_8_ruling_5_a_kept_empty_reply_takes_the_earlier_list():
    rows = [{"job": "assessment", "point": 2, "kept": True, "text": json.dumps({"differentials": []})},
            {"job": "alarm", "point": 1, "kept": False, "text": "{}"},
            {"job": "assessment", "point": 1, "kept": False,
             "text": json.dumps({"differentials": [{"condition": "Made-up A"}, {"condition": "Made-up B"}, "junk"]})},
            {"job": "assessment", "point": 3, "kept": False, "text": json.dumps({"differentials": []})}]
    assert searches.lists_from_replies(rows) == [["Made-up A", "Made-up B"], ["Made-up A", "Made-up B"], []]


def test_15_9_5d_a_search_is_sent_in_v1s_form_byte_for_byte():
    assert searches.search_text("Made-up condition").encode("utf-8") == b"task: search result | query: Made-up condition"
    assert searches.passage_text("a_file.md", "the piece").encode("utf-8") == b"title: a_file.md | text: the piece"


def test_15_9_5d_search_k_takes_list_k_and_starts_again_after_the_last():
    lists = [["a"], ["b"], ["c"]]
    assert [searches.list_for(k, lists) for k in range(7)] == [["a"], ["b"], ["c"], ["a"], ["b"], ["c"], ["a"]]


@pytest.mark.parametrize("vector, fault", [
    ([0.1] * 768, None),
    ([0.1] * 767, "767 numbers, not 768"),
    ([0.1] * 767 + [math.nan], "number 767 is a not-a-number"),
    ([math.inf] + [0.1] * 767, "number 0 is infinite"),
    (["0.1"] + [0.1] * 767, "number 0 is not a number"),
    ([True] + [0.1] * 767, "number 0 is not a number"),
    ("not a list", "not a list of numbers"),
])
def test_15_9_5d_the_check_of_a_vector(vector, fault):
    assert searches.vector_fault(vector) == fault
