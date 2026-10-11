"""The stored results of part two, made up for the suite: the pages of
part one through a made-up voice worker and a made-up language model, so
the commands and the tables can be tested with no card, no model and no
recording. Every reply here is made up."""

from __future__ import annotations

import json
import re
from pathlib import Path

from openconsult.bench.speech import commands2
from openconsult.bench.writer import ResultWriter
from openconsult.db import open_database
from openconsult.llm.door import Door
from openconsult.llm.engine import EngineTimeout
from openconsult.llm.profile import GEMMA_4_QAT
from openconsult.llm.record import ModelCalls
from openconsult.settings import paths
from openconsult.speech import environment
from openconsult.speech.choices import WHISPERX_PYANNOTE
from tests.fakes import FakeEngine
from tests.made_up_drugs import write_list
from tests.made_up_key_facts import write_made_up
from tests.made_up_recordings import entry, made_sound, made_up_recordings, scripts_folder, write_wav
from tests.test_speech_tables import MARKS, results_of

NOTE = {"reasoning": "Made up.", "subjective": [{"text": "No chest pain at rest. Takes metformin.", "turns": [0]}],
        "objective": [{"text": "BP 150/95", "turns": [1]}], "assessment": [],
        "plan": [{"text": "Hospital if pain at rest", "turns": [2]}, {"text": "Review in 2/52", "turns": [9]}]}


class ScriptedEngine(FakeEngine):
    """Answers by the job of the call: the first label check times out, the
    second misses a line, the rest name every line; every note of round two
    has its reasoning cut short (the helper tells the engine the round)."""

    def __init__(self):
        super().__init__(script=[])
        self.by_job: dict[str, int] = {}
        self.round = None

    def chat(self, call):
        self.calls.append(call)
        n = self.by_job[call.job] = self.by_job.get(call.job, 0) + 1
        if call.job == "bench_label_check":
            if n == 1:
                raise EngineTimeout("made-up: no answer")
            lines = len(re.findall(r"^\[\d+\] ", call.user, flags=re.M))
            labels = [{"line": i, "label": "doctor" if i % 2 else "patient"} for i in range(1, lines + 1)]
            return self.chat_item(call, {"lines": labels[:-1] if n == 2 else labels})
        if call.job == "bench_drug_name":
            return self.chat_item(call, {"doubtful": [{"line": 1, "heard": "metformin", "meant": "metformin"},
                                                      {"line": 1, "heard": "zzz", "meant": ""}]})
        note = json.loads(json.dumps(NOTE))
        if self.round == 2:
            note["reasoning"] = "Made up"
        return self.chat_item(call, note)


def build(tmp_path: Path, recordings_kept, monkeypatch, voice_worker, with_calls: bool = True) -> dict:
    monkeypatch.setattr(paths, "default_data_folder", lambda: tmp_path / "owner-data")
    folder = recordings_kept.folder
    minute_sha = write_wav(folder / "minute.wav", made_sound(2.0))
    minute = entry("minute", "minute.wav", minute_sha, speakers=1, length_s=2.0, machine_voices=True, voice_only=True,
                   doctor_voice=None, parts={"DOCTOR": "a machine voice"})
    made_up_recordings(folder, extra=[minute])
    listed = json.loads((folder / "recordings.json").read_text())
    listed["recordings"][0]["doctor_voice"] = "minute"
    (folder / "recordings.json").write_text(json.dumps(listed, indent=1), encoding="utf-8")
    recordings_kept.settle()
    out = tmp_path / "out"
    results_of(folder, out)
    data = tmp_path / "data"
    python = environment.python(data, WHISPERX_PYANNOTE)
    python.parent.mkdir(parents=True)
    python.write_text("")
    scripts = scripts_folder(tmp_path)
    marks = tmp_path / "marks.json"
    marks.write_text(json.dumps(MARKS), encoding="utf-8")
    said: list[str] = []
    assert commands2.speech_voice(out, folder, data, None, None, say=said.append, make_worker=lambda d: voice_worker()) == 0
    engine = ScriptedEngine()
    door = Door(engine, ModelCalls(open_database(out / "calls" / "calls.db")), GEMMA_4_QAT)
    codes = []
    if with_calls:
        for job, round_n in (("label_check", None), ("drug_name", None), ("note", 1), ("script_note", 1), ("note", 2), ("script_note", 2)):
            engine.round = round_n
            codes.append(commands2.speech_calls(out, folder, [scripts], job, round_n, data, say=said.append, make_door=lambda p: door))
    return {"folder": folder, "out": out, "data": data, "scripts": scripts, "marks": marks, "said": said, "engine": engine,
            "codes": codes, "key_facts": write_made_up(tmp_path), "drug_list": write_list(tmp_path), "door": door,
            "results": ResultWriter(out / "calls").read_all()}
