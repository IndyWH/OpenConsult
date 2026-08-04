# Consultation AI — Project Plan

**A research/educational prototype for AI-assisted medical consultations — fully local, human-in-the-loop, English-only in v1.**

Transcribes a doctor–patient consultation live, offers real-time clinical decision support (differentials, questions to ask, signs to elicit), then produces a diarised transcript, a concise doctor-style note with every claim cited to the transcript, referral letters, and evidence-grounded guideline summaries — all running locally on consumer hardware.

> ⚠️ **Status & intent:** This is an experimental prototype for research, education, and demonstration purposes only. It is **not** a medical device, has not undergone any regulatory assessment, and must never be used with real patients or real patient data. All development and demos use synthetic (scripted/acted) consultations.

---

## 1. Why this project

- **Low-resource language clinical NLP — closed with a published negative result.** This project began with Sri Lanka's real workflow in mind: consultations in Sinhala, heavily code-switched with English medical terms, documented in English. A pre-registered evaluation then showed that no available model transcribes code-switched clinical Sinhala safely — drug names and key numbers did not survive in any candidate — so v1 is English-only by explicit decision, and the evaluation records in `evals/` are kept as a standalone research contribution. Sinhala is out of scope, not postponed.
- **Local-first, privacy-first.** Everything — speech recognition, translation, clinical reasoning — runs on a single local machine. No consultation audio or text leaves the premises. This mirrors real-world data-protection constraints in healthcare.
- **Human-in-the-loop by design.** Every AI output is a *draft*. Nothing enters the record until the doctor reviews, edits, and approves it.

## 2. What it does (user's-eye view)

**During the consultation (live):**
1. The doctor starts a session in the browser; the microphone streams audio to the server.
2. A rough live transcript appears as the conversation happens.
3. A side panel updates periodically with: a working differential diagnosis, suggested questions to ask, and clinical signs to look for — helping narrow the differential in real time.

**After the consultation (a background job, takes a minute or two):**
4. The full recording is re-transcribed at higher quality and **diarised** (labelled *Doctor:* / *Patient:*), with quality gates that refuse to draft from an untrustworthy transcript.
5. A concise SOAP-style note is drafted — every claim citing the transcript turns it came from — plus a guideline summary grounded in retrieved guideline text (not the model's memory).
6. The doctor reviews, edits, and signs off the note. Only then is it final — and only from a signed note can referral letters be drafted.

**Around the edges:**
- User accounts with roles (doctor, receptionist, admin) — enforced server-side; the receptionist manages the queue and can never open clinical content.
- A patient database holding consultations, transcripts (both languages), notes, and an audit trail of who did what and what the AI suggested when.

See PROJECT_PLAN.md for the full plan.

> **New to the project?** Start with the [help series](help/00-introduction.md) — a short, diagram-led tour of what the app does, how it's built, and why it works the way it does (including what an independent security audit found). It's written for reading, not installing.

## Getting started (Phase 0)

Requirements: Linux, [uv](https://docs.astral.sh/uv/) (installs its own Python 3.12), PostgreSQL 18 with pgvector.

```bash
# 1. Install uv (one-time)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install PostgreSQL + pgvector (one-time)
sudo apt update && sudo apt install -y postgresql postgresql-18-pgvector

# 3. Install project dependencies
uv sync

# 4. Configure: copy the template, then set SECRET_KEY to a real value
#    (`openssl rand -hex 32`) — the app refuses to start on a missing,
#    short, or placeholder key
cp .env.example .env

# 5. Create the first admin from the server shell (password prompted) —
#    public registration can never create an admin
uv run python scripts/manage_users.py create your-username admin "Your Name"

# 6. Run the app — the production invocation, exactly what the systemd
#    unit on the reference machine runs
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

(`--reload` is development-only: it auto-restarts on code edits and must
never be used for an internet-exposed app.)

Then open http://127.0.0.1:8000/login and register two accounts — one
receptionist, one doctor. Registrations start pending: approve both from
the admin account you created in step 5 (*Users* view). The two-role demo
flow, per the plan:

1. **Receptionist** → *Today* tab: add a synthetic patient to the walk-in
   queue (reorder with ↑/↓ while waiting).
2. **Doctor** → *Today* tab: click **Start consultation** on a waiting
   patient → the live consultation page opens, tied to that patient.
3. Consult (speak), press **Stop** → the queue entry completes, the note
   pipeline runs, and the review page opens.
4. Review, acknowledge any urgency banner, **Approve** → the consultation
   is archived read-only in the *Consultations* tab.

Role boundaries are enforced server-side: the receptionist manages the
queue but gets 403s on transcripts, notes, and review pages. Admins get
an *Audit* tab (who viewed/edited/approved/acknowledged what, when).

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

**Speaker diarisation (one-time setup):** the finalisation pipeline uses
`pyannote/speaker-diarization-3.1`, which is licence-gated on Hugging
Face. Create a free account, accept the model's terms on its model page,
and authenticate with `hf auth login` — do this before your first Stop,
not after.

**The voice (Phase 7a):** the app speaks through Piper, installed
deliberately outside the app's environment (see NOTICE for why):

```bash
uv tool install piper-tts
# download voice en_GB-alba-medium (.onnx + .json) to ~/.local/share/piper-voices/
```

Point `TTS_COMMAND` and `TTS_MODEL_PATH` at it in `.env` (absolute
paths — see `.env.example`). The sound-check button beside Start
confirms the room can hear it.

**Post-consultation note (Phase 2):** pressing Stop triggers the
finalisation pipeline — WhisperX re-transcription, pyannote speaker
diarisation, Doctor/Patient role attribution — and lands you on a review
page with a draft SOAP note. Every claim cites its transcript turns
(click to verify); numbers/drugs/laterality resting on low-confidence
audio are marked ⚠. Edit in place, Regenerate after transcript
corrections, Approve to sign off, or copy as EMR-ready plain text.
The heavy models take turns on the GPU (MedGemma is unloaded while
WhisperX/pyannote run), so finalisation takes a minute or two.

Evaluations for the CDS urgency alarm, RAG grounding, and note quality
live in `evals/`, with reusable harnesses in `scripts/evaluate_*.py`.

Run the tests with:

```bash
uv run pytest
```

For running everything as system services that survive a reboot
(PostgreSQL, Ollama, the app), and for the after-reboot checklist and
known failure modes, see `HANDOVER.md` — the engineering record. The
reader-facing tour lives in `help/`.

## Licence

This project's own code is licensed **AGPL-3.0-or-later** — see
`LICENSE`. The vendored face engine at `vendor/kindalive/` remains MIT
under its upstream licence (`vendor/kindalive/LICENSE`); `NOTICE`
records the full third-party picture, including model and corpus terms.
The "never real patients" rule at the top of this README is a research-
scope constraint of the prototype, not a licence term.
