# HANDOVER

The record for OpenConsult v2: decisions and measurements, newest first.
It stays under 500 lines. Older entries move to HANDOVER_ARCHIVE.md.
The spec is V2_SPEC.md. The record for v1 is the HANDOVER.md on the main branch.

## 2026-10-11. Stage 5c, part two: what is done with the transcripts, and the full rehearsal

Built on 11 Oct 2026. The plan was reviewed by Cowork the same day (five
changes); all are in. The checks and the rehearsal ran on 11 Oct with the
v1 service off. The rehearsal is a rehearsal: no figure from it counts
(spec 13.4 rule 2; 15.9 ruling 6).

What was done:
- Fix one: the Nemotron worker's last word before a silence is passed on
  once the model has decoded WORD_CLOSE_S past its last token (a plain
  class, speech/nemotron/wordflow.py, loaded by path as the join is), so
  the line's own wait of 3.0 s can run in silence. The figure is 2.0 s,
  not the plan's 1.0: on the card the model gave one word of the clip its
  two tokens 16 frames (1.28 s) apart across two decoding steps, and one
  second could have cut it in two. The Stop reply's notes carry the counts
  that prove no word was split. The tied pair has its own stream and does
  not change.
- Fix two: the wait to first shown runs from the line's start; the true
  times serve every arm; the true start goes to the first line of a speech
  and the true end to its last (bench/speech/waits.py, tables.py). Part
  one's 18 results rescored: only the wait differs.
- The lines a model reads (bench/speech/model_lines.py): from the smallest
  timed pieces at Stop, two neighbours joined when the first does not end a
  sentence, both carry the same label and less than 1.0 s lies between; a
  piece never split; turns as v1 joins them; v1's two role words and
  Unknown (ruling 22); the words around a transcript exactly as the details
  give them, pinned byte for byte.
- The three jobs of the bench (bench/speech/jobs.py, prompts/): the
  owner's three prompts byte for byte, hashed before they are read and
  marked -text; the forms, the note's being v1's as it stands; the limits as
  named figures; through the door's one new method, ask_own, with the same
  limits, form check and record; the app's table of jobs untouched (the
  word check of stage 3: 4,038 of 4,038 before and after).
- The voice method (bench/speech/voice.py, voice/worker.py): the doctor's
  voice learnt from a listed recording marked voice_only, each line given
  its distance from that voice by pyannote's wespeaker model loaded by path
  with the hub's network off; the reading made on the bench's side from
  two figures around the pinned pipeline's clustering threshold (0.7046,
  a band of 0.1) and a line under 1.0 s unsure; the list gains
  doctor_voice and voice_only; the replay refuses a voice-only recording.
- Who spoke, four readings side by side (bench/speech/who.py): the choice,
  the label check, the voice, and together, each counted word by word.
- The UK drug list (bench/speech/druglist.py; speech-drugs): one month of
  the Prescription Cost Analysis fetched and made into a list of whole
  names, generic without salt and form words, brand from the front of a
  product that is not its own generic equivalent, split at a bracket, a
  slash, a plus and the words with and and; dressings, appliances and the
  two nutrition sections left out; the class codes counted, not leaned on.
- The three ways to spot a doubtful drug name and the three classes
  (bench/speech/doubt.py), the key facts (keyfacts.py), the notes' five
  counts and the chance (notes.py), the calls (calls.py) and the tables of
  part two (tables2.py), with the one scoring command taking the key-fact
  file and the drug list where part two's results are there.
- Three commands: speech-voice, speech-drugs, speech-calls; speech-score
  gains --key-facts and --drug-list (CLAUDE.md).

The rulings of spec 15.9 for part two, each in one line:
2. The three ways benched as a report only; nothing marks a name on a page.
   Done for the rehearsal.
4. The voice (D53) and the words (ruling 17) benched, together and apart;
   nothing built into the app. Done for the rehearsal.
15. The notes written twice from each page and twice from the script.
    Done.
16. A real drug that is not the one spoken counted, with the list, for
    every choice, as a whole name of the list. Done.
17, 18, 19. The three prompts byte for byte (sha256 pinned). Done.
20. The key facts applied by code; the lists are Cowork's. Done.
22. A turn with no speaker is Unknown. Done.
21. Part two as its own run, with the cycle of 15.3. This is it.

Decided in the plan review (Cowork, 11 Oct), as decisions of this stage:
a drug is a whole name of the list, never one word of a longer name; the
driver never loads the language model beside a speech model and marks the
calls failed if a worker is still alive; the short form n/7, n/52, n/12 is
days, weeks or months only when n is 24 or less; the voice figure is a
distance; the nearest entry is none when no entry meets a single group.
Decided while building: WORD_CLOSE_S is 2.0 s (above); foods are the
sections the drug file names Oral nutrition and Enteral nutrition (0913,
0914), not 0904; speech-drugs takes the recordings and data folders so it
refuses them; a failed call is failed and not refused.

Measurements, 11 Oct 2026, RTX 4090, v1 off:
- 451 tests, 16.4 s, none skipped. App code 6,464 lines without the
  bench (12,703 with it), tests 8,185. Largest file speech/nemotron/
  models.py, 516 lines; no function over 80. CLAUDE.md 99 lines.
- The two environments built into the working folder from the warm cache
  in 11 s and 1 s (7.2 GB and 5.5 GB); the two local self-tests passed,
  22 of 22 each, before the run and again after it. The word check of
  stage 3: 4,038 of 4,038 calls rebuilt exactly before and after the
  door's change.
- Fix one on the card: 60 s each of zeros, noise at -50 and at -30 dBFS,
  no line; the clip then 30 s of silence with no Stop until the end, 22 of
  22 words, the last line final 3.09 s after its end and 28 s before Stop;
  the largest gap between two tokens of one word 16 frames, no token after
  a close by time. Recording 477: the last word's line final 3.21 s after
  its end, 191 s before Stop (part one: at Stop, 194 s). The new Nemotron
  pages beside the old: 462 94 lines and 661 words on both, 0 words
  differ; 473 117 to 114 lines, 741 to 742 words, 3 differ; 477 51 to 50
  lines, 359 words, 0; the made recording 92 to 90 lines, 971 words, 0;
  the longest wait to final 3.2 to 3.4 s on every recording (the made
  recording 4.22 to 3.24).
- Fix two: part one's 18 results rescored with the new code, 3,838 leaves
  of scores.json differ and every one is under the wait; 36 lines of
  report.md, every one a wait. The least true wait to final is above zero
  on every arm; to first shown it reads below zero on the one-transcript
  choices (a line's first two words can stand in an earlier partial).
- The drug list: July 2026, 235,494,243 bytes, 533,087 rows, fetched in
  8 s; 3,801 names (2,679 of one word, 1,122 longer; 1,181 generic, 2,620
  brand) made in 5 s; 19 of script 19's 20 drug names in it.
- The minute of the doctor's voice: 39.3 s, 37.3 s of speech, peak -0.97
  dBFS, typical -22.3, no sample clips.
- The rehearsal (13:22 to 13:51, 29 min, nobody attending): Nemotron's
  four results in 23 min; the voice method on the five pages of the made
  recording in 6 s, and the plain not-run record on the nine pages of the
  old recordings; 64 calls in 6 min, 1 failed (the doubtful drug names on
  Nemotron's page of the made recording, cut at 1,500 tokens), 0 refused;
  the tables twice from the stored results, byte for byte the same. The
  connection records of the speech steps are empty. The card: Nemotron
  4,022 MiB, the voice worker 1,396, the language model 17,444 at its
  highest; never both at once.
- The calls: the label check median 9.9 s, longest 16.9; output median
  1,411 tokens, longest 2,665 of 3,000 (about 21 tokens a line, not the
  13 the limit was set from). The doubtful drug names median 0.6 s,
  longest 10.1 (the cut one). The notes median 4.8 s, longest 8.2; output
  median 736, longest 1,284. The notes from the scripts median 4.1 s.
- Read as a doubter (item 14): the scoring of figures counted a note's
  own turn citations and read 5-10 as 510, fixed in c03b5de (361 figures
  "not spoken" over 28 notes became 34); the tied pair's pages of 462 and
  477 carry one speaker label, so their notes were given one turn and
  cited turns that do not exist (every entry); on the made recording
  AssemblyAI wrote glipizide for gliclazide three times early on, and the
  language model then flagged the three later, right, gliclazide as
  doubtful and named glipizide as the medicine meant; the list way marks
  everyday words close to a brand (perfect, diabetes); a garbled name at
  a closeness of 0.72 is missed at the figure of 0.75; no reply was
  refused and no reasoning was cut.
- The private word check printed nothing before every commit. Nothing
  private is in V2: the private check's counts are all 0.

After Cowork's check, 11 Oct 2026 (STAGE5C2_FIX.md):
- A note's shorthand is read as words before a key fact or a drug name is
  looked for (a slash between words, a sign before a figure, 3x, a range,
  a hyphen read both ways), on both sides of a rule; the app's matching
  and every mark of part one stay as they are (6207dfd).
- The first table of part two says on how many pages a reading ran, and
  not run where it ran on none, and whether a drug written as another
  real drug reached the note, in how many of the notes (6488e7e).
- Cowork corrected five rules of the key-fact file (13-01, 01-04, 01-18,
  15-13, 19-23); the tables to read are stage5c2-rehearsal-tables-v4,
  made once with the three fixes, byte for byte the same twice.
- Windows, 13 Oct: one test removed the folder of calls with the made-up
  door's database still open. The fault was in the test; the app is unchanged.

Made untrue by this stage:
- CLAUDE.md, Running it: the three new commands and the two options;
  fixed in this commit. The README's line; fixed in this commit.
- V2_SPEC.md 15.9, the details of part two: WORD_CLOSE_S is 2.0 s, not
  the join's pause; the drug file's columns (27, ICB in place of STP, one
  new) and the lack of a class-code table on the portal's pages, so the
  rule tells generic from branded by the data; the licence sentence is not
  on the dataset page; the foods' sections. Cowork folds these in.
- The plan's figure for the card (18,000 MiB): the language model took
  17,444 MiB at its highest.

For 5d: the language model with its 16,384 context took 17,444 MiB
on the card; the voice worker under 1,396 MiB. For 5e: the two figures of
the voice method and the closeness figure of the list are drafts, to be
set again from the stored distances and marks on the new recordings; the
wait to first shown can read below zero against the true start on the
one-transcript choices (a line's first two words can stand in an earlier
partial), a limit of the measure to put right. For stage 6: the four
readings' counts on the old recordings say what the label check alone
does on a real voice, and the made recording's say nothing of the voice
method (a man's and a woman's machine voice).

Next: the owner's check (uv sync, then the four self-tests on his real
data folder), then push; the GitHub check must be green on all three
systems. Then Cowork checks the report from the raw files.

## 2026-10-11. Stage 5c, part one: the replay bench and the transcript marks

Built on 10 and 11 Oct 2026. The plan was reviewed by Cowork on 10 Oct
(ten changes); all are in. The checks and the rehearsal ran on 11 Oct
with the v1 service off. The rehearsal is a rehearsal: no figure from it
counts (spec 13.4 rule 2; 15.9 ruling 6).

What was done:
- The rule against words from silence looks as wide as a choice's times
  allow (ruling 12): Declares gains time_slack_s (Nemotron 1.0 s, the
  rest 0), refuse_quiet looks that far to each side and refuses only if
  the whole stretch is quiet; while sound is still being fed a stretch
  that reaches past it counts as not quiet, and at Stop nothing is still
  to come, so a quiet last line is refused for every choice. Two tests of
  5b feed more quiet sound before their made-up lines, same assertions.
- The matching of words lives in the app (speech/matching.py): capitals
  and punctuation ignored; apostrophes, then hyphens and split words, then
  numbers, then units, then the British and American spellings in one
  table made the same, in that fixed order; a slash between figures is
  over; a figure against its unit is split. The alignment classes each
  page word as heard, in place of a spoken word, or from nowhere.
- The check for missing speech (speech/missing.py; 11.5 rule 2; D45;
  ruling 13): five or more live words the transcript at Stop lacks; two
  seconds or more of sound above -30 dBFS (not yet measured on raw sound)
  that no line covers, quiet gaps under 0.5 s joined. Stage 6 shows it.
- The speech bench (bench/speech): the banked list and its reader (a
  checksum that differs, a name not listed or a list not whole is refused
  before any sound is read; consent held by code, ruling 14); the
  reference from a script with the cut and the notes; the replay through
  the door in 0.25 s pieces, each fed when its sound has ended, with
  everything the door gives kept, the moments, and the loudness windows;
  the marks (passages with or without a sign, words from silence, what
  the rule did, words that differ with negations and numbers, drug and
  test names as whole words with the bracket form, who spoke by best
  fit, the wait, how exact the times are, the signs counted); agreement
  against the script from the arms with a model of their own only, a
  word every arm left out still counting; the tables, byte for byte the
  same from the same results, never written over.
- The two arms of the bench (ruling 15): the tied Nemotron pair, v1's
  pairing on the 5b frame in the Nemotron environment, its late text
  changes kept in the result's notes and never sent as a revision; and
  WhisperX with v1's line, the line given to the live model only and
  hashed into every result. Neither is in the app's table of choices;
  the command refuses their names.
- The conversion of the sound's rate in the three local workers
  (speech/common/resample.py): scipy's own filter for a change by three,
  61 taps, Kaiser 5.0, its state carried across pieces; 16,000 or 48,000
  taken, any other rate refused.
- Three commands: speech-fetch, speech-run, speech-score (CLAUDE.md).
- The suite gains a guard on where recordings are kept (R18), with its
  twin. After Cowork's check the guard tells a changed file by the sha256
  of its bytes as well as its size and time: a coarse file clock gave a
  clean copy "DID NOT RAISE" on the twin once in two runs.
- A segment's speaker at Stop on a tie between two clusters is now no
  speaker (spec 15.9 ruling 4: unsure, never guessed), and the answer no
  longer follows the hash order (found by scoring the rehearsal twice).
- The bench's files are the same bytes on the three systems: the tables
  are written with "\n" line ends, and v1's line is marked -text in
  .gitattributes so Git never changes a byte of what is hashed (ruling 3).
- The GitHub check was red on Windows at 41025f2, in four tests only: a
  made-up script written in text mode no longer matched its checksum, and
  a path was compared as a string with a slash. The script is now written
  as bytes and the path compared by its parts. The owner's push is the proof.

The rulings of spec 15.9 for 5c, part one, each in one line:
12. The wider rule, with the figures as named constants; Nemotron's first
    word of the clip now reaches the page (it was refused in 5b). Done.
13. A passage is 5 words or more, a pause 2 s or more: in the marks. Done.
14. No old recording left the machine: the list says so for each, the
    bench refused the six cloud tries before any worker, the records are
    empty; the made recording (two machine voices, script 19) went to the
    two EU addresses. Done.
15. Six arms ran: the four choices, the tied pair, WhisperX with v1's line
    (the line byte for byte, hash c72f4adc...). The other extras are part two.
16. Drug names counted as whole words, the bracket form caught, names in
    v1's line apart; a wrong name that is a real drug is part two.
17 to 20. Part two. Nothing built.
21. Part one as its own run, with the cycle of 15.3. This is it.

Decided in the plan review (Cowork, 10 Oct), as decisions of this stage:
at Stop the wider stretch is cut at the end of the sound; the matching
lives in the app and the app never imports the bench; a piece is fed
when its sound has ended; a gap covers a passage by words and a stretch
by time, and a passage whose neighbours sit in one piece is unseeable by
a stretch; agreement is the same written word from every arm with a model
of its own, at least three, and a word every arm left out is not
agreement; the fixed order of the matching's steps; the tied pair's late
changes travel in the stopped reply's notes; the arguments reaching the
WhisperX models are recorded in the checks; the connection recorder sits
on the worker's Python from the driver's side (a sitecustomize named in
PYTHONPATH), with no code in V2.

Measurements, 10 and 11 Oct 2026, RTX 4090, v1 off:
- 400 tests, 16.0 s, none skipped. App code 6,328 lines without the
  bench (10,469 with it), tests 6,774. Largest file speech/nemotron/
  models.py, 500 lines; no function over 80. CLAUDE.md 99 lines.
- The two environments built into the working folder from the warm cache
  in 11 s and under 1 s (7.2 GB and 5.5 GB); every model found at its
  pinned revision, nothing downloaded; the tied pair's 3.5 model found
  in the shared cache at v1's revision ea30d66d (2.37 GB).
- The four self-tests on the working folder passed, 22 of 22 each.
  Nemotron's first word, And at 0.08 to 0.16 s, was accepted (5b: refused).
  The WhisperX models received no initial_prompt, prefix or hotwords; the
  arm with v1's line gave the line to the live model and nothing to the
  pass at Stop. No local worker opened a connection or looked up a name;
  each cloud worker reached its EU host and nothing else.
- Silence (60 s each of zeros, noise at -50 and at -30 dBFS, measured
  -inf, -49.5 and -29.6 dBFS): none of the four local arms wrote a word,
  live or at Stop; nothing to refuse.
- The conversion, in both environments: a 1 kHz tone at -20 dBFS came
  through at -19.99; a 12 kHz tone came through at -87.3 (67 dB down),
  the loudest bin below 8 kHz at -84.3 dBFS (4 kHz); lengths equal. The
  clip at 48,000 through the four local arms: 22 of 22 live and at Stop
  on three; the tied pair 22 at 48,000 and 21 at 16,000 (American for
  Americans).
- The three old recordings became WAV with flac -d (MD5 verified) and
  their samples equal ffmpeg's independent decode. The made recording:
  361.5 s, peak -0.75 dBFS, typical -21.6, no clipped sample, pauses at
  -75 dBFS or quieter; its cut runs to speech 8 at 56.7 s.
- The bench refused, before anything was fed: a wrong checksum, a file
  not listed, a result folder in the repo, in the data folder and where
  recordings are kept; a result asked for a second time; six cloud tries
  on old recordings and the cut, with empty connection records.
- The rehearsal (00:37 to 02:23, 1 h 45 min, nobody attending): six arms,
  18 results, every arm exit 0, no failure; every result carries the
  list's checksum; the cloud arms sent 361.47 s each (the made recording)
  and nothing else; the local workers' connection records are empty; the
  card peaked at 10,309 MiB. No arm wrote a word into silence that the
  rule let stand; no real word was refused; the one refused line (one
  word, Speechmatics, in a pause) was invented. Two passages missing with
  no sign, both on the tied pair, which is not in the app. Nemotron let
  nine invented words through by looking wider; its diarisation found one
  cluster only on two of the three old recordings. WhisperX's one
  segment end 2.9 s early made a false sign. In 477's three minutes of
  digital silence no arm wrote anything; Nemotron's last line stayed
  pending until Stop (194 s). v1's line changed no drug-name figure.
  No figure counts; the report in the log folder has them all.
- Scoring the same 18 results twice gave two different tables (who
  spoke on 477): a segment's speaker at Stop came from a set, and a tie
  followed the hash seed. Fixed in turns.py: on a tie, no speaker. Scored
  again twice after the fix, byte for byte the same; on 477 the two
  WhisperX arms moved ten words from the right speaker to no speaker,
  and no other figure in the tables changed.
- The private word check printed nothing before every commit. The two
  keys' values appear in no file of LOGS newer than the start marker, in
  the working tree or in the commits (counts 0).

Made untrue by this stage:
- CLAUDE.md, Running it: the three bench commands; fixed in this commit.
  The README's line; fixed in this commit.
- V2_SPEC.md 15.9, the details of 5c: "sound that has not been fed yet
  counts as not quiet" now holds while sound is still fed, and at Stop
  the stretch is cut (plan review change 1); the agreement rule counts
  only the arms with a model of their own and a word every arm left out
  is not agreement (change 5); the tied pair's late changes travel in
  notes (change 7); the matching lives in the app (change 2). Cowork
  folds these in.
- The plan's figure for the card (9,000 MiB): the rehearsal peaked at
  10,309 MiB, during WhisperX's Stop on the made recording.

For part two: the key-fact lists and the UK drug list (spec); the tied
pair's late changes (9 lines over the four recordings, 8 of them on the
made recording, no word lacking on the page); the arms' times beside the
figures of the wider rule (Nemotron's speech ends up to 1.33 s late, 3 of
84 beyond its 1.0 s; the tied pair's starts up to 1.09 s late; the exact
choices within 0.5 s but for WhisperX's one segment end 2.9 s early); the
signs (one right, three false, each explained in the report; the -30 dBFS
figure of the check has not been measured on raw sound, and a recording's
quiet words sat under it where a passage went unsigned); whether a
pending line should close after some seconds of silence (owner).

Next: the owner's check (uv sync, then the four self-tests on his real
data folder), then push; the GitHub check must be green on all three
systems. Then Cowork checks the report from the raw files, and the prompt
for part two is written.
