"""No words from silence (spec 15.9 ruling 1; 11.5 rule 1; V1_LESSONS
1.2, 1.6). The sound here is made by code, never taken from a recording."""

import math
import random
import struct

from openconsult.speech.lines import Line
from openconsult.speech.loudness import QUIET_DBFS, Loudness, dbfs, refuse_quiet, rms_of

RATE = 16000


def silence(seconds, rate=RATE) -> bytes:
    return bytes(2 * int(seconds * rate))


def sine(seconds, dbfs_level, rate=RATE, hz=440.0) -> bytes:
    peak = 32767 * math.sqrt(2) * 10 ** (dbfs_level / 20)
    n = int(seconds * rate)
    return struct.pack(f"<{n}h", *(int(round(peak * math.sin(2 * math.pi * hz * i / rate))) for i in range(n)))


def square(seconds, rate=RATE) -> bytes:
    n = int(seconds * rate)
    return struct.pack(f"<{n}h", *(32767 if i % 40 < 20 else -32767 for i in range(n)))


def noise(seconds, dbfs_level, rate=RATE, seed=1) -> bytes:
    rnd = random.Random(seed)
    sigma = 32768 * 10 ** (dbfs_level / 20)
    n = int(seconds * rate)
    return struct.pack(f"<{n}h", *(max(-32768, min(32767, int(rnd.gauss(0, sigma)))) for i in range(n)))


def test_1_6_the_loudness_measure():
    assert dbfs(0.0) == -math.inf and rms_of(__import__("array").array("h")) == 0.0
    loud = Loudness(RATE)
    loud.add(square(0.5))
    assert all(abs(w) < 0.01 for w in loud.windows) and len(loud.windows) == 5
    tone = Loudness(RATE)
    tone.add(sine(1.0, -20.0))
    assert all(abs(w + 20.0) < 0.5 for w in tone.windows)
    quiet = Loudness(RATE)
    quiet.add(silence(1.0))
    assert quiet.windows == [-math.inf] * 10 and quiet.seconds == 1.0


def test_1_6_windows_sit_on_the_session_clock_across_pieces():
    # 250 ms pieces, as the live page sends them: 2.5 windows each, the half carried over.
    loud = Loudness(RATE)
    for piece in (silence(0.25), silence(0.25), sine(0.25, -20.0), sine(0.25, -20.0)):
        loud.add(piece)
    assert len(loud.windows) == 10 and loud.seconds == 1.0
    assert loud.loudest(0.0, 0.5) == -math.inf
    assert abs(loud.loudest(0.6, 1.0) + 20.0) < 0.5
    assert abs(loud.loudest(0.0, 1.0) + 20.0) < 0.5      # the loudest window of the span
    # A span past the full windows sees the piece still in hand; one with no sound is silence.
    loud.add(sine(0.05, -10.0))
    assert abs(loud.loudest(1.0, 1.05) + 10.0) < 1.0
    assert Loudness(RATE).loudest(0.0, 1.0) == -math.inf


def test_change_2_the_measure_takes_the_sessions_rate():
    at_48k = Loudness(48000)
    at_48k.add(sine(0.5, -20.0, rate=48000))
    assert len(at_48k.windows) == 5 and at_48k.seconds == 0.5
    assert all(abs(w + 20.0) < 0.5 for w in at_48k.windows)


def test_ruling_1_no_words_from_silence_and_its_twin():
    quiet = Loudness(RATE)
    quiet.add(silence(3.0))
    lines = [Line(None, 0.0, 1.5, "Thank you.", None), Line(None, 1.5, 3.0, "Thank you.", None)]
    accepted, refused = refuse_quiet(lines, quiet)
    assert accepted == [] and [r.line for r in refused] == lines       # kept, never thrown away (1.2)
    assert all(r.loudest_dbfs == -math.inf and r.threshold_dbfs == QUIET_DBFS for r in refused)
    low = Loudness(RATE)
    low.add(noise(3.0, -50.0))
    assert refuse_quiet(lines, low)[0] == []
    # The twin: the same lines over sound that says somebody spoke are accepted.
    loud = Loudness(RATE)
    loud.add(sine(3.0, -20.0))
    assert refuse_quiet(lines, loud) == (lines, [])
    # A quiet word inside a line of silence is enough: the loudest window decides.
    mixed = Loudness(RATE)
    mixed.add(silence(1.0) + sine(0.2, -30.0) + silence(1.8))
    assert refuse_quiet(lines[:1], mixed) == (lines[:1], [])
