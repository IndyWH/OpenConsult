# Phase 7b — kindalive integration: the owner's build brief

**Dated 2026-07-25. These are the project owner's own conclusions from
reviewing the upstream repository, and he has asked that they be followed
as written when the work is built.** They existed nowhere but a chat
window before this file; recorded here so they are not lost.

Companion to `PHASE_7_SPEC.md` § Stage 7b, which stays the authoritative
statement of what 7b is *for*. This file is the *how*.

---

## Upstream assessment

**[github.com/smithandrewjohn/kindalive](https://github.com/smithandrewjohn/kindalive)** — MIT licensed.

Judged **high quality** on review: `mypy --strict` in CI, roughly 181
tests, and a coverage gate. It is itself a human-plus-Claude-Code
project — it carries a `CLAUDE.md` and `claude/*` branches.

## Architecture as understood

A **simulated-neurochemistry engine**: 8 chemicals with true half-life
decay, feeding **stateless projections** to 8 emotions and a **12-muscle
FACS `FaceState`**. That state renders as a retro LED dot-matrix face via
a single dependency-free canvas module of roughly 10 KB at
`web_assets/face3d.js`.

Its API is:

```js
initFace3D(divId);
window.kindaliveFace.setTargets(payload);
```

It self-animates blinking, saccades and breathing. `setSpeaking` drives a
mouth flap suitable for TTS lip-sync.

---

## Build decisions — all the owner's

### 1. VENDOR the zero-dependency core

Vendor `engine/`, `emotions/`, `expression/face.py`, **pinned to a
specific upstream commit**. It is a single-author project and MIT permits
vendoring. **Record the pinned commit hash when the work starts.**
Attribution goes in `NOTICE`.

### 2. SKIP the upstream LLM interpreter entirely

Inject `ChemicalImpulse` objects **deterministically** from consultation
events instead — or from a single affect-hint field piggybacked on the
existing CDS assessment JSON.

Rationale: zero additional model calls on the 4090, reproducible, and
consistent with this project's temperature-0 / seed-42 discipline for
clinical outputs.

### 3. A `[clinical]` personality preset

Create a `[clinical]` preset in kindalive's TOML config, starting from
its **stoic** preset: high GABA and serotonin baselines, near-zero
adrenaline with **shortened half-lives**, damped reactivity.

**Add hard caps in our own impulse-mapping layer as well**, so the face
stays inside a narrow professional band regardless of what the engine
produces. Belt and braces deliberately: the preset expresses the intent,
the caps enforce it.

> The owner explicitly wants **limited emotional range — a clinical
> presence, not an expressive companion.**

### 4. No new transport

Drop `face3d.js` into `app/static` and push payloads over the **existing
WebSocket**. No new transport.

### 5. Styling

A small **bedside-device panel** inside the existing cream theme, with
kindalive's mood accent recoloured to our palette. See `docs/mockups/`
and `DESIGN_SPEC.md`.

> **Note (updated 2026-07-28):** `DESIGN_SPEC.md` and the approved
> mockups (`docs/mockups/live_mockup.html` / `review_mockup.html`) are
> now IN the repository. The original spec was lost — it existed only in
> Downloads and a deleted chat — and the committed DESIGN_SPEC.md is a
> reconstruction (its header says so; the code and mockups are
> authoritative where they disagree).

### 6. Expect a calibration pass

Upstream weights are tuned for an **expressive companion robot**, so they
will not be right for this out of the box. Budget a calibration pass
against our own tests.

---

## Research design attached to 7b

**Face on versus face off, as a randomised arm across matched script
runs**, with actors rating the system using an adapted **CARE** measure
(Consultation and Relational Empathy).

This is *why* `PHASE_7_SPEC.md` requires face-off to remain a
**first-class runtime state**: it is the **control arm of a study**, not
a fallback for when the face misbehaves. Anything that degrades face-off
into a second-class path invalidates the comparison.
