"""Made-up upload services, inside the suite (spec 15.9, the details of 5e:
Tests). Each stands where the real service's upload service stands, as
the function the bench hands every request to: it keeps each request,
answers as the service's pages describe, and can be told to fail a
delete or to keep the words after one. Nothing here opens a connection,
and every word, key and id is made up."""

import json

from openconsult.bench.speech.upload import Answer

MADE_UP_KEY = "made-up-upload-key-0123456789"
WORDS = "the made up page says nine plain words here."


def _json(status: int, body) -> Answer:
    return Answer(status, json.dumps(body).encode("utf-8"))


class MadeUpSpeechmatics:
    """after_delete: gone (404), tombstone (a job at status deleted, the
    transcript 404), words (the transcript still answers), error (500).
    delete_status: what the delete is answered with."""

    def __init__(self, after_delete="gone", delete_status=200, model="enhanced", domain="medical", runs=1):
        self.requests, self.deleted = [], False
        self.after_delete, self.delete_status, self.model, self.domain, self.runs = after_delete, delete_status, model, domain, runs

    def transcript(self) -> dict:
        results, t = [], 1.0
        for index, word in enumerate(WORDS.rstrip(".").split()):
            results.append({"type": "word", "start_time": t, "end_time": t + 0.2,
                            "alternatives": [{"content": word, "confidence": 0.9, "speaker": "S1" if index < 4 else "S2"}]})
            t += 0.3
        results.append({"type": "punctuation", "start_time": t, "end_time": t, "is_eos": True,
                        "alternatives": [{"content": ".", "confidence": 1.0, "speaker": "S2"}]})
        return {"format": "2.9", "job": {"id": "job-1", "data_name": "x", "duration": 7},
                "metadata": {"transcription_config": {"language": "en", "operating_point": self.model, "domain": self.domain,
                                                      "diarization": "speaker"}},
                "results": results}

    def __call__(self, method, url, headers, body):
        self.requests.append({"method": method, "url": url, "headers": dict(headers), "body": body})
        path = url.split("/v2", 1)[1]
        if method == "POST" and path == "/jobs":
            return _json(201, {"id": "job-1"})
        if method == "DELETE":
            if self.delete_status == 200:
                self.deleted = True
            return _json(self.delete_status, {"job": {"id": "job-1", "status": "deleted"}})
        if path.startswith("/jobs?"):
            return _json(200, {"jobs": [{"id": "job-1", "status": "deleted" if self.deleted else "done", "data_name": "x"}]})
        if self.deleted and self.after_delete == "error":
            return _json(500, {"error": "made up"})
        if path == "/jobs/job-1":
            if self.deleted:
                return _json(404, {"code": 404}) if self.after_delete == "gone" else \
                    _json(200, {"job": {"id": "job-1", "status": "deleted", "data_name": "x", "duration": 7}})
            self.runs -= 1
            return _json(200, {"job": {"id": "job-1", "status": "running" if self.runs >= 0 else "done"}})
        if path.startswith("/jobs/job-1/transcript"):
            if self.deleted and self.after_delete != "words":
                return _json(404, {"code": 404})
            return _json(200, self.transcript())
        return _json(400, {"error": "made up: no such call"})


class MadeUpAssemblyAI:
    """after_delete: replaced (the text fields hold the service's word for
    deleted), empty (the fields are empty), gone (404), words (the text is
    still there), url (the words are gone but the upload's address stays)."""

    UPLOAD_URL = "https://cdn.made-up.example/upload/1111-aaaa"

    def __init__(self, after_delete="replaced", delete_status=200, model="universal-3-5-pro", domain="medical-v1",
                 transcript_status=200):
        self.requests, self.deleted = [], False
        self.after_delete, self.delete_status, self.model, self.domain = after_delete, delete_status, model, domain
        self.transcript_status, self.polls = transcript_status, 0

    def completed(self) -> dict:
        words, t = [], 1000
        for index, word in enumerate(WORDS.split()):
            words.append({"text": word, "start": t, "end": t + 200, "confidence": 0.9, "speaker": "A" if index < 4 else "B"})
            t += 300
        return {"id": "tr-1", "status": "completed", "audio_url": self.UPLOAD_URL, "text": WORDS, "words": words,
                "utterances": [{"speaker": "A", "text": WORDS, "start": 1000, "end": t, "words": words}],
                "audio_duration": 7, "speech_model_used": self.model, "domain": self.domain, "speaker_labels": True}

    def after(self) -> Answer:
        whole = self.completed()
        if self.after_delete == "gone":
            return _json(404, {"error": "not found"})
        if self.after_delete == "words":
            return _json(200, whole)
        url = self.UPLOAD_URL if self.after_delete == "url" else "http://deleted_by_user"
        said = "" if self.after_delete == "empty" else "Deleted by user."
        return _json(200, {"id": "tr-1", "status": "completed", "audio_url": url, "text": said, "words": None,
                           "utterances": None, "audio_duration": 7})

    def __call__(self, method, url, headers, body):
        self.requests.append({"method": method, "url": url, "headers": dict(headers), "body": body})
        path = url.split("/v2", 1)[1]
        if method == "POST" and path == "/upload":
            return _json(200, {"upload_url": self.UPLOAD_URL})
        if method == "POST" and path == "/transcript":
            return _json(self.transcript_status, {"id": "tr-1", "status": "queued"})
        if method == "DELETE":
            if self.delete_status == 200:
                self.deleted = True
                return self.after()
            return _json(self.delete_status, {"error": "made up"})
        if path.startswith("/transcript?"):
            return _json(200, {"transcripts": [{"id": "tr-1", "status": "completed", "audio_url": "http://deleted_by_user"}]})
        if path == "/transcript/tr-1":
            if self.deleted:
                return self.after()
            self.polls += 1
            return _json(200, {"id": "tr-1", "status": "processing"}) if self.polls < 2 else _json(200, self.completed())
        return _json(400, {"error": "made up: no such call"})
