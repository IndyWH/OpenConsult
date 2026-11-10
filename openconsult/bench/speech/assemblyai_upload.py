"""AssemblyAI, a whole recording sent once (spec 15.9, rulings 9, 16 and
28; the details of 5e). The EU address of its upload service; one model
named alone, so that no second model can answer in silence; the medical
mode on; who spoke on, with the number of speakers given. No word list,
no prompt. The uploaded file is held apart from the transcript and no
call deletes it alone: deleting the transcript deletes it, by the
service's own page, so an upload with no transcript cannot be deleted
and is reported as such. The upload call carries no file name."""

from __future__ import annotations

import json
from urllib.parse import urlsplit

from openconsult import words
from openconsult.bench.speech.upload import Answer, Http, lines_from_words

NAME, ARM, TITLE = "assemblyai", "assemblyai_upload", words.ARM_ASSEMBLYAI_UPLOAD
KEY_NAME = "ASSEMBLYAI_API_KEY"
EU_HOST = "api.eu.assemblyai.com"
BASE = f"https://{EU_HOST}/v2"
# The pre-recorded model the service's own page recommends (read 10 Nov
# 2026); the live choice is another model by the service's names.
MODEL, DOMAIN, LANGUAGE, SPEAKERS = "universal-3-5-pro", "medical-v1", "en", 2


def body_for(upload_url: str) -> dict:
    """The transcript request, word for word. No keyterms_prompt, no prompt,
    no word_boost, no custom_spelling."""
    return {"audio_url": upload_url, "speech_models": [MODEL], "language_code": LANGUAGE, "speaker_labels": True,
            "speakers_expected": SPEAKERS, "domain": DOMAIN}


def stamp() -> dict:
    return {"choice": ARM, "service": NAME, "address": BASE, "model": MODEL,
            "options": {"domain": DOMAIN, "language_code": LANGUAGE, "speaker_labels": True, "speakers_expected": SPEAKERS,
                        "keyterms_prompt": None, "prompt": None}}


def _auth(key: str) -> dict:
    return {"Authorization": key}


def submit(http: Http, key: str, wav: bytes, file_name: str) -> tuple[dict | None, str | None]:
    sent = http.request("POST", f"{BASE}/upload", {**_auth(key), "Content-Type": "application/octet-stream"}, wav)
    upload_url = (sent.json() or {}).get("upload_url")
    if sent.status != 200 or not upload_url:
        return None, f"the file was not taken: HTTP {sent.status}"
    # The host the service names for the file is kept as a state; the bench never opens it.
    job = {"id": None, "upload_url": str(upload_url), "upload_host": urlsplit(str(upload_url)).hostname}
    asked = http.request("POST", f"{BASE}/transcript", {**_auth(key), "Content-Type": "application/json"},
                         json.dumps(body_for(job["upload_url"])).encode("utf-8"))
    body = asked.json() or {}
    if asked.status != 200 or not body.get("id"):
        return job, f"the transcript was not taken: HTTP {asked.status}"
    job["id"] = str(body["id"])
    return job, None


def _get(http: Http, key: str, job: dict) -> Answer:
    return http.request("GET", f"{BASE}/transcript/{job['id']}", _auth(key))


def poll(http: Http, key: str, job: dict) -> tuple[str, str]:
    answer = _get(http, key, job)
    body = answer.json() or {}
    if answer.status != 200:
        return "failed", f"the transcript could not be read: HTTP {answer.status}"
    if body.get("status") in ("queued", "processing"):
        return "waiting", ""
    if body.get("status") == "completed":
        job["completed"] = body          # the completed answer is the reply: it is not asked for twice
        return "done", ""
    return "failed", f"the transcript ended as {body.get('status')}"


def fetch(http: Http, key: str, job: dict) -> tuple[dict | None, str | None]:
    return job.pop("completed", None), None


def counted_s(reply: dict) -> float | None:
    duration = reply.get("audio_duration")
    return None if duration is None else float(duration)


def applied(reply: dict) -> tuple[dict, str | None]:
    model = reply.get("speech_model_used") or reply.get("speech_model")
    found = {"model": model, "domain": reply.get("domain"), "speaker_labels": reply.get("speaker_labels"),
             "warnings": (reply.get("metadata") or {}).get("warnings")}
    if model != MODEL:
        return found, f"the service answered with the model {model}, not {MODEL}"
    if reply.get("domain") != DOMAIN:
        return found, f"the service answered with the domain {reply.get('domain')}, not {DOMAIN}"
    return found, None


def lines_of(reply: dict) -> list[dict]:
    words = [{"text": str(w["text"]), "start": w["start"] / 1000.0, "end": w["end"] / 1000.0, "confidence": w.get("confidence"),
              "speaker": None if w.get("speaker") is None else str(w["speaker"])}
             for w in (reply.get("words") or []) if str(w.get("text", "")).strip()]
    return lines_from_words(words)


def deletable(job: dict) -> bool:
    return bool(job.get("id"))


def delete(http: Http, key: str, job: dict) -> Answer:
    return http.request("DELETE", f"{BASE}/transcript/{job['id']}", _auth(key))


def ask_again(http: Http, key: str, job: dict) -> list[tuple[str, Answer]]:
    return [("the transcript", _get(http, key, job))]


def must_not_hold(job: dict) -> str | None:
    return job.get("upload_url")


def listing(http: Http, key: str) -> Answer:
    """The account's transcripts of the last days, for the count at the end."""
    return http.request("GET", f"{BASE}/transcript?limit=200", _auth(key))
