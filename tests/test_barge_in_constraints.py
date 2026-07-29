"""The two standing constraints on the barge-in detector — as TESTS.

Both were recorded in HANDOVER ("Phase 7 opened", item 6) for whoever
built session 3, and both are the kind of rule that erodes when it lives
only in a comment:

1. **The detector stream must NEVER be wired to the mic meter.** The
   meter's invariant is one capture — it runs off the same getUserMedia
   stream the transcriber consumes, so it cannot disagree with what the
   server hears (docket #78 mic-check fabrication; #70 degraded audio).
   The detector's stream is echo-cancelled and processed differently: a
   meter reading it would describe audio the server never receives, which
   is precisely the fabrication shape this project keeps designing
   against. The detector has ONE sink (its own analyser) and one job (a
   boolean).

2. **The approved disclosure must NOT gain an interruption line.** The
   wording deliberately says nothing about interrupting so it stays true
   whether or not barge-in is enabled and stays constant across the face
   study's arms. The original test asserting the absence
   (tests/test_speech.py::test_the_disclosure_says_nothing_about_interrupting)
   stays EXACTLY as written — this file pins its source text so an
   amendment fails loudly here rather than passing quietly there.

These are structural assertions on the shipped page and phrase table, in
the repo's established style (the speaking-bar position tests after 447):
a test asserting only "the code exists" would have passed through every
incident this project has had.
"""

from __future__ import annotations

from pathlib import Path

LIVE = Path("app/static/live.html").read_text()


def _section(start_marker: str, end_marker: str, source: str = LIVE) -> str:
    start = source.index(start_marker)
    return source[start:source.index(end_marker, start)]


# --- constraint 1: the meter never reads the detector stream ----------------

def test_the_level_meter_reads_the_shared_capture_not_the_detector():
    """The meter's sampling loop must touch only the shared analyser —
    the one fed by the stream the transcriber consumes."""
    meter = _section("// Level meter:", "}, 100);")
    assert "analyser.getFloatTimeDomainData" in meter
    assert "barge" not in meter.lower(), (
        "the level meter is reading the barge-in detector's stream — the "
        "red pill would describe audio the server never hears")


def test_the_sound_check_measures_from_the_shared_capture_not_the_detector():
    """Same invariant, other consumer: the sound check's measurement
    function reads the shared analyser (spec 10.3)."""
    current_rms = _section("function currentRms()", "\n}")
    assert "analyser.getFloatTimeDomainData" in current_rms
    assert "barge" not in current_rms.lower()


def test_the_detector_stream_has_exactly_one_sink_its_own_analyser():
    """One boolean, one sink. A second `.connect(` on the detector source
    — the meter, the worklet, the destination, anything — is the
    regression this test exists to catch."""
    assert LIVE.count("bargeSource.connect(") == 1
    assert "bargeSource.connect(bargeAnalyser)" in LIVE


def test_the_shared_analyser_is_never_reassigned_to_the_detector():
    """The subtle route to the same fault: leaving the meter's code alone
    and pointing its analyser at the detector's."""
    for needle in ("analyser = barge", "analyser=barge",
                   "sourceNode = barge", "sourceNode=barge"):
        assert needle not in LIVE, needle


def test_the_detector_stream_never_leaves_the_detector_section():
    """`bargeStream` exists only between the detector's section header and
    the end of its teardown: never transmitted, never recorded, never
    handed to any other consumer on the page."""
    detector = _section(
        "// ==================================== Phase 7a session 3: barge-in detector",
        "function stopSpeaking")
    assert LIVE.count("bargeStream") == detector.count("bargeStream") > 0
    assert "MediaRecorder" not in LIVE, "nothing on this page records audio itself"
    # And the meter's bar elements are nowhere near it.
    assert "barEls" not in detector


# --- constraint 2: the disclosure gains no interruption line ----------------

def test_the_original_disclosure_absence_test_is_unamended():
    """Pins the ORIGINAL test's source verbatim. The instruction for this
    session was that it stays exactly as it is — so a rewording, a
    softening, or a deletion over there fails here, as a named regression
    rather than a tweak."""
    expected = '''def test_the_disclosure_says_nothing_about_interrupting():
    """Deliberate: it must stay true whether or not barge-in is enabled,
    and constant across the face study's arms. Session 3 must not add an
    interruption line."""
    text = speech.PHRASES["disclosure"].lower()
    for word in ("interrupt", "stop me", "cut in", "talk over"):
        assert word not in text
'''
    assert expected in Path("tests/test_speech.py").read_text()


def test_the_phrase_table_does_not_branch_on_the_barge_in_flag():
    """The disclosure stays constant whether or not barge-in is enabled —
    which requires that no phrase is CONSTRUCTED from the flag. The table
    may mention barge-in in its comments (it does, to explain the
    constraint); it may not read BARGE_IN_* to choose words."""
    from app import speech as speech_module
    source = Path("app/speech.py").read_text()
    table = source[source.index("PHRASES: dict[str, str] = {"):
                   source.index("ENCOURAGER_IDS")]
    assert "BARGE_IN" not in table
    # And behaviourally: the rendered disclosure is a fixed sentence.
    assert speech_module.render_phrase("disclosure", "Herath") == (
        "Hello. I'm a computer, not a person. I'll ask you some questions "
        "about what's brought you in. Dr Herath is here with you and you "
        "can speak to them at any time.")
