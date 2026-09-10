# OpenConsult — Project Plan

**A research/educational prototype for AI-assisted medical consultations — English in v1, with code-switched clinical Sinhala as its founding research question.**

Transcribes a doctor–patient consultation live, offers real-time clinical decision support (differentials, questions to ask, signs to elicit), then produces a diarised English transcript, a concise doctor-style note, suggested investigations, and evidence-grounded guideline summaries — all running locally on consumer hardware. See *What v1 is, and is not* below for the scope line and where the Sinhala question landed.

> ⚠️ **Status & intent:** This is an experimental prototype for research, education, and demonstration purposes only. It is **not** a medical device, has not undergone any regulatory assessment, and must never be used with real patients or real patient data. All development and demos use synthetic (scripted/acted) consultations.

---

## What v1 is, and is not

> **This block is deliberately unnumbered, and the omission is
> load-bearing — please do not "tidy" it into the sequence.** (Added
> 2026-07-25.) Numbering it would renumber sections 1–10 and silently
> break every cross-reference now pointing into this file's numbered
> sections. Those references would still *resolve* — to the wrong
> section — so nothing would fail visibly; the documents would simply
> start citing the wrong thing. Verified 2026-07-25, the referring
> documents are:
>
> - **HANDOVER.md** — `§§4, 7` (phase table, Phase 5 row), `§4` (Key
>   design decisions), `§§4, 7` (Phase 5 section), plus `plan §4`
>   (translation layer), `plan §7` (benchmark-first) and `plan §8`
>   (audio retention).
> - **PHASE_7_SPEC.md** — `§4` in hard rule 6 and in the sequencing-note
>   gate update.
> - **`evals/2026-07-10_sinhala_asr_benchmark.md`** and
>   **`evals/2026-07-12_sinhala_asr_recordings_eval.md`** — both cite
>   `plan §7` ("benchmark FIRST, train later").
> - **This file** — §5's `FinalTranscript` entry, §7's risk row and the
>   retention paragraph below all point at §4's Scope decision block.
>
> Note that `evals/2026-07-17_finetune_plan.md` is *not* in this list:
> the `§4` and `§7` in its decision header refer to its own sections,
> not to this file. If this block ever must be numbered, renumber and
> fix all of the above in the same commit.

The project asks whether a single consumer GPU in a spare room can
support a general practice consultation end to end: listen, reason
alongside the doctor, and produce a cited note the doctor signs. The
low-resource language question — *listen in Sinhala, document in
English* — is why the project exists, and it was the first question the
project answered.

**The answer, as of 2026-07-25, is no with current off-the-shelf
models.** That answer is a result, not a gap: it was reached through a
pre-registered protocol run to completion —
`evals/2026-07-10_sinhala_asr_benchmark.md` (benchmark),
`evals/2026-07-12_sinhala_asr_recordings_eval.md` (recordings eval,
including its § Step 6 adjudication), and the not-proceeding header of
`evals/2026-07-17_finetune_plan.md`.

**What v1 does.** English consultations, end to end: live streaming
transcription; live CDS with urgency escalation; corpus-grounded
guideline retrieval that refuses when the corpus doesn't cover the
topic; a cited draft SOAP note the doctor edits and approves; referral
letters generated from the approved note; users, roles, the walk-in
queue, and an audit log. All of it local — no cloud inference.

**What v1 does not do.** Transcribe or translate Sinhala, or any other
non-English language.

**The consequence, stated precisely.** Once the finalisation
transcript-quality gate ships, non-English audio will be **refused at
finalisation** rather than drafted from — because an English-forced
pipeline does not fail loudly on Sinhala speech; it produces a fluent
hallucinated translation and a normal-looking draft note from it. That
is consultation #70, and it was approved before anyone noticed. **That
gate is approved and specified as a pre-Phase-7 build item, but it is
NOT YET BUILT.** Until it ships, the #70 path remains open — which is
precisely why the gate sits on the Phase 7 entry gate rather than in the
deferred review docket.

**The Sinhala research artifacts are retained deliberately** — both
`_si` scripts, the `03_diabetes_review_si` recording and its frozen
reference, `scripts/evaluate_sinhala_asr.py`, the benchmark, the
recordings eval, the adjudication worksheet, and the fine-tune plan.
They are a pre-registered negative result on code-switched clinical ASR
and are intended for external collaboration. (§4's Scope decision block
records the same retention, plus the separate reason the `FinalTranscript`
si/en schema seam stays.)

## 1. Why this project

- **Low-resource language clinical NLP.** Sinhala medical speech recognition is almost untouched territory. Sri Lankan consultations are conducted in Sinhala (heavily code-switched with English medical terms) while notes and prescriptions are written in English. This project models that exact workflow: *listen in Sinhala, document in English*. **That was the question the project asked first, and answered first** — the answer, as of 2026-07-25, is that no off-the-shelf model can do it, established by benchmark, recordings eval and owner adjudication and recorded in `evals/` (see *What v1 is, and is not* above). The question stands; the equity case for it stands; what changed is that v1 now documents in English only.
- **Local-first, privacy-first.** Everything — speech recognition, translation, clinical reasoning — runs on a single local machine. No consultation audio or text leaves the premises. This mirrors real-world data-protection constraints in healthcare.
- **Human-in-the-loop by design.** Every AI output is a *draft*. Nothing enters the record until the doctor reviews, edits, and approves it.

## 2. What it does (user's-eye view)

**During the consultation (live):**
1. The doctor starts a session in the browser; the microphone streams audio to the server.
2. A rough live transcript appears as the conversation happens.
3. A side panel updates periodically with: a working differential diagnosis, suggested questions to ask, and clinical signs to look for — helping narrow the differential in real time.

**After the consultation (a background job, takes a minute or two):**
4. The full recording is re-transcribed at higher quality and **diarised** (labelled *Doctor:* / *Patient:*).
5. ~~The Sinhala transcript is translated into English; both versions are kept.~~ — **not implemented in v1.** This step is conditional on Sinhala restarting; v1 has no Sinhala transcript to translate. See *What v1 is, and is not*.
6. A concise SOAP-style note is drafted, plus a suggested investigations list (bloods, imaging) and a guideline summary grounded in retrieved guideline text (not the model's memory).
7. The doctor reviews, edits, and signs off the note. Only then is it saved as final.

**Around the edges:**
- User accounts with roles (doctor, receptionist, admin) — role provides context, shapes the interface, and controls access.
- **Two role-specific views mirroring a real Sri Lankan GP surgery:** a **front-desk view** for the receptionist (register patients, manage today's queue) and a **consulting view** for the doctor (open the queue, start a session). The receptionist can manage patients and the queue but cannot open transcripts or clinical notes.
- A patient database holding consultations, transcripts (~~both languages~~ — **English only in v1**; the second language is conditional on Sinhala restarting), notes, and an audit trail of who did what and what the AI suggested when.

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
                         (designed; NOT BUILT in v1)
    → SOAP note draft → investigations → guideline summary
                                           │
[5] RAG Service ◄──────────────────────────┘
    pgvector store over guideline content (NICE/CKS or SL)

[7] Frontend: server-rendered pages + HTMX + WebSocket
    (live transcript pane, live CDS pane, note review/edit)
```

**Key design decisions (locked in):**
- **Live path is rough, final path is accurate.** No diarisation during the consultation; a slower, higher-quality pass runs afterwards.
- **Transcribe then translate** (not Whisper's direct translate mode) — preserves the Sinhala transcript as a first-class artifact. **Not exercised in v1** (no Sinhala transcription), but retained as the design of record if Sinhala restarts — and the adjudication supports it: the failure is in *transcription*, not in translation, so the shape of this decision was never what broke.
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
| Sinhala ASR | ~~Whisper large-v3 fine-tuned for Sinhala~~ — **OUT OF SCOPE FOR v1** (2026-07-25, see below) | Investigated and closed with a negative result: no off-the-shelf model handles code-switched clinical Sinhala |
| Translation | ~~LLM-based (Gemma 3 27B) or dedicated NMT model~~ — **OUT OF SCOPE FOR v1** (2026-07-25, see below) | The translation layer has no Sinhala transcript to consume once Sinhala ASR is out of scope |
| Clinical reasoning LLM | **MedGemma 27B** (quantised) | Medically tuned, fits a 4090, runs locally |
| Guideline grounding | RAG with **pgvector** (inside PostgreSQL) | Traceable recommendations; no extra database to run |
| Backend | **FastAPI** + WebSockets | Async Python framework; handles streaming audio and live UI updates |
| Database | **PostgreSQL** | Robust, does relational + vector search in one place |
| Frontend | Server-rendered HTML + **HTMX** + a WebSocket pane | Keeps the project Python-centric; no separate JavaScript codebase to learn |
| Auth | FastAPI + session cookies, role-based access | Simple, auditable |
| Packaging | Docker Compose (later phases) | One-command demo setup |

*(Why not Gradio: it's excellent for demos of a single model, but user accounts, roles, a patient database, and audit trails need a real web application.)*

### Scope decision: English-only for v1 (2026-07-25, owner)

**OpenConsult is English-only for v1.** Sinhala transcription, the
translation layer, and dual-language transcript generation are **out of
scope for v1**.

**The reason is measured, not resourcing.** The pre-registered benchmark
(`evals/2026-07-10_sinhala_asr_benchmark.md`) and recordings evaluation
(`evals/2026-07-12_sinhala_asr_recordings_eval.md`) established that no
off-the-shelf model handles code-switched clinical Sinhala. The
adjudication of 2026-07-25 (§ Step 6 of the recordings eval) established
that **four of twelve curated clinical terms — including two drug names
— survive in no model at all.** Phase 5 is therefore closed with a
negative result rather than paused; the negative result is itself the
finding.

Two retentions, both deliberate:

1. **All Sinhala research artifacts stay in the tree** — both `_si`
   scripts, the `03_diabetes_review_si` recording and its frozen
   reference, `scripts/evaluate_sinhala_asr.py`, the benchmark record,
   the recordings eval, the adjudication worksheet, and the fine-tune
   plan. They are a standalone research contribution — a pre-registered
   negative result on code-switched clinical ASR — and are intended for
   external collaboration. Nothing here is dead weight to be tidied
   away.
2. **The si/en seam in the `FinalTranscript` design is retained on
   purpose**, even though nothing populates the Sinhala side in v1.
   Removing it and later restoring it would be a schema migration
   against a database holding approved clinical notes.

## 5. Data model (first cut)

- **User** — name, role (doctor / receptionist / admin), credentials
- **Patient** — synthetic demographics only
- **QueueEntry** — patient added to today's queue by the receptionist; ordered list, status: `waiting → in consultation → done` (matches the walk-in, take-a-number flow of a typical SL surgery rather than calendar slots)
- **Consultation** — belongs to a patient and a doctor; status: `live → processing → finalised`
- **TranscriptSegment** — rough live segments (timestamped, no speaker)
- **FinalTranscript** — diarised, role-attributed; Sinhala and English versions. *The Sinhala side is a **retained schema seam**, deliberately unpopulated in v1: removing it and later restoring it would be a migration against a database holding approved clinical notes. See §4, Scope decision.*
- **Note** — SOAP draft → doctor-edited → approved (versioned)
- **CDSSnapshot** — what the CDS engine suggested and when (valuable for research and audit)
- **Investigation / GuidelineSummary** — suggested tests and retrieved guideline excerpts with sources
- **AuditEvent** — who viewed/edited/approved what, when

## 6. Phased plan

Each phase produces something demonstrable on its own.

**Phase 0 — Foundations (repo, environment)**
Set up the GitHub repo, Python environment, Postgres, and a "hello world" FastAPI app. Write 3–5 scripted mock consultations (English first, then Sinhala) and record them — these become the permanent test set.
*Done when:* repo runs locally with one command; test recordings exist.
*Note (2026-07-25):* the Sinhala half was done — **both `_si` scripts were written and are retained** (`01_chest_pain_si`, `03_diabetes_review_si`), with marking schemes, as-spoken references and romanised reading guides. `03_diabetes_review_si` **was recorded** and is the recording the whole Phase 5 evaluation rests on. `01_chest_pain_si` is **not being recorded for v1** — it needs a Sinhala-speaking second reader and only feeds an out-of-scope arm; the script stays in the tree.

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
*Done when:* **the question is answered** — whether off-the-shelf models can transcribe code-switched clinical Sinhala well enough to produce a usable English note, established by benchmark, recordings evaluation and owner adjudication.
**Status: COMPLETE as of 2026-07-25. The answer is no.** This is why the phase reads *closed*, not *abandoned*: the pre-registered protocol ran to completion and returned a negative result, which is a finding. Shipping a Sinhala pipeline was contingent on that answer being yes; it was not.

> **Criterion corrected 2026-07-25** (recorded here rather than changed silently). The original read: *"a Sinhala mock consultation produces a usable English note."* It was replaced for two reasons. First, it can never be met on the measured evidence, so it would leave Phase 5 permanently and misleadingly incomplete. Second, it conflated **investigating** whether this is possible with **shipping** it — the phase was designed and pre-registered to answer a question, and the corrected criterion is the one the protocol was actually built against.

**Phase 6 — Users, roles, front desk, audit, polish**
Registration and roles (doctor / receptionist / admin) with role-specific views: the receptionist's **front-desk view** (register patients, manage today's queue) and the doctor's **consulting view** (pick a patient from the queue, start the session). Role-based access enforced — the receptionist cannot open transcripts or notes. Plus patient records, audit log, Docker Compose packaging, and a demo script for the interview: *receptionist registers and queues a patient → doctor opens the queue and consults → live transcript + CDS → signed-off note in the record.*
*Done when:* a stranger can run the two-role demo end-to-end from the README.

Phases 1–2 are sequential; 3, 4, and 5 are largely independent after that, so they can be reordered by interest.

## 7. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Sinhala ASR quality is poor | **This risk materialised.** The mitigation worked as designed — pipeline built English-first, language layer swappable, benchmark before training — and the benchmark's answer was that no candidate is usable. Resolved 2026-07-25 by scoping Sinhala out of v1 (§4, Scope decision), not by training |
| Code-switched speech mangles English medical terms | **This risk materialised, and was the decisive one.** Measured explicitly on the mock set as planned: mechanical English-term recall 0/106 for every fine-tune, and four of twelve curated clinical terms unrecoverable in every model |
| CDS suggestions flip-flop or hallucinate | Structured JSON prompting, low temperature, carry previous state into each prompt; treat as an explicit experiment |
| Guideline hallucination | RAG-only guideline content with visible citations; nothing from model memory |
| Real-time performance on one GPU | Live path uses a smaller/faster Whisper model; heavy models (MedGemma 27B, WhisperX) run post-consultation |
| Scope creep | Phase gates with "done when" criteria; live diarisation, multi-speaker support, mobile UI are explicitly out of scope for v1 |
| Regulatory / ethical exposure | Prototype-only framing (banner in-app and in README), synthetic data only, human sign-off required on all outputs |

## 8. Data protection posture (even for synthetic data)

Built as if it were real, because that's the point of the demonstration:
encryption at rest for the database and audio files, role-based access control, full audit logging, a defined retention policy (audio deleted after finalisation unless flagged for research), and no external API calls with consultation content — all inference is local.

## 9. Out of scope for v1

Live (streaming) diarisation · more than two speakers · prescription generation · calendar-based appointment scheduling, patient self-booking, and SMS reminders (the queue covers v1) · EHR/EMR integration · mobile app · Tamil language support (a natural v2 candidate for Sri Lanka — see §10 for the recorded position: a testable question with the method already built, gated on finding a clinically-knowledgeable native Tamil speaker to adjudicate).

## 10. Roadmap ideas beyond v1

- **Evaluation paper: code-switched Sinhala clinical ASR benchmark** — *promoted; this one has a finished result rather than a planned one.* The pre-registered protocol is complete through adjudication (benchmark → recordings eval → step 6), and it returned a clean negative: no off-the-shelf model handles code-switched clinical Sinhala, with four of twelve curated clinical terms — two of them drug names — unrecoverable in every model. The negative result strengthens the paper rather than weakening it.
- Fine-tuned Sinhala medical ASR model published to Hugging Face — **conditional**, on the same restart trigger recorded in the fine-tune plan header: a materially better Sinhala or multilingual model, or a code-switched clinical dataset, appearing. Not proceeding as of 2026-07-25.
- **Tamil support (Sri Lanka's second consultation language)** — *neither demoted nor promoted by the Sinhala result; recorded 2026-07-25 as a **testable question** with a method already built.*

  **The Sinhala result is evidence about Tamil, but does not settle it.** Tamil is the better-resourced language — notably, Common Voice collects Tamil and never collected Sinhala — so the no-public-test-set problem that shaped the whole Sinhala benchmark may simply not apply.

  **What the Sinhala evidence does not establish.** The CER collapse from 0.035 on read speech to 0.46 on the real recording confounds three variables the eval did not separate: read versus conversational speech, clean corpus audio versus real-room audio, and monolingual versus code-switched content. That number alone therefore does *not* establish that code-switching was the cause. **The confound is unresolved, and the experiment that would resolve it is designed but unrun** — `evals/2026-07-25_sinhala_confound_prereg.md`; its A-vs-B contrast tests exactly the premise the Tamil prediction below rests on.

  **What it does establish, with a clean mechanism.** The 0/106 English-term recall failure — every Sinhala fine-tune transliterated or lost every English medical term — has a language-independent cause: fine-tuning on monolingual data destroys the model's ability to emit Latin-script English tokens. Any monolingual Tamil fine-tune should be expected to fail the same way.

  **Strategic consequence, which reverses the Phase 5 approach.** Sinhala required fine-tuning because stock Whisper produced degenerate repetition loops at every model size. Tamil is far better represented in Whisper's training data, so stock `large-v3` or a successor may not loop — and if it does not, the reason to fine-tune disappears, taking with it the very mechanism that erased the English terms. **The first Tamil candidate should therefore be a strong multilingual model, not a Tamil fine-tune.** That is a cheap prediction to test with the existing harness.

  **The method transfers.** `scripts/evaluate_sinhala_asr.py`, the curated-term-list design, the frozen-reference pre-registration and the adjudication instrument all carry over to Tamil; only the scripts and the term list need writing.

  **The real blocker is not technical.** The adjudication step requires a native Tamil speaker with clinical knowledge. The owner adjudicated Sinhala himself; Tamil would need a collaborator. **That is the gating dependency for any Tamil work** — not GPU time, not the harness.
- Sri Lankan national guideline corpus for the RAG layer — **checked against the English-only decision on 2026-07-25 and unaffected.** Recorded as verified rather than assumed, because this is the other Sri Lanka-specific roadmap item and a future reader would otherwise have to re-derive it. Two independent reasons: Sri Lankan national guidelines are published in English, and the RAG layer never depended on Sinhala transcription in the first place — it retrieves against guideline text, not against the consultation transcript's language.
- Proper appointment scheduling (calendar slots, patient self-booking, SMS reminders)

---

*Built by a doctor learning by building. Contributions and criticism welcome.*
