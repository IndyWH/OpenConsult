"""A made-up engine behind the joint, so the suite needs no Ollama and
no card (spec 15.7). Its replies are made-up JSON; nothing here is what
a model said."""

from __future__ import annotations

import json

from openconsult.llm.engine import Call, EngineStatus, Reply


def reply(text, ended="complete", status=200, error=None, prompt_tokens=50, output_tokens=20,
          wall_ms=5, total_ms=4, load_ms=0, read_ms=1, write_ms=3) -> Reply:
    """A complete reply whose text is the JSON of `text` when it is not a string."""
    content = text if isinstance(text, str) or text is None else json.dumps(text)
    raw = json.dumps({"message": {"content": content}}) if content is not None else error
    return Reply(ended, content, status, error, prompt_tokens, output_tokens, total_ms, load_ms,
                 read_ms, write_ms, wall_ms, "", raw)


ALARM_QUIET = {"reasoning": "made up", "time_critical_possible": False,
               "already_done_or_arranged": False, "urgent_actions": []}
ALARM_FIRES = {"reasoning": "made up", "time_critical_possible": True,
               "already_done_or_arranged": False,
               "urgent_actions": [{"action": "Made-up step", "reason": "made-up reason"}]}
ASSESSMENT = {"reasoning": "made up",
              "differentials": [{"condition": "Made-up condition A", "likelihood": "high",
                                 "rationale": "made up"},
                                {"condition": "Made-up condition B", "likelihood": "low",
                                 "rationale": "made up"}],
              "questions_to_ask": ["A made-up question?"], "signs_to_check": ["a made-up sign"]}


class FakeEngine:
    """Answers from a script, in order. An item is a Reply, an exception
    to raise, or a dict or string that becomes a complete reply. With no
    script it answers every alarm quietly and every assessment with the
    made-up list."""

    name = "made-up"

    def __init__(self, script=None, version="0.0-made-up", digest="made-up-digest", present=True):
        self.script = list(script) if script is not None else None
        self.calls: list[Call] = []
        self._version, self._digest, self._present = version, digest, present

    def chat(self, call: Call) -> Reply:
        self.calls.append(call)
        if self.script is None:
            item = ALARM_QUIET if call.job == "alarm" else ASSESSMENT
        else:
            item = self.script.pop(0)
        if isinstance(item, BaseException):
            raise item
        if isinstance(item, Reply):
            text = item.text
            request = json.dumps({"job": call.job, "user": call.user})
            return Reply(item.ended, text, item.status, item.error, item.prompt_tokens,
                         item.output_tokens, item.total_ms, item.load_ms, item.read_ms,
                         item.write_ms, item.wall_ms, request, item.raw)
        return self.chat_item(call, item)

    def chat_item(self, call: Call, item) -> Reply:
        made = reply(item)
        return Reply(made.ended, made.text, made.status, None, made.prompt_tokens,
                     made.output_tokens, made.total_ms, made.load_ms, made.read_ms,
                     made.write_ms, made.wall_ms, json.dumps({"job": call.job, "user": call.user}),
                     made.raw)

    def version(self, timeout_s: float = 2.0):
        return self._version

    def model_digest(self, tag: str, timeout_s: float = 2.0):
        return self._digest if self._present else None

    def status(self, tag: str, timeout_s: float = 2.0) -> EngineStatus:
        if self._version is None:
            return EngineStatus(False, None, None, None)
        return EngineStatus(True, self._version, self._present, self._digest if self._present else None)
