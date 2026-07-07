# Urgency-escalation evaluation — CDS `urgent_actions` field

**Date:** 2026-07-07
**Component:** CDS engine (`app/cds.py`), MedGemma 27B text-it, Q4_K_M GGUF via
Ollama, temperature 0.0, fixed seed 42, structured-output JSON schemas,
two-call architecture (assessment + stateless urgency safety-check), prompts
as of the commit this evaluation ships with.
**Harness:** `scripts/evaluate_urgency.py` — replays each mock consultation
through the engine 4 turns at a time (as the live path would), recording every
`urgent_actions` payload. Raw per-update data: `evals/urgency_results.json`.

## Question under test

Does the CDS urgency alarm (`urgent_actions`) fire on time-critical
presentations, stay silent on routine ones, and clear once the transcript
shows the urgent step done or arranged?

**Success criteria:** fires on all 5 emergency scripts; silent on all 4
routine scripts; fired alarms clear by the final update (every emergency
script ends with the doctor arranging the action).

## Test set

| Script | Presentation | Expected |
|---|---|---|
| 01 | Exertional chest pain, cardiac risk factors (possible ACS) | **fire** (ECG this visit) |
| 02 | Febrile child day 3, dengue watch, no warning signs | silent |
| 03 | Diabetes + hypertension review, neuropathy | silent |
| 04 | Poorly controlled asthma, mild exacerbation, sats 98% | silent |
| 05 | Dyspepsia, alarm-symptom screen negative | silent |
| 06 | "Funny turn": resolved focal deficit, probable AF (TIA) | **fire** (same-day referral, ECG, aspirin) |
| 07 | Script 05's frame + melaena + postural dizziness (GI bleed) | **fire** (immediate admission) |
| 08 | Sudden breathlessness, pleuritic pain, swollen calf, OCP (PE) | **fire** (emergency transfer) |
| 09 | Script 02's child on day 4: drowsy, mottled, anuric (shock) | **fire** (ambulance now) |

Scripts 06–09 were written specifically for this evaluation as red-flag
variants; each contains an "expected urgent_actions" marking scheme in its
header. The emergency content is deliberately embedded in soft framing
(patient minimising in 06, a familiar routine frame in 07 and 09) so the
alarm has to respond to clinical content, not tone.

## Results

**8/9 scripts meet expectations.** All five emergencies fire and all five
clear once the transcript shows the action arranged. Three of four routine
cases are silent; the fourth (script 02) is the documented borderline-dengue
case below — a transient alarm that clears, recorded as a FAIL per the
marking scheme and deferred to end-of-project clinical review.

| Script | Expected | Fired | First fired | First action said | Cleared | Dx stability | Verdict |
|---|---|---|---|---|---|---|---|
| 01_chest_pain_en.md | fire | yes | turn 4/40 | Bedside ECG | yes | 9/9 | PASS |
| 02_febrile_child_en.md | silent | yes | turn 8/33 | Same-day dengue NS1 + FBC; same-day review | yes | 7/8 | **FAIL (false alarm — see below)** |
| 03_diabetes_review_en.md | silent | no | — | — | n/a | 9/9 | PASS |
| 04_asthma_en.md | silent | no | — | — | n/a | 7/7 | PASS |
| 05_epigastric_pain_en.md | silent | no | — | — | n/a | 10/10 | PASS |
| 06_tia_funny_turn_en.md | fire | yes | turn 4/39 | Hospital admission | yes | 9/9 | PASS |
| 07_gi_bleed_en.md | fire | yes | turn 8/31 | Hospital admission | yes | 6/7 | PASS |
| 08_pulmonary_embolism_en.md | fire | yes | turn 4/32 | Bedside ECG; pulse oximetry ± ABG; chest X-ray | yes | 6/7 | PASS |
| 09_septic_child_en.md | fire | yes | turn 4/27 | Hospital admission | yes | 4/6 | PASS |

First-fire timing versus the scripts' expected windows: 07 fires at turn 8,
inside its expected 8–14 (the melaena description); 09 at turn 4 (the
drowsiness is in the mother's opening lines); 06 at turn 4, ahead of its
expected 6–12 — the weakness-and-slurred-speech story is already on the
table by turn 4; 08 at turn 4, ahead of its expected 10–16, firing on the
sudden-breathlessness-plus-pleuritic-pain picture before the calf swelling
joins. Early firing on partial pictures is the intended fire-on-suspicion
behaviour. Differential stability stayed high throughout (worst case 4/6
updates unchanged, in the septic child where the picture genuinely
evolves). Raw per-update data: `evals/urgency_results.json`.

## Design notes: what it took to make the alarm work

The alarm went through five design iterations, and the failure modes are
worth recording because they will recur in any structured-output medical
LLM task.

**Attempt 1 — just add the field.** Schema gained `urgent_actions`; the
prompt said "almost always EMPTY... an alarm that rings for every patient
protects no one." Result: the alarm never fired, not even on the chest-pain
script — the anti-noise framing plus strict schema decoding made "empty" the
path of least resistance.

**Attempt 2 — concrete firing examples in the prompt** ("exertional chest
pain with cardiac risk factors → immediate ECG"). Still silent, even on a
fresh assessment with the full risk history in view.

**Diagnosis.** Asked the same question in *plain text* (no JSON schema), the
same model produced a long reasoning trace and then recommended exactly the
right escalation. The quantised MedGemma build reasons in a visible
scratchpad before answering; **schema-constrained decoding suppresses that
reasoning phase, and un-reasoned, the model defaults to the cautious
answer — an empty alarm.** The capability was present; the output format was
starving it.

**Attempt 3 — scratchpad inside the schema.** A `reasoning` field generated
first, plus a free-text `urgency_check` field generated immediately before
`urgent_actions`. This passed informal single-script checks and shipped —
then the first full evaluation run (all nine scripts, chained state)
returned **7/9 with two missed emergencies**: chest pain silent (having
fired that morning — temperature sampling made the alarm a coin flip), TIA
silent, and none of the three alarms that did fire cleared afterwards.

**Attempt 4 — remove the anchor, type the checkpoint.** Three changes:
temperature 0 with a fixed seed (an alarm must not be a coin flip);
previous-state feedback stripped of urgency fields (feeding back an empty
alarm anchors the model into keeping it empty); `urgency_check` converted
from prose to typed booleans, because tracing showed the model writing
"Immediate step demanded: ECG" *in the checkpoint text* while still
emitting an empty actions array — prose does not bind, grammar-constrained
booleans nearly do. Result: better (TIA and GI bleed passed) but the
chest-pain case still failed both directions: `time_critical_possible:
true` for seven consecutive updates with an empty actions array, and
`already_done_or_arranged` flapping back to false after the doctor
committed to the ECG.

**Attempt 5 (shipped) — one call, one job.** Every isolated urgency probe
all day had answered correctly; every failure occurred when urgency shared
a call with the assessment-revision task. So urgency became its own
stateless call — a "safety officer" that sees only the current transcript,
fresh each update — and all bookkeeping moved into code: the engine clears
the alarm deterministically when the check reports the step arranged, and
"arranged" latches for the session. One more prompt tightening was needed
after the split: the dedicated safety officer over-fired on chronic disease
(diabetic neuropathy → "urgent medication review"), fixed by defining
time-critical as *serious harm within hours to days* with explicit
negative examples ("could cause harm over months" is false).

Net cost: two model calls per update (~15–20 s total). The urgency
reasoning is kept in the assessment object as an audit trail (future
`CDSSnapshot` rows).

Two further prompt tightenings after the split, both from evaluation
failures: the safety officer initially recommended "full clinical
assessment and vital signs" as an urgent action on the routine febrile
child — the consultation itself, urgently recommended — fixed by stating
that history, examination, and routine same-visit tests are never
urgent_actions; and bare "dengue" in the fires-list was qualified to
"dengue WITH warning signs", since suspected uncomplicated dengue is
handled by routine same-day testing.

The arc of all five attempts, compressed: **the model's clinical judgement
was never the problem — every failure was an interaction between task
framing, decoding constraints, and state feedback.** Fire/clear decisions
needed isolation from the revision task, prose commitments needed to become
typed fields, and bookkeeping needed to move out of the model entirely.

## The residual case: borderline dengue warning signs (script 02)

After all fixes, script 02 still records a formal FAIL: a transient alarm
at turn 8 that clears later in the consultation. This one is documented
rather than tuned away, because inspection shows it is a clinical judgement
call, not an engineering defect:

- At turn 8 the transcript holds: day-3 fever, retro-orbital pain,
  **vomited twice this morning, not eating**, dengue in the lane. The
  model's reasoning explicitly cites WHO dengue warning-sign criteria —
  persistent vomiting is on that list, and two episodes plus anorexia is
  borderline.
- The "urgent" actions it proposes — same-day NS1 + FBC, same-day review —
  are **exactly what the script's doctor then does**. The disagreement is
  whether that plan is labelled routine dengue-watch care (the marking
  scheme's position) or urgent action (the model's).
- Further prompt-tuning to silence this case would mean teaching the
  safety officer to dismiss borderline warning signs in order to pass the
  test — the wrong direction for a safety component.

**Decision (project owner, 2026-07-07):** the marking scheme stands and
script 02 is recorded as a FAIL. The case is deferred to end-of-project
clinical review, where the options are: relax the expectation for 02 (a
transient, clearing, content-correct alarm on borderline warning signs is
acceptable), or encode a sharper threshold (e.g. WHO's "persistent
vomiting" as ≥3 episodes) with clinical sign-off. Until then the alarm
keeps its cautious behaviour on borderline dengue presentations.

## Held-out generalisation check (added after the main run)

The nine-script evaluation shares a weakness with the prompt it tests:
every emergency it contains is *named in the urgency prompt's examples
list*, so a passing score cannot distinguish clinical generalisation from
example-matching. One held-out case was therefore written for a condition
the prompt never mentions: **testicular torsion presenting as abdominal
pain in a 15-year-old** (`10_testicular_torsion_en.md`), reproducing the
classic trap — the true site emerges only on direct questioning of an
embarrassed teenager. Run once, deterministic settings (temperature 0,
seed 42), same harness. Raw data: `evals/urgency_heldout_10.json`.

| Script | Expected | Fired | First fired | First action said | Cleared | Dx stability | Verdict |
|---|---|---|---|---|---|---|---|
| 10_testicular_torsion_en.md | fire | yes | turn 4/38 | Immediate surgical referral | yes | 8/9 | PASS |

The alarm fired at turn 4 — before the scrotal findings are on the table —
on "sudden severe right lower abdominal pain waking a teenager from sleep,
with vomiting": acute-abdomen reasoning, not a lookup of the prompt's
examples. The final leading differential was testicular torsion, and the
alarm cleared when the doctor phoned the surgical registrar. n=1 held-out
case; a broader unlisted-condition sweep would strengthen the claim, but
the alarm demonstrably does not require its emergencies to be enumerated.

## Limitations

- Scripted text fed directly to the engine — no ASR noise. The live path
  will present garbled words; a follow-up evaluation should replay recorded
  audio through transcription first (blocked on Phase 0 recordings).
- One model, one quantisation, one prompt version; n=1 run per script,
  though temperature 0 + fixed seed make the run reproducible. Robustness
  across paraphrases of the same case is untested (a future eval could
  perturb the scripts).
- The evaluator of "correct" content is the script author's marking scheme,
  reviewed by a doctor (the project owner).
- Update cadence is per-4-turns; the live system triggers per-150-characters,
  so first-fire timing in production may differ by a turn or two.

## Reproduce

```bash
ollama serve &
uv run python scripts/evaluate_urgency.py
```
