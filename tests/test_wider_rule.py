"""The rule against words from silence looks as wide as a choice's times
allow (spec 15.9, ruling 12; 11.5 rule 5), and at Stop nothing is still
to come. Made sound, made-up lines; nothing here hears a model."""

import math

from openconsult.speech.choices import (ASSEMBLYAI, EXACT_TIMES_S, NEMOTRON, NEMOTRON_TIME_SLACK_S, SPEECHMATICS,
                                        WHISPERX_PYANNOTE)
from openconsult.speech.door import Door
from openconsult.speech.lines import Line
from openconsult.speech.loudness import Loudness, refuse_quiet
from tests.fakes import MadeUpWorker
from tests.test_loudness import silence, sine

RATE = 16000


def loudness_of(*pieces):
    loud = Loudness(RATE)
    for piece in pieces:
        loud.add(piece)
    return loud


def test_ruling_12_the_rule_looks_as_wide_as_the_choices_times_allow():
    # Speech from 1.0 to 1.5 s, quiet before and after, 5.0 s fed in all.
    loud = loudness_of(silence(1.0), sine(0.5, -20.0), silence(3.5))
    beside = Line(None, 2.0, 2.3, "No", None)                   # 0.5 s after the speech ended
    assert refuse_quiet([beside], loud, slack_s=EXACT_TIMES_S)[1][0].line == beside     # exact times: refused
    assert refuse_quiet([beside], loud, slack_s=NEMOTRON_TIME_SLACK_S) == ([beside], [])  # 1.0 to 3.3 s holds speech: kept
    deep = Line(None, 3.5, 3.8, "No", None)                     # 2.5 to 4.8 s is all quiet
    accepted, refused = refuse_quiet([deep], loud, slack_s=NEMOTRON_TIME_SLACK_S)
    assert accepted == [] and refused[0].line == deep and refused[0].loudest_dbfs == -math.inf


def test_ruling_12_sound_not_yet_fed_counts_as_not_quiet_while_more_is_to_come():
    loud = loudness_of(silence(3.0))
    late = Line(None, 2.5, 2.8, "No", None)
    assert refuse_quiet([late], loud, slack_s=NEMOTRON_TIME_SLACK_S) == ([late], [])    # 1.5 to 3.8 s reaches past 3.0
    assert refuse_quiet([late], loud, slack_s=EXACT_TIMES_S)[0] == []                   # ends inside the sound: refused
    assert loud.reaches_past(3.0) is False and loud.reaches_past(3.05) is True
    loud.add(silence(0.05))                                                             # a piece in hand counts as a window
    assert loud.reaches_past(3.05) is False and loud.reaches_past(3.2) is True


def test_ruling_12_at_stop_nothing_is_still_to_come_so_a_quiet_last_line_is_refused():
    # Speech to 1.0 s, then quiet to 3.0 s. The same line in the last
    # second: kept while sound is still being fed, refused at Stop.
    loud = loudness_of(sine(1.0, -20.0), silence(2.0))
    last = Line(None, 2.5, 2.9, "Thank you.", None)
    assert refuse_quiet([last], loud, slack_s=NEMOTRON_TIME_SLACK_S, more_to_come=True) == ([last], [])
    accepted, refused = refuse_quiet([last], loud, slack_s=NEMOTRON_TIME_SLACK_S, more_to_come=False)
    assert accepted == [] and refused[0].line == last
    # Through the door, on the Nemotron choice: the feed keeps it, Stop refuses it.
    segment = {"id": 1, "start": 2.5, "end": 2.9, "text": "Thank you.", "speaker": "S1", "confidence": None}
    worker = MadeUpWorker(live=[[]] * 11 + [[segment]],
                          final={"last_live": [{**segment, "id": 2}], "seconds": {}})
    door = Door(NEMOTRON, make_worker=lambda: worker, installed=lambda: True)
    door.open(RATE, speakers=1)
    for piece in [sine(0.25, -20.0)] * 4 + [silence(0.25)] * 7:
        door.feed(piece)
    fed = door.feed(silence(0.25))
    assert [line.text for line in fed.lines] == ["Thank you."] and fed.refused == ()
    final = door.stop(speakers=1)
    assert final.last_live == () and [r.line.id for r in final.refused] == [2]
    assert [line.id for line in final.lines] == [1]                   # the line kept live stands


def test_ruling_12_the_text_not_yet_final_is_judged_as_wide():
    pending = [{"start": 0.0, "end": 0.5, "text": "no"}]
    for choice, shown in ((NEMOTRON, "no"), (SPEECHMATICS, "")):
        worker = MadeUpWorker(pending=[[], [], [], pending])
        door = Door(choice, make_worker=lambda w=worker: w, installed=lambda: True)
        door.open(RATE, speakers=1)
        for _ in range(3):
            door.feed(silence(0.25))
        assert door.feed(silence(0.25)).partial == shown       # 0 to 1.5 s reaches past the 1.0 s fed for Nemotron


def test_11_5_rule_5_each_choice_declares_how_exact_its_times_are():
    assert (NEMOTRON_TIME_SLACK_S, EXACT_TIMES_S) == (1.0, 0.0)
    assert NEMOTRON.declares.time_slack_s == NEMOTRON_TIME_SLACK_S
    for choice in (WHISPERX_PYANNOTE, SPEECHMATICS, ASSEMBLYAI):
        assert choice.declares.time_slack_s == EXACT_TIMES_S


def test_5b_finding_the_first_word_of_the_clip_reaches_the_page_with_the_wider_rule():
    # 5b: Nemotron timed "And" at 0.08 to 0.16 s, in the clip's quiet
    # opening, and the rule refused a real word. Speech starts at 0.24 s.
    loud = loudness_of(silence(0.24), sine(2.76, -20.0))
    first = Line("S1", 0.08, 0.16, "And", None, 1)
    assert refuse_quiet([first], loud, slack_s=WHISPERX_PYANNOTE.declares.time_slack_s)[0] == []
    assert refuse_quiet([first], loud, slack_s=NEMOTRON.declares.time_slack_s) == ([first], [])
    assert refuse_quiet([first], loud, slack_s=NEMOTRON.declares.time_slack_s, more_to_come=False) == ([first], [])
