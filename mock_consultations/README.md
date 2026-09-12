# Mock consultations — the permanent test set

Scripted doctor–patient consultations for developing and benchmarking the
pipeline. **All patients, names, and clinical details are fictional.** English
versions first (per PROJECT_PLAN.md Phase 0); Sinhala code-switched versions
(Phase 5) and a UK private-GP series (CDS restraint + urgency) follow — see the
dedicated sections below.

**File suffixes:** `_en` English, `_si` Sinhala/English code-switched, `_uk` UK
private-GP series (English). Speaker labels are always Latin caps
(`**DOCTOR:**` / `**PATIENT:**` / `**MOTHER:**`) so `app/mock_scripts.py` parses
every script regardless of the spoken language.

## The five cases and why they were chosen

| # | Case | What it stresses in the pipeline |
|---|------|----------------------------------|
| 01 | Chest pain, 52 M | Urgency detection, broad differential (cardiac vs reflux vs musculoskeletal), red-flag reasoning |
| 02 | Febrile child (mother speaks), 6 F | Third-party history, dengue-season reasoning, safety-netting advice, paediatric dosing context |
| 03 | Diabetes + hypertension review, 58 F | Dense medical vocabulary (drug names, doses, investigations), chronic-disease SOAP structure |
| 04 | Asthma, poorly controlled, 24 F | Medication step-up logic, device/technique counselling, numeric findings (PEFR, sats) |
| 05 | Epigastric pain, 35 M | Alarm-symptom screening, lifestyle history (alcohol, NSAIDs), test-and-treat plan |

## Red-flag variants (06–09)

Written for the CDS urgency evaluation (`evals/`): four emergency
presentations, each with an **expected urgent_actions** marking scheme in its
header. Scripts 07 and 09 reuse the frames of 05 and 02 so the only material
difference is the red flags — a controlled comparison.

| # | Case | The alarm must catch |
|---|------|----------------------|
| 06 | "Funny turn", 72 M — resolved TIA, probable AF | Emergency hiding behind a minimising patient ("it's probably nothing") |
| 07 | Script 05's dyspepsia + melaena + dizziness — GI bleed | Red flags appearing inside a familiar routine frame |
| 08 | Breathless, pleuritic pain, swollen calf, 41 F — PE | A picture assembling across the history piece by piece |
| 09 | Script 02's child on day 4: drowsy, mottled, anuric — shock | Deterioration of a previously routine presentation |

Each script has an **Expected clinical content** section — the marking scheme.
When later phases generate a SOAP note, differential, or investigations list
from the recording, check it against that section.

## Sinhala code-switched versions (Phase 5)

`01_chest_pain_si.md` and `03_diabetes_review_si.md` are Sinhala/English
code-switched versions of the two English scripts — the way a real Sri Lankan
surgery sounds: the patient speaks mostly Sinhala with embedded English medical
and loan terms ("pressure eka", drug names, test names); the doctor mixes both.
01 is a lighter code-switch (chest pain vocabulary); 03 is the dense case (drug
names, doses, investigations) that stresses English-term retention hardest.

Each file contains, in order: the header noting which eval it serves; the
**Expected clinical content** marking scheme (identical to the English twin —
only the language differs); the **English-term list** the pre-registered ASR
metric needs (frozen before viewing any hypothesis); the **as-spoken reference
transcript** in Sinhala script (the parseable `**DOCTOR:**`/`**PATIENT:**`
turns); and a turn-by-turn **romanised reading guide** for whoever records them.

- **Serves:** the Phase 5 Sinhala ASR *recordings* evaluation, pre-registered in
  `evals/2026-07-10_sinhala_asr_benchmark.md` — specifically the code-switching
  per-script-class error metric and the mechanical English-term recall. The
  transliteration-vs-loss distinction is settled in that record's manual
  adjudication pass (strict script matching means a Sinhala transliteration of a
  drug name is a *mechanical* miss).
- **Reference `.txt` files:** draft references generated now from the scripts sit
  in `recordings/refs/<id>.txt` (turn texts concatenated, no speaker labels —
  live-path convention). Per the pre-registration, correct them to *what was
  actually said* before viewing any model output, then freeze.
- **Regenerate the drafts** after editing a script:
  ```bash
  uv run python -c "from app.mock_scripts import parse_script, as_live_transcript; \
    open('mock_consultations/recordings/refs/01_chest_pain_si.txt','w').write(\
    as_live_transcript(parse_script('mock_consultations/01_chest_pain_si.md')))"
  ```

## UK private-GP series (11–15, `_uk` suffix)

A London private-GP series testing two things the Sri Lankan set does not isolate:
**CDS restraint** (does the differential stay appropriately broad, or does the
model over-commit?) and **buried-red-flag urgency** (does the alarm fire when the
emergency is hidden in casual, minimised asides?). Each header names the eval it
serves and carries its **Expected clinical content** and **Expected
urgent_actions** marking schemes, written now, before any recording.

| # | Case | Role in the evals |
|---|------|-------------------|
| 11 | "Tired all the time", 34 F | Undifferentiated — **no** single diagnosis; differential must stay broad. Urgency alarm must **stay silent** (negative control). |
| 12 | Non-specific dizziness, 45 M | Undifferentiated, harder — stay broad *and* keep cardiac arrhythmia on the list *without* firing the alarm. Balanced restraint. |
| 13 | Classic migraine with aura, 29 F | **Differentiable control** — the picture is textbook, so narrowing confidently IS correct. Proves restraint = calibration, not blanket caution. Alarm silent. |
| 14 | Giant cell arteritis, 71 F | **Subtle emergency** — new temporal headache with jaw claudication + transient visual loss + scalp tenderness, each buried and minimised. Alarm must **fire** (sight-threatening). |
| 15 | Cauda equina syndrome, 40 M | **Subtle emergency** — saddle numbness + urinary hesitancy + bilateral leg symptoms hidden inside an ordinary "did my back in" story. Alarm must **fire** (function-threatening). |

Designed as controlled comparisons: 13 and 14 share a presenting complaint
(headache) with opposite correct behaviour; 11/12/13 are the urgency eval's
*negative* controls (must not fire) and 14/15 the *positive* ones (must fire) —
the same controlled-comparison logic the 05/07 and 02/09 pairs use.

**Wiring into the harnesses (deliberately not done yet).** The urgency harness
(`scripts/evaluate_urgency.py`) runs an explicit filename→expected dict, and the
notes harness globs `[01]*_en.md`; neither picks up `_uk.md`/`_si.md`
automatically, so these scripts do not perturb existing eval runs. To evaluate
them once recorded, add the `_uk` filenames to the urgency dict with their
`Should fire` values (11/12/13 → False, 14/15 → True). The differential-restraint
dimension (breadth / over-commitment) is a **new** metric — its pass/fail criteria
are written into each 11–13 header pending a harness of its own.

## Auto-mode actor briefs (16–18, `_auto` suffix)

A **different format**, written for Phase 7c auto mode. The 01–15 scripts write
out both sides of the conversation, which works when the doctor asks the
questions. In auto mode Alba asks them, so nobody can know in advance what will
be asked and a two-hander script is unusable. These files split the consultation
where auto mode splits it.

1. **The golden minutes.** A word-for-word monologue in the patient's voice, read
   aloud from the moment Alba's invitation ends. It fills the golden window,
   during which Alba may only encourage and may never ask. Each script is about
   220 words, roughly 90 s at conversational pace, matching the
   `AUTO_GOLDEN_MINUTES_S` default. Each contains one deliberate mid-narrative
   dry-up, so the golden encouragers ("Go on." / "Please, tell me more.") are
   exercised where a real patient would falter.
2. **A background paragraph.** Prose, not a checklist, so the actor improvises in
   character and stays consistent. They answer from it once the questions start,
   giving only what was asked.

Each file also carries its **Expected clinical content** and **Expected
urgent_actions** marking schemes, written before any run, exactly as 11–15 do.

| # | Case | Role in the evals |
|---|------|-------------------|
| 16 | Viral URTI demanding antibiotics, 47 M | **Difficult patient** — irritable, self-important, openly sceptical of the machine, pressing hard for an antibiotic he must not have. Restraint case: the alarm must **stay silent**. Carries an omission test — a minimised penicillin allergy he never volunteers. |
| 17 | Perimenopause, 48 F | **Common presentation, undifferentiated** — a scatter of symptoms the interview has to assemble. Calibration: name the menopause without dropping thyroid disease and iron deficiency. Alarm silent. Omission test — past migraine with aura. |
| 18 | Ectopic pregnancy, 31 F | **Emergency by omission** — the answer turns on asking when the last *normal* period was and whether she could be pregnant. She supplies a plausible wrong answer twice. Alarm must **fire**. |

**How the actor plays them** is written into each file as numbered steps, so the
brief handed to a role-player is one self-contained page per case.

**A note on the golden script and the parser.** Each monologue is written as
consecutive `**PATIENT:**` lines, so `app/mock_scripts.py` parses it like any
other script and `as_live_transcript` yields a frozen reference for the first 90
seconds of every run. Stage directions and the actor's instructions sit outside
the turn lines and are ignored by the parser. Nothing after the golden minutes
has a reference transcript, and cannot have one — the questions phase is
improvised by construction.

**Wiring into the harnesses (deliberately not done).** As with `_uk`, neither
harness picks `_auto` files up: the urgency harness runs an explicit
filename→expected dict and the notes harness globs `[01]*_en.md`. To evaluate
these once recorded, add them to the urgency dict with their `Should fire` values
(16/17 → False, 18 → True).

**Prereg status.** These three sit **outside** the frozen five `_uk` scripts named
in `PHASE_7C_EVAL_PREREG.md` § Run design. Runs made from them are logged as
pilot runs, not gate data, and the prereg stays untouched.

## Recording guidance

- **Two speakers, real voices** — doctor and patient read by different people
  (diarisation in Phase 2 assumes exactly two speakers). For case 02 the
  second speaker is the mother.
- **Quiet room, phones on silent.** A modest USB mic or a phone held between
  speakers is fine; consistent distance matters more than equipment.
- **Format:** WAV, 16-bit, 16 kHz or higher, mono is fine.
- **Pace:** natural conversation speed with normal pauses — do not
  over-articulate; the pipeline must cope with real speech.
- **Naming:** `01_chest_pain_en.wav`, `02_febrile_child_en.wav`, … placed in
  `mock_consultations/recordings/`.
- Small ad-libs and stumbles are good, not mistakes — leave them in.

Note: `.wav` files are currently gitignored. Once recordings exist we'll
decide how to store them (likely Git LFS) so the test set stays with the repo.
