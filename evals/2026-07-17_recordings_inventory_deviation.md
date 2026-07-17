# Recordings inventory + deviation report — consultations #66–70

**Date:** 2026-07-17
**Purpose:** pre-adjudication inventory of the five genuine two-voice
recordings made 2026-07-12 through the live app. Per-recording deviation
reports (stored WhisperX final-pass transcript vs the mock script) for
the owner to adjudicate references BEFORE any scoring. **No eval has been
run on these reports and none will be until the references are signed
off.**
**Raw word-level diffs:** `evals/deviation_diffs_2026-07-17/dev_6[6-9].txt`
(every divergent block, including trivial punctuation; the tables below
list only the deviations that matter).

## Inventory

Identity was established by checksum: each `data/recordings/
consultation_NN.wav` is byte-identical to its named copy in
`mock_consultations/recordings/`.

| Cid | Script | Duration | Status | ASR turns (script) | Avg conf | Audio quality |
|---|---|---|---|---|---|---|
| 66 | 01_chest_pain_en | 5.0 min | approved | 22 (40) | 0.78 | 16 kHz mono, RMS −21 dBFS, clip 0.001%, clean |
| 67 | 02_febrile_child_en | 5.5 min | approved | 19 (33) | 0.78 | clean |
| 68 | 03_diabetes_review_en | 6.8 min | awaiting_review | 27 (37) | 0.78 | clean |
| 69 | 04_asthma_en | 5.7 min | awaiting_review | 25 (25→30) | 0.75 | clean |
| 70 | 03_diabetes_review_si | 7.5 min | approved | 29 | **0.49** | clean audio; transcript invalid (see §70) |

All five recordings are audio-healthy: 16 kHz mono, speech levels around
−22 dBFS RMS, effectively zero clipping, dialogue-typical pauses. Turn
counts below script counts are adjacent same-speaker merges (expected).
Word-level similarity script↔ASR: 0.93 / 0.90 / 0.88 / 0.90 (66–69).

## Deviation reports (66–69, English)

Excluded as trivial throughout: punctuation and ellipses, case,
"alright/all right", "colour/color", digits vs number words ("twenty"→
"20"). Everything else is listed. **Adjudication question for each row:
did the reader actually say the script text (→ ASR error) or deviate
from the script (→ reference = what was said)?** Only listening can
settle that.

### #66 — 01_chest_pain_en (similarity 0.931)

| # | Script | ASR heard | Class |
|---|---|---|---|
| 1 | pushing the **three-wheeler** | "freewheeler" | noun, known problem class |
| 2 | to your arm, your **jaw**, your back | "your **toe**" | radiation sites — clinical |
| 3 | heart sounds are normal, **no murmurs** | "normal." (murmurs lost) | exam negative dropped |
| 4 | chest **wall** | "chest **fold**" | exam |
| 5 | left arm in a **smoker** | "in a **small curve**" | risk-factor statement garbled |
| 6 | Mr. **Perera** | "Pereira" | name |
| 7 | (end of recording) | extra "uh i like." after final thank-you | stop artifact |

Minor: "supplying"→"supplied in", "treat that"→"treat the",
"good. let's"→"good. go. let's". No low-confidence turns.

### #67 — 02_febrile_child_en (similarity 0.895)

| # | Script | ASR heard | Class |
|---|---|---|---|
| 1 | She's **six**. | "She's **sick**." | age lost — clinical |
| 2 | **Sanuki** (4×) | "Sanaki" ×3, "Sanathi" ×1 | name, inconsistent |
| 3 | water, **king** coconut (2×) | "**pink** coconut" | fluids advice |
| 4 | bleeding from the gums **when** brushing | "gums **vein** brushing" | bleeding screen garbled |
| 5 | complained about the **ears** | "about **years**" | symptom screen |
| 6 | if **it's dengue** / with **dengue** | "if it is **dangle**" / "with **denko**" | condition name, 2 of ~5 mentions |
| 7 | **only** [paracetamol] | "**clearly**" | loses the paracetamol-only restriction |

Minor: "hurts/hurt", "illnesses/illness", "giving/given",
"jeewani/jeevani", "day-three/day three", "so today is/today's".
Low-confidence: turn 18 (0.58) — the final goodbyes.

### #68 — 03_diabetes_review_en (similarity 0.879 — worst of the four)

| # | Script | ASR heard | Class |
|---|---|---|---|
| 1 | **gliclazide** (3 mentions) | "glycoside" ×2, "**glyphosate**" ×1 | drug name wrong at EVERY mention |
| 2 | the **losartan 50 for the pressure** | "the **lows have turned 50 for depression**" | drug AND indication mangled |
| 3 | new **cholesterol** tablet (recap) | "**nucleotide**" | drug class garbled |
| 4 | feeling **faint** | "feeling **pain**" | hypo symptom |
| 5 | was **8.4**. we want it below 7 | "was **84**." | HbA1c decimal lost — load-bearing number |
| 6 | the **reduced** [sensation] | "**rigorous**" | neuropathy finding |
| 7 | *"I'll go, doctor."* (patient turn) | (absent) | whole turn lost |
| 8 | alright **doctor** | "all right **professor**" | low-confidence turn 23 (0.31) |
| 9 | (after scripted close) | "you know i'm not very good at this. you know i don't read the script but i do naturally." | **off-script reader speech captured at the end** — trim or include? owner's call |

Minor: "hba1c"→"hpa1c", "start small fifteen"→"starts more 15", "plain
tea is"→"plain tears", "gotukola mallum dhal"→"gotu kola melun dal",
"bought"→"brought", reader restart "sorry" mid-HbA1c sentence.

### #69 — 04_asthma_en (similarity 0.899)

| # | Script | ASR heard | Class |
|---|---|---|---|
| 1 | breathing rate is **18** | "**80**." | respiratory rate 18→80 — clinically absurd, load-bearing |
| 2 | the **salbutamol** | "**salvator mold**" | drug name |
| 3 | **beclometasone** | "beclometzone" | drug name (near-miss) |
| 4 | my mother **says** | "my mother's **death**" | invented death |
| 5 | quiet for **years** | "for **a year**" | timeline |
| 6 | **chest pain**? no pain | "**just pain**" | negative-screen question garbled |
| 7 | worse after **dust** | "after **dusk**" | trigger → time of day |
| 8 | still **waking** with cough | "still **working**" | follow-up criterion |
| 9 | 98 **percent** | "98." | unit lost (context preserves meaning) |

Minor: "playing up"→"playing off", "needing"→"kneading",
"nadeesha"→"nadisha", "spacer a"→"spacer. the", "puff"→"up".
Low-confidence: turn 23 (0.44).

### Cross-recording patterns

1. **Drug names are the dominant material failure** even in the WhisperX
   large-v3 final pass on this accented audio: gliclazide 0/3,
   salbutamol 0/1, beclometasone 0/1, losartan 0/1 across 68/69 —
   the same class the live-path `WHISPER_INITIAL_PROMPT` was built for;
   the final pass has no such prompt. Worth considering before scoring.
2. **Two load-bearing numbers corrupted** (HbA1c 8.4→84, RR 18→80) —
   both in claims the ⚠ confidence-flag regex targets, but the flag only
   fires below 0.6 confidence; neither turn was low-confidence. The
   deterministic-flagging assumption ("low confidence marks the risky
   turns") did not hold for these two.
3. **End-of-recording contamination** in 66 and 68: off-script speech
   after the scripted close (worst: 68's "I don't read the script…").
   Decide whether references include it (as-spoken) or recordings are
   treated as ending at the scripted close.
4. Names drift (Perera, Sanuki, Nadeesha) — expected, low clinical
   weight, but they seed the patient-identity fields.

## #70 — 03_diabetes_review_si (special handling)

**A Sinhala-script reference exists and is already frozen.** Chain of
custody, verified today:

- `mock_consultations/03_diabetes_review_si.md` carries the as-spoken
  Sinhala+embedded-English reference turns (written before recording).
- `mock_consultations/recordings/refs/03_diabetes_review_si.txt` — the
  parsed reference (37 turns), drafted 2026-07-11, declared as-spoken by
  the owner's verbatim attestation 2026-07-12 and frozen unchanged.
- `evals/recordings_manifest_si.jsonl` embeds that reference
  **byte-identically** (checked today) — the pre-registered manifest is
  self-contained and ready.
- `refs/03_diabetes_review_si.terms.txt` — the 12-term curated
  English-term list, frozen 2026-07-12 before any model output was seen.
- The 2026-07-12 recordings eval already ran against exactly this
  reference; nothing further is needed from the owner for #70's manifest.
  (The transliteration adjudication worksheet remains pending,
  separately: `evals/adjudication_03_si_worksheet.md`.)

**Flag — the stored transcript and note for #70 are invalid.** The
finalisation pipeline forces `language="en"`, so WhisperX produced a
loose *English translation* of the Sinhala audio, including a degenerate
repetition loop (turn 3 repeats "I've been drinking a lot of water these
days" four times), average confidence 0.494 (vs ~0.78 for the English
recordings), and the last ~33 s of audio (450 s file, transcript ends
417 s) were never transcribed. **A SOAP note was generated from this
translated/hallucinated transcript and approved.** Recommendation:
exclude #70's stored transcript/note from any clinical-content scoring —
the recordings-eval path with the frozen Sinhala reference is the only
valid measurement route for this consultation. Whether to keep the
approved note (harmless test data) or re-finalise once a Sinhala path
exists is the owner's decision. This also confirms the HANDOVER note
that Phase 5 must swap the *final* transcription path, not just the
live one.

## What the owner needs to decide (blocking any scoring)

1. For each material row in 66–69: reader deviation (reference follows
   the audio) or ASR error (reference follows the script)? Listening
   required; the raw diffs give surrounding context.
2. End-of-recording off-script speech (66, 68): include in references or
   trim.
3. #70: confirm the frozen reference stands (nothing new needed), and
   decide the fate of its approved English-pipeline note.
