# Phase 7 — Supervised autonomous history-taking ("auto mode")

Owner's concept, 2026-07-24. Status: approved direction, staged build; nothing started. This phase crosses the project's founding line — the AI moves from advising the doctor to acting on the patient — so the hard rules below are constitutional, not preferences.

## Vision

A small Auto toggle beside Start consultation. In auto mode, Consultation AI conducts the history-taking conversation with the (synthetic/actor) patient by voice — listening like a good GP, asking questions derived from its own CDS agenda — while the doctor supervises, intervenes at will, and performs the examination. An expressive robot face gives the system a bedside presence.

## Hard rules (all stages, non-negotiable)

1. The AI asks questions and acknowledges; it NEVER advises, reassures, interprets, breaks news, or hints at diagnosis to the patient. Any drafted utterance that is not a question or a minimal acknowledgement is suppressed in code, not just prompt.
2. Urgency pause protocol (owner-refined 2026-07-24): when the urgency alarm fires, auto mode PAUSES — it stops speaking and asking, but keeps listening and transcribing — and the alert is presented to the supervising doctor. Pause, not termination: alarms can be transient (the script-02 dengue boundary case), and the stateless urgency officer re-evaluates fresh on every update, so clarification can clear a false alarm on its own. On acknowledging the alert the doctor chooses: RESUME AUTO (the question agenda is reprioritised toward the alarm's clarifying questions) or TAKE OVER (drop to standard mode). Ratchet: a re-fire of the same urgent action after a resume pauses again and requires a fresh acknowledgement — no automatic ack-resume loops — and an alarm still unresolved at Stop carries into the review page's acknowledge-gated banner exactly as today.
3. The doctor always wins: doctor speech (barge-in) cancels the AI's current and queued utterances instantly. Toggling out of auto mode is one tap and immediate.
4. Disclosure: the patient/actor is told they are talking to a machine. The robot face (deliberately non-human) reinforces rather than replaces this.
5. Everything is logged: every question asked, its CDS rationale, its timing, and every doctor intervention — CDSSnapshot-style, for research and audit.
6. English only until Sinhala TTS/ASR reach parity (realistically v2+).
7. Synthetic consultations only, as everywhere in this project.

## Consultation behaviour policy (owner's clinical spec)

Mimic real GP craft, not interrogation:

- **Golden minutes.** Open with a single invitation ("Please, tell me what's brought you in") then stay silent for the first 2–3 minutes while the patient talks freely. During this phase the system produces only minimal encouragers ("mm-hm", "I see", "go on") triggered after natural pauses (~1.5–2 s of silence), and NO questions.
- **Open-to-closed cone.** When the patient's free narrative dries up (sustained silence or explicit hand-back), begin with open questions ("Can you tell me more about the chest pain?") before narrowing to specific/closed questions (onset, radiation, exacerbating factors...) drawn from the CDS questions_to_ask agenda.
- **One question at a time**, wait for the answer, let the CDS revise the agenda on each answer (the existing revision rules already remove answered questions).
- **Examination handover.** The system never pretends to examine. When the agenda is exhausted or the doctor intervenes, it hands over explicitly: "Thank you — Dr X will examine you now."

Each of these is measurable (see eval design) — the policy is written to be scored.

## Staged build

### Stage 7a — Tap-to-ask (the stepping stone; ~1/10 of the work)
CDS panel questions become tappable. Doctor taps → local TTS speaks the question to the patient → answer flows through the existing ASR/CDS pipeline. No turn-taking AI, no end-of-turn detection, no barge-in problem — the doctor IS the turn-taker. Builds and battle-tests: TTS integration (Piper or equivalent, fully local), audio output path alongside capture (echo handling: mute/AEC-gate the ASR while the system speaks, and exclude system utterances from the patient transcript by construction — the system knows when it is speaking), spoken-question logging, and patient reaction to a machine voice.

### Stage 7b — The face (kindalive integration; can land with 7a)
https://github.com/smithandrewjohn/kindalive — MIT (attribution in NOTICE), Python, drives emotion from local Ollama-compatible models, renders a retro LED dot-matrix face via 12 FACS-based muscles from a simulated-neurochemistry state that evolves smoothly.

- Embed the web face renderer in the live page (renderer-agnostic per upstream; a canvas/web component beside or replacing the idle CDS space in auto mode).
- Drive it cheaply: add one optional field to the existing CDS assessment JSON (e.g. patient_affect_hint or situation summary line) and feed that to kindalive's impulse input — zero additional model calls on the 4090. Direct small-model mode via Ollama is the fallback if the hint quality disappoints.
- The face listens in 7a already (reacts while the patient talks, blinks, attends) even though the doctor still taps the questions — presence before autonomy.
- Face is a runtime toggle, independent of auto mode: OFF must remain a first-class state (it is the control arm of the face study, and some demos will want no face).

### Stage 7c — Supervised auto (the full loop)
The system taps its own buttons, governed by the behaviour policy above:
- End-of-turn detection: VAD silence threshold + a lightweight "has the patient finished the thought?" check; err toward waiting (a slow system is polite; an interrupting one is clinically wrong and fails the eval).
- Latency budget: encourager < 1 s; question (MedGemma selection + TTS synthesis) ≤ ~2 s from end-of-turn. Pre-synthesise the top agenda question during the patient's turn to hide latency.
- Barge-in: doctor VAD-detected speech cancels playback immediately (rule 3). Doctor utterances route to the transcript as doctor turns as today.
- Phase state machine in code (invitation → golden-minutes → open → closed → handover), with the LLM choosing content WITHIN the current phase, never the phase itself.

## Evaluation design (pre-register before building 7c)

Reuse the existing method: mock scripts already carry expected-clinical-content marking schemes; the patient side can be played by an actor from the script while auto mode conducts the interview.

Primary metrics, all computable from logs:
- **Elicitation coverage**: fraction of the script's marking-scheme content the auto interview surfaced (the auto-mode analogue of note coverage).
- **Talk-time ratio** (patient speaking time / total) and **time-to-first-question** — the golden-minutes compliance pair.
- **Open:closed ratio** over consultation thirds (should fall over time — the cone).
- **Interruption count** (system spoke while patient mid-turn) — target ~0.
- **Urgency latency** in auto mode: script-14-style buried red flags must still fire the alarm and halt questioning.
- **Face study (7b)**: face on/off as randomised arm across matched script runs — effect on actor disclosure length and content. (With real participants one day, this is an ethics-approved study; with actors it is a rehearsal of the method.)

## Explicitly out of scope for Phase 7

Sinhala voice interaction; AI examination of any kind; AI communication of findings/diagnosis/plan to the patient; unsupervised operation (no doctor present); real patients (as everywhere).

## Sequencing note

Phase 7 starts only after the current docket obligations are stable (Phase 5 adjudication/decision, Phase 0 recordings, Docker/demo packaging).

**Gate update 2026-07-25.** The **Phase 5 precondition is satisfied**: the step 6 adjudication completed 2026-07-25 and the fine-tune was deferred to v2 by owner decision the same day (`evals/2026-07-12_sinhala_asr_recordings_eval.md` § Step 6; decision header in `evals/2026-07-17_finetune_plan.md`). The **recordings precondition now means `05_epigastric_pain_en` only** — `01_chest_pain_si` is deferred alongside Phase 5, since it needs a Sinhala-speaking second reader and only feeds the paused Sinhala arm. **The remaining gate is therefore: `05_epigastric_pain_en`, Docker Compose packaging, and the two-role demo script.**

7a+7b make a strong demo milestone on their own and are the recommended first commitment; 7c is committed separately after 7a/7b review.
