# SPEC — Docker packaging and demo script

Drafted 2026-07-25 by Claude Cowork. **Signed off by the owner 2026-08-04** — see
*Owner decisions (2026-08-04)* at the end of this document for the five decisions
that resolve Part 3.

The last item on the Phase 7 gate, alongside `05_epigastric_pain_en` and the transcript-quality gate
(refuse path now built).

Two deliverables in one spec because they constrain each other: the demo needs its own data, and
packaging is what makes the demo reproducible on a machine that isn't mlrig.

---

## Part 1 — Packaging

### 1.1 The thing that will bite: proxy trust breaks in Docker

`app/ratelimit.py` trusts `X-Forwarded-For` **only when the direct peer is loopback**, because that is
where Tailscale Serve and Funnel terminate on the host. In Compose, the reverse proxy is a *different
container*, so the direct peer is a bridge-network address, never loopback.

Consequences if this is missed, and it is easy to miss because nothing errors:

- Every request appears to come from the proxy container's IP, so per-IP login and registration rate
  limits become **global** limits — one attacker locks out every user, or one user's retries throttle
  everyone.
- `user.login`, `user.login_failed` and `user.registered_pending` all record the proxy's IP, so the
  source-IP forensics added for public exposure quietly stop working.

Required change: replace the loopback test with a configurable trusted-proxy set,
`TRUSTED_PROXY_CIDRS`, defaulting to loopback only so today's host deployment is unchanged. Compose
sets it to the bridge subnet. Tests must cover a spoofed `X-Forwarded-For` from an untrusted peer
being ignored, and a real one from a trusted peer being honoured.

This is a security-relevant change to a defence added for public exposure. It belongs in its own
commit with its own tests, not folded into a Dockerfile commit.

### 1.2 What cannot go in the image

**The corpus.** 38 sources, 1301 chunks of NICE, CKS, CDC and WHO content, licensed for local research
use only, never committed or redistributed. **An image containing it is redistribution.** Ship
`corpus/manifest.yaml` and `scripts/ingest_guidelines.py`; the operator ingests on first run.

First-run ingestion is a long network step that can legitimately fail, and guideline drift is real —
the 2026-07-24 expansion caught NG51 replaced by NG253/NG254, NG138 by NG250, and both replacements'
`/Recommendations` URLs silently redirecting. So first run must: report per-source success and failure,
exit non-zero listing every source that failed its `expect_title` or `expected_queries` gate, and be
safely re-runnable. A partially ingested corpus must not present as ready.

**The models.** MedGemma 27B Q4_K_M is ~17 GB; add embeddinggemma, faster-whisper distil-large-v3,
WhisperX large-v3 and pyannote 3.1 and the image would be tens of gigabytes. Ollama pulls on first
run. The HF models need the operator's own token, and **pyannote 3.1 requires manual licence
acceptance on huggingface.co** — that cannot be automated and must be a documented prerequisite, not a
runtime surprise.

**Any secret.** `.env` is gitignored and must never be baked into a layer. Compose reads it from the
host; the HF token arrives as an env var or a mounted HF cache. `.env.example` is the contract.

### 1.3 Services

| Service | Recommendation |
|---|---|
| `db` | Bundle. Postgres 18 with pgvector. Needs a first-run init that grants `CREATEDB` to `consultation_app` and installs `vector` in `template1` — see §1.5. |
| `ollama` | Bundle behind a Compose profile, GPU-attached, **and** support pointing at an existing host Ollama via `OLLAMA_HOST`. mlrig already runs it as a user-space systemd service; forcing a second copy would waste 17 GB of model storage. |
| `app` | Own image. Waits for `db` and for Ollama to answer before serving. |
| proxy | Out of scope for v1. HTTPS is the operator's problem — see §1.6. |

### 1.4 Base image and the dependency scars

The pinned overrides in `pyproject.toml` were tuned against WSL2 and Ubuntu 26.04: `ctranslate2 ≥ 4.6`
(4.4 fails with "cannot enable executable stack" on newer glibc), `pyannote` pinned to 3.4.0 with
`vad_method="silero"`, `torchcodec` excluded entirely (0.7 cannot load against FFmpeg 8, and its mere
presence made transformers' chunked ASR pipeline return empty transcripts — the uniform WER/CER 1.000
incident).

Every one of those is a glibc, FFmpeg or CUDA-library interaction. **Match the base image to Ubuntu
26.04** to keep the known-good combination, and re-validate the audio path inside the image before
declaring the packaging done — a green pytest run on the host proves nothing about the container.

`app.transcription._preload_cuda_libraries()` must still run before torch and ctranslate2 imports in
the container's fresh processes.

### 1.5 The test-database gotcha

`tests/conftest.py` creates and drops `consultation_ai_test` per session and **refuses to fall back to
the live database by design**. That needs `ALTER ROLE consultation_app CREATEDB` and
`CREATE EXTENSION vector` in `template1` (pgvector is untrusted, so the test DB can only inherit it).

If the bundled Postgres is not initialised with both, the suite does not degrade — it refuses. Put both
in the `db` service's init scripts so `docker compose run app pytest` works on a fresh clone.

### 1.6 GPU, VRAM and HTTPS

GPU access needs the NVIDIA Container Toolkit, and on WSL2 that is its own setup. Document the real
requirement: **24 GB VRAM, effectively exclusive.** `app/finalize.py` unloads MedGemma with
`keep_alive=0`, polls `/api/ps`, runs WhisperX and pyannote, frees them, and lets MedGemma reload —
sequencing that assumes nothing else is competing for the card. A second GPU workload on the host will
cause OOM, not slowness.

HTTPS: `getUserMedia` requires a secure origin, so the live page's microphone only works on
`localhost` or over TLS. `localhost` is fine for a single-machine demo. Anything else needs a
certificate, which is what Tailscale Serve provides on mlrig. State the constraint plainly rather than
shipping a proxy nobody asked for.

### 1.7 Volumes, health and startup

Named volumes for Postgres data, audio (WAV and FLAC), the corpus, Ollama models and the HF cache. The
retention sweep and the FLAC-on-approval step both operate on the audio volume, so it must survive
`docker compose down`.

`GET /api/monitor/pulse` is the natural container health check: unauthenticated by design, aggregate
counts only, cached ~10 s so probing cannot load the database.

On startup the app re-enqueues any consultation left `queued` with audio on disk, so a container
restart must not strand a recording. Worth an explicit test in the packaged environment.

---

## Part 2 — Demo script

### 2.1 The rule that comes first

**No governance action touches a real row.** Docket item 5's lesson was written after consultation #70
was left wrongly visible for two days, and the identical failure recurred six minutes after the fix.
The demo is the highest-risk place for this, because it is performed under time pressure in front of
an audience.

So the demo gets **its own data**: a seed script creating clearly-marked synthetic patients and
consultations, and a scoped teardown that resets only those rows. `scripts/seed_demo.py` and
`scripts/reset_demo.py`, both refusing to touch anything they did not create — same convention as
`sweep_expired_audio(only_ids=…)` and `purge_voided`.

### 2.2 Proposed run of play, roughly ten minutes

1. **Reception** — receptionist registers a walk-in and adds to the queue. Shows role separation.
2. **Doctor picks the patient** — server-sourced patient banner, the wrong-patient defence.
3. **Mic check** — the level meter running off the same `getUserMedia` stream the transcriber consumes.
   One capture, so the meter cannot disagree with what the server hears. Small moment, strong point.
4. **Live consultation** — streaming transcript, CDS differentials revising as evidence arrives,
   questions disappearing once answered, guideline panel citing the corpus.
5. **A refusal** — ask the guideline layer something out of corpus. The recorded refusal cases are
   torsion, postpartum haemorrhage and cricket. Cricket lands the point that this thing knows what it
   does not know, and gets a laugh.
6. **Urgency** — if a red-flag script is used, the alarm firing and the acknowledge-gate.
7. **Stop and finalise** — the pipeline, then the review page.
8. **Verification** — click a citation chip and land on the transcript turn. This is the whole thesis
   of the project in one gesture; give it time.
9. **Approve, then a referral letter** — generated from the approved note only, with the grounding
   gate.

### 2.3 What to leave out, and why

RBAC probes and 403s — true but dull. Void, unvoid and purge — the exact actions §2.1 forbids on real
rows; if governance must be shown, show it on a seeded demo row and reset afterwards. Anything
involving the five real accounts.

### 2.4 The gate refusal is now demoable, with a caveat

The transcript-quality gate refusing a non-English recording is a strong safety demonstration: the
system declines to draft rather than fabricating. But do **not** demo it with #70's audio — that is a
voided real consultation and a research fixture. Record a short throwaway non-English utterance
specifically for the demo. Owner decision: worth the extra recording, or leave the gate as something
described rather than shown?

---

## Part 3 — Owner decisions

1. **Ollama bundled or host?** Recommendation: support both, default to host on mlrig to avoid a second
   17 GB of models.
2. **Which script does the demo use?** A routine English one keeps it calm; a `_uk` buried-red-flag
   script (14 giant cell arteritis, 15 cauda equina) shows the urgency path but raises the stakes live.
   Recommendation: routine as the spine, with the urgency path shown from a pre-recorded consultation
   rather than performed.
3. **Demo the gate refusal?** (§2.4) Needs one short throwaway recording.
4. **Show approve-to-activate registration?** It is a good security story for an audience that cares
   about governance, and it is entirely safe on seeded data.
5. **Target audience for the packaging.** "Runs on another clinician's machine" and "runs on a
   reviewer's machine for a paper" imply different amounts of first-run polish. The corpus and model
   prerequisites are a real barrier for a non-technical operator.

---

## Owner decisions (2026-08-04)

The five Part 3 questions, decided at sign-off:

1. **Ollama** — support both: bundled behind a Compose profile,
   GPU-attached, **and** a host install via `OLLAMA_HOST`. **Default to
   host**, avoiding a second ~17 GB of models on the reference machine.
2. **Demo script** — the demo performs a **routine English script live**;
   the urgency path is shown **from a pre-recorded consultation**, not
   performed.
3. **Gate refusal** — **WILL be demoed**, using a short throwaway
   non-English clip the owner records for the purpose (owner-supplied;
   never #70's audio).
4. **Approve-to-activate registration** — **shown, on seeded data only.**
5. **Packaging audience** — first-run polish targets a **paper reviewer /
   technical reader**: clear prerequisites and loud validated first-runs,
   a technical operator assumed.
