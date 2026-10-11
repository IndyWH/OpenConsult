# HANDOVER

The record for OpenConsult v2: decisions and measurements, newest first.
It stays under 500 lines. Older entries move to HANDOVER_ARCHIVE.md.
The spec is V2_SPEC.md. The record for v1 is the HANDOVER.md on the main branch.

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

## 2026-10-10. Stage 5b: the Nemotron choice and the two cloud choices

Built on 10 Oct 2026. The plan was reviewed by Cowork the same day (nine
changes and one addition to Part 4); all are in. The checks on the card
and against the two services ran on 10 Oct with the v1 service off.

What was done:
- Three more speech choices behind the door of 5a (openconsult/speech):
  Nemotron on the card, Speechmatics and AssemblyAI through their EU
  addresses. Each is proven by the self-test of 5a, each command names
  its choice (--choice), and This machine has one line for each.
- The door: a choice whose labels are live is told the number of
  speakers at open and the number goes to the worker; a choice with one
  transcript gets at Stop every line the door already gave, with the
  last ones made final, from the door's own record by id (11.1). Stop
  never refuses over a count that differs from the one at open: both
  counts are recorded (the last words are said at Stop). A revision
  from a service changes a label and nothing else, and never costs a
  line. New failures by name: no_key, key_refused, no_credit,
  no_internet, service_down, limit_reached, address_refused,
  connection_lost. The WhisperX choice behaves as before.
- The keys: one module (settings/keys.py) reads SPEECHMATICS_API_KEY
  and ASSEMBLYAI_API_KEY from the process environment, then from .env
  in the data folder; a key goes into its own worker's environment and
  nowhere else, and every worker's environment has every other key's
  name taken out. .env.example is committed with empty values.
- The cloud frame (speech/common/cloud.py), on websockets 17.2, the one
  library added to the base app: the EU address is a named constant,
  dial refuses any other before a connection, main takes no argument
  and reads no environment value for it; the certificate and the host
  are checked by the library's default context with no argument that
  could weaken it; a dead line is noticed within 50 s (ping 20, pong
  20, close 10, the library's own defaults) and is connection_lost;
  nothing reconnects. A made-up service on loopback stands in for both
  services in the suite; the suite never reaches the internet.
- Speechmatics: StartRecognition with the enhanced model, the medical
  domain, speaker diarization, partials on, the session's rate,
  max_speakers from 2 up, no additional_vocab. One line per run of
  label from an AddTranscript; UU is no speaker. EndOfStream, then
  EndOfTranscript. The service sends Info (its usage and its region)
  before RecognitionStarted; the worker reads past it.
- AssemblyAI: the parameters in the query, model universal-3-6-pro
  named, speaker_labels, domain medical-v1, max_speakers as given, no
  keyterms_prompt, no format_turns (the model always formats). The
  Begin echo is checked field by field; a field the echo does not carry
  is recorded as not echoed. A Turn that ends is one line; PENDING and
  UNKNOWN are no speaker; a SpeakerRevision gives id and label only.
  Terminate, then Termination. A wrong key is answered after the
  handshake with an Error frame (1008) and a close.
- Nemotron (ruling 8): one worker, one environment built from a
  committed lock with NeMo at v1's commit 1688cc3d, torch 2.12.0 from
  PyPI, Python 3.12. The English model alone writes the words at the
  revision and the setting of Task 17's third arm ([70, 13]); the
  speaker model beside it, at v1's revision, in the Low latency row of
  its card (1.04 s). Each has its own features (v1's splice), chunker
  and cache; nothing of v1's pairing. The join (nemotron/join.py) is a
  plain function: a word that no stretch covers, or that two speakers
  cover equally, has no speaker; a line closes at a sentence's end, a
  change of speaker or a pause of 1.0 s, or by time at 3.0 s.
- Carried from 5a: the home page's line; a death's reason is one plain
  sentence (codes stripped, traceback and warning lines skipped, a cut
  first line of the log window dropped, a library's own log lines and a
  worker's [note] lines never taken); the worker-side frames shared by
  every worker folder (speech/common/frames.py). Eighteen comments
  that cited private plan reviews now give their reason (ruling 11).

The rulings of spec 15.9 for 5b, each in one line:
8. The English model alone writes the words; the speaker model only
   says who spoke; item 6 proved the words identical with and without
   it; the join can change no word. Done.
9. The EU address only, medical on, labels live, no word list: pinned
   word for word against the made-up service and proven on the real
   connections (items 11 to 13). Done.
10. AssemblyAI stays; what it keeps is for the bench report and stage
    9. Nothing built; the self-test's sentence says the clip leaves.
11. The tidy-up commit opened the stage. Done.

Decided in the plan review (Cowork, 10 Oct), as decisions of this stage:
the number given at open is sent to AssemblyAI as max_speakers as given
and to Speechmatics from 2 up, with no headroom; a label beyond a number
a service could not be given stands as the service gave it; Stop never
refuses over a count; a revision never costs a line; a worker holds its
own key and no other; the certificate is always checked; the dead-line
figures are the library's own; AssemblyAI's text is formatted without
format_turns (its migration page); the home page's line is the review's
draft; the Nemotron environment is not Task 17's (Python 3.12 and torch
from PyPI here; 3.13 and NVIDIA's index there), the model, revision and
setting the same. Decided while building: a field the Begin echo does
not carry is not a difference (it echoes no max_speakers); the workers
log the opening sent and the first reply as [note] lines.

Measurements, 10 Oct 2026, RTX 4090, v1 off:
- 346 tests, 16.1 s, none skipped. App code 5,864 lines without the
  bench, tests 5,492. Largest file speech/nemotron/models.py, 497
  lines; no function over 80. CLAUDE.md 99 lines.
- The Nemotron environment: 159 packages locked, 156 installed on
  Linux, 5.5 GB, built in 22 s from a warm cache; the second run
  audited and changed nothing in 0.3 s. Both models found in the shared
  cache at their pinned revisions, none downloaded.
- Nemotron self-test passed: 21 of 22 words live and at Stop (the same
  lines). The first word, And, came at 0.08 to 0.16 s, in the clip's
  opening silence, and the rule refused it at -43 dBFS: the model's
  frame times can run ahead of the first word. Load 6.9 s, then the
  warm-up. Lines 2.19 to 3.18 s after their last word; Stop 0.04 s; the
  slowest step 0.18 s. Four lines of 4, 2, 7 and 8 words. The card's
  highest sample 4,321 MiB. The English model alone gave the same 22
  words, word for word. Silence and noise (zeros, -50, -30 dBFS, 60 s
  each): no word, nothing to refuse. The connection record was empty.
  Killed mid-clip: died with the exit code, no second start, a new open
  worked.
- Speechmatics self-test passed, 22 of 22; open 0.1 to 0.16 s; a line
  4.7 to 4.9 s after its last word (the service's default max_delay);
  Stop 0.18 s; 11 lines (ten of one word, one of twelve), every word
  S1, every confidence 1.0; RecognitionStarted after an Info with
  region eu. AssemblyAI self-test passed, 22 of 22; open 0.85 s; lines
  1.2 and 2.1 s after their last word; Stop 1.1 to 1.4 s; 3 lines (5, 2
  and 15 words) with confidences 0.994, 0.705 and 0.981; the middle
  line PENDING live and revised to A at Stop. The connection records
  hold only the EU host's lookup and connection, three lines each.
  Silence and noise, 180 s to each: no word. A wrong key: Speechmatics
  HTTP 401, AssemblyAI an Error frame 1008; both the plain sentence,
  one attempt. Killed mid-clip: as Nemotron. Sound sent: about 234 s to
  Speechmatics, 218 s to AssemblyAI, the clip and made sound only.
- The keys' values appear in no file under the working data folder,
  the log, the plan, the report or the repo (counts 0).
- This machine on the working data folder: Nemotron installed and
  passed, Speechmatics passed, AssemblyAI passed, each with its date.
- The WhisperX self-test on 5a's folder passed with this code, 22 of 22.
- The private word check printed nothing before every commit.

Made untrue by this stage:
- CLAUDE.md, Running it: --choice on the two commands; the README's
  line. Both fixed in this commit.
- V2_SPEC.md 15.9, the details of 5b: "the number is given to the
  worker" holds, but a service may not take it (Speechmatics below 2)
  or may not echo it (AssemblyAI); the list of new failures lacks
  connection_lost; a line now has an id; the Begin echo rule is as
  decided above. Cowork folds these in.
- The plan's figure for the Nemotron card memory (4,000 MiB) was met
  (4,321 at the highest sample, with the clip; 5a's WhisperX took 7,600).

For stage 6: a cloud worker's connection is opened at the door's open,
so Start pays 0.1 to 0.9 s; a dead line is noticed within 50 s; the
Nemotron English model's first word can be timed in silence before it,
so the rule may refuse a real first word; AssemblyAI's labels come
PENDING for a short turn and are revised at Stop; Speechmatics gives
one line per word early in a session.

Next: the owner's check (install-speech --choice nemotron, the four
self-tests, the app on 8001: This machine shows the rows), then push;
the GitHub check must be green on all three systems. Then the 5c
brainstorm.

## 2026-10-10. Stage 5a: the transcription door

Built on 9 and 10 Oct 2026. The plan was reviewed by Cowork on 9 Oct
(seven changes) and the build again at the gate for the card (six
changes); both are in. The checks on the card ran on 10 Oct with the v1
service off.

What was done:
- One door to transcription (openconsult/speech): open at the sound's
  rate, feed, stop with the number of speakers given. Every call gives
  lines of text, each with a speaker or none, a start, an end and a
  confidence or none (11.4), or a failure with its reason: not
  installed, died, no answer, worker error, bad reply, no session,
  session open, rate not supported, bad speakers. It never raises into
  the app, and tries nothing else (10.4). Every result carries the stamp:
  the choice, its models with their revisions or checksums, and its
  library versions (R20).
- The rule against words from silence, in the door, as a plain function:
  the loudness of every piece fed, in 100 ms windows on the session
  clock; a line is refused when even its loudest window is at or below
  QUIET_DBFS = -40 dBFS. It runs on live lines, on the text not yet
  final, on the last live lines made final at Stop, and on the raw
  segments before the merge. What it refuses is kept and marked.
- The worker frame: v1's frames kept word for word, a reader thread in
  place of select, each start with its own queue and event; a made-up
  worker runs as a real subprocess in the suite on the three systems.
- The first choice, WhisperX with pyannote, as a worker run only by its
  own environment's Python: the live stream on faster-whisper
  distil-large-v3 (v1's buffer and commit margin), and at Stop the
  live buffer transcribed once more so the last seconds are final, then
  WhisperX large-v3 with word times and pyannote 3.1 with the count
  given. No text is given to any model. The merge of raw segments into
  turns is a plain function in the base app; raw segments are kept as
  they came, flagged refused or not.
- The environment lives in the data folder, built from the committed
  lock file by openconsult install-speech, which then finds or fetches
  every model at a pinned revision or checksum. The worker runs with the
  hub's network off and loads from disk only; the voice activity model
  is loaded by path, not by name. No model downloads without a click.
- The self-test: the clip in 250 ms pieces at real time, Stop with one
  speaker, at least 20 of the 22 expected words in order, live and at
  Stop. openconsult self-test runs it; the result is stored in the new
  table speech_self_test (version 3); This machine shows the two rows
  on a suitable card.
- The base app gains no library. NOTICE gains the environment's direct
  libraries, the models it fetches, and the clip.

The rulings of spec 15.9, each in one line:
1. Two hard marks for a speech choice: the bench of 5c and 5e. Nothing
   built; the rule against words from silence is the app's side of the
   second mark.
2. A misheard drug name is marked, never corrected silently: stage 6
   and the bench. Nothing built.
3. No speech model is given a line of drug names: v1's line is not
   carried; the record of item 8 shows no prompt, prefix or hotwords.
4. An unsure line is shown as unsure: stage 6. Nothing built.
5. Two cloud services enter the bench: 5b. Nothing built.
6. Stage 5 in five steps; this is 5a. Done when This machine says the
   choice is installed and the self-test passed: it does.
7. The sound as the microphone gives it: the door takes the rate with
   the session (the new recordings are 48 kHz); the real worker takes
   16,000 in 5a. Conversion is 5c's.

Decided in the plan review of 9 Oct (Cowork), as decisions of this stage:
the models are fetched at install, never by the worker; the sound's rate
travels with the session; the last live lines are made final at Stop;
no made-up confidence, so a turn with no scored word has none (v1 gave
0.5: the gate of stage 6 must expect none); no test for a control a
later stage builds; the archive is archive/HANDOVER_ARCHIVE.md; the
clip's source is proven (whisper.cpp's sample, identical by checksum).
Decided at the gate (Cowork): the pass at Stop asks the network nothing;
a second open never throws sound away; a count below one is refused by
the door; the stamp says only what is known (pyannote's inner models are
stamped with the revision their main ref loads, read from disk); names
and comments cite what they pin; the worker's log never holds what was
said (its libraries held to warnings and above).

Measurements, 10 Oct 2026, RTX 4090, v1 off:
- 255 tests, 6.4 s, none skipped. App code 4,063 lines without the
  bench (6,138 with it), tests 4,165. Largest file
  speech/whisperx/models.py, 399 lines; no function over 80. CLAUDE.md
  99 lines.
- The environment: 123 packages locked, 119 installed on Linux, 7.2 GB,
  built in 10 s from a warm uv cache; the second run audited and
  changed nothing in 3.0 s. Every model found in the caches, none
  downloaded. Every library permissive except the nvidia-* wheels
  (NVIDIA's proprietary CUDA licence).
- The self-test passed: 22 of 22 words live and at Stop. The worker
  loaded in 2.9 s. The one live line that was final before Stop came
  3.0 s after its sound ended; the last line was made final at Stop in
  0.07 s. The pass at Stop took 2.1 s: load 1.0, transcribe 0.3, align
  0.5, diarise 0.3. Nothing refused. The card's highest sample 7,600 MiB
  (every 2 s). A second run with every connection and name lookup in the
  worker recorded: the record was empty. The worker's log holds none of
  the clip's words.
- Silence: 60 s of zeros, of white noise at -50 dBFS and of white noise
  at -30 dBFS, live and at Stop: neither model wrote a word, so the rule
  had nothing to refuse, the -30 dBFS noise included. Measured levels
  -inf, -50.0 and -30.0 dBFS. A measurement for 5e, not a pass mark.
- v1's 445 figure, the source of the threshold, was an RMS over each
  filler line's whole span; the rule uses the loudest 100 ms window of a
  line, which is the stricter measure for refusing.
- No text to a model: the live model's transcribe is called with
  language en, beam 5, vad_filter, no condition on previous text and
  nothing else; every prompt built is the bare start sequence (start of
  transcript, English, transcribe; plus no timestamps for WhisperX), with
  prefix None and hotwords None; WhisperX's options carry initial_prompt
  None, prefix None, hotwords None.
- The worker killed mid-clip: the next feed failed with died, the exit
  code and the log's last line; feed and stop after it said no session;
  no second worker was started; a new open loaded a new worker and the
  whole clip went through.
- The private word check printed nothing before every commit.

Made untrue by this stage:
- CLAUDE.md, Running it: the two new commands; the archive's path. The
  README's line. Both fixed in this commit.
- V2_SPEC.md 11.1 and 15.9 say the pass at Stop runs on the recording:
  in 5a the worker keeps the sound it was fed and runs the pass on that;
  stage 6 may hand it the file. 15.9 says the library versions are v1's:
  the speech libraries are, and 43 helper packages resolved newer. The
  spec is silent on the self-test's pass rule (20 of 22) and on the
  rate carried with the session. Cowork folds these in.
- The plan's figure for the threshold on raw sound is still owed to 5e.

Next: the owner's check (install-speech, self-test, the app on 8001:
This machine shows the two rows), then push; the GitHub check must be
green on all three systems. Then the 5b brainstorm. For stage 6: the
gate must expect a confidence of none; the worker's log and the sound
the worker keeps belong to no consultation yet.
