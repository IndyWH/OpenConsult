"""A made-up engine behind the joint, so the suite needs no Ollama and
no card (spec 15.7). Its replies are made-up JSON; nothing here is what
a model said."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from openconsult.bench.llamacpp import LlamaCppEngine
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
        self.status_calls = 0
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
        self.status_calls += 1
        if self._version is None:
            return EngineStatus(False, None, None, None)
        return EngineStatus(True, self._version, self._present, self._digest if self._present else None)


# ------------------------------------- a made-up server for the bench's engines

CALL = Call(job="alarm", tag="made-up/model", system="SYSTEM WORDS", user="user words",
            form={"type": "object", "required": ["ok"]}, temperature=0.5, seed=7, context=16384,
            max_tokens=1000, think=False, timeout_s=5.0)
REVISION = "0123456789abcdef0123456789abcdef01234567"


class MadeUpServer:
    """A loopback server that answers each path from a table and keeps
    what it was sent. An answer is (status, body) or a function of the
    request's body that gives one."""

    def __init__(self):
        self.routes, self.received = {}, []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def _answer(self, body):
                outer.received.append((self.path, body))
                found = outer.routes.get(self.path, (404, {"error": "made-up: no such path"}))
                status, reply = found(body) if callable(found) else found
                data = (reply if isinstance(reply, str) else json.dumps(reply)).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                self._answer(None)

            def do_POST(self):
                self._answer(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))

            def log_message(self, *args):
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.address = f"http://127.0.0.1:{self._server.server_address[1]}"
        self._thread = threading.Thread(target=self._server.serve_forever, args=(0.01,), daemon=True)
        self._thread.start()

    def chats(self):
        return [body for path, body in self.received if path == "/v1/chat/completions"]

    def stop(self):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()


def chat_reply(content, finish="stop", **extra):
    return 200, {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": finish}],
                 "usage": {"prompt_tokens": 50, "completion_tokens": 20}, **extra}


def describe(server, engine_class, context=16384, model_path="/made-up/model.gguf", root=f"/made-up/snapshots/{REVISION}"):
    """What each engine's own pages give for the context, the version and the model."""
    if engine_class is LlamaCppEngine:
        server.routes["/props"] = (200, {"default_generation_settings": {"n_ctx": context},
                                         "build_info": "b1-made-up", "model_path": model_path})
    else:
        server.routes["/version"] = (200, {"version": "0.0-made-up"})
        server.routes["/v1/models"] = (200, {"data": [{"id": "another/model", "root": "/elsewhere", "max_model_len": 1},
                                                       {"id": CALL.tag, "root": root, "max_model_len": context}]})


def answer_by_job(body):
    """A chat reply that fits the form of whichever job asked."""
    job = body["response_format"]["json_schema"]["name"]
    return chat_reply(json.dumps(ALARM_QUIET if job == "alarm" else ASSESSMENT))


# ------------------------------------- a made-up speech worker behind the door

class MadeUpWorker:
    """Stands where the real worker process stands, in this process. It
    keeps every request it was given, answers from what the test set, and
    can die on the Nth request. Nothing here hears any sound."""

    def __init__(self, live=None, final=None, pending=None, die_after=None, ready=True,
                 rate_only=None, info=None, revisions=None):
        self.live = list(live or [])          # segment lists, one per audio request
        self.pending = list(pending or [])
        self.revisions = list(revisions or [])   # revision lists, one per audio request
        self.final = final or {"last_live": [], "segments": [], "seconds": {"load": 1.0, "stop": 2.0}}
        self.die_after = die_after
        self.ready_ok = ready
        self.rate_only = rate_only
        self.info = {}
        self._info = info or {"type": "ready", "models": {"made-up": {"revision": "r0"}},
                              "versions": {"made-up": "0.0"}}
        self.requests: list[tuple[dict, bytes]] = []
        self.starts = 0
        self.state, self.kind, self.reason = "stopped", None, None

    def start(self):
        self.starts += 1
        self.state = "starting"

    def wait_ready(self, timeout_s=None):
        if not self.ready_ok:
            self.state, self.kind, self.reason = "failed", "died", "made-up: could not load"
            return False
        self.state, self.info = "ready", self._info
        return True

    def stop(self):
        self.state = "stopped"

    def request(self, header, payload=b"", timeout_s=None):
        from openconsult.speech.worker import WorkerGone
        self.requests.append((header, payload))
        if self.state != "ready":
            raise WorkerGone(self.kind or "died", self.reason or "made-up: not ready")
        if self.die_after is not None and len(self.requests) >= self.die_after:
            self.state, self.kind, self.reason = "failed", "died", "made-up: died with exit code 3"
            raise WorkerGone(self.kind, self.reason)
        kind = header["type"]
        if kind == "open":
            if self.rate_only and header["rate"] != self.rate_only:
                return {"type": "error", "fatal": False, "reason": "rate_not_supported",
                        "message": f"made-up: takes {self.rate_only} only"}
            return {"type": "opened", "session": header["session"]}
        if kind == "audio":
            return {"type": "lines", "session": header["session"],
                    "segments": self.live.pop(0) if self.live else [],
                    "pending": self.pending.pop(0) if self.pending else [],
                    "revisions": self.revisions.pop(0) if self.revisions else []}
        if kind == "stop":
            return {"type": "stopped", "session": header["session"], **self.final}
        return {"type": "error", "fatal": False, "message": f"made-up: unknown {kind!r}"}

    def requested(self, kind):
        return [(h, p) for h, p in self.requests if h["type"] == kind]
