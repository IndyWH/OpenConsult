"""The word check (spec 15.7, ruling 3): a made-up v1 record, built by
this test's own serialiser in v1's shape, matches; a one-character
change in any of the compared parts is counted as a mismatch."""

import hashlib
import json

import pytest

from openconsult.bench.cases import case_named, load_cases
from openconsult.bench.wordcheck import check, load_records
from openconsult.db import open_database
from openconsult.llm.door import Door
from openconsult.llm.record import ModelCalls
from openconsult.prompts import loader
from tests.fakes import FakeEngine
from tests.test_bench import made_up_folder

LINE = "The patient is a 31-year-old woman."
SYSTEM = {"assessment": loader.prompt("assessment"), "urgency": loader.prompt("alarm")}
FORM = {"assessment": loader.form("assessment"), "urgency": loader.form("alarm")}
CAP = {"assessment": 1500, "urgency": 1000}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def v1_record(call: str, user: str, point: int, reply: dict, temperature=0.0, seed=42, model="gemma4:26b-a4b-it-qat",
              think=False, num_ctx=16384, chain="D-A1") -> dict:
    """What v1's bench wrote for one call, with the whole request hashed
    the way its library serialised it."""
    options = {"temperature": temperature, "seed": seed, "num_ctx": num_ctx, "num_predict": CAP[call]}
    body = {"model": model, "messages": [{"role": "system", "content": SYSTEM[call]},
                                         {"role": "user", "content": user}],
            "format": FORM[call], "stream": False, "keep_alive": "30m", "options": options, "think": think}
    compact = json.dumps(body, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return {"arm": "D", "workload": "495", "case_key": "seven", "chain": chain, "pass": point, "call": call, "model": model,
            "think_sent": think, "options_sent": options, "user_sha256": sha(user),
            "request_sha256": hashlib.sha256(compact).hexdigest(), "reply_content": json.dumps(reply)}


REPLY_1 = {"reasoning": "made up", "differentials": [{"condition": "Made-up A", "likelihood": "low", "rationale": "x"},
                                                       {"condition": "Made-up B", "likelihood": "low", "rationale": "y"}],
           "questions_to_ask": [], "signs_to_check": []}
ALARM = {"reasoning": "made up", "time_critical_possible": False, "already_done_or_arranged": False, "urgent_actions": []}


@pytest.fixture
def setting(tmp_path, clock):
    folder = made_up_folder(tmp_path)
    cases = [case_named(load_cases(folder), "seven")]
    db = open_database(tmp_path / "bench" / "calls.db")
    door = Door(FakeEngine(), ModelCalls(db, clock))
    yield cases, door
    db.close()


def records():
    first = f"{LINE}\n\nHere is the transcript of the consultation so far:\nMade-up pass one."
    later = (f"{LINE}\n\nWe have more information.\n\nThis is a stale list of possibilities, made from an "
             f"earlier, shorter transcript:\nMade-up A\nMade-up B\n\nHere is the updated transcript of the "
             f"consultation so far:\nMade-up pass two.")
    alarm_1 = f"{LINE}\n\nLIVE TRANSCRIPT SO FAR:\nMade-up pass one."
    return [v1_record("assessment", first, 1, REPLY_1), v1_record("urgency", alarm_1, 1, ALARM),
            v1_record("assessment", later, 2, REPLY_1, temperature=0.5, seed=3, chain="D-B3"),
            v1_record("assessment", first, 1, REPLY_1, temperature=0.5, seed=3, chain="D-B3")]


def test_15_7_the_word_check_matches_a_recorded_request_and_catches_a_changed_one(setting, tmp_path):
    cases, door = setting
    found = check(records(), cases, door)
    assert found["matched"] == found["total"] == 4 and found["mismatches"] == []
    assert found["by_workload_and_job"] == {"495/alarm": 1, "495/assessment": 3}
    # Twins: each changed part is named.
    changed = records()
    changed[0]["user_sha256"] = sha("other words")
    changed[1]["options_sent"]["num_ctx"] = 8192
    changed[2]["model"] = "other:tag"
    changed[3]["think_sent"] = True
    found = check(changed, cases, door)
    assert found["matched"] == 0
    assert [m["differs_in"] for m in found["mismatches"]] == [["message"], ["options"], ["model"], ["think"]]
    # A record whose request hash alone differs (a changed prompt or form in v1) is caught too.
    off = records()[:1]
    off[0]["request_sha256"] = "0" * 64
    assert check(off, cases, door)["mismatches"][0]["differs_in"] == ["whole request (prompt, form or any part)"]
    # Records are read from a file; an errored call is left out, as v1's verifier did.
    path = tmp_path / "calls.jsonl"
    rows = records() + [{**records()[0], "error": "ConnectError"}, {"arm": "N", "call": "assessment"}]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    assert len(load_records(path)) == 4
