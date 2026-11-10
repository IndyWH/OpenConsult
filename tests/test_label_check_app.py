"""The label check of 5e, sent as the app sends it today, and the bench's
own beside it (spec 15.9, the details of 5e: Who spoke; 15.10 ruling 7;
ruling 17). Made-up pages and a made-up engine: what a model says is
never asserted."""

import dataclasses

from openconsult.bench.speech import calls, jobs, model_lines
from openconsult.consult import labels
from openconsult.llm import jobs as app_jobs
from openconsult.llm.door import Door
from openconsult.llm.profile import GEMMA_4_QAT
from openconsult.prompts import loader
from tests.fakes import FakeEngine

# A choice that gives pieces of one or two words (as one service does), and a page at Stop of raw segments.
STOP_LINES = [{"start": 0.1 * i, "end": 0.1 * i + 0.08, "text": word, "speaker": "S1" if i < 4 else "S2"}
              for i, word in enumerate("Where is the pain? In my back.".split())]
RESULT = {"stop": {"lines": STOP_LINES, "raw": []}}


class CuttingEngine(FakeEngine):
    """Answers a label check with every line labelled, or says it ran to
    its limit of length, as an engine does on a page that is too long."""

    def __init__(self, cut: bool):
        super().__init__(script=[])
        self.cut = cut

    def chat(self, call):
        self.calls.append(call)
        if self.cut:
            made = self.chat_item(call, {"lines": []})
            return dataclasses.replace(made, ended="cut", text='{"lines": [{"line": 1, "label": "doc', output_tokens=call.max_tokens)
        count = call.user.count("\n[") + call.user.startswith("[")
        return self.chat_item(call, {"lines": [{"line": n, "label": "doctor"} for n in range(1, count + 1)]})


def test_15_10_ruling_7_the_label_check_is_sent_as_the_apps_own_function_writes_the_lines_at_stop():
    prepared = calls.prepare("label_check_app", RESULT, reference=None)
    rows = prepared["lines"]
    # Each line the choice gave is one row, numbered from 1 in order: nothing joined, nothing split.
    assert [row["n"] for row in rows] == list(range(1, 8)) and [row["text"] for row in rows] == [l["text"] for l in STOP_LINES]
    # The text is the app's own: its function, its frame file.
    assert prepared["user"] == labels.lines_text(rows)
    assert prepared["user"] == loader.fill(loader.frame("label_check"), transcript="\n".join(f"[{r['n']}] {r['text']}" for r in rows))
    # The bench's own reading joins the same page into the lines of part two: two lines, not seven.
    own = model_lines.lines_of(STOP_LINES)
    assert [line["text"] for line in own] == ["Where is the pain?", "In my back."]
    # Around the lines, both readings send the same words: the heading of the app's frame.
    assert model_lines.lines_text(own).split("\n")[0] == prepared["user"].split("\n")[0] == "TRANSCRIPT:"
    # The same prompt file and the same limits as the app's own job, for both readings.
    job = jobs.JOBS["label_check"]
    assert (job.max_tokens, job.timeout_s) == (app_jobs.JOBS["label_check"].max_tokens, app_jobs.JOBS["label_check"].timeout_s)
    assert jobs.prompt_text("label_check") == loader.prompt("label_check") and jobs.FOLDER_OF["label_check"] == loader.FOLDER
    assert calls.JOB_KINDS[:2] == ("label_check_app", "label_check")


def test_5e_a_page_the_apps_limits_cannot_take_is_kept_as_failed_and_nothing_is_worked_round(tmp_path):
    from openconsult.db import open_database
    from openconsult.llm.record import ModelCalls
    database = open_database(tmp_path / "calls.db")
    try:
        prepared = calls.prepare("label_check_app", RESULT, reference=None)
        cut = Door(CuttingEngine(cut=True), ModelCalls(database), GEMMA_4_QAT)
        record = calls.one_call(cut, "label_check_app", prepared)
        # A reply cut at its limit is a failed call: no label is taken, and nothing is asked a second time.
        assert record["call"]["ok"] is False and record["labels"] is None and record["refusal"] is None
        assert len(cut._engine.calls) == 1 and cut._engine.calls[0].max_tokens == 3000
        assert cut._engine.calls[0].user == prepared["user"]                      # sent whole, as it stood
        whole = Door(CuttingEngine(cut=False), ModelCalls(database), GEMMA_4_QAT)
        record = calls.one_call(whole, "label_check_app", prepared)
        assert record["call"]["ok"] and record["labels"] == {str(n): "doctor" for n in range(1, 8)}
    finally:
        database.close()


def test_5e_eight_kinds_of_page_whisperx_with_v1s_line_has_a_page_at_stop_of_its_own():
    stored = {("whisperx_v1_line", "one"): {"failure": None}, ("whisperx_pyannote", "one"): {"failure": None},
              ("speechmatics_upload", "one"): {"failure": None}, ("nemotron", "one"): {"failure": {"at": "feed"}}}
    assert [arm for arm, _, _ in calls.pages_for_calls(stored, None, None)] == ["speechmatics_upload", "whisperx_pyannote",
                                                                               "whisperx_v1_line"]
