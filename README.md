# Consultation AI — Project Plan

**A research/educational prototype for AI-assisted medical consultations in Sinhala and English.**

Transcribes a doctor–patient consultation live, offers real-time clinical decision support (differentials, questions to ask, signs to elicit), then produces a diarised bilingual transcript, a concise doctor-style note, suggested investigations, and evidence-grounded guideline summaries — all running locally on consumer hardware.

> ⚠️ **Status & intent:** This is an experimental prototype for research, education, and demonstration purposes only. It is **not** a medical device, has not undergone any regulatory assessment, and must never be used with real patients or real patient data. All development and demos use synthetic (scripted/acted) consultations.

---

## 1. Why this project

- **Low-resource language clinical NLP.** Sinhala medical speech recognition is almost untouched territory. Sri Lankan consultations are conducted in Sinhala (heavily code-switched with English medical terms) while notes and prescriptions are written in English. This project models that exact workflow: *listen in Sinhala, document in English*.
- **Local-first, privacy-first.** Everything — speech recognition, translation, clinical reasoning — runs on a single local machine. No consultation audio or text leaves the premises. This mirrors real-world data-protection constraints in healthcare.
- **Human-in-the-loop by design.** Every AI output is a *draft*. Nothing enters the record until the doctor reviews, edits, and approves it.

## 2. What it does (user's-eye view)

**During the consultation (live):**
1. The doctor starts a session in the browser; the microphone streams audio to the server.
2. A rough live transcript appears as the conversation happens.
3. A side panel updates periodically with: a working differential diagnosis, suggested questions to ask, and clinical signs to look for — helping narrow the differential in real time.

**After the consultation (a background job, takes a minute or two):**
4. The full recording is re-transcribed at higher quality and **diarised** (labelled *Doctor:* / *Patient:*).
5. The Sinhala transcript is translated into English; both versions are kept.
6. A concise SOAP-style note is drafted, plus a suggested investigations list (bloods, imaging) and a guideline summary grounded in retrieved guideline text (not the model's memory).
7. The doctor reviews, edits, and signs off the note. Only then is it saved as final.

**Around the edges:**
- User accounts with roles (doctor, admin, observer) — role provides context and controls access.
- A patient database holding consultations, transcripts (both languages), notes, and an audit trail of who did what and what the AI suggested when.

See PROJECT_PLAN.md for the full plan.

## Getting started (Phase 0)

Requirements: Linux, [uv](https://docs.astral.sh/uv/) (installs its own Python 3.12), PostgreSQL 18 with pgvector.

```bash
# 1. Install uv (one-time)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install PostgreSQL + pgvector (one-time)
sudo apt update && sudo apt install -y postgresql postgresql-18-pgvector

# 3. Install project dependencies
uv sync

# 4. Run the app
uv run uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000 — you should see a hello-world JSON response.
Interactive API docs live at http://127.0.0.1:8000/docs.

**Live transcription (Phase 1):** open http://127.0.0.1:8000/live, click
Start, allow microphone access, and speak. Confirmed text appears with
timestamps; the grey italic line is the model's provisional guess. Runs
`distil-large-v3` on the GPU (override with `WHISPER_MODEL`, e.g.
`WHISPER_MODEL=small.en` for CPU-only machines). The first run downloads
the model (~1.5 GB).

**Live clinical decision support (Phase 3):** the live page shows a CDS
panel — differential diagnoses, questions to ask, signs to check — updated
as the conversation grows. It needs MedGemma running locally via
[Ollama](https://ollama.com):

```bash
ollama serve &
ollama pull hf.co/unsloth/medgemma-27b-text-it-GGUF:Q4_K_M   # ~17 GB, needs ~20 GB GPU
```

Without Ollama running, transcription still works; the CDS panel reports
itself unavailable. Replay a mock consultation through the CDS engine
without speaking:

```bash
uv run python scripts/simulate_cds.py mock_consultations/01_chest_pain_en.md
```

**Guideline grounding (Phase 4):** the live page shows a guidelines panel —
a summary grounded ONLY in retrieved guideline passages, each claim cited,
with a provenance line (corpus name, version, ingestion date). If the local
corpus doesn't cover the topic, the panel declines rather than improvises.
The corpus itself is not committed (third-party content); rebuild it from
the committed manifest:

```bash
ollama pull embeddinggemma          # one-time: the embedding model
uv run python scripts/ingest_guidelines.py   # fetch + chunk + embed into pgvector
```

Evaluations for the CDS urgency alarm and the RAG grounding live in
`evals/`, with reusable harnesses in `scripts/evaluate_*.py`.

Run the tests with:

```bash
uv run pytest
```
