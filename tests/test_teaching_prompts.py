"""The thirteen files of teaching as the owner approved them (spec 15.14,
rulings 10 to 13 and the details of run 10a; 15.8 rulings 1 and 43), the
loader's reader of the layouts and its fill in one pass. No model, and
nothing a model wrote."""

import hashlib
import re
from pathlib import Path

from openconsult.prompts import loader
from tests.test_prompts import GUIDELINE_WORDS, KNOWN_CAPITALS

JOBS = ("teaching_case", "teaching_patient", "teaching_examination", "teaching_feedback")
# The sha256 of each file's bytes, as rulings 10 to 13 and the details of run 10a give them.
APPROVED = {
    "teaching_case": "9b2f69bf784d5efede474d938b52df05d7b41d62e76df171e1b730a83f2bcbdc",
    "teaching_case.frame": "67b3c7995b61a29c4d4bd877fe42399dd3f8afeab7bcd79a1600323972418173",
    "teaching_case.form": "19dff9f5a29aeeb737675d0843b96e3883a382a600acbea0b91ff29fe754f8b3",
    "teaching_patient": "0da417e11f3f0ec8a64e5e665108232bb44a0a90894afa79e4daec70f2ec6f91",
    "teaching_patient.frame": "d6d9e6123cda044df97358b47e7129c18de43d02ebafabb631fcd2889be4ccc2",
    "teaching_patient.form": "125e7a1d0ac47d9e6d38892e738339ba19de9c5f8ce8b9989dcda345274c87b3",
    "teaching_examination": "f7f55378be26cb7a2140ba9172efeba6825603582763b8e630fe6379184b799d",
    "teaching_examination.frame": "a72b30bb29938f465f9ecc3b8196d588490bd4629c30950b1e5c28831730b837",
    "teaching_examination.form": "f78b0d586b5d13b04bb2f4ca168ce9a7e0eb8f87cf888e5786bdfbe6a58ff609",
    "teaching_feedback": "80a7797520dc7f0dba25caa6860d4eb4c47dc45833cc0de73761f1f065284626",
    "teaching_feedback.frame": "b968304515fe601e996a0b094af61af33f90d25480dc53680b5ef730d0078738",
    "teaching_feedback.form": "4a2aff46f4001194e6e2cdf557fc6f1ff17a11babf0ed02ed46384321b355012",
    "teaching.layout": "cc8051d49d1dcb1c84a171ff68a2db8e72c888a5e40972fc0c9fe24178d4af26",
}


def data_of(name: str) -> bytes:
    if name.endswith(".form"):
        return loader.form_bytes(name[:-len(".form")])
    if name.endswith(".layout"):
        return loader.layout_bytes(name[:-len(".layout")])
    return loader.file_bytes(name) if name.endswith(".frame") else loader.prompt_bytes(name)


def test_15_14_rulings_10_to_13_the_thirteen_files_are_the_approved_bytes():
    assert len(APPROVED) == 13
    for name, digest in APPROVED.items():
        data = data_of(name)
        assert hashlib.sha256(data).hexdigest() == digest == loader.APPROVED_BYTES[name], name
        assert data.endswith(b"\n") and not data.endswith(b"\n\n") and b"\r" not in data, name
        if not name.endswith((".form", ".layout")):
            assert b'"' not in data, name                       # 15.8 ruling 43: no prompt or frame shows the model a double quote
    assert hashlib.sha256(b"one changed letter").hexdigest() not in APPROVED.values()      # the twin
    for job in JOBS:
        assert loader.prompt(job).endswith("Output JSON only.") and loader.form(job)["type"] == "object"


def test_15_14_the_layouts_are_read_as_one_file_and_hold_every_pattern_the_frames_need():
    lay = loader.layout("teaching")
    assert sorted(lay) == ["case", "diagnosis", "diagnosis_must", "empty", "examined", "fact", "finding", "investigation", "point",
                           "points_heading", "result", "said_doctor", "said_patient", "step", "step_referral", "turn_doctor",
                           "turn_patient", "who", "who_parent"]
    assert sorted(lay["points_heading"]) == ["data_gathering", "management", "relating"]
    # Every slot of the four frames and of the case layout is one the module fills: none is left with nothing to fill it.
    slots = {job: set(re.findall(r"\{([a-z_]+)\}", loader.frame(job))) for job in JOBS}
    assert slots["teaching_case"] == {"topic", "level"}
    assert slots["teaching_patient"] == {"patient", "opening_words", "facts", "ideas", "concerns", "expectations", "hidden_agenda",
                                         "conversation", "doctor"}
    assert slots["teaching_examination"] == {"findings", "doctor"}
    assert slots["teaching_feedback"] == {"case", "points", "differential", "investigations", "plan", "turns", "examined",
                                          "answer_differential", "answer_investigations", "answer_plan"}
    assert set(re.findall(r"\{([a-z_]+)\}", lay["case"])) == {"who", "opening_words", "facts", "ideas", "concerns", "expectations",
                                                              "hidden_agenda", "findings", "safety_net"}


def test_12_3_rule_1_a_fill_in_one_pass_never_reads_a_value_again():
    # A learner's typed words go into a frame of many slots: braces in them are never taken for a later slot.
    filled = loader.fill_once("A: {first}\nB: {second}\nC: {third}", first="typed {second} and {third}", second="two", third="{first}")
    assert filled == "A: typed {second} and {third}\nB: two\nC: {first}"
    assert loader.fill_once("{n}. {text} {unknown}", n=3, text="words") == "3. words {unknown}"      # a number is written; a slot not named stays
    assert loader.fill_once("no slot", ) == "no slot"
    # The twin: the older fill, slot after slot, does read the first value again.
    assert loader.fill("A: {first}\nB: {second}", first="typed {second}", second="two") == "A: typed two\nB: two"


def test_R13_R21_the_patterns_of_the_layouts_as_a_model_reads_them():
    """In the file a pattern's line break is the two letters of a JSON escape, which hides the word after it from
    the check on the file's own text; so the patterns are checked again as they are read."""
    lay = loader.layout("teaching")
    patterns = [value for value in lay.values() if isinstance(value, str)] + list(lay["points_heading"].values())
    assert len(patterns) == 21
    countries = [c.strip().lower() for c in (Path(__file__).parent / "countries.txt").read_text(encoding="utf-8").splitlines() if c.strip()]
    seen = set()
    for pattern in patterns:
        assert '"' not in pattern
        assert not any(word in pattern.lower() for word in GUIDELINE_WORDS)
        assert not any(re.search(rf"\b{re.escape(country)}\b", pattern.lower()) for country in countries)
        seen |= set(re.findall(r"\b[A-Z][A-Z]+\b", pattern))
    assert not seen - KNOWN_CAPITALS
    assert {"IDEAS", "CONCERNS", "EXPECTATIONS", "EXAMINATION", "SAFETY"} <= seen      # the five the file's own text hides
