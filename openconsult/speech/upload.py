"""A whole recording sent once to a cloud speech service (spec 15.9,
rulings 9, 28, 31, 36 and 42; the details of 5e; 15.13, rulings 29 and 33
and the details of run 9b). Read by the app, for the recording sent
after Stop, and by the bench, which measured it first. A whole recording is
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

It is not a speech choice. The app reaches it by two ways and no other
(consult/whole.py): the tick for better accuracy, and the one press
after a lost connection."""

from __future__ import annotations

import datetime as dt
import errno
import json
import re
import socket
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
# After the delete, an ask that brought no answer at all is made once more, this long after, and never a third time
# (15.13, ruling 49: a failed request is not an answer). The second try has a limit of its own, the limit of the test
# of a connection: a design choice, so that the two second tries add at most 2 x (5 + 10) = 30 s to the stage at Stop.
SECOND_ASK_WAIT_S = 5.0
SECOND_ASK_LIMIT_S = 10.0


class AddressRefused(Exception):
    """A URL that is not https to the service's EU host."""


@dataclass
class Answer:
    status: int                # 0 when no answer came
    body: bytes
    error: str | None = None
    never_connected: bool = False   # no answer, and the failure shows that no connection to the service was opened at all

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


def _urllib_send(method: str, url: str, headers: dict, body: bytes | None, timeout_s: float = REQUEST_TIMEOUT_S) -> Answer:
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=timeout_s) as reply:
            return Answer(reply.status, reply.read())
    except urllib.error.HTTPError as refused:
        return Answer(refused.code, refused.read() or b"")
    except (urllib.error.URLError, OSError, TimeoutError) as gone:
        return Answer(0, b"", f"{type(gone).__name__}"[:80], never_connected(gone))


def never_connected(gone: Exception) -> bool:
    """Whether a failure shows that no connection to the service was opened
    at all: its name was not found, the connection was refused, or there
    is no route to it. Then nothing can have left this computer. Anything
    else, a limit of time among them, may have come after the connection
    was open, and shows nothing (15.13, ruling 52)."""
    reason = gone.reason if isinstance(gone, urllib.error.URLError) else gone
    if isinstance(reason, (socket.gaierror, ConnectionRefusedError)):
        return True
    return isinstance(reason, OSError) and reason.errno in (errno.ENETUNREACH, errno.EHOSTUNREACH)


class Http:
    """Every request of one service: https to the EU host and nowhere else."""

    def __init__(self, eu_host: str, send: Callable | None = None):
        self.eu_host = eu_host
        self._send = send or _urllib_send
        self.sent: list[dict] = []     # method, url and status of every request, never a header

    def request(self, method: str, url: str, headers: dict, body: bytes | None = None, timeout_s: float | None = None) -> Answer:
        """timeout_s: a limit of its own for this one request; with none the sender's own stands."""
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.hostname != self.eu_host or parts.port not in (None, 443):
            raise AddressRefused(url)
        answer = self._send(method, url, headers, body) if timeout_s is None else self._send(method, url, headers, body, timeout_s)
        self.sent.append({"method": method, "url": url, "status": answer.status, "bytes_sent": len(body or b""),
                          **({"never_connected": True} if answer.never_connected else {})})
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
              "delete": None, "asked_again": [], "gone": None, "proof": None, "request": NOT_MADE}
    result["upload"] = upload
    started = clock()

    def failed(at: str, detail: str) -> None:
        if result["failure"] is None:
            result["failure"] = {"at": at, "failure": "upload_failed", "detail": detail}

    job, reply, lines = None, None, []
    before = len(http.sent)
    try:
        job, problem = service.submit(http, key, wav, file_name)
        upload["job"] = job
        upload["request"] = request_made(http.sent[before:])
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
        _delete_and_prove(service, http, key, job, lines, upload, sleep)
    result["stop"] = {"t": upload["seconds_to_result"], "t_asked": 0.0, "lines": lines, "last_live": [], "refused": [],
                      "raw": [], "seconds": {"sent_to_result": upload["seconds_to_result"]}, "revisions": [],
                      "speakers": {}, "notes": {"requests": list(http.sent)}}
    return result


NOT_MADE, NEVER_CONNECTED, MADE = "not_made", "never_connected", "made"


def request_made(sent: list[dict]) -> str:
    """What the record can show of the request that carries the recording,
    the first of a sending (15.13, ruling 52): never made; made, with no
    connection to the service ever opened, so that nothing left this
    computer; or made, with any answer of the service, a refusal too, or
    a failure that may have come after the connection was open, so that
    the app cannot show that nothing left."""
    if not sent:
        return NOT_MADE
    return NEVER_CONNECTED if sent[0].get("never_connected") else MADE


def _delete_and_prove(service, http: Http, key: str, job: dict | None, lines: list[dict], upload: dict,
                      sleep: Callable = time.sleep) -> None:
    """The delete, then each ask of the service once; an ask that brought
    no answer at all is made once more, a few seconds later, and never a
    third time (ruling 49). An ask that brought any answer is never made
    again. The last answer of each ask is judged by the rule above
    (ruling 44), and every try is kept, in order."""
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
    proofs, judged = [], {}

    def judge(what: str, answer: Answer, second: bool) -> None:
        ok, why = proves_gone(answer, result_words, service.must_not_hold(job), service.lines_of)
        upload["asked_again"].append({"what": what, **answer.kept(), "gone": ok, "why": why, **({"try": 2} if second else {})})
        proofs.append(f"{what}, asked again after {SECOND_ASK_WAIT_S:.0f} s: {why}" if second else f"{what}: {why}")
        judged[what] = ok

    silent = []
    for what, answer in service.ask_again(http, key, job):
        judge(what, answer, False)
        if answer.status == 0:
            silent.append(what)
    if silent:
        sleep(SECOND_ASK_WAIT_S)
        for what in silent:
            for again, answer in service.ask_again(http, key, job, only=what, timeout_s=SECOND_ASK_LIMIT_S):
                judge(again, answer, True)
    upload["gone"], upload["proof"] = all(judged.values()), "; ".join(proofs)


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
