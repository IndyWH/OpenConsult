# HANDOVER

The record for OpenConsult v2: decisions and measurements, newest first.
It stays under 500 lines. Older entries move to HANDOVER_ARCHIVE.md.
The spec is V2_SPEC.md. The record for v1 is the HANDOVER.md on the main branch.

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

## 2026-10-20. Stage 6a: the live consultation, from Start to Stop

Built and proven on 20 Oct 2026 in one session. The plan was reviewed by
Cowork the same day (six points; all are in). The report is
STAGE6A_REPORT.md in the private log folder. The room run is the owner's,
still to come: the steps are in the report.

The rulings it builds, one line each (spec 15.10):
- 1: an alarm that says time critical and names no action is shown with
  one plain line, the reasoning one tap away, kept as an earlier alarm and
  recorded as its own state.
- 2: a failed assessment call keeps the earlier lists on screen, marked
  from the earlier pass, with the failure line; the first pass shows the
  line alone; the next pass gets the same stale names.
- 7: at Stop the app asks which speaker was you, waits with no limit, then
  runs the label check, proves no word changed and marks each changed
  label; a line the check calls unsure is shown unsure.
- 8: the two checks of 5c unchanged, each a warning at its place; the gate
  refuses only an empty or too short transcript, flags a missing passage,
  a line with no speaker and a low-confidence line, and says plainly when
  confidence was not measured.
- 9: the new-patient form (name, date of birth, sex, all required, under
  the line that every patient is acted), the Start screen as 8.2 with the
  two ticks and the intended time opening on the time used last, Start
  disabled with its reason on the control, two speakers told at open, no
  box for the reason for the visit.
- 10: the quiet clock changes colour at the intended time and nothing
  else happens; the intended time is stored.
- 12: typing counts as use on the new-patient form, by a page script, and
  a page with an unsaved edit never refreshes itself.
- 14: a line the choice gave no speaker takes the check's label and stays
  shown unsure.
- 16: 6a from Start to Stop; nothing of 6b is built.

What was built (the app without the bench 9,130 lines, from 7,062 at 3c;
the tests 11,351 lines):
- schema version 4: patient, consultation, live_line, transcript_line,
  cds_pass, warning; model_call gains consultation_id, written by the
  door when a call is asked for a consultation.
- consult/live.py, the consultation as a class with named fields; one
  module each for the recording (a WAV written as the sound arrives, its
  header patched after every piece, opened for exclusive creation, R18),
  the transcript as shown, the passes, Stop in order, who spoke, the label
  check and the gate; patients/patients.py; consult/consultations.py (the
  rows).
- the pages: the new-patient form, the Start screen, the live page with a
  socket for the sound and the state, the stopping page with the
  who-spoke question, the final transcript page; three page scripts in
  their own files (live.js the connection and the sound, panels.js the
  table of handlers, use.js typing as use) and the worklet; every sentence
  in words.py, handed to the scripts as data.
- the label check's prompt is one file, openconsult/prompts/label_check.
  prompt.txt, sha256 of its bytes 262d1ef8...de557a as ruling 17 gives it;
  the bench reads that file now and its own copy is gone (spec 5.1); the
  frame around the lines, label_check.frame.txt, holds the bench's words
  (TRANSCRIPT:, then [n] and the words), sha256 44f10e08...1e0637, and a
  test pins the text sent against the bench's own builder.
- a consultation left live or stopping by the last run is carried on at
  the next start: nothing deleted, no row left live, Continue on the home
  page (review point 3).

The constants, each with its source:
- NEW_CHARS_FOR_PASS 150: v1's CDS_MIN_NEW_CHARS, characters of new final
  text, with the first pass on the first line; no clock interval.
- TOO_SHORT_WORDS 60: a design choice, a tenth of the shortest banked
  script (01, 667 words by the bench's parser).
- LOW_CONFIDENCE 0.60: v1's.
- The label check: 3,000 tokens and 120 s, the bench's figures.
- The alarm sameness rule: the same alarm while its actions' words are the
  same after the matching's normalise; the no-action state is one alarm
  while it holds. It decides only what the screen shows and which
  acknowledgement holds here. Stage 12 must look at it again before it
  decides what pauses Alba (R8, R29): a model that rewords an action
  would otherwise pause her again.

The speech choice of a consultation: Nemotron where installed, else the
WhisperX choice where the room check offers it and it is installed; no
cloud choice is chosen by the app before stage 9 (the statement of 7.3 and
the cloud mark do not exist yet).

Measurements, 20 Oct 2026, RTX 4090, v1 off, vLLM 0.31.0 started by hand
with the room of 3c, the Nemotron worker started by the app from a
throwaway data folder, the sound fed through the page's own path (the
socket, the capture message, pieces of 0.25 s at the speed spoken):
- The self-test clip (11 s, one speaker, two told): the worker ready in
  15.9 s on a warm cache (21.7 s cold); the first line on the page 2.5 s
  after the feed began; the three figures from the app's own audit line: word to page 2.14 s typical, pass 0.57 s typical, Stop to final 1.3 s. The label check answered in 0.44 s
  and called the lines unsure; the gate refused the transcript as too
  short (22 words) and said confidence was not measured.
- Recording 462 (script 01, 305 s, two readers; consent covers tests on
  this computer): word to page 2.23 s typical, pass 2.98 s typical (19 passes, 18 shown; one landed after Stop and was recorded, not shown; the walls 0.53 to 3.20 s), Stop to final 11.0 s, of which the label check on 94 lines took 7.0 s; the alarm fired on passes 2 to 15 and was quiet before and after; the check changed 23 labels; 22 lines shown unsure; one uncovered stretch of 2.2 s at 13.9 s; the speaker model gave one label only (S1), so the other reader's lines came through the answer as unsure and through the check as patient: the Nemotron finding of 5c, seen live.
- 613 tests, green three times before the last commit, 22.7 to 22.9 s,
  none skipped; the GitHub start check passed. No file over 600 lines, no
  function over 80. CLAUDE.md 98 lines. The private word check printed
  nothing before every commit. Nothing left the machine: the models were
  found in the hub's cache, nothing fetched; no key and no token was read;
  the engine folder and the Ollama service were not touched.

Made untrue by this stage: the home sentence, README's so far and
CLAUDE.md's running lines, fixed in this commit; 15.6's line that stage 2
has no page script is history, as it said it would be; the note of stage 3
that model_call rows are tied in stage 6 is now done; the bench's prompts
folder holds two prompts, not three, and the bench reads the label check's
from the app. One thing seen in passing, not touched: the Ollama service
on this machine answers as version 0.40.6 today, not the 0.33.3 of 15.8
ruling 39; the app chose vLLM, so nothing of 6a ran on it.

Departures from the plan: the proof ran before the documents commit, so
that the figures in this entry are real; the plan's test 36 (the lock
held off from Start to final) is pinned inside the R1 test of the Start
screen and the who-spoke page test, not as its own; the who-spoke stage
is not a spinning state, because it waits on the doctor.

For 6b: the final transcript rows are transcript_line with n, label,
unsure, changed_by_check and revised_by_service; the gate's refusal is
Consultation.final.refused and the warning rows; the stored loudness
(consultation.loudness) and the recording file are there for the player;
the last pass's lists are in cds_pass with shown = 1; the model line is
built by web/live.py; a label the doctor undoes is set with
Consultations.set_labels. The note prompt of ruling 3 is not written.

## 2026-10-15. The two carried prompts: the double quotes out, benched on vLLM

Built and run on 15 Oct 2026 in one session, after the owner and Cowork
read the two prompts word for word (spec 15.8, rulings 41 to 43). The plan
was reviewed by Cowork the same day (three points; all are in). The report
is PROMPTS_BENCH_REPORT.md in the private log folder.

What changed: every double quote came out of both prompts (two in the
assessment, fourteen in the alarm) and one sentence was added to each,
asking the model never to write one. The files are the spec's two blocks
byte for byte. sha256 of each as the loader reads it, less the final line
break: assessment 437d7f32b3b020f8757ce96fdcf31ae4b85aef0b949e56f81546b3e200e1c6bb,
alarm 1e05ffc8634b4093897ec53cd590111fbb2bdeac0abbd4462c8298f5582c9451.
The three frames and the two forms are untouched (ruling 43). The test
pins each file to its ruling's hash, prompts/loader.py holds the same two
in APPROVED, and a test pins that no prompt or frame holds a double quote.

The word check of stage 3 (15.7, ruling 3) now matches the prompt sent
against the approved hash, not v1's. The whole request is still compared
against v1's recorded hash, with v1's own prompt put back in its slot,
which is what still proves the form and every other part call for call.
v1's two texts are given with --v1-prompts and proven first against the
arm-start records of the v1 file; the approved texts given in their place
are refused with both hashes named. The counts are unchanged: 892 of 892
for task 5 and 3,146 of 3,146 for task 5b, 1,898 of 1,898 for each call
(143 + 182 + 598 + 975), mismatches 0.

The bench of ruling 43: vLLM 0.31.0 started as 3c starts it (the repack
at revision 2096d38d, context 16,384, the compact form of ruling 22 at
start, the room 1,400,000,000 bytes), all 16 cases, the 13 chains, the
two calls of a pass sent together; 3,796 calls, none failed, no chain
failed; thinking off in every request and no thinking text in any reply;
87 minutes. The marks by the repo's score tool, and the same by a private
count from the raw files that imports nothing of the bench:
- Temperature 0, which decides (ruling 18): H1 to H6 3 of 3 each; H7
  none. Candidate: yes. The typical pass of 495 2.72 s (chains 2.78,
  2.71, 2.72), the slowest 2.91, beside 5d's 2.73 and 3c's 2.78.
- Temperature 0.5, apart: H1 to H6 10 of 10 each; H7 missed on one chain
  of ten, script 10 B6, where one differential at one update named an
  ovarian torsion while saying the patient is male. Over all 13 chains the
  soft marks are 8 of 9: S12 missed on script 05, which fired in 9 chains
  against the mark of 4; the time marks met (2.94 s typical, 4.07 slowest).
- The three counts, beside the vLLM arms of 7 Oct (the together arm for
  the chains at 0, the thirteen-chain arm for 0.5 and the totals):
  replies cut by a stray quote 0 at 0 (7 Oct 0) and 0 at 0.5 (7 Oct 21 of
  2,920); no reasoning holds a double quote, and 384 of 3,796 hold a
  single one. Empty lists 0 at 0 (7 Oct 0) and 1 at 0.5 (7 Oct 0): script
  13 chain B2 at its last update, a whole reply with a full reasoning and
  every list empty, so the earlier list was kept (ruling 5). Alarms time
  critical with no action 12 at 0 (7 Oct 8 together, 10 one after another)
  and 57 at 0.5 (7 Oct 63): 69 in all against 73, every one in a whole
  reply.
- Kept by ruling 43's rule: yes. Every hard mark met at 0 with no failed
  chain, the cut replies fewer at 0.5 (0 against 21) and still none at 0.
  The form pattern held in reserve is not needed on this showing.

Measurements, 15 Oct 2026, RTX 4090, v1 off: 558 tests, green three times
before the last commit. CLAUDE.md 99 lines. The private word check printed
nothing before every commit. Nothing left the machine: vLLM ran with its
reach to the hub and its usage reports off; no key and no token was read;
the engine folder is unchanged but for the script's own run files, whose
13 Oct copies are kept in the log folder; the Ollama service is as it was.

Made untrue by this stage: CLAUDE.md's wordcheck line, fixed in this
commit. The line of the stage 3 entry below that the prompts are v1's
words exactly is history: from this commit they are the spec's approved
wording. The public engine-bench folder records 7 Oct's prompt hashes in
its arm.json files, which is right as the record of that bench; it is not
touched and not run again (ruling 43).
