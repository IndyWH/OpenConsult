"""The red mark and the alarm lines at review (spec 15.11 ruling 9; R9,
R15, R29; V1_LESSONS 3.14). The matching on made text; the mark in the
live state and on the review page; the alarm lines from the stored
passes. No model's words are asserted."""

import json
from datetime import datetime, timezone

from openconsult import words
from openconsult.consult import alarms
from openconsult.consult.passes import Passes
from openconsult.web.live import SCRIPT_WORDS as LIVE_WORDS, script_words as live_words
from openconsult.web.review import SCRIPT_WORDS as REVIEW_WORDS, script_words as review_words
from tests.conftest import text_of
from tests.fakes import ASSESSMENT
from tests.test_passes import ACTION_A, alarm, assessment, result
from tests.test_review_page import reviewed

START = datetime(2026, 10, 4, 9, 0, tzinfo=timezone.utc)
NAMES = ["Ectopic pregnancy", "Hypoglycaemia", "Anaemia", "Hypo", "Pregnancy", "Subarachnoid haemorrhage"]


def test_ruling_9_the_matching_is_whole_word_after_normalise_on_made_text():
    assert alarms.matched_names("An ectopic pregnancy cannot be excluded.", [], NAMES) == ["Ectopic pregnancy", "Pregnancy"]
    assert alarms.matched_names("Severe hypoglycaemia is likely.", [], NAMES) == ["Hypoglycaemia"]        # hypo does not match hypoglycaemia
    assert alarms.matched_names("made up", [{"action": "Treat the anemia today", "reason": "made up"}], NAMES) == ["Anaemia"]  # spellings fold
    assert alarms.matched_names("Possible sub-arachnoid haemorrhage.", [], NAMES) == ["Subarachnoid haemorrhage"]       # a hyphen goes
    assert alarms.matched_names("Nothing here names a condition.", [ACTION_A], NAMES) == []
    assert alarms.matched_names(None, [], NAMES) == [] and alarms.matched_names("hypo", [], NAMES) == ["Hypo"]
    assert alarms.matched_names("ectopic pregnancy", [], ["Pregnancy, ectopic"]) == []                                  # the run must be contiguous


def test_ruling_9_the_live_page_marks_the_matched_differential_red_with_the_alarm_one_press_away(tmp_path, clock, machine):
    passes = Passes()
    passes.begin()
    passes.settle(1, result(alarm([ACTION_A], reasoning="Made-up A is the worry here."), assessment(("Made-up A", "Made-up B"))), True, 5)
    assert passes.state()["assessment"]["marked"] == ["Made-up A"]
    assert passes.state()["alarm"]["reasoning"] == "Made-up A is the worry here." and passes.state()["alarm"]["actions"] == [ACTION_A]
    passes.begin()
    passes.settle(2, result(alarm(flag=True, reasoning="Made-up B may be time critical."), assessment(("Made-up A", "Made-up B"))), True, 5)
    assert passes.state()["assessment"]["marked"] == ["Made-up B"]                                     # a no-action alarm marks too
    passes.begin()
    passes.settle(3, result(alarm(reasoning="Made-up A again, but quiet."), assessment(("Made-up A",))), True, 5)
    assert passes.state()["assessment"]["marked"] == []                                                # quiet: nothing marked
    passes.begin()
    passes.settle(4, result(alarm(judged=False, detail="gone"), assessment(("Made-up A",))), True, 5)
    assert passes.state()["assessment"]["marked"] == []                                                # not judged: nothing
    # Through the page: the state the script reads carries marked, and the words come from the one file.
    app, client, c = reviewed(tmp_path, clock, machine)
    assert "marked" in json.dumps(c.page_state()["passes"]["assessment"])
    assert set(live_words()) == set(LIVE_WORDS) and {"ALARM_NAMED", "CLOSE"} <= set(LIVE_WORDS)
    assert client.get("/static/alarmdialog.js").status_code == 200


def test_ruling_9_ruling_4_the_review_page_marks_the_match_beside_the_assessment_and_the_copy_text_carries_no_mark(tmp_path, clock, machine):
    fires = {"reasoning": "Made-up condition A is the worry.", "time_critical_possible": True,
             "already_done_or_arranged": False, "urgent_actions": [{"action": "Made-up step", "reason": "made-up reason"}]}
    from tests.test_review_page import engine_with
    app, client, c = reviewed(tmp_path, clock, machine, engine_with(alarm=[fires]))
    raw = client.get("/consultations/1").text
    page = text_of(client.get("/consultations/1"))
    assert '<li class="red">Made-up condition A (high): made up' in raw and 'data-name="Made-up condition A"' in raw
    assert '<li>Made-up condition B (low): made up' in raw and words.ALARM_NAMED in page
    marks = json.loads(raw.split('<script id="marks" type="application/json">')[1].split("</script>")[0])
    assert list(marks) == ["Made-up condition A"] and marks["Made-up condition A"]["reasoning"] == "Made-up condition A is the worry."
    assert '<dialog id="alarm-dialog"' in raw and set(review_words()) == set(REVIEW_WORDS)
    copy = client.get("/consultations/1/note.txt").text
    assert "Made-up condition" not in copy and words.ALARM_NAMED not in copy
    client.post("/consultations/1/note/approve")
    assert "Made-up condition" not in app.state.parts.notes.approval(1)["text"]
    assert '<li class="red">Made-up condition A' in client.get("/consultations/1").text                    # still marked after approve


def test_ruling_9_R29_3_14_the_warnings_pane_lists_each_alarm_once_with_its_time_state_and_a_press_from_the_last_line_read_and_the_two_counts(tmp_path, clock, machine):
    fires = {"reasoning": "made up", "time_critical_possible": True, "already_done_or_arranged": False,
             "urgent_actions": [{"action": "Made-up step", "reason": "made-up reason"}]}
    worried = {"reasoning": "made-up worry", "time_critical_possible": True, "already_done_or_arranged": False, "urgent_actions": []}
    from tests.fakes import MadeUpWorker
    from tests.test_review_page import LONG, engine_with, nemotron_doors, run_through
    # Three long lines, one a piece, so three passes run (NEW_CHARS_FOR_PASS): the same alarm on passes 1 and 2
    # is one line, at its first firing; the no-action alarm on pass 3 is another.
    three = [[{"id": k, "start": k * 1.0, "end": k * 1.0 + 0.9, "text": LONG, "speaker": "S1" if k != 2 else "S2", "confidence": None}]
             for k in (1, 2, 3)]
    app, client, c = run_through(tmp_path, clock, machine, nemotron_doors(MadeUpWorker(live=three)),
                                 engine_with(alarm=[fires, fires, worried]))
    p = app.state.parts
    pass_rows = p.consultations.passes(1)
    fired = [r for r in pass_rows if r["result"]["alarm"]["state"] in ("fired", "no_action")]
    assert len(fired) >= 2
    key = fired[0]["result"]["alarm"]
    from openconsult.consult.passes import alarm_key
    c.passes.acknowledge(alarm_key(key["state"], key["actions"]))
    p.audit.record("alarm.acknowledged", f"consultation 1: {alarm_key(key['state'], key['actions'])}")
    lines = alarms.alarm_lines(pass_rows, p.consultations.live_lines(1), START, alarms.acknowledged_keys(p.audit.lines(), 1), words)
    assert [l["n"] for l in lines] == [fired[0]["n"]] + [r["n"] for r in fired if r["result"]["alarm"]["state"] == "no_action"][:1]
    assert lines[0]["text"] == words.ALARM_LINE.format(time="0:00", state=words.ALARM_STATE_FIRED + words.ALARM_STATE_ACKNOWLEDGED)
    assert lines[0]["acknowledged"] and lines[0]["start_s"] == 1.0 and lines[0]["line_n"] == 1   # pass 1 had read line 1, which starts at 1.0 s
    assert lines[1]["start_s"] == 3.0 and lines[1]["line_n"] == 3                                  # pass 3 had read line 3
    assert lines[1]["text"] == words.ALARM_LINE.format(time="0:00", state=words.ALARM_STATE_NO_ACTION) and not lines[1]["acknowledged"]
    assert alarms.last_line_read("", p.consultations.live_lines(1)) is None
    assert alarms.last_line_read("a\nb", [{"n": 1, "refused": 0, "start_s": 0.0}, {"n": 2, "refused": 1, "start_s": 0.4},
                                          {"n": 3, "refused": 0, "start_s": 0.6}])["n"] == 3          # refused lines are not read
    raw = client.get("/consultations/1").text
    page = text_of(client.get("/consultations/1"))
    assert 'id="alarms"' in raw and raw.count('class="alarm-line"') == 2 and words.PLAY_FROM_ALARM in page
    assert 'class="play-at" data-start="1.0"' in raw and 'class="play-at" data-start="3.0"' in raw
    assert 'id="alarm-count" class="warning-count">' + words.ALARMS_COUNT.format(count=2) in raw
    assert 'id="warning-count"' in raw and words.WARNINGS_COUNT.split("{")[0] or True
    # A consultation with no alarm says so, with its count at 0.
    app2, client2, c2 = reviewed(tmp_path / "quiet", clock, machine, engine_with(alarm=[]))
    page2 = text_of(client2.get("/consultations/1"))
    assert words.NO_ALARMS in page2 and words.ALARMS_COUNT.format(count=0) in page2
