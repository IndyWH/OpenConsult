"""The AssemblyAI worker (spec 15.9, rulings 5, 9 and 10; the details of
5b): live text with speaker labels through the service's EU address, the
medical mode on, no word list. Run by the app on its own Python as a
process of its own, on the cloud frame. It never imports the app.

The address is a named constant, and main dials it and nothing else: no
argument and no environment value can change it. The options are fixed
in code and travel as the connection's query parameters: the model is
named, so a change of the service's default can never change it in
silence; the number of speakers given at open is sent as max_speakers,
as given, with no headroom. The service echoes what it applied in its
Begin message, and a session whose echo differs from what was asked is
refused, so an ignored option can never pass in silence. The model
formats its text itself (punctuation and capitals), so format_turns is
not sent. The key comes from this process's environment under
ASSEMBLYAI_API_KEY and goes into the handshake header only.

A Turn with end_of_turn becomes one line (id = turn_order) with the
words' times and the mean of their confidence; A, B and so on are the
speakers; PENDING (a turn too short to judge) and UNKNOWN are no speaker
(ruling 4). A Turn not yet ended is the text not yet final. A
SpeakerRevision gives revisions of id and label only: its words and
times are never read, so no word and no time can change. Stop sends
Terminate and reads until Termination; the final SpeakerRevision the
service always sends at the end arrives before it.
"""

from __future__ import annotations

import json
import os
import sys
from urllib.parse import urlencode

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "common"))
import cloud  # noqa: E402

SERVICE = "assemblyai"
KEY_NAME = "ASSEMBLYAI_API_KEY"
EU_HOST = "streaming.eu.assemblyai.com"
ADDRESS = f"wss://{EU_HOST}/v3/ws"

MODEL = "universal-3-6-pro"
DOMAIN = "medical-v1"
ENCODING = "pcm_s16le"
LEAST_RATE, MOST_RATE = 8000, 96000      # the service's range for sample_rate
NO_SPEAKER = ("PENDING", "UNKNOWN")

# The service's close codes, as its errors page lists them.
CLOSE_KINDS = {3009: "limit_reached", 1011: "service_down", 3005: "service_down"}
ACCOUNT_WORDS = ("balance", "disabled", "insufficient", "credit")


def headers(key: str) -> dict:
    return {"Authorization": key}


def parameters(rate: int, speakers: int) -> dict:
    """The connection parameters, word for word: the model, the rate and
    encoding, speaker labels, the medical mode, and the number of
    speakers as given. No keyterms_prompt, no prompt, no format_turns."""
    return {"speech_model": MODEL, "sample_rate": int(rate), "encoding": ENCODING,
            "speaker_labels": "true", "domain": DOMAIN, "max_speakers": int(speakers)}


def address_for(rate: int, speakers: int, address: str = ADDRESS) -> str:
    return f"{address}?{urlencode(parameters(rate, speakers))}"


def stamp() -> dict:
    return {"model": MODEL, "options": {"domain": DOMAIN, "speaker_labels": True, "encoding": ENCODING,
                                        "keyterms_prompt": None, "format_turns": None}}


class Session(cloud.Session):
    def __init__(self, ws, rate: int, speakers: int):
        super().__init__(ws, rate, speakers)
        self.begin: dict | None = None

    def start(self) -> None:
        first = json.loads(self.first_reply())
        # The parameters and the first reply hold no key and no spoken word,
        # so the worker's log keeps them: the proof of what was asked and
        # what the service applied.
        print(f"opening sent: {json.dumps(parameters(self.rate, self.speakers))}", file=sys.stderr, flush=True)
        print(f"first reply: {json.dumps(first)}", file=sys.stderr, flush=True)
        if first.get("type") != "Begin":
            raise cloud.Refused("service_down", f"first reply {first.get('type')!r}")
        applied = first.get("configuration") or {}
        asked = {"speech_model": MODEL, "domain": DOMAIN, "speaker_labels": True, "max_speakers": self.speakers}
        got = {"speech_model": applied.get("model", applied.get("speech_model")), "domain": applied.get("domain"),
               "speaker_labels": applied.get("speaker_labels"), "max_speakers": applied.get("max_speakers")}
        if got != asked:
            raise cloud.Refused("worker_error", f"the service applied {got}, not {asked}")
        self.begin = first

    def take(self, message) -> None:
        if isinstance(message, bytes):
            return
        body = json.loads(message)
        kind = body.get("type")
        if kind == "Turn":
            self._turn(body)
        elif kind == "SpeakerRevision":
            for item in body.get("revisions") or []:
                label = item.get("speaker_label")
                self.revisions.append({"id": int(item["turn_order"]), "speaker": _speaker(label)})
        elif body.get("error") is not None:
            raise cloud.Refused(*_error_kind(body.get("error_code"), str(body.get("error"))))

    def end_message(self) -> str:
        return json.dumps({"type": "Terminate"})

    def ended(self, message) -> bool:
        return not isinstance(message, bytes) and json.loads(message).get("type") == "Termination"

    def on_close(self, code: int | None, reason: str) -> tuple[str, str]:
        kind, detail = _error_kind(code, reason)
        return kind, detail

    def _turn(self, body: dict) -> None:
        text = str(body.get("transcript") or "").strip()
        if not body.get("end_of_turn"):
            self.partial = text
            return
        self.partial = ""
        words = body.get("words") or []
        scores = [float(w["confidence"]) for w in words if w.get("confidence") is not None]
        if words:
            start, end = float(words[0]["start"]) / 1000.0, float(words[-1]["end"]) / 1000.0
        else:
            start = end = self.sent_s
        if not text:
            return
        self.segments.append({"id": int(body["turn_order"]), "speaker": _speaker(body.get("speaker_label")),
                              "start": round(start, 3), "end": round(end, 3), "text": text,
                              "confidence": round(sum(scores) / len(scores), 3) if scores else None})


def _speaker(label) -> str | None:
    return None if label is None or str(label) in NO_SPEAKER else str(label)


def _error_kind(code, reason: str) -> tuple[str, str]:
    """The service's close code and reason as the door's name. 1008 is
    the key, unless the reason names the account's balance."""
    text = f"{code}: {reason}"[:200]
    if code == 1008:
        return ("no_credit" if any(w in reason.lower() for w in ACCOUNT_WORDS) else "key_refused"), text
    if code in CLOSE_KINDS:
        return CLOSE_KINDS[code], text
    if code in (3006, 3007, 3008):
        return "worker_error", text
    return "connection_lost", text


def open_session(ws, rate: int, speakers: int) -> Session:
    session = Session(ws, rate, speakers)
    try:
        session.start()
    except cloud.Refused:
        session.close()
        raise
    return session


def dial(key: str, rate: int, speakers: int, address: str = ADDRESS):
    """The one connection of a session, with the parameters in its query;
    a rate the service does not take is refused before any connection."""
    if not LEAST_RATE <= int(rate) <= MOST_RATE:
        raise cloud.Refused("rate_not_supported", f"this choice takes sound from {LEAST_RATE:,} to {MOST_RATE:,} "
                                                  f"samples a second, not {int(rate):,}")
    return cloud.dial(address_for(rate, speakers, address), EU_HOST, headers(key))


def main(dial_with=None, inp=None, out=None, environ=None) -> int:
    """No argument and no environment value names the address: ADDRESS is
    dialled. dial_with, inp, out and environ are for the suite."""
    if dial_with is None:
        dial_with = dial
    return cloud.run(SERVICE, KEY_NAME, ADDRESS, stamp(),
                     lambda key, rate, speakers: open_session(dial_with(key, rate, speakers), rate, speakers),
                     inp, out, environ)


if __name__ == "__main__":
    sys.exit(main())
