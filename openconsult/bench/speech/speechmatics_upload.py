"""Speechmatics, a whole recording sent once (spec 15.9, rulings 9 and 28;
the details of 5e). The EU address of its upload service; its enhanced
model with the medical domain, the live choice's own names; who spoke on.
Its upload service takes no number of speakers, so none is sent and the
stamp says so. No word list. The file is held with the job, and deleting
the job removes it."""

from __future__ import annotations

import json
import uuid

from openconsult import words
from openconsult.bench.speech.upload import Answer, Http, lines_from_words

NAME, ARM, TITLE = "speechmatics", "speechmatics_upload", words.ARM_SPEECHMATICS_UPLOAD
KEY_NAME = "SPEECHMATICS_API_KEY"
EU_HOST = "eu1.asr.api.speechmatics.com"
BASE = f"https://{EU_HOST}/v2"
LANGUAGE, MODEL, DOMAIN, DIARIZATION = "en", "enhanced", "medical", "speaker"
NO_SPEAKER = ("UU",)


def config() -> dict:
    """The job's settings, word for word. No additional_vocab."""
    return {"type": "transcription",
            "transcription_config": {"language": LANGUAGE, "model": MODEL, "domain": DOMAIN, "diarization": DIARIZATION}}


def stamp() -> dict:
    return {"choice": ARM, "service": NAME, "address": BASE, "model": MODEL,
            "options": {"language": LANGUAGE, "domain": DOMAIN, "diarization": DIARIZATION, "additional_vocab": None,
                        "speakers_given": None}}


def _auth(key: str) -> dict:
    return {"Authorization": f"Bearer {key}"}


def multipart(wav: bytes, file_name: str, boundary: str) -> bytes:
    head = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"config\"\r\n\r\n{json.dumps(config())}\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"data_file\"; filename=\"{file_name}\"\r\n"
            f"Content-Type: audio/wav\r\n\r\n").encode("utf-8")
    return head + wav + f"\r\n--{boundary}--\r\n".encode("utf-8")


def submit(http: Http, key: str, wav: bytes, file_name: str, boundary: str | None = None) -> tuple[dict | None, str | None]:
    boundary = boundary or uuid.uuid4().hex
    answer = http.request("POST", f"{BASE}/jobs", {**_auth(key), "Content-Type": f"multipart/form-data; boundary={boundary}"},
                          multipart(wav, file_name, boundary))
    body = answer.json() or {}
    if answer.status not in (200, 201) or not body.get("id"):
        return None, f"the job was not taken: HTTP {answer.status}"
    return {"id": str(body["id"])}, None


def poll(http: Http, key: str, job: dict) -> tuple[str, str]:
    answer = http.request("GET", f"{BASE}/jobs/{job['id']}", _auth(key))
    status = ((answer.json() or {}).get("job") or {}).get("status")
    if answer.status != 200:
        return "failed", f"the job could not be read: HTTP {answer.status}"
    if status == "running":
        return "waiting", ""
    if status == "done":
        # The job's own record holds the settings the service took; the transcript's metadata repeats only some.
        job["config"] = ((answer.json() or {}).get("job") or {}).get("config")
        return "done", ""
    return "failed", f"the job ended as {status}"


def fetch(http: Http, key: str, job: dict) -> tuple[dict | None, str | None]:
    answer = http.request("GET", f"{BASE}/jobs/{job['id']}/transcript?format=json-v2", _auth(key))
    body = answer.json()
    if answer.status != 200 or not isinstance(body, dict):
        return None, f"the transcript could not be read: HTTP {answer.status}"
    return body, None


def counted_s(reply: dict) -> float | None:
    duration = (reply.get("job") or {}).get("duration")
    return None if duration is None else float(duration)


def applied(reply: dict, job: dict | None = None) -> tuple[dict, str | None]:
    """What the service says it applied, and the reason the result is not
    the arm's when the model or the medical domain differ. The settings
    the service took are in the job's own record. The transcript's
    metadata names the model and, on 10 Nov 2026, no domain: that is kept
    as it came (domain_in_transcript), so the report can say that the
    reply itself does not prove the medical domain."""
    taken = (((job or {}).get("config") or {}).get("transcription_config")) or {}
    used = ((reply.get("metadata") or {}).get("transcription_config")) or {}
    model = used.get("model") or used.get("operating_point")
    found = {"model": model, "domain": taken.get("domain"), "diarization": used.get("diarization"),
             "model_taken": taken.get("model") or taken.get("operating_point"), "domain_in_transcript": used.get("domain"),
             "adapted": ((reply.get("metadata") or {}).get("language_pack_info") or {}).get("adapted")}
    if model != MODEL or found["model_taken"] != MODEL or taken.get("domain") != DOMAIN:
        return found, (f"the service answered with the model {model} and holds the model {found['model_taken']} and the domain "
                       f"{taken.get('domain')}, not {MODEL} and {DOMAIN}")
    return found, None


def lines_of(reply: dict) -> list[dict]:
    words: list[dict] = []
    for item in reply.get("results") or []:
        best = (item.get("alternatives") or [{}])[0]
        content = str(best.get("content", ""))
        if item.get("type") == "punctuation":
            if words and content:
                words[-1]["text"] += content
            continue
        if item.get("type") != "word" or not content:
            continue
        speaker = best.get("speaker")
        words.append({"text": content, "start": item["start_time"], "end": item["end_time"],
                      "confidence": best.get("confidence"), "speaker": None if speaker in (None, *NO_SPEAKER) else str(speaker)})
    return lines_from_words(words)


def deletable(job: dict) -> bool:
    return bool(job.get("id"))


def delete(http: Http, key: str, job: dict) -> Answer:
    return http.request("DELETE", f"{BASE}/jobs/{job['id']}?force=true", _auth(key))


def ask_again(http: Http, key: str, job: dict) -> list[tuple[str, Answer]]:
    return [("the job", http.request("GET", f"{BASE}/jobs/{job['id']}", _auth(key))),
            ("its transcript", http.request("GET", f"{BASE}/jobs/{job['id']}/transcript?format=json-v2", _auth(key)))]


def must_not_hold(job: dict) -> str | None:
    return None


def listing(http: Http, key: str) -> Answer:
    """The account's jobs, deleted ones too, for the count at the end."""
    return http.request("GET", f"{BASE}/jobs?include_deleted=true&limit=100", _auth(key))
