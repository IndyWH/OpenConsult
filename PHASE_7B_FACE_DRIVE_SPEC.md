# Phase 7b — the face drive, rewritten

**Dated 2026-08-01. Written after consultation 463, where the owner saw a
curious face at the start turn into a smiling face that stayed smiling
while the patient described chest pain and a family history of heart
disease.**

Companion to `PHASE_7B_KINDALIVE.md` (the owner's original build brief)
and `PHASE_7_SPEC.md` § Stage 7b. Those stay authoritative on what 7b is
*for*. This file records what was wrong with the drive, what replaced it,
and the numbers.

---

## 1. What was wrong

Three faults, one of them the whole story.

**The dominant input was a metronome.** `FaceDriver.on_patient_audio()`
was called from the live loop on every PCM frame that arrived while the
system itself was not speaking. There is no voice-activity test and no
speaker test on that path, so the call did not mean *the patient is
talking*. It meant *the microphone is on*, which is true for the whole
consultation. The driver rate-limited it to one injection every two
seconds, so the face received a steady tick for as long as the
consultation ran.

**That tick was wired to the wrong chemical.** Each tick injected
dopamine. In the vendored `FACE_WEIGHTS`, dopamine is the largest single
term in `lip_corner_pull` (0.40) and in `cheek_raise` (0.45) — it is the
smile. Attention and alertness live in adrenaline
(`eyelid_upper_raise` 0.55, `brow_outer_raise` 0.50). Using dopamine for
*someone is talking* was a category error, and the consequence was that
the longer the consultation ran, the harder the face smiled.

**Nothing came back down.** Chemical half-lives in the vendored engine
run from 20 minutes (dopamine) to 4 hours (serotonin). Inside a
15-minute consultation, decay is negligible. The engine has saturation
dampening on repeated impulses from one source, which slows the climb but
does not reverse it. The face was therefore, to a good approximation, a
function of elapsed time.

**And the affect hint could not compete, and pointed the wrong way.**
`distressed` injected oxytocin +0.15 (smile weight +0.15) and cortisol
+0.06 (smile weight −0.25): a net effect on the smile of about +0.008.
A distressed patient made the face smile very slightly *more*.

### Measured, not inferred

The real `FaceDriver` and the real vendored engine were run offline
against a simulated 15-minute consultation on a manual clock
(`sim.py`, `trace.csv`).

| | start | 15 min |
|---|---|---|
| dopamine | 0.40 | 0.91 |
| `lip_corner_pull` (smile), affect hint on | 0.31 | 0.61 |
| `lip_corner_pull`, affect hint never fired | 0.31 | 0.56 |

The control run is the important one: with the affect hint disabled
entirely the smile still climbs almost as far. Roughly five sixths of
what the owner watched happen was the metronome, not the patient.

The *curious* face at the start is the same mechanism in reverse.
`brow_inner_raise` carries an **inverted** dopamine term — it fires on
the deficit *below* baseline. At the opening there is no accumulated
dopamine while resting adrenaline still lifts the outer brow and upper
eyelid: raised brows, no smile, which reads as curiosity. As dopamine
accumulates the deficit disappears and the smile takes over. Curious then
smiling is exactly what the code predicts.

The `clinical` arm did not escape this. Its caps are one-sided
(`min(max(value, neutral), neutral + band)` — a muscle may rise above
neutral but never fall below it), so the smile rose until it hit its band
ceiling and then sat there: a permanent mild smile instead of a growing
one.

---

## 2. What replaces it

### 2.1 Nothing integrates

Affect is a **state**, not an event. The driver holds a target chemistry
for the current affect, ramps toward it with a fixed time constant, and
then holds it. Attention is a **bounded level** in [0, 1] with an attack
and a release, not an accumulating impulse.

No repeating stimulus can push any chemical upward without limit, because
there is no accumulator. The face cannot drift with time. This is a
structural property, not a tuning choice, and it is asserted by test
(criterion C1): the face at 15 minutes equals the face at 2 minutes, to
within 0.01 on every muscle, with the affect held and the room active
throughout.

The practical consequence is worth stating: even if the activity floor is
set wrongly and the room reads as permanently active, the failure is
cosmetic — the eyes sit slightly open — not a return of the 463 defect.

### 2.2 Attention rides adrenaline

`on_speech_activity()` replaces `on_patient_audio()`. It is called when a
frame's RMS clears a floor, and it counts **both speakers plus the
assistant's own voice** (owner decision, 2026-08-01: the face is a
listening presence for the patient, and it is at least as relevant while
the doctor — or Alba — is the one talking, which is also what Stage 7c
will need). Attention raises adrenaline only, by `FACE_ATTENTION_GAIN`,
which lifts the upper eyelids and outer brows: the face looks up and
attends. It touches no smile-driving chemical.

**Corrected 2026-08-01b.** The floor's default value, `1e-4`, is the one
**three** existing surfaces already use, not one: the silence-nudge
activity detector and the dead-mic pill, both in `app/static/live.html`,
and `SOUND_CHECK_SILENT_RMS` in `app/speech.py`. Starting there means the
face and the nudge cannot disagree about when the room is quiet.

`FACE_ACTIVITY_RMS` is nevertheless **deliberately its own setting, and
it is allowed to diverge from those three**, because it answers a
different question: the other three ask whether the microphone is alive,
and the face asks whether anyone is speaking. Without this note a later
tidy-up will consolidate all four to one constant and quietly change what
the face does.

### 2.3 The engine's dynamics are deliberately unused

The vendored `NeurochemicalEngine` remains the state holder and
`project_face` remains the projection from chemistry to the twelve FACS
muscles. Its **decay, cross-chemical interactions and saturation are not
used**: their time constants are an order of magnitude too slow for a
consultation, which is the root of the original defect and cannot be
tuned away without editing vendored files.

Stated plainly, because it changes what kindalive is in this project:
after this change kindalive supplies the FACS projection, the renderer
and the config; the clinical behaviour lives in our targets, in our
repository, where it can be reviewed. That is a loss of emergent
plausibility and a gain in reviewability, and on a clinical surface the
trade is the right way round. The vendored files remain untouched at
their pinned commit `a29bcf7`; `NOTICE` needs no change.

### 2.4 The mouth belongs to speech

`face3d.js` draws an open mouth above `jaw_open` 0.10 and layers its
syllable-rate flap on top while the assistant speaks. Kindalive opens the
jaw for excitement, which is right for a companion robot and wrong here:
at any real dopamine level the emotional term alone crosses the
threshold, so a resting face appears to be about to speak. `jaw_open` is
capped at `JAW_REST_CAP` (0.08) in **both** modes. This is not an
expression cap — `jaw_open` carries no emotional information that the
smile and brow do not already carry.

### 2.5 The clinical arm can express concern again

With the drive corrected, the old pin list left the clinical arm able to
show warmth but not concern, which is the original defect in miniature.
`brow_inner_raise` and `lip_corner_depress` move from PINNED to BANDED,
and the band becomes **two-sided** (`neutral ± band`) rather than
one-sided, so a muscle may now fall below neutral as well as rise above
it. The arm still limits how much sadness a clinical face may show.

**This is an owner decision and it is one line to revert** — the two
muscle names in `BANDED_MUSCLES`. It affects the comparison arm only;
`full` remains the default and is what runs live.

---

## 3. The calibration

The five target chemistries were fitted by bounded least squares against
the vendored `FACE_WEIGHTS`, to a written brief for each affect, with
hard caps on the anger and disgust muscles. The brief came first; the
numbers were fitted to it.

### Amended 2026-08-01b — the resting face is kindalive's own

**Owner decision, 2026-08-01.** `neutral` is no longer a resting
expression that was designed here. It is now the vendored
`SPECIES_DEFAULTS` from `vendor/kindalive/engine/chemicals.py`,
untouched, and `PRESET_BASELINES` is set to the same values so the
deficit-driven muscles measure from kindalive's own resting point rather
than from an invented one. **Most of a consultation sits at neutral, and
that state should be borrowed, not designed.** The other four affects
moved only as far as keeping the ladder ordered around the new neutral
required. `FACE_DRIVE_VERSION` is `2026-08-01b`, so the audit rows
separate the two builds.

Two consequences, both recorded honestly:

- **C2 and C3 now test the MOUTH CURVE** — `lip_corner_pull` minus
  `lip_corner_depress` — rather than the smile muscle alone. That is what
  `face3d.js` draws the mouth from, so it is what a person actually sees;
  a smile muscle read on its own can fall while a deepening frown makes
  the visible mouth worse than the number suggests. **This is a stricter
  and more faithful criterion, not a looser one:** the ordered gap rose
  from 0.03 to 0.05 and the distress requirement from 0.12 to 0.20.
- **C5's warmth floor now EXEMPTS neutral, and that is a relaxation.**
  The floor of 0.18 was written here, and neutral's warmth is now
  whatever kindalive rests at (0.12, from oxytocin 0.20). The floor still
  binds on the four states this project authors. It was relaxed because
  the requirement changed — the resting face is borrowed now — and not
  because the code failed to meet it.

| affect | the face it is asked to make |
|---|---|
| positive | warm open smile, relaxed brow |
| neutral | kindalive's own resting chemistry, untouched — borrowed, not designed |
| anxious | alert and steady: eyes a little wider, smile mostly gone |
| low | gentle concern: inner brows up, mouth soft, warmth high |
| distressed | clear concern: brows up over the render threshold, mouth gently down, warmth highest of all |

Two things the fit had to respect that are not in the weights matrix:

- **`face3d.js` only draws nine of the twelve muscles.** `cheek_raise`,
  `nose_wrinkle` and `lip_press` are computed, sent, and ignored by the
  renderer. Calibrating against them is calibrating against nothing. They
  are still held inside their caps, because a physical face may read them
  later.
- **The brow bar has a render threshold.** `drawMask` draws it only when
  `brow_lower > 0.18` or `brow_inner_raise > 0.28` or
  `brow_outer_raise > 0.4`. A concern face below 0.28 is invisible, so
  `distressed` and `low` are calibrated above it deliberately.

Resulting steady states, `full` mode, room active (measured 2026-08-01b
from the passing test run; **curve** is what the mouth is drawn from):

| affect | smile | frown | curve | brow inner | eyelid upper | pucker (warmth) | jaw |
|---|---|---|---|---|---|---|---|
| positive | 0.57 | 0.02 | +0.55 | 0.03 | 0.24 | 0.25 | 0.08 |
| neutral | 0.26 | 0.06 | +0.20 | 0.04 | 0.15 | 0.12 | 0.08 |
| anxious | 0.25 | 0.19 | +0.06 | 0.14 | 0.29 | 0.25 | 0.08 |
| low | 0.17 | 0.29 | −0.12 | 0.30 | 0.22 | 0.31 | 0.08 |
| distressed | 0.13 | 0.35 | −0.22 | 0.30 | 0.21 | 0.34 | 0.03 |

The mouth now crosses from up to down between `anxious` and `low`, which
the smile column alone never showed. Warmth **rises** as the patient's
state worsens across the four authored affects. That is the listener's
response the original mapping was reaching for, now actually implemented:
the face leans in, it does not fall apart. Neutral sits below them at the
vendored resting warmth, by the amendment above.

Every number in `AFFECT_TARGETS` is a first calibration against a written
brief, not a validated setting. The mock-patient feedback round is still
what decides whether these read correctly to a person.

---

## 4. Acceptance criteria

Written before the numbers were tuned. All thirteen pass.

| | criterion |
|---|---|
| C1 | no drift: the face at 15 min equals the face at 2 min within 0.01, affect held, room active |
| C2 | the mouth CURVE (`lip_corner_pull` − `lip_corner_depress`) ordered positive > neutral > anxious > low > distressed, each gap ≥ 0.05 |
| C3 | distress turns the mouth down by ≥ 0.20 of curve against neutral — the 463 defect, inverted |
| C4 | the concern brow renders (> 0.28) for distressed and low |
| C4b | no concern brow (≤ 0.10) when the patient is positive or neutral |
| C5 | warmth is greatest where most needed, and never below 0.18 in the four authored affects (neutral exempt — see § 3) |
| C6 | no anger or disgust in any affect: brow_lower ≤ 0.15, nose_wrinkle ≤ 0.15, lip_press ≤ 0.25, eyelid_lower_tighten ≤ 0.20 |
| C7 | 90% of the way to a new affect within 20 s |
| C8 | attention lifts the eyelids by 0.03–0.15 between a quiet and an active room |
| C9 | deterministic: identical input, identical output |
| C10 | concern, not grief: the mouth curve turns down by no more than 0.25 |
| C11 | the clinical arm can still order the smile and move the concern brow |
| C12 | the resting mouth stays closed (jaw_open ≤ 0.10) in every affect |

---

## 5. What is unchanged

- **The urgency alarm is still not wired to the face**, for the reason
  the module docstring has always given: an alarmed face would tell the
  patient something the doctor has not decided yet.
- **Face off is still a first-class state.** No driver, no `face_state`
  traffic, card absent from the DOM. It is the control arm of the CARE
  study and nothing here touches it.
- **Determinism.** No model call, no randomness, no GPU on this path. The
  clock stays injectable and the tests still drive it.
- **`full` remains the default.**

## 6. Still open

- The mock-patient feedback round, unchanged as the thing that decides
  whether these expressions read correctly to a person.
- `FACE_ACTIVITY_RMS` wants calibrating from a real room recording; its
  default is the `1e-4` the silence-nudge detector, the dead-mic pill and
  `SOUND_CHECK_SILENT_RMS` already share, and it is deliberately free to
  diverge from all three once calibrated (§ 2.2).
- CDS assessments are still not persisted — **partly closed 2026-08-01**
  by the `PATIENT_AFFECT` log line (commit `316cbe4`), which is what made
  consultation 465 explicable at all.
  - **Now visible:** every affect verdict, one line per assessment, with
    the session id, the audio position, the value, and whether it changed
    — logged whether the face is on or off, and distinguishing an absent
    field from the value `neutral`. Enough to reconstruct an affect
    timeline for a consultation from the journal, and enough to see a
    model that never moves off one verdict.
  - **Still not:** it is a log, not a record. It is not in the database,
    not joined to the consultation row, not queryable beside the
    transcript, and it goes when the journal rotates. The rest of the
    assessment — differentials, questions, urgency — is still not
    persisted per revision at all, so a past consultation still cannot be
    **replayed** through the face with its real timeline. That remains a
    small table, and it is also evidence for the paper.
