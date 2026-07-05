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

## 3. Architecture overview

Everything runs on one Linux machine (target: RTX 4090, 96 GB RAM). Seven logical components:

```
Browser (mic + UI)
   │  audio chunks + live updates (WebSocket)
   ▼
[1] Audio Gateway (FastAPI) ──────────────┐
   │                                       │
   ▼                                       ▼
[2] Live ASR worker            [6] App Core (FastAPI)
    faster-whisper + VAD            auth, roles, patients,
   │  rough transcript              sessions, audit log
   ▼                                       │
[3] CDS Engine                             ▼
    MedGemma → structured JSON      PostgreSQL (+ pgvector)
    (differentials, questions,             ▲
     signs) → pushed to UI                 │
                                           │
[4] Finalisation Pipeline (async, post-consultation)
    WhisperX re-transcription → pyannote diarisation
    → role attribution → Sinhala→English translation
    → SOAP note draft → investigations → guideline summary
                                           │
[5] RAG Service ◄──────────────────────────┘
    pgvector store over guideline content (NICE/CKS or SL)

[7] Frontend: server-rendered pages + HTMX + WebSocket
    (live transcript pane, live CDS pane, note review/edit)
```

**Key design decisions (locked in):**
- **Live path is rough, final path is accurate.** No diarisation during the consultation; a slower, higher-quality pass runs afterwards.
- **Transcribe then translate** (not Whisper's direct translate mode) — preserves the Sinhala transcript as a first-class artifact.
- **Guidelines via retrieval (RAG), not model memory** — recommendations must be traceable to a source document.
- **Raw audio is retained until finalisation succeeds**, then handled per the data-retention policy.
- **Draft-until-approved:** all AI outputs require explicit doctor sign-off.

## 4. Technology choices (and why, in plain terms)

| Layer | Choice | Why |
|---|---|---|
| OS / runtime | Linux, Python 3.11+ | Standard for ML tooling; matches target hardware |
| Live speech-to-text | **faster-whisper** (CTranslate2) | Whisper-quality transcription, fast enough for near-real-time on a 4090 |
| Voice activity detection | Silero VAD (built into faster-whisper) | Chunks audio at natural pauses so transcription streams smoothly |
| Final transcription + diarisation | **WhisperX** + **pyannote.audio** | Word-level timestamps + "who spoke when"; `num_speakers=2` for the doctor–patient case |
| Sinhala ASR | Whisper large-v3 fine-tuned for Sinhala (existing HF fine-tunes first; own fine-tune if needed) | Base Whisper's Sinhala is weak; fine-tunes on Common Voice / OpenSLR Sinhala close the gap. Whisper handles Sinhala–English code-switching better than monolingual models |
| Translation | LLM-based (Gemma 3 27B) or dedicated NMT model — to be benchmarked | Sinhala→English medical translation quality is a key experiment |
| Clinical reasoning LLM | **MedGemma 27B** (quantised) | Medically tuned, fits a 4090, runs locally |
| Guideline grounding | RAG with **pgvector** (inside PostgreSQL) | Traceable recommendations; no extra database to run |
| Backend | **FastAPI** + WebSockets | Async Python framework; handles streaming audio and live UI updates |
| Database | **PostgreSQL** | Robust, does relational + vector search in one place |
| Frontend | Server-rendered HTML + **HTMX** + a WebSocket pane | Keeps the project Python-centric; no separate JavaScript codebase to learn |
| Auth | FastAPI + session cookies, role-based access | Simple, auditable |
| Packaging | Docker Compose (later phases) | One-command demo setup |

*(Why not Gradio: it's excellent for demos of a single model, but user accounts, roles, a patient database, and audit trails need a real web application.)*

## 5. Data model (first cut)

- **User** — name, role (doctor / admin / observer), credentials
- **Patient** — synthetic demographics only
- **Consultation** — belongs to a patient and a doctor; status: `live → processing → finalised`
- **TranscriptSegment** — rough live segments (timestamped, no speaker)
- **FinalTranscript** — diarised, role-attributed; Sinhala and English versions
- **Note** — SOAP draft → doctor-edited → approved (versioned)
- **CDSSnapshot** — what the CDS engine suggested and when (valuable for research and audit)
- **Investigation / GuidelineSummary** — suggested tests and retrieved guideline excerpts with sources
- **AuditEvent** — who viewed/edited/approved what, when

## 6. Phased plan

Each phase produces something demonstrable on its own.

**Phase 0 — Foundations (repo, environment)**
Set up the GitHub repo, Python environment, Postgres, and a "hello world" FastAPI app. Write 3–5 scripted mock consultations (English first, then Sinhala) and record them — these become the permanent test set.
*Done when:* repo runs locally with one command; test recordings exist.

**Phase 1 — Streaming transcription (highest technical risk)**
Browser mic → WebSocket → faster-whisper → live transcript on screen. English only.
*Done when:* a live English transcript appears with acceptable lag (~2–5 s).

**Phase 2 — Post-consultation note generation**
On session end: WhisperX + pyannote diarisation, role attribution, MedGemma drafts a SOAP note, doctor review/edit screen.
*Done when:* a mock consultation yields a diarised transcript and an editable draft note.

**Phase 3 — Live CDS loop**
Feed the growing transcript to MedGemma incrementally; render differentials, suggested questions, and signs. The hard part is **prompt design for stability** — structured JSON output that evolves sensibly rather than flip-flopping every update.
*Done when:* the CDS panel updates during a mock consultation and its suggestions are coherent over time.

**Phase 4 — Investigations + RAG guidelines**
Build the pgvector store over guideline content; generate the investigations list and a guideline summary with citations to retrieved passages.
*Done when:* the final note includes investigations and a sourced guideline summary.

**Phase 5 — Sinhala language layer**
Benchmark existing Sinhala Whisper fine-tunes on the mock recordings (word error rate, and how they handle code-switched English terms). Fine-tune Whisper on the 4090 if existing models fall short. Add the translation step; store dual-language transcripts.
*Done when:* a Sinhala mock consultation produces a usable English note.

**Phase 6 — Users, patients, audit, polish**
Registration/roles, patient records, audit log, Docker Compose packaging, demo script for the interview.
*Done when:* a stranger can run the demo end-to-end from the README.

Phases 1–2 are sequential; 3, 4, and 5 are largely independent after that, so they can be reordered by interest.

## 7. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Sinhala ASR quality is poor | Whole pipeline built English-first; language layer is a swappable module. Benchmark existing fine-tunes before training. Fine-tuning is itself a demonstrable result |
| Code-switched speech mangles English medical terms | Use Whisper-family models (multilingual by design); measure this explicitly on the mock set |
| CDS suggestions flip-flop or hallucinate | Structured JSON prompting, low temperature, carry previous state into each prompt; treat as an explicit experiment |
| Guideline hallucination | RAG-only guideline content with visible citations; nothing from model memory |
| Real-time performance on one GPU | Live path uses a smaller/faster Whisper model; heavy models (MedGemma 27B, WhisperX) run post-consultation |
| Scope creep | Phase gates with "done when" criteria; live diarisation, multi-speaker support, mobile UI are explicitly out of scope for v1 |
| Regulatory / ethical exposure | Prototype-only framing (banner in-app and in README), synthetic data only, human sign-off required on all outputs |

## 8. Data protection posture (even for synthetic data)

Built as if it were real, because that's the point of the demonstration:
encryption at rest for the database and audio files, role-based access control, full audit logging, a defined retention policy (audio deleted after finalisation unless flagged for research), and no external API calls with consultation content — all inference is local.

## 9. Out of scope for v1

Live (streaming) diarisation · more than two speakers · prescription generation · EHR/EMR integration · mobile app · Tamil language support (a natural v2 candidate for Sri Lanka).

## 10. Roadmap ideas beyond v1

- Fine-tuned Sinhala medical ASR model published to Hugging Face
- Evaluation paper: code-switched Sinhala clinical ASR benchmark
- Tamil support (Sri Lanka's second consultation language)
- Sri Lankan national guideline corpus for the RAG layer

---

*Built by a doctor learning by building. Contributions and criticism welcome.*
