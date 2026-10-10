# HANDOVER

The record for OpenConsult v2: decisions and measurements, newest first.
It stays under 500 lines. Older entries move to HANDOVER_ARCHIVE.md.
The spec is V2_SPEC.md. The record for v1 is the HANDOVER.md on the main branch.

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

## 2026-10-07. Stage 3b: the engine bench

Built over 6 and 7 Oct 2026 and published on 7 Oct, after the owner ruled
that the bench of 7 Oct is the one public bench (spec 15.8, ruling 24).
The two local publish commits of the first bench came out of the history
first, in one rebase, with a bundle of the repo kept outside it.

What was done, 6 Oct:
- Two small items first. An empty list keeps the earlier list: when an
  assessment reply fits its form but its list of differentials is empty,
  and an earlier list exists, the pass gives the earlier entries whole,
  says that the list was kept, and hands the same names to the next pass.
  The record still holds the model's own reply. At the first pass empty
  stays empty. And the terminal's second line now says the browser will
  open by itself; the old line stays for --no-browser.
- The pass is three plain functions: the two messages, the sending, the
  settling. run_pass calls them in the same order and behaves as before.
- Two more engines, llama.cpp and vLLM, as modules of the bench behind
  the joint of stage 3 (bench/chat_engine.py, llamacpp.py, vllm.py). The
  bench command takes the kind of engine, its address and the name it
  knows the model by. The app cannot reach them and has no switch for
  one; a test in a fresh Python proves it. No setting was built.
- In the bench: the two calls of a pass sent together; the repeat test;
  the exporter, which writes an arm's public form and never writes over
  a published file; and the marks worked out again from published
  replies (score --replies).
What was done, 7 Oct:
- Candidate means ruling 18: every hard mark met on the chains at
  temperature 0, read from the data and never from a chain's name, and
  none of them failed. The chains at 0.5 are a stress test, counted the
  same way and reported apart. The 18 marks over 13 chains do not change.
- bench/figures.py and the command openconsult-bench figures: the rules
  of 7 Oct in the repo's own tool. The typical pass of a round, Rule B at
  half a second in every round, the steadiness of the day on Ollama's own
  rounds, the tokens written and the time for each token, and the counts
  from the replies: failed chains, replies cut mid-sentence, empty and
  kept lists, time critical with no action, the first alarm, the same
  answer in every chain at 0. It works from the public folder alone and
  gives the same figures from the private result folders. The rounds and
  the arms' roles are data (engine-bench/rounds.json). Every figure in
  seconds is rounded half up from the milliseconds, once. The compare
  command, its line of 1 second and the 13-chain candidate went.
- The exporter takes the card's memory over an arm's own steps (--steps),
  because the arms took turns through the day.
- Published in engine-bench: the report, how the bench was run, the
  cases, the six arms of 7 Oct, rounds.json, the tool's figures as data,
  the machine's figures as small data files, and bench-of-6-oct with the
  two kept parts of the first bench. 71 files, 4.2 MB.
- No library added. NOTICE has nothing to add.

The rulings of spec 15.8, each in one line:
1. Every prompt a model reads is put to the owner word for word. No
   prompt changed; the two hashes are as v1's.
2. The engine bench is published. Done: engine-bench.
3. The v1 service is off. Nothing to do here.
4. What the plan review of stage 3 settled is in the spec. Nothing here.
5. An empty list keeps the earlier list. Done, in the pass.
6. Showing the app somewhere else: stage 6's brainstorm. Nothing built.
7. The vLLM arm ran the repack by xbill9, at its fixed revision. Done.
8. The calls of a pass are also sent together, as a measurement. Done.
9. Does an engine give the same answer twice: the repeat test, 6 Oct. Done.
10. What counts as faster, as first fixed. Replaced by 17 and 18.
11. Every case the bench reads is published. Done.
12. The words in the terminal at the start. Done.
13. The together arm on Ollama ran on a second Ollama process. Done.
14. Ollama runs llama.cpp inside it. Said in the report.
15. The two travel cases are published unchanged, with a note. Done.
16. The push was held and vLLM got a second arm, with the switch. Done.
17. Faster means half a second, in every round. In the tool.
18. Temperature 0 decides who is a candidate. In the tool.
19. The full bench ran again on 7 Oct. Done.
20. The together arms ran the three chains at temperature 0. Done.
21. Three rounds, the order rotating; steadiness on Ollama. Done.
22. vLLM ran with the switch only; two figures per engine. Done.
23. The first bench waited for the second. Done.
24. One public bench, the bench of 7 Oct. Done.
25. What the public folder holds. Done, as written.
26. Anyone can rerun the figures: openconsult-bench figures. Done.
27. How the two commits came out: bundle, then one rebase. Done.
28. The first lines of the report in the owner's words; the docs script
    checks each figure in them against the tool. Done.

Decided in the plan reviews (Cowork), as decisions of this stage:
- 6 Oct: the kept list holds the earlier entries whole, marked kept; a
  failed assessment call is not an empty list. vLLM 0.31.0 and llama.cpp
  v0.6.0, the newest on the day. In the repeat test the earlier list came
  from the reference arm's chain A1. Nothing public names a path, a user
  or a host; the word check reads the unpacked text of each packed file.
- 7 Oct: the card over an arm's own steps is the pooled median. A reply
  that did not end ok or cannot be read as its form is counted apart,
  never as cut. A difference below zero is written as longer. The kept
  files of 6 Oct are as written then, and the note in bench-of-6-oct says
  what candidate meant that day. No figure from an arm that is not in
  the folder. Seconds are rounded half up from the milliseconds, once.

For stage 6:
- Whether the screen keeps the earlier list through a failed assessment
  call is the owner's ruling then. Nothing is built for it.
- Sending the two calls together shortens the pass on every engine, but
  the alarm itself comes back later (1.46 s against 1.12 s on Ollama),
  and on Ollama it needs OLLAMA_NUM_PARALLEL=2, which the service does
  not set. The app still sends one after another.
- The stray quote (ruling 16) goes to the session on the two carried
  prompts. The engine choice has a brainstorm of its own: a compact form
  for Ollama or llama.cpp, and the speech model beside the language model
  on the card, were not tested.

Measurements. The bench's figures are from engine-bench/README.md.
- 199 tests, 4.5 s, none skipped (191 before). App code about 2,260 lines
  without the bench; the bench 2,064; tests 3,190. Largest file
  bench/figures.py, 407 lines. CLAUDE.md 99 lines.
- The run of 7 Oct: 768 chains, 14,016 calls, every call ok, no chain
  failed; 07:17 to 15:25, nobody at the desk, the screensaver never seen
  in 487 minutes.
- Every hard mark met on every engine at both temperatures. Over 13
  chains llama.cpp missed two soft marks (S10 13, 9 and S14 6).
- The typical pass of 495 by round, one after another: Ollama 5.13,
  5.07, 5.12 s; llama.cpp 5.12, 5.12, 5.12; vLLM 3.56, 3.47, 3.43. Sent
  together: 3.76, 3.76, 3.75; 3.83, 3.81, 3.85; 2.78, 2.78, 2.77. The day
  was steady: Ollama's rounds 0.06 s apart.
- Rule B: vLLM faster by the rule, 1.57, 1.61 and 1.69 s shorter than
  Ollama one after another and 0.98, 0.99, 0.98 s shorter together.
  llama.cpp not faster either way (0.01 shorter to 0.05 longer; 0.07 to
  0.10 longer together). Every together arm is more than 1.25 s shorter
  than Ollama one after another in every round.
- At temperature 0 vLLM wrote 254,979 tokens against 319,170 on Ollama
  and 325,947 on llama.cpp (20 % fewer), at 5.33 ms a token against 6.44
  and 6.52 (17 % less). About half of its gain is the switch.
- Replies cut mid-sentence at 0.5: Ollama 23, llama.cpp 35, vLLM 21 of
  2,920; at 0: 0, 6, 0. The vLLM arm of 6 Oct without the switch: 14
  chains failed, all at 0.5. Time critical with no action: 65, 29, 73.
- The same answer in all three chains at 0: 16 of 16 cases on Ollama
  and llama.cpp, 0 on vLLM. The repeat test of 6 Oct, sets of ten all the
  same, of 12: Ollama 2; llama.cpp 3, and 12 with its prompt cache off;
  vLLM 0, and 10 with batch invariance on.
- The card, pooled over each arm's own steps: Ollama 17,139 MiB (70 %),
  llama.cpp 15,591 (63 %), vLLM 23,137 (94 %, its fixed share). Starts:
  llama.cpp 2.0 s, vLLM 25.8 s; Ollama's first call with the model not
  loaded 3.4 to 3.5 s.
- Empty lists: 3 on Ollama, each kept, all at 0.5; none elsewhere.
- The private word check printed nothing before every commit but the
  published folder's, where its 61 lines are all in case and reply files
  and equal the list Cowork read at the gate.

Made untrue by this stage:
- CLAUDE.md, Running it: the bench commands, now with figures and export
  and the kinds of engine. README: the line that points to engine-bench.
  Both fixed in this commit.
- V2_SPEC.md 15.8, the details of 6 Oct: the reference arm is not
  published (ruling 25 says so); compare.json and compare.md no longer
  exist; the typical pass of ruling 10 is replaced by that of 17. Ruling 7
  and 15.7 ruling 5 were corrected by the owner on 6 Oct. 15.8 ruling 24
  gives the card as 23,137 and 17,139 MiB: that is the pooled median over
  the arm's own steps, which the tool and the exporter now use.
- V1_LESSONS 9.1 says temperature 0 with a fixed seed is not
  reproducible. On 7 Oct it was, on Ollama and llama.cpp, on 16 of 16
  cases over three chains hours apart; on vLLM it was not.

Next: the owner reads the report and pushes; the GitHub check must be
green on all three systems. Then, if he wishes, his answer to issue 1 in
his own words. Owed before stage 6: the session in which the owner and
Cowork read the two carried prompts word for word.
