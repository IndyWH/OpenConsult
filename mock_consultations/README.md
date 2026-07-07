# Mock consultations — the permanent test set

Five scripted doctor–patient consultations for developing and benchmarking the
pipeline. **All patients, names, and clinical details are fictional.** English
versions first (per PROJECT_PLAN.md Phase 0); Sinhala versions follow in
Phase 5.

## The five cases and why they were chosen

| # | Case | What it stresses in the pipeline |
|---|------|----------------------------------|
| 01 | Chest pain, 52 M | Urgency detection, broad differential (cardiac vs reflux vs musculoskeletal), red-flag reasoning |
| 02 | Febrile child (mother speaks), 6 F | Third-party history, dengue-season reasoning, safety-netting advice, paediatric dosing context |
| 03 | Diabetes + hypertension review, 58 F | Dense medical vocabulary (drug names, doses, investigations), chronic-disease SOAP structure |
| 04 | Asthma, poorly controlled, 24 F | Medication step-up logic, device/technique counselling, numeric findings (PEFR, sats) |
| 05 | Epigastric pain, 35 M | Alarm-symptom screening, lifestyle history (alcohol, NSAIDs), test-and-treat plan |

Each script has an **Expected clinical content** section — the marking scheme.
When later phases generate a SOAP note, differential, or investigations list
from the recording, check it against that section.

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
