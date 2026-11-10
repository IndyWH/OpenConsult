"""The pass at Stop of a cloud speech service, as an arm of the bench alone
(spec 15.9, rulings 9, 28 and 31; the details of 5e). A whole recording is
sent once to the service's own upload service at its EU address; the reply
is kept as it came and as the lines of a page at Stop; then the job is
deleted at the service and asked for once more, and the answer that it is
gone is kept beside the result. A delete that fails or is not proven is
never passed over: the result says so and the command stops.

The address. Each service's EU host is a named constant, and send refuses,
before any connection is opened, a URL that is not https to exactly that
host. No redirect is followed. The certificate is checked by Python's own
default; nothing here can switch that off.

The key comes from the key folder by the one module that reads keys, goes
into the one header, and is in no result, no log line and no reason.

The app cannot reach this: it is not a speech choice, and nothing outside
the bench imports it."""

from __future__ import annotations

import datetime as dt
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlsplit

from openconsult.speech.loudness import QUIET_DBFS, WINDOW_S, Loudness

POLL_S = 3.0
RESULT_TIMEOUT_S = 1800.0      # a whole recording; the gate's clip is given GATE_TIMEOUT_S
GATE_TIMEOUT_S = 600.0
REQUEST_TIMEOUT_S = 300.0
GONE_STATUSES = (404, 410)
WORDS_IN_A_ROW = 3             # an answer after the delete may hold no three words in a row of the result
BODY_KEPT = 4000               # of an answer that is not JSON, this much is kept


class AddressRefused(Exception):
    """A URL that is not https to the service's EU host."""


@dataclass
class Answer:
    status: int                # 0 when no answer came
    body: bytes
    error: str | None = None

    def json(self):
        try:
            return json.loads(self.body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None

    def kept(self):
        """The answer as the result file keeps it: whole when it is JSON."""
        parsed = self.json()
        return {"status": self.status, "error": self.error,
                "body": parsed if parsed is not None else self.body[:BODY_KEPT].decode("utf-8", "replace")}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None            # a redirect is an answer, never a second connection


def _urllib_send(method: str, url: str, headers: dict, body: bytes | None) -> Answer:
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=REQUEST_TIMEOUT_S) as reply:
            return Answer(reply.status, reply.read())
    except urllib.error.HTTPError as refused:
        return Answer(refused.code, refused.read() or b"")
    except (urllib.error.URLError, OSError, TimeoutError) as gone:
        return Answer(0, b"", f"{type(gone).__name__}"[:80])


class Http:
    """Every request of one service: https to the EU host and nowhere else."""

    def __init__(self, eu_host: str, send: Callable | None = None):
        self.eu_host = eu_host
        self._send = send or _urllib_send
        self.sent: list[dict] = []     # method, url and status of every request, never a header

    def request(self, method: str, url: str, headers: dict, body: bytes | None = None) -> Answer:
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.hostname != self.eu_host or parts.port not in (None, 443):
            raise AddressRefused(url)
        answer = self._send(method, url, headers, body)
        self.sent.append({"method": method, "url": url, "status": answer.status, "bytes_sent": len(body or b"")})
        return answer


# ------------------------------------------------------- proven gone

def words_of(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def _texts(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _texts(item)]
    if isinstance(value, list):
        return [text for item in value for text in _texts(item)]
    return []


def holds_words_of(answer: Answer, result_words: list[str], read: Callable | None = None, n: int = WORDS_IN_A_ROW) -> bool:
    """Whether the answer holds n words in a row of the result: in any one
    of its fields, or when it is read as the service's own result is read
    (a service may give each word a field of its own). An answer that is
    not JSON is read as one text."""
    runs = {tuple(result_words[i:i + n]) for i in range(len(result_words) - n + 1)}
    parsed = answer.json()
    texts = _texts(parsed) if parsed is not None else [answer.body.decode("utf-8", "replace")]
    if read is not None and isinstance(parsed, dict):
        try:
            texts.append(" ".join(str(item["text"]) for item in read(parsed)))
        except (KeyError, TypeError, ValueError, AttributeError):
            pass                   # not the shape of a result: its fields were read above
    for text in texts:
        found = words_of(text)
        if any(tuple(found[i:i + n]) in runs for i in range(len(found) - n + 1)):
            return True
    return False


def proves_gone(answer: Answer, result_words: list[str], must_not_hold: str | None = None,
                read: Callable | None = None) -> tuple[bool, str]:
    """The rule: a 404 or a 410 proves it; so does an answer of 200 that
    holds no three words in a row of the result, and that does not hold
    the address of the uploaded file. Anything else proves nothing."""
    if answer.status in GONE_STATUSES:
        return True, f"HTTP {answer.status}"
    if answer.status != 200:
        return False, f"HTTP {answer.status}: neither gone nor an answer to read" if answer.status else "no answer came"
    if holds_words_of(answer, result_words, read):
        return False, "the answer still holds words of the result"
    if must_not_hold and must_not_hold in answer.body.decode("utf-8", "replace"):
        return False, "the answer still holds the address of the uploaded file"
    return True, "HTTP 200 with no words of the result"


# ------------------------------------------------------------ one upload

def loudness_of(pcm: bytes, rate: int) -> dict:
    import math
    measured = Loudness(rate)
    measured.add(pcm)
    return {"window_s": WINDOW_S, "dbfs": [None if w == -math.inf else round(w, 1) for w in measured.windows]}


def run_upload(service, http: Http, key: str, wav: bytes, file_name: str, described: dict, pcm: bytes, rate: int,
               clock: Callable = time.monotonic, sleep: Callable = time.sleep, now: Callable = dt.datetime.now,
               timeout_s: float = RESULT_TIMEOUT_S) -> dict:
    """One file sent whole, the result read, the job deleted and asked for
    again. The result is in the form of a replay's, so every count of the
    bench can be made on its page: no live pieces, and the lines at Stop.
    Whatever happened after a job exists at the service, the delete is
    still sent and proven."""
    result = {"arm": service.ARM, **described, "rate": rate, "piece_s": None, "window_s": WINDOW_S,
              "quiet_dbfs": QUIET_DBFS, "time_slack_s": 0.0, "started_at": now().isoformat(timespec="seconds"),
              "stamp": service.stamp(), "pieces": [], "stop": None, "loudness": loudness_of(pcm, rate), "failure": None}
    upload = {"service": service.NAME, "address": service.BASE, "file_name": file_name, "bytes": len(wav),
              "job": None, "reply": None, "counted_s": None, "seconds_to_result": None, "applied": None,
              "delete": None, "asked_again": [], "gone": None, "proof": None}
    result["upload"] = upload
    started = clock()

    def failed(at: str, detail: str) -> None:
        if result["failure"] is None:
            result["failure"] = {"at": at, "failure": "upload_failed", "detail": detail}

    job, reply, lines = None, None, []
    try:
        job, problem = service.submit(http, key, wav, file_name)
        upload["job"] = job
        if problem:
            failed("send", problem)
        else:
            while True:
                state, detail = service.poll(http, key, job)
                if state != "waiting":
                    break
                if clock() - started > timeout_s:
                    state, detail = "failed", f"no result within {timeout_s:.0f} s"
                    break
                sleep(POLL_S)
            if state == "failed":
                failed("result", detail)
            else:
                reply, problem = service.fetch(http, key, job)
                upload["seconds_to_result"] = round(clock() - started, 3)
                if problem:
                    failed("result", problem)
                else:
                    upload["reply"] = reply
                    upload["counted_s"] = service.counted_s(reply)
                    upload["applied"], problem = service.applied(reply, job)
                    lines = service.lines_of(reply)
                    if problem:
                        failed("model", problem)
    finally:
        _delete_and_prove(service, http, key, job, lines, upload)
    result["stop"] = {"t": upload["seconds_to_result"], "t_asked": 0.0, "lines": lines, "last_live": [], "refused": [],
                      "raw": [], "seconds": {"sent_to_result": upload["seconds_to_result"]}, "revisions": [],
                      "speakers": {}, "notes": {"requests": list(http.sent)}}
    return result


def _delete_and_prove(service, http: Http, key: str, job: dict | None, lines: list[dict], upload: dict) -> None:
    if not job:
        upload["gone"], upload["proof"] = True, "nothing was taken by the service"
        return
    if not service.deletable(job):
        upload["gone"], upload["proof"] = False, "the service holds an uploaded file and gives no call that deletes it alone"
        return
    result_words = words_of(" ".join(line["text"] for line in lines))
    deleted = service.delete(http, key, job)
    upload["delete"] = deleted.kept()
    if deleted.status not in (200, 204, *GONE_STATUSES):
        upload["gone"], upload["proof"] = False, f"the delete was answered HTTP {deleted.status}" if deleted.status else "the delete got no answer"
        return
    proofs, gone = [], True
    for what, answer in service.ask_again(http, key, job):
        ok, why = proves_gone(answer, result_words, service.must_not_hold(job), service.lines_of)
        upload["asked_again"].append({"what": what, **answer.kept(), "gone": ok, "why": why})
        proofs.append(f"{what}: {why}")
        gone = gone and ok
    upload["gone"], upload["proof"] = gone, "; ".join(proofs)


def line(words: list[dict], speaker: str | None) -> dict:
    """One line of a page from its words: {text, start, end, confidence}."""
    scored = [w["confidence"] for w in words if w.get("confidence") is not None]
    return {"speaker": speaker, "start": round(float(words[0]["start"]), 3), "end": round(float(words[-1]["end"]), 3),
            "text": " ".join(w["text"] for w in words),
            "confidence": round(sum(scored) / len(scored), 4) if scored else None, "id": None}


def lines_from_words(words: list[dict]) -> list[dict]:
    """Lines by speaker and sentence: a line ends where the speaker changes
    or a word ends a sentence. No word is changed, added or lost."""
    lines, current = [], []
    for word in words:
        if current and word["speaker"] != current[-1]["speaker"]:
            lines.append(line(current, current[-1]["speaker"]))
            current = []
        current.append(word)
        if word["text"].rstrip().endswith((".", "?", "!")):
            lines.append(line(current, current[-1]["speaker"]))
            current = []
    if current:
        lines.append(line(current, current[-1]["speaker"]))
    return lines
