# HANDOVER

The record for OpenConsult v2: decisions and measurements, newest first.
It stays under 500 lines. Older entries move to HANDOVER_ARCHIVE.md.
The spec is V2_SPEC.md. The record for v1 is the HANDOVER.md on the main branch.

## 2026-10-28. Stage 8a: the referral letters, benched four times, then wired

Built in five sessions on 28 Oct 2026. The plan was reviewed by Cowork the
same day (three points; all are in). The bench of the two new prompts ran
first and stopped at its figures four times; the owner ruled after each
run (spec 15.12, rulings 14 to 17), three sentences of the letter prompt
changed after the first, four after the second, one after the third, and
five rules of the check were made finer; the fourth ruling let the figures
stand and wired the page from the patch held since the first run. The
report is STAGE8A_REPORT.md in the private log folder. The room run is the
owner's, still to come: the steps are in the report, and his reading of
the letters is the judge of them (V1_LESSONS, the twelve, point 1).

The spec, committed five times, not a character changed: 6e46f3d
(sha256 c5833101..., the brainstorm of 28 Oct), 731aa30 (5d5a374a...,
ruling 14), be3e933 (67d60a1c..., ruling 15), a7ade2d (1d8529a7...,
ruling 16), 8cecb12 (56e9dd5f..., ruling 17).

The rulings it builds, one line each (spec 15.12):
- 1: one letter per specialty, any number per consultation; code writes
  the salutation (Dear Consultant and the item's title), the Re line
  (name, date of birth and sex as the consultation ran with them) and
  the sign-off (Yours faithfully, the one user's title and name); the
  model writes the body only.
- 2: after Approve the review page shows the referral items: the ones
  the note states, then, under a line that they are the model's
  suggestions and not advice, the ones it suggests; the list call runs
  once per approved note, at the first opening after Approve; code sorts
  the items by the cited Plan line and the specialty's words
  (referrals.sort_items), never the model.
- 3 and 8: openconsult/prompts/letter.prompt.txt sha256 220d61f0...
  (as ruling 16 left it; b2e5e816..., d10ccaa4... and 49c1f652... were
  the three earlier texts of the day) and referrals.prompt.txt
  5eab5bb5..., each the approved block byte for byte with one line
  break, proven by hash and by cmp against Cowork's copies. The two
  frames are fixed words in letter.frame.txt (SPECIALTY: {specialty}, a
  blank line, APPROVED CONSULTATION NOTE: and {note}) and
  referrals.frame.txt (APPROVED CONSULTATION NOTE: and {note}); the
  letter call sees each Assessment entry's words replaced by
  letter.withheld.txt ([assessment withheld from referral letters]), the
  numbers unchanged. The patient line opens both messages (R11); the
  background block reaches neither (D24).
- 4: the check in code (consult/letter_check.py), per sentence against
  the lines its paragraph cites: a heading and an Assessment line are
  never citable; a number must be in the cited lines (the age excepted;
  a figure inside a word counts); a result verb over a line that only
  plans the test is an upgrade; the model's placeholder anywhere fails
  the sentence; an expectation sentence stands only on a line holding
  Patient's expectations and a colon, else dropped; an allergy sentence
  stands only on a cited line holding the word, else dropped and
  counted; a failed sentence becomes the placeholder, one for a run; the
  letter is refused under half grounded, LETTER_GROUNDED_HALF = 0.5
  beside CITATION_HALF.
- 8: name a specialty, two fields and one control, a named item and its
  letter with no list call.
- 10: the bench, below. 11: the note lines sent are a named part of the
  record, in referral_list.note_lines and letter.note_lines.
- 14 to 17: the four benches and the rulings on them, below.

The record (6.5): schema version 7 brings a version 6 folder forward with
every row kept: referral_list (the approved note it was made from, the
call, the note lines sent, the failure), referral_item (kind stated,
suggested or named; specialty, title, reason, urgency, the lines cited,
position), letter (its item and number, the call, engine, version, tag
and digest, the prompt's hash, the note lines sent as masked, both
bodies, the check's detail, the four counts, refused, the failure, the
seconds, the doctor's refusal), letter_edit (before and after),
letter_approval (one per letter, the text). Delete takes them with the
consultation, counted in the audit line.

The bench (ruling 10; bench/letters.py and letter_marks.py): four
approved notes (A, B by reference to 7b's cases; C dysphagia and D polyp
with psoriasis, made for 8a), 13 chains each (A1 to A3 at temperature 0,
B1 to B10 at 0.5), one list call a chain and one letter call per
specialty, through the door with the app's own numbering, frames and
check; vLLM 0.31.0 at the local port, the model of 3c (digest
2096d38d...), thinking off in every request and none in any reply; about
three minutes a run; 260 letter calls over the four runs, one failed
(a loop of bracketed line numbers to the 2,500-token limit, 13.8 s,
stored as too_long). The five marks, fixed before the first run and
never loosened: M1 no letter refused and no failed call, 13 of 13; M2
the placeholder absent in at least 12 of 13; M3 no Assessment citation
and no number outside the cited lines, 13 of 13; M4 no expectation
sentence for the one note without the line, 13 of 13; M5 the stated
list as the note states it, 13 of 13. The four runs side by side, chains
holding the mark of 13 (run 1 the morning prompt and the first check;
run 2 after ruling 14; run 3 after ruling 15, the finer check; run 4
after ruling 16, the allergy rule):

| mark | A 1 | A 2 | A 3 | A 4 | B 1 | B 2 | B 3 | B 4 | C 1 | C 2 | C 3 | C 4 | D 1 | D 2 | D 3 | D 4 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M1 | 13 | 13 | 13 | 12 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 |
| M2 (12 needed) | 12 | 8 | 0 | 9 | 13 | 13 | 10 | 13 | 13 | 2 | 13 | 13 | 11 | 9 | 10 | 13 |
| M3 numbers | 12 | 8 | 1 | 9 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 12 | 10 | 10 | 13 |
| M3 Assessment | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 |
| M4 (A only) | 13 | 13 | 13 | 13 | | | | | | | | | | | | |
| M5 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 12 | 12 | 12 | 12 | 13 | 13 | 13 | 13 |

Marks held: 13, 11, 11, 13 of 17. The fourth run, as numbers: held, M1 on
B, C and D, M2 on B, C and D, M3 on B, C and D, M4 on A, M5 on A, B and
D; missed, M1 on A (12 of 13, the one failed call), M2 on A (9 of 13),
M3 on A (9 of 13 without a number outside the lines), M5 on C (12 of 13,
the list call's empty answer on seed 5, the fourth time). Every mark held
in every chain at temperature 0, the app's own sampling (10.4). The
longest finished letter reply was 505 tokens in 2.88 s against the
letter job's 2,500 tokens and 120 s; the longest list reply under 300
tokens in 1.5 s against 1,500 and 60 s.

The owner's four rulings of the day, in plain words:
- 14, after the first run (13 held): nothing invented reached a letter,
  but C's letter never said the suspected-cancer referral was urgent,
  and A's letter gave the medicines as they were before the Plan changed
  them. Three sentences of the letter prompt changed (the urgency
  said; the medicines as the Plan leaves them); no rule of the check
  changed; run again.
- 15, after the second run (11 held): the two things were now written,
  but every C letter wrote the haemoglobin with a unit the note does not
  give, the upgrade rule replaced C's true results sentence in 11 of
  13, and the model's own placeholder inside a sentence went uncaught.
  Four sentences of the prompt changed (no unit the note does not give,
  no reckoning; a started medicine with its dose; citations in
  note_lines only; the placeholder as a sentence of its own) and four
  rules of the check (the upgrade per sentence; the placeholder
  anywhere; a figure inside a word; a unit's figure); run a third time.
- 16, after the third run (11 held): C clean and A's medicines right,
  but six letters carried an allergy status the note does not hold,
  which no rule read; the invention R4 exists to stop. One sentence of
  the prompt changed (allergy status only where a note line records it,
  no placeholder for a missing one) and one rule of the check (an
  allergy sentence stands only on a cited allergy line, else dropped and
  counted); run a fourth time, and the ruling on wiring made on what
  reaches the page, not on M2 and M3 alone.
- 17, after the fourth run (13 held): nothing invented reached a letter;
  of 65 letters 34 state an allergy status and every one rests on a
  cited note line that records it, the one written for a note without
  an allergy line dropped by the new rule; no unit the note does not
  give, no bracketed fragment, no old dose, no stopped medicine given as
  taken, no Assessment line cited, no letter refused. The misses are
  four chains of A at temperature 0.5, each a placeholder the doctor
  sees beside its line before Approve, one failed call said plainly, and
  C's one empty list. The figures stand, no fifth run; M2 and M3 on A at
  0.5 are the record of how well this model cites; the page is wired.

Left for the brainstorm of 8b as prompt matters with their own bench,
what the check cannot read:
- the letter prompt: C's urgent suspected-cancer referral unnamed in
  2 of 13 chains (0 of 13 in the third run) when the concerns line is
  cited instead of the Plan line;
- the letter prompt: D's dermatology letter opening with the nose, the
  other letter's problem, in 12 of 13;
- the letter prompt: a medicine the Plan starts named in 1 letter of 39,
  the sentence that asks for it not reaching the model;
- the referrals prompt, unchanged all day: an empty list on C's seed 5
  in all four runs; and the expectation pattern's pronoun form.

The proof on this machine (stage8a_proof.py on a copy of 7b's data
folder, through the app's own pages; stage8a-proof.log; counts only): the
folder came from version 6 to 7 with every row kept; vLLM chosen. A final
consultation with no approved note shows no section and makes no list
call. The owner's consultation of 20 Oct (30 numbered lines, 25 citable):
one list call at the first opening and none at the second, 1.0 s, the
stored note lines the list text byte for byte, the request the patient
line and the frame with no block; 1 stated and 2 suggested items. The
letter drafted against vLLM in 2.1 s: engine, version, tag, digest and
the prompt file's hash stored, the note lines sent the masked text byte
for byte, the request the letter message byte for byte; 14 sentences, 14
grounded, the body as the check left it equal to the check run again on
the stored model body. An edit kept what stood before; Approve wrote the
assembled text, the copy text is that text alone, every post after is
refused on its control. Name a specialty: no second list call, one letter
call, the typed title in the salutation. On a made consultation whose
made note holds a planned line, a made letter got each thing the check
gives it: the paragraph citing Assessment alone became the placeholder,
a number not in its line the placeholder beside its kept sentences, a
planned test written as a result the placeholder with the planning
sentence kept, an allergy sentence with no allergy line dropped and
counted (9 sentences, 5 grounded, 3 placeholders, 1 dropped, shown in
the counts sentence); a made letter 0 of 3 grounded was refused with the
reason on the page, no body, Approve refused.

What was built, by file: consult/letter_rows.py (the rows), referral_note.py
(the numbering, the masking, the two messages), referrals.py (the list
call, the sorting by code, the named item), letter_check.py and letter.py
(the check, the draft, assemble); web/letters.py, templates/_letters.html
and letter.html, static/letters.js; bench/letters.py and letter_marks.py;
Door.engine_name. The constants: LETTER_GROUNDED_HALF = 0.5 (ruling 4;
v1's shape); the jobs' limits, referrals 1,500 tokens and 60 s, letter
2,500 tokens and 120 s (the plan); CHAINS = 13 and MARK_PLACEHOLDER_ABSENT
= 12 (ruling 10). Every sentence shown to the user is in words.py, the
section's, the letter's (LETTER_COUNTS now with the allergy count) and
ten audit events, drafts for the owner to correct on screen; the
placeholder in the prompt and the one the check writes are one string,
pinned by a test.

Sizes (5.4): no function over 80 lines; no file over 600 but words.py at
721, accepted under 5.4 as 7a's review did. The suite: 711 before commit
16, 723 from commit 17 (ten page tests, the no-block case in
test_background, one on the allergy count shown), green three times
before the last commit. Nothing pushed.

What this stage has made untrue: README's so far and CLAUDE.md's running
and bench lines, fixed in this commit; 6b's entry, moved to the archive;
stage-prompts/STAGE_08A.md, whose rule 4 gives the letter prompt's first
hash and whose rule 5 says a missed mark stops the stage, both
superseded by rulings 14 to 17, kept as the record of the prompt as
given; the plan's items 4, 5, 8 and 9, as the report lists. The spec's
15.12 says Done when you see: not yet, and the 15.4 row's done-when
sentence waits on the owner's room run; both are Cowork's.

What 8b should know: the review page is the draft note, then the
Referral letters section, then the controls, the warnings and alarms, the
transcript with the player, the model line, Delete; the letter's own page
is /consultations/{cid}/letters/{lid}; the guideline panel lives on the
live page. The stored parts by name (ruling 11): referral_list.note_lines
and letter.note_lines hold the numbered note as each call read it,
model_call.request the request as sent, tied by call_id;
letter.model_body the paragraphs with their note_lines;
letter.check_detail each sentence's verdict and reason and
allergies_dropped. The embedding worker of the bench kit sits in
openconsult/bench/shared/embedding2 with its own pyproject and lock,
started by bench/shared/commands.py; 8b brings it into the app as a
worker of its own, started where the room check put it (15.8, ruling
32). The check cannot read a sentence with no number that the note does
not support, an omission, or which problem a letter is about: those are
the doctor's eye, or a prompt matter. The model can loop; the token
limit stopped it, the clock did not have to.

## 2026-10-21. Stage 7b: the bench of 8.6, and the background to the model

Built in two sessions on 21 Oct 2026. The plan was reviewed by Cowork the
same day (three points; all are in). The first session ran the bench and
stopped at its figures, as the prompt said; the owner ruled (spec 15.11,
ruling 11); the second committed the ruling and finished the wiring from
the held patch. The report is STAGE7B_REPORT.md in the private log folder.

The owner's room run of 7a, 21 Oct 2026, his words: Previous note
appeared on the right hand side. Good note. Good diarisation.

The bench (8.6; 15.11, ruling 6 and the detail The bench of 8.6): the two
approved cases, each in two arms, with the block and without, 13 chains
each (A1 to A3 at temperature 0, B1 to B10 at 0.5), the two calls sent
together, cut every 4 turns and the end; vLLM 0.31.0 at the local port,
the model of 3c (xbill9/gemma-4-26B-A4B-it-qat-q4_0-w4a16-ct, digest
2096d38dad51a19b8e982b44241c47102a8bbb00, context 16,384), thinking off
in every request and no thinking text in any reply; 287 calls an arm,
no failed call, no failed chain; about 8 minutes an arm. The block in the
arm with it is the case's earlier note parsed by earlier.sections_of and
laid out by background.build_block, placed by messages.with_background,
so what was benched is what the app sends. The table, by background-score
from the stored results alone:

| case | arm | chains | fired | named hypoglycaemia | both | named subarachnoid | typical pass s |
|---|---|---|---|---|---|---|---|
| A_hypo | with | 13 | 13 | 13 | 13 | 0 | 3.1 |
| A_hypo | without | 13 | 13 | 13 | 13 | 0 | 2.77 |
| B_headache | with | 13 | 13 | 0 | 0 | 13 | 3.0 |
| B_headache | without | 13 | 13 | 0 | 0 | 13 | 2.94 |

The marks, fixed as numbers in the plan before the run:
- A1, case A with the block, both at least 12 of 13: 13 of 13. Held.
- A2, case A without the block, both fewer than with it: 13 of 13
  against 13 of 13. Missed; by the owner's ruling, not judged.
- B1, case B with the block, fired 13 of 13: 13 of 13. Held.
- B2, case B without the block, fired 13 of 13: 13 of 13. Held.

The owner's ruling, in plain words (ruling 11): the figures stand and
there is no second run. Case A was written so that today's words alone
would leave the list wide, and for this model they did not: the first
four turns put hypoglycaemia first in every chain at the first pass,
with the block or without, so there was nothing left for the background
to help with. That is a limit of the case, not a finding against the
block. The background did not mislead (case B's migraine history
softened nothing) and did not slow the pass (0.1 to 0.3 s longer for
about 300 words more of input). Mark A2 is recorded as not judged on
this material, and the block is wired on A1, B1 and B2. What 8.6 asked
and what was shown: that the background does not mislead and that the
alarm still fires are shown; that it helps where it should is not shown
by this bench, because its case did not need help.

Owed to a later stage: a bench of its own with a case A that needs the
history, such as the same patient 12 days after starting dapagliflozin
with vomiting, abdominal pain and fast breathing and no mention of her
tablets, where ketoacidosis belongs on the list only with the note; the
preclinical study's cases may supply it. The bench needs nothing more:
run --background and background-score, as CLAUDE.md gives them.

What was built:
- messages.with_background: the message as with_patient built it, split
  at its first blank line; the patient line, a blank line, the block, a
  blank line, the frame as it was (ruling 5; R25). cds_pass.messages
  and run_pass take the block; the bench and the app pass it.
- At Start, when the switch is on, web/consult.begin builds the block
  once by background.block_for and hands it to the Consultation, which
  gives it to every pass; off, or no note, hands None. The alarm and the
  assessment get it in both passes of a consultation; the note call and
  the label check never do (8.4; D24; R4); the stored request holds the
  message as sent. Proven on a copy of 7a's throwaway folder with the
  made doors: the stored alarm request of a second consultation under
  patient 3, with two approved notes, was the patient line, the block
  and the frame byte for byte, 1,825 bytes with the block 1,413; the
  label check and the note held none; with the switch off no request
  held it; the record check printed counts only.
- The switch's label at Start is now SWITCH_USES_AS_BACKGROUND (Use the
  earlier notes as background for the model and show them on your
  screen.); 7a's label stays in words.py as its record. The mark of 8.5,
  EARLIER_NOTES_IN_USE (Earlier notes in use.), at the top of the
  decision support panel from the page state's background flag while
  the block is sent, and at review beside the model's last differentials
  when the row says the switch was on and notes were listed, read from
  the row alone (the plan review, point 2); the copy text, the approved
  text and the print carry no mark. Two new sentences, both in words.py.
- The small fix of 15.11: Consultation.close joins the Stop thread and
  shuts the pass pool waiting; the lifespan closes every running
  consultation, so the app joins the thread at shutdown; the two page
  tests of test_stop.py close their consultations before the database;
  one test pins that no thread of a consultation outlives it.
- The bench side (commit 3 of the first session): the 7b case list with
  the earlier note and its date, run --background, bench/background.py
  and background-score, each with its test on made results. No case
  text, note text or reply enters the repo.

691 tests, green three times before the last commit, none skipped, no
thread exception warning. No function over 80 lines; no file over 600
but words.py at 654 (accepted under 5.4 by 7a's plan review). CLAUDE.md
98 lines. The private word check printed nothing before every commit.
The three background files are byte for byte as ruling 5 gives them
(sha256 48875847...2fe3, 79b41aaf...08b7, c00401b4...2b4e), proven before
the wiring commit and before the last; the four prompts, their frames,
their forms and the patient line are untouched.

The Ubuntu check of run 17 (the push of 60bc652) failed the small fix's
test once, 1 of 691: after close() the table still held consultation-1_0,
the idle pool worker of an earlier test's consultation with the same id
in its own database, whose app never ran its shutdown and whose pool
waited on the garbage collector; the other machines collected it in time.
The fix, 21 Oct: close() ends by waiting, bounded by CLOSE_WAIT_S (5 s),
until no thread named stop-{id} or consultation-{id}_ is alive; every app
built in a test is shut down at its end as the lifespan does it
(conftest); and a deleted consultation is closed before it is dropped
from the running table, the same leak in the room. Proven with the
collector switched off: 42 such threads on the table before the test,
then none; the test's assertion is as it was.

What stage 8 should know: Alba's area and question calls take the same
block in the same place by with_background (ruling 5, last sentence;
D24). The three background files and with_background are the whole of
what a model reads for the background; the switch's stored setting
decides it. The review page's mark reads the row, never the record.

Made untrue by this stage: README's line that the earlier notes reach
the doctor's screen only and the background waits for its bench, and
CLAUDE.md's bench lines without --background and background-score, both
fixed in this commit; the 7a entry's lines that no call carries the
block and that the switch's label says the notes are shown on your
screen, now history; the words of ruling 6 that case A's words alone
leave the list wide, which did not hold for this model on this script
(ruling 11 records it). The entries of 6a (20 Oct) and 15 Oct move to
the archive to keep this file under 500 lines.

## 2026-10-21. Stage 7a: patients and earlier consultations, the patient side

Built and proven on 21 Oct 2026 in one session. The plan was reviewed by
Cowork the same day (six points; all are in). The report is
STAGE7A_REPORT.md in the private log folder. The room run is the owner's,
still to come: the steps are in the report. 7b, the background to the
model after its bench, is not built here.

The rulings it builds, one line each (spec 15.11):
- 1: the home page is the Patients page: the rows waiting at Stop and
  for review at the top, the one search box (part of a name with case
  and accents folded; digits as the number exactly and, failing that, as
  part of a name; a date of birth typed as a date), the list last seen
  first with the five columns; the number is the row's id.
- 2: the patient's page corrects each of the three on its own control,
  patient_change keeping before, after, when and by whom, audited; every
  consultation keeps the three as copied at its Start, shown on its own
  page from its own row with one dated line when they were corrected
  after it; the live consultation holds the row it started with (R11).
- 3: the Start screen of a patient with an approved note lists the notes
  (number, date, assessment or first plan entry) and the switch, on by
  default, labelled as showing the earlier notes on your screen; the
  setting and the numbers listed are stored with the consultation; no
  list and no switch without an approved note.
- 4: the earlier-notes pane in the live page's side column, below the
  assessment, never the fixed zone: the last three approved before the
  consultation started, folded, the approved text of note_approval
  opened in place with citations stripped; hidden when the switch is
  off; earlier.js only shows and hides.
- 5: openconsult/prompts/background.frame.txt (sha256 48875847...2fe3),
  background.note.txt (79b41aaf...08b7) and background.cut.txt
  (c00401b4...2b4e, the plan review's point 1), together every word a
  model reads for the background; the block built by
  consult/background.py from earlier.panel_notes, cut on the laid-out
  text after the last whole entry that fits; no call carries it, and a
  test proves it over a whole consultation (8.4).
- 7: audio_retention_days in the setting table, default 90, 0 keeps, on
  the Thresholds section, audited from what to what; the sweep at
  start-up and every 24 hours in the lifespan's own task, deferred 60 s
  while a consultation is stopping; one audio_deletion row and one audit
  line per sweep that deleted; after Stop's final step the WAV becomes
  Ogg Opus (mono, 32 kbps, voip), decoded back and checked within
  DURATION_TOLERANCE_S, the WAV removed only then; a failure leaves the
  WAV with its reason on the page; with no converter at all nothing is
  attempted, the row says why and the start's decision line stands.
- 8: consult/deletion.py, the rows in one transaction children first,
  then the file, one audit line of counts and no words; refused when not
  final or already gone; Delete patient only when no consultation is
  left; both ask once on the page; the orphan sweep reports at start-up.
- 9: consult/alarms.py matches an alarm's reasoning and actions to the
  differential names with matching.normalise and a contiguous whole-word
  run; marked in the live state and on the review page beside the
  assessment with the alarm in a dialog; one alarm line per alarm key at
  its first firing with its state then, acknowledged from the audit
  log, a press playing from the last line the pass had read; two counts
  on Approve.
- 10: 7a the patient side; 7b after the bench.

What was built (the app without the bench 11,254 lines of Python, from
10,019 at 6b, and 1,243 of pages and scripts; the tests 13,135 lines):
- schema version 6: patient_change; on the consultation the three
  details it ran with, earlier_notes_shown, earlier_notes,
  recording_format, conversion_failure, audio_deleted_at;
  audio_deletion; setting. A version 5 folder comes forward with every
  row, the details filled from the patient as it stands. The database
  gains a transaction context.
- patients/patients.py (the list, the fold, the search, the
  corrections); web/patients.py and patient.html; patients.html as the
  home page; consult/earlier.py, background.py, opus.py, retention.py,
  deletion.py, alarms.py; settings/stored.py; earlier.js and
  alarmdialog.js; the converter as a decision element with its row on
  This machine on every machine.
- imageio-ffmpeg 0.6.0 is a dependency: a static ffmpeg 7.0.2 with
  libopus for Linux (x86_64, aarch64), macOS (x86_64, arm64) and Windows
  (x86_64), found by uv; the computer's own ffmpeg on the path is the
  fallback. On this machine the room check found the package's.

The constants, each with its source:
- BACKGROUND_NOTE_MAX_WORDS 400: the longest note of 5c part two held 228
  words of entries, the longest of the 6b bench 317; a margin over both.
  A design choice; the room may move it.
- DURATION_TOLERANCE_S 0.1: a made 1 s and 7.37 s WAV decoded back from
  Opus to the sample on this machine; five Opus frames of 20 ms.
- SWEEP_EVERY_S 86,400 and RETRY_S 60 (ruling 7); DEFAULT_RETENTION_DAYS
  90 (v1's).

My proof, 21 Oct 2026, on a copy of 6b's throwaway database and
recordings brought forward to version 6, the made doors of the suite,
the package's converter: the Patients page listed the four patients last
seen first and found patient 3 by part of the name, by the number and by
the date of birth; the Start screen for patient 3 listed consultation
3's approved note with the switch on; consultation 5 started with the
switch's setting and the three details stored; the live page showed the
pane with note 3 below the assessment; a made pass whose alarm named
Made-up condition A marked it red; no call carried the block (alarm,
assessment, label check, note); after Stop the 192,044-byte WAV became a
10,511-byte Opus file that decoded to 2.00 s against 2.00 s fed, served
as audio/ogg, with three press-a-line controls; the review page showed
the red mark, one alarm line and the two counts (2 warnings, 1 alarm);
a correction of patient 3's date of birth left consultations 3 and 5
showing 21 Oct 1990 with the dated line; Delete on consultation 4
removed 5 lines, 4 live lines, 1 pass, 3 model calls, 7 warnings and the
352,044-byte file, with the audit line of counts; the sweep at 0 deleted
nothing and at 1 day deleted the three recordings of 20 Oct (10,456,132
bytes) and left the new Opus file; the Log page showed each line. 682
tests, green three times before the last commit, none skipped. No file
over 600 lines but words.py at 648 (accepted under 5.4 by the plan
review, point 2); no function over 80. CLAUDE.md under 100 lines. The
private word check printed nothing before every commit. Nothing of any
recording entered the repo.

Made untrue by this stage: the home page's Waiting for review list as
its own page (home.html is gone; the rows sit at the top of the Patients
page); 6b's lines that the audio-gone line becomes true in stage 7, now
true; 6a's line that the retention clock and deletion are stage 7, now
built; the home sentence, README's so far and CLAUDE.md's running lines,
fixed in this commit; the 3c entry of 13 Oct moves to the archive.

Seen in passing, not touched: the approved text of 6b's proof holds an
entry whose citation was stripped to leave a space before its full stop
(the copy text of 6b), which the Start screen's line and the block show
as it stands; the block's reading of an approved text is byte-faithful
to what was approved.

For 7b: cds_pass places the block between with_patient's line and each
frame, a blank line each side, for both calls, with the stored request
holding it; background.block_for(notes, patient_id, started_at,
consultation_id) gives the block or None; the switch's setting is stored
with the consultation, so 7b reads consultation.earlier_notes_shown to
decide whether the block is sent (ruling 3); the second label goes in
words.py beside SWITCH_SHOWS_ON_SCREEN and the Start screen picks it
once the bench's pass is recorded; the mark of 8.5 goes on the
assessment pane of the live page; earlier.panel_notes is the one reader
of the approved notes for the pane and the block alike.
