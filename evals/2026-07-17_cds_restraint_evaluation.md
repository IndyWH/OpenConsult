# CDS differential-restraint evaluation — UK private-GP series (11–15)

**Date:** 2026-07-17
**Component:** CDS engine (`app/cds.py`), MedGemma 27B text-it, Q4_K_M
GGUF via Ollama, temperature 0.0, fixed seed 42, two-call architecture
(assessment + stateless urgency safety-check), prompts as of the commit
this evaluation ships with. Unchanged from the 2026-07-07 urgency
evaluation — no prompt was tuned for these scripts.
**Harness:** `scripts/evaluate_cds_restraint.py`, which imports and
reuses the per-script replay machinery of `scripts/evaluate_urgency.py`
(4 turns per update, as the live path would) and adds the
differential-breadth metric. Raw per-update data:
`evals/cds_restraint_results.json`.

> Correction to an earlier HANDOVER note: it said the `_uk` scripts wire
> in "once recorded". The urgency/CDS harnesses run on **script text**,
> not audio — that is how the 2026-07-07 nine-script evaluation ran — so
> these five needed no recording to evaluate. Recordings later add only
> the noisy-ASR arm (do the same conclusions survive real WhisperX
> output?). This record is the text-input baseline.

## Questions under test

The UK series was written as a controlled set for two dimensions the
earlier evals did not isolate:

1. **Urgency (buried red flags + false-alarm restraint).** Do 14 and 15
   fire when the emergency is buried in casual, minimised asides amid a
   benign-sounding history? Do 11 and 12 stay silent on undifferentiated
   presentations with no red flag?
2. **Differential-breadth restraint (new dimension).** Does the
   differential's breadth match the evidence? 11 and 12 must stay
   **broad** (undifferentiated); 13 must **narrow confidently** to
   migraine — the calibration control that proves restraint is *matching
   confidence to evidence*, not blanket caution; 14 and 15 must let the
   **emergency lead** the differential.

## Test set

Each script carries an Expected clinical content + Expected
urgent_actions marking scheme in its header, written before this run.

| Script | Presentation | Urgency | Restraint (final differential) |
|---|---|---|---|
| 11 | "Tired all the time", 34F — undifferentiated | silent | stay **broad**, none high-confidence |
| 12 | Non-specific dizziness, 45M — undifferentiated | silent | stay **broad**, retain cardiac, none high |
| 13 | Classic migraine with aura, 29F — differentiable | silent | **narrow** confidently to migraine |
| 14 | Giant cell arteritis, 71F — buried emergency | **fire** | GCA **leads** |
| 15 | Cauda equina, 40M — buried emergency | **fire** | cauda equina **leads** |

13 and 14 are a deliberate controlled pair: **same presenting complaint
(headache), opposite correct behaviour** — 13 narrows to a benign
diagnosis and stays silent, 14 escalates a sight-threatening one.

## The restraint metric — design and choices

The assessment schema has no explicit "leading" flag; differentials are
a ranked list (most-likely-first), each graded likelihood
high/moderate/low. So commitment is read from those two signals, on the
**final** update (full information, where calibration should be clearest),
with the whole trajectory retained in the JSON:

- **breadth** `n_differentials` — length of the final list.
- **`n_high`** — how many conditions are graded "high" likelihood.
- **`top_condition` / `top_high`** — the leading condition and whether it
  is graded "high"; `top_high` is the operational definition of a
  confident commitment.

Mapped to each script's own marking scheme:

- **11, 12 (must stay broad):** PASS iff `n_differentials ≥ 5` **and**
  `n_high == 0` — the schemes' "≥5 categories, none high-confidence /
  leading".
- **13 (must narrow confidently):** PASS iff the leading condition **is**
  migraine **and** `top_high` — the scheme's "confidently identifies
  migraine (with aura) as the leading diagnosis". Refusing to commit, or
  spurious breadth, is the FAIL — the mirror image of over-commitment.
- **14, 15 (emergency anchors):** PASS iff the emergency concept is the
  **leading** dx. Their primary pass/fail is the urgency arm; the
  restraint arm checks the differential also surfaced the emergency as
  the working diagnosis.

Concept matching is keyword-based on the lowercased leading condition
(migraine; giant cell / temporal arteritis / gca; cauda equina).

**Why the confidence-grade dimension and not breadth alone.** Breadth
alone would have *passed* script 11 (it lists 5 differentials). The
failure is entirely in the grading — which is exactly what the `n_high`
clause exists to catch. Measuring list length without the grade would
have missed a real calibration error; this run validates including both.

**Choices flagged as limitations.** (1) We count list entries, not
semantically-deduplicated categories — a model listing two overlapping
labels would score breadth 2; inspected by eye, none of the five tripped
this. (2) Commitment is read from the top item's grade, not from prose —
the schema has no leading flag, and the grade is what the review UI shows
the doctor, so it is the honest signal. (3) The final-update verdict is
the pass/fail; premature over-commitment mid-consultation is *reported*
(the trajectory) but not failed on, since the acceptance criteria are
written against the complete history.

## Results

**Urgency arm: 5/5. Restraint arm: 4/5.** The one restraint failure
(script 11) is a genuine, subtle over-commitment analysed below.

### Urgency arm

| Script | Expected | Fired | First fired | Cleared | Verdict |
|---|---|---|---|---|---|
| 11 tired-all-the-time | silent | no | — | n/a | **PASS** |
| 12 dizziness | silent | no | — | n/a | **PASS** |
| 13 migraine | silent | no | — | n/a | **PASS** |
| 14 giant cell arteritis | fire | yes | turn 4/31 | yes (by 28) | **PASS** |
| 15 cauda equina | fire | yes | turn 8/27 | yes (by 24) | **PASS** |

Both emergencies fire and clear once the doctor arranges the step. **14
fired at turn 4** — earlier than the scheme's "mid-history, when the
visual disturbance is mentioned" expectation: the engine escalated on
*new temporal headache in a 71-year-old* before the jaw-claudication /
transient-visual-loss cluster fully assembled. That is appropriate
caution on this presentation (new headache over 50 is itself a GCA red
flag), not a false alarm — the diagnosis is correct. **15 fired at turn
8**, matching the scheme: after the saddle numbness and urinary symptoms
surface amid the mechanical-back-pain history — the engine resisted the
strong benign base rate. First actions were on-target: for 14, "urgent
ESR and CRP; urgent ophthalmology/rheumatology referral"; for 15,
"immediate referral for spinal MRI".

### Restraint arm

| Script | Mode | # dx | # high | Leading dx | Lead conf | Verdict |
|---|---|---|---|---|---|---|
| 11 | broad | 5 | **2** | Iron deficiency anaemia | high | **FAIL (over-committed)** |
| 12 | broad | 5 | 0 | Orthostatic hypotension | moderate | **PASS** |
| 13 | narrow | 4 | 1 | Migraine | high | **PASS** |
| 14 | lead | 5 | 2 | Giant cell arteritis | high | **PASS** |
| 15 | lead | 5 | 2 | Cauda equina syndrome | high | **PASS** |

## Findings

**1. The 13-vs-11 contrast is the calibration result.** Both end with
the leading condition graded "high" — the identical mechanical signal —
but 13 PASSES and 11 FAILS, because the metric applies each script's own
scheme: high-confidence migraine on a textbook aura history is correct
narrowing; high-confidence iron-deficiency anaemia on an undifferentiated
TATT history is over-commitment. This is precisely what the restraint
dimension was built to distinguish, and it distinguishes it. 13 also kept
the list appropriately short (4) with migraine leading from turn 4 and
held it stable to the end — confident and stable, not vague.

**2. Script 11's failure is subtle and is a boundary case.** The engine
kept the list correctly **broad** — all five finals (iron-deficiency
anaemia, depression/anxiety, hypothyroidism, sleep apnoea, CFS/ME) are in
the script's marking scheme — but graded **two** of them "high"
(iron-deficiency anaemia from turn 4, depression/anxiety added at turn
12) and never revised them down as the negatives accumulated (no weight
loss, no night sweats, preserved appetite). So the breadth is right and
the *members* are right; only the confidence is miscalibrated. Both
high-graded conditions are clinically defensible top candidates for TATT
(the script gives heavy periods → iron loss, and flat mood), which is why
this reads as genuine early over-commitment rather than a wild miss — and
why, like the script-02 dengue boundary case, whether the strict "none
high-confidence" rule should stand is a clinical-judgement call for the
owner. **Deferred to the docket.**

**3. Script 12 is the clean restraint pass — balanced, not merely
cautious.** Five differentials, none high-confidence, and critically it
**retained "Presyncope (Cardiac)" in the list without firing the urgency
alarm** — the exact behaviour the scheme asked for (don't dismiss the
cardiac possibility, don't escalate it absent a red flag). Restraint here
is holding two things at once.

**4. The emergencies lead correctly with appropriate secondary
commitment.** 14 leads GCA "high" with polymyalgia rheumatica also
"high" (the correct overlap); 15 leads cauda equina "high" with lumbar
disc herniation "high" (the correct mechanism). High confidence on a
buried emergency, reached from minimised asides, is correct commitment —
the same signal that fails on 11 passes here because the evidence
warrants it.

## Verdict

The urgency dimension generalises to the UK series without any prompt
change: buried red flags (14, 15) are caught and cleared, and
undifferentiated presentations (11, 12) do not false-alarm — 5/5. The new
restraint dimension is 4/5, with the single failure being a real,
narrow, and clinically-arguable over-commitment on the hardest
undifferentiated case, flagged for owner adjudication rather than
silently passed or failed. The metric behaved as designed: it separated
correct confident narrowing (13) from incorrect early narrowing (11) on
an identical mechanical signal.

## Limitations

- n = 1 per script, deterministic settings (temp 0, seed 42); this
  measures the engine's fixed behaviour on these texts, not variance.
- Clean script text, not ASR output — the recordings arm (noisy WhisperX
  transcripts) is the pending second half, and the 2026-07-17 recordings
  deviation report shows drug/number corruption that could move a
  differential; whether these verdicts survive that is untested.
- Breadth is list length, not deduplicated categories (see metric
  design); the confidence signal is the top item's grade, not prose.
- Self-consistent judge-free scoring: the verdicts are mechanical against
  the frozen schemes, so there is no LLM-judge unreliability here — but
  the schemes themselves encode clinical choices (e.g. 11's strict "none
  high-confidence") that the owner may revise.

## Reproduce

```bash
uv run python scripts/evaluate_cds_restraint.py   # 11–15, both arms
uv run python scripts/evaluate_urgency.py         # canonical 10-script urgency (unchanged)
```
