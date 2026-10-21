# HANDOVER

The record for OpenConsult v2: decisions and measurements, newest first.
It stays under 500 lines. Older entries move to HANDOVER_ARCHIVE.md.
The spec is V2_SPEC.md. The record for v1 is the HANDOVER.md on the main branch.

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

## 2026-10-20. Stage 6b: the live consultation, from Stop to approve

Built and proven on 20 Oct 2026 in two sessions (the first cut by the
usage limit after the player's commit). The plan was reviewed by Cowork
the same day (five points; all are in). The bench of the note prompt ran
first and the owner ruled on it the same day. The report is
STAGE6B_REPORT.md in the private log folder. The room run is the owner's,
still to come: the steps are in the report.

The rulings it builds, one line each (spec 15.10):
- 3: the note prompt is one file, openconsult/prompts/note.prompt.txt,
  the approved block byte for byte, sha256 0666c026...284207, proven by
  hash and by cmp against Cowork's copy; the answer form needs at least
  one subjective entry.
- 4: beside the assessment stand the differentials of the last shown
  pass, read from cds_pass, under a heading that says they are the
  model's and not part of the note; the copy text, the approved text and
  the browser's print of the page hold the note alone.
- 5: the frame around the transcript is the bench's words,
  note.frame.txt, sha256 44f10e08...1e0637 (the label check's bytes);
  the three speaker words live in consult/note.py and the bench reads
  them there, so no word a model reads is new.
- 6: the form has text and turns and nothing else; an entry's words are
  stored and shown letter for letter; the app holds no list of names and
  no replacement.
- 8: v1's citation check as plain functions, CITATION_HALF 0.5; an entry
  that cites no real line is kept and marked; a note in which fewer than
  half the entries cite a real line is refused with the count and its
  entries discarded.
- 11: the review page in the busy GP's order; draft again only after an
  edit, never by itself, the earlier draft kept; Approve audited, the
  note read-only after; Refuse recorded.
- 12: every keystroke on the page is use; an unsaved edit holds off the
  quiet refresh.
- 16: 6b from Stop to approve. The player of 8.8 as D51; the recording
  route to the logged-in user on this computer only (15.6 ruling 6).

What was built (the app without the bench 10,019 lines of Python, from
9,130 at 6a, and 1,018 of pages and scripts; the tests 12,106 lines):
- schema version 5: note_draft (stamp, prompt hash, what the model read,
  citation count, refused, failure), note_entry (as written and as it
  stands, the turns cited and the lines they hold), note_edit,
  transcript_edit (words, label, undo, swap, each with what stood before),
  note_approval (one at most, with the approved text), note_refusal;
  transcript_line gains set_by_doctor. A version 4 folder comes forward
  with its rows.
- consult/note.py: the turns by the bench's rule over the lines as they
  stand, the citation check, the copy text, the last shown differentials,
  the draft; consult/note_rows.py the rows; the note as the last stage of
  Stop after the gate, the stopping page saying Drafting the note, the
  page going to the review page; 6a's final transcript page folded into
  the review page.
- web/review.py with review.html, review.js, player.js and print.css;
  use.js widened to any element marked data-use; the recording route; the
  copy text served as note.txt; Draft the note for a final consultation
  that has none; the home page's list of consultations waiting for
  review, one row each by the latest state.
- the bench's note job reads the app's prompt, frame, form and limits and
  its own two note files are gone (spec 5.1); speech-calls takes --kind.

The constants, each with its source:
- NOTE_MAX_TOKENS 3,000 and NOTE_TIMEOUT_S 120: the bench's figures; the
  rehearsal's longest note was 1,284 tokens and 8.2 s.
- CITATION_HALF 0.5: v1's, a design choice and not a measurement; the
  room may move it.

The bench of the note prompt, 20 Oct 2026, on vLLM 0.31.0 with the room
of 3c, thinking off, 28 page notes and 8 script notes, two rounds at
temperature 0 and seed 42, the baseline v1's prompt on 11 Oct: rule 1 (no
reply cut by a stray quote) held, 0 of 36 beside 0; rule 2a (no real drug
of the model's own on the made recording's AssemblyAI page) held, 0 and 0
beside 0 and 0; rule 2b (the garbled name written as heard with unclear)
not judged on this material, since the only garbled mention sits on a
page where the drug is also spoken rightly three times and no page holds
a drug garbled everywhere; rule 3 (key facts not found from the scripts)
held, 12 beside 20; rule 4 (figures not spoken) held, 33 and 6 beside 34
and 8. Kept by the owner's ruling of 20 Oct. The typical note call 4.67 s
beside 4.83. One finding: the note on the tied pair's page of 477, round
2, ran to the 3,000-token limit with a turns list that never ended (its
round 1 answered in 445 tokens); if it recurs in the room the cure is a
limit on the turns list in the answer form, benched on its own, not a
change to the prompt's words. Rule 2b stays for 5e. The detail's wording
of rule 2 was corrected by the plan review before the run.

The owner's room run of 6a, 20 Oct 2026, consultation 1 on his own data
folder: word to page 3.03 s typical, pass 2.61 s typical, Stop to final
19.6 s. His words: OpenConsult was spot on; alarms came at the right
time.

My proof of 6b, 20 Oct 2026, on a copy of 6a's throwaway data folder
brought forward to version 5, vLLM up: consultation 3 (94 lines, 19 pass
rows) had no note; Draft the note answered in 4.6 s with 26 entries, all
26 cited, 145 line presses; five differentials beside the assessment; 47
on the Approve control (24 warning rows and 23 labels the check changed);
a press on line 30, which starts at 76.0 s, had the recording at 78.9 s
three seconds later; note.txt 33 lines, the four headings and the
entries' words, no differential, no bracketed number, no model line;
Approve wrote the approval row (1,115 characters, the copy text
unchanged), left no entry or line form on the page, and refused a second
Approve and a line edit on the control; the Log page shows Note drafted
and Note approved; the home list went from four to three. Consultations
1, 2 and 4, refused by the gate, show no note and Draft the note disabled
with the reason. 648 tests, green three times before the last commit,
none skipped. No file over 600 lines, no function over 80. CLAUDE.md 98
lines. The private word check printed nothing before every commit.
Nothing of the bench or the recordings entered the repo.

Made untrue by this stage: 6a's line, above, that Stop ends at the final
transcript page (the note is drafted after the gate and the page goes to
the review page; final.html is gone); the home sentence, README's so far
and CLAUDE.md's running lines, fixed in this commit; the bench's prompts
folder holds one prompt now, the drug name's; the 15.10 detail's sentence
on rule 2 of the bench, which Cowork folds into the spec with the ruling.

Departures from the plan: the proof ran before the documents commit, as
6a's did; the plan's 38 tests landed as 36 (the line-words edit, the
citation-stripping copy, the audio-gone line and the home list's one row
each are pinned inside their neighbours, and the note stage's spinning
state inside the Stop test).

For stage 7: the line that the recording has gone, with the date, stands
in the player's place when the file is missing (player.available), built
now and true once the retention clock removes files; an edited line's
words change transcript_line.text in place with the words before in
transcript_edit, and the raw words stay in stop_raw and live_line; the
approved text in note_approval is the record of what was approved; the
state column keeps its three values, and an approved consultation is one
with a note_approval row.
