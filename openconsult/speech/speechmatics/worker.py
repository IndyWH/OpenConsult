"""The Speechmatics worker (spec 15.9, rulings 5, 9 and 10; the details of
5b): live text with speaker labels through the service's EU address, the
medical option on, no word list. Run by the app on its own Python as a
process of its own, on the cloud frame. It never imports the app.

The address is a named constant, and main dials it and nothing else: no
argument and no environment value can change it. The options are fixed
in code. The sound is sent at the rate the session gives; the service
takes any rate in Hz. The key comes from this process's environment
under SPEECHMATICS_API_KEY and goes into the handshake header only.

Each AddTranscript message becomes one line per run of speaker label,
with the words' times and the mean of their confidence; S1, S2 and so on
are the speakers, and UU (the service's label for a word whose speaker
it cannot identify) is no speaker (ruling 4). AddPartialTranscript is the
text not yet final. Stop sends EndOfStream and reads until
EndOfTranscript, so the last words arrive.
"""

from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "common"))
import cloud  # noqa: E402

SERVICE = "speechmatics"
KEY_NAME = "SPEECHMATICS_API_KEY"
EU_HOST = "eu.rt.speechmatics.com"
ADDRESS = f"wss://{EU_HOST}/v2"

# Ruling 9: the medical option (the enhanced model with the medical
# domain), speaker labels, and the text not yet final. No additional_vocab.
LANGUAGE = "en"
MODEL = "enhanced"
DOMAIN = "medical"
DIARIZATION = "speaker"
ENCODING = "pcm_s16le"
LEAST_MAX_SPEAKERS = 2        # the service takes max_speakers from 2 up

# The service's error types and close codes, as its reference lists them.
ERROR_KINDS = {"not_authorised": "key_refused", "not_allowed": "no_credit", "timelimit_exceeded": "no_credit",
               "quota_exceeded": "limit_reached", "job_error": "service_down", "unknown_error": "service_down"}
CLOSE_KINDS = {4001: "key_refused", 4003: "no_credit", 4006: "no_credit", 4005: "limit_reached",
               1011: "service_down", 4013: "service_down"}


def headers(key: str) -> dict:
    return {"Authorization": f"Bearer {key}"}


def opening(rate: int, speakers: int) -> dict:
    """The opening message, word for word. The number of speakers goes to
    the service when it can take it (2 or more); with 1 nothing is sent,
    and the stamp says so."""
    config = {"language": LANGUAGE, "model": MODEL, "domain": DOMAIN, "diarization": DIARIZATION,
              "enable_partials": True}
    if speakers >= LEAST_MAX_SPEAKERS:
        config["speaker_diarization_config"] = {"max_speakers": int(speakers)}
    return {"message": "StartRecognition",
            "audio_format": {"type": "raw", "encoding": ENCODING, "sample_rate": int(rate)},
            "transcription_config": config}


def stamp() -> dict:
    return {"model": MODEL, "options": {"language": LANGUAGE, "domain": DOMAIN, "diarization": DIARIZATION,
                                        "enable_partials": True, "additional_vocab": None, "encoding": ENCODING}}


class Session(cloud.Session):
    def __init__(self, ws, rate: int, speakers: int):
        super().__init__(ws, rate, speakers)
        self.next_id = 1
        self.started: dict | None = None

    def start(self) -> None:
        sent = opening(self.rate, self.speakers)
        self.send(json.dumps(sent))
        # The opening message and the replies before the session starts
        # hold no key and no spoken word, so the worker's log keeps them:
        # they are the proof of what was asked and what the service applied.
        print(f"opening sent: {json.dumps(sent)}", file=sys.stderr, flush=True)
        deadline = time.perf_counter() + cloud.FIRST_REPLY_S
        while True:
            # The service may send Info (its usage, its region) or Warning
            # before RecognitionStarted; those are read and kept, not taken
            # for the answer.
            first = json.loads(self.first_reply(max(0.1, deadline - time.perf_counter())))
            print(f"first reply: {json.dumps(first)}", file=sys.stderr, flush=True)
            kind = first.get("message")
            if kind == "Error":
                raise Refused_from_error(first)
            if kind == "RecognitionStarted":
                self.started = first
                return
            if kind not in ("Info", "Warning"):
                raise cloud.Refused("service_down", f"first reply {kind!r}")

    def take(self, message) -> None:
        if isinstance(message, bytes):
            return
        body = json.loads(message)
        kind = body.get("message")
        if kind == "AddTranscript":
            self.segments += self._lines(body)
            self.partial = ""
        elif kind == "AddPartialTranscript":
            self.partial = (body.get("metadata") or {}).get("transcript", "").strip()
        elif kind == "Error":
            raise Refused_from_error(body)

    def end_message(self) -> str:
        return json.dumps({"message": "EndOfStream", "last_seq_no": self.pieces})

    def ended(self, message) -> bool:
        return not isinstance(message, bytes) and json.loads(message).get("message") == "EndOfTranscript"

    def on_close(self, code: int | None, reason: str) -> tuple[str, str]:
        return CLOSE_KINDS.get(code, "connection_lost"), f"{code}: {reason}"[:200]

    def _lines(self, body: dict) -> list:
        """One line per run of speaker label, from the words' times."""
        lines, run = [], None
        for item in body.get("results") or []:
            best = (item.get("alternatives") or [{}])[0]
            content = str(best.get("content") or "")
            if not content:
                continue
            speaker = best.get("speaker")
            speaker = None if speaker in (None, "UU") else str(speaker)
            is_word = item.get("type") != "punctuation"
            if run is None or (is_word and speaker != run["speaker"]):
                run = {"speaker": speaker, "start": float(item["start_time"]), "end": float(item["end_time"]),
                       "words": [], "scores": []}
                lines.append(run)
            run["end"] = max(run["end"], float(item["end_time"]))
            if is_word:
                run["words"].append(content)
                if best.get("confidence") is not None:
                    run["scores"].append(float(best["confidence"]))
            elif run["words"]:
                run["words"][-1] += content
            else:
                run["words"].append(content)
        made = []
        for run in lines:
            made.append({"id": self.next_id, "speaker": run["speaker"], "start": run["start"], "end": run["end"],
                         "text": " ".join(run["words"]),
                         "confidence": round(sum(run["scores"]) / len(run["scores"]), 3) if run["scores"] else None})
            self.next_id += 1
        return made


def Refused_from_error(body: dict) -> cloud.Refused:  # noqa: N802 - reads as what it makes
    kind = ERROR_KINDS.get(body.get("type"), "worker_error")
    return cloud.Refused(kind, f"{body.get('type')}: {body.get('reason')}"[:200])


def open_session(ws, rate: int, speakers: int) -> Session:
    session = Session(ws, rate, speakers)
    try:
        session.start()
    except cloud.Refused:
        session.close()
        raise
    return session


def main(dial=None, inp=None, out=None, environ=None) -> int:
    """No argument and no environment value names the address: ADDRESS is
    dialled. dial, inp, out and environ are for the suite, which gives a
    made-up service and its own streams."""
    if dial is None:
        dial = lambda key: cloud.dial(ADDRESS, EU_HOST, headers(key))  # noqa: E731
    return cloud.run(SERVICE, KEY_NAME, ADDRESS, stamp(),
                     lambda key, rate, speakers: open_session(dial(key), rate, speakers), inp, out, environ)


if __name__ == "__main__":
    sys.exit(main())
