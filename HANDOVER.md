# HANDOVER

The record for OpenConsult v2: decisions and measurements, newest first.
It stays under 500 lines. Older entries move to HANDOVER_ARCHIVE.md.
The spec is V2_SPEC.md. The record for v1 is the HANDOVER.md on the main branch.

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

## 2026-10-04. Stage 3: the language model door

What was done:
- Every call to the language model goes through one door (openconsult/llm):
  a table of two jobs, the assessment and the alarm, each with its prompt
  file, answer form, limit on length (1,500 and 1,000 tokens) and limit on
  time (60 s each). One result: an answer, or a failure with its reason:
  too slow, too long, unreachable, bad form, or did not fit. Nothing is
  retried and nothing else is tried.
- The door writes the record of every call itself, table model_call at
  version 2: when, the job, the engine and its version, the model's tag
  and digest, the hash of the prompt sent, exactly what was sent, the raw
  reply, the tokens, the times and the outcome. It lives in the data
  folder only. A version 1 folder comes forward with nothing lost.
- The two prompts cross from v1 word for word as files in
  openconsult/prompts, with their forms and the fixed words around the
  transcript as frames; one loader; the app and the bench read the same
  files. Their hashes equal v1's recorded values and a test pins them.
- One pass (openconsult/consult): the alarm first, then the assessment,
  both with the patient line, the assessment with the earlier names as a
  stale list; the bookkeeping in code; a failed alarm is a third state,
  not judged, never read as no alarm.
- The joint between the door and an engine carries the parts of a call and
  one plain reply. The Ollama engine behind it uses the standard library.
- The app opens the browser by itself once it answers; --no-browser.
- This machine says whether Ollama runs and whether Gemma 4 QAT is
  present, on a machine with a suitable card only.
- The bench kit (openconsult/bench): the case list with checksums, 13
  chains, the replay through the same door, a writer that never writes
  over a result, the scoring with the marks of Tasks 5 and 5b, the word
  check, and the command openconsult-bench. Cases and results live in the
  private log folder; the repo holds the code and the marks only.
- No library added. NOTICE has nothing to add.

The rulings of spec 15.7, each in one line:
1. The stage 2 leftovers are in 15.6. Nothing to do here.
2. The browser opens by itself once the app answers; --no-browser for the
   tests and the GitHub check; no screen is not an error. Done.
3. The same marks: the word check rebuilt 1,898 of 1,898 assessment and
   1,898 of 1,898 alarm calls of arm D exactly, and the 13-chain run met
   every hard mark (7 of 7), both time marks and 8 of 9 soft marks. Done.
4. Gemma 4 QAT only; the joint is built so Claude and Qwen fit later with
   no change to the jobs. Done.
5. The engine bench is stage 3b. The bench takes any engine's address. Nothing else here.

Decided in the plan review of 4 Oct 2026 (Cowork), as decisions of this stage:
- The door sends "truncate": false. Measured that day: by default this
  Ollama (0.33.3) cut a 77,585-token input to 8,195 tokens, half the
  context, and answered as if nothing had happened; with the field it
  refuses with HTTP 400 exceed_context_size_error, which the door records
  as did_not_fit. The word check compares the message, model, think and
  options one by one and then the whole body with that one key removed.
  v1 runs with Ollama's default.
- The record holds the sha256 of the system message as sent, equal to
  v1's recorded value (the file's text less its final line break).
- What crosses the joint is the parts of a call, not Ollama's shape;
  keep_alive 30m lives in the Ollama engine.
- The two This machine lines show only on a machine with a suitable card;
  elsewhere nothing about Ollama is shown and Ollama is not asked.
- The soft marks stand as the numbers fixed against arm N in Task 5b
  (03, 04, 11, 13 at most 1 chain fired; 05 at most 4; script 12 at most
  13 and a median of at most 5 updates; restraint 13, 14, 15 at least 12;
  cleared at least 12 on each emergency script). Arm D's figure is shown
  beside each as v1 today.
- A failed alarm call is a third state in the pass result: not judged,
  with the reason. A script chain with any failed call is a failed chain;
  on 495 and the travel cases a failed pass meets no rule.
- The two time marks were set for a three-call pass; v2's pass is two
  calls (no affect call, which took part in no mark). Reported as written.
- R21's check names no publisher: the prompts hold no guideline word and
  every capitalised word in a prompt is on a known list in the test.
- The sampling override on the door is reachable from the bench only. It
  is not a setting. The engine's address is one fixed value in the store.
- browser.py sits at the top of the package beside cli.py.
- HOME_SO_FAR and the This machine lines are drafts for the owner.

For stages 6 and 12: the door's call waits until the reply comes. The
live consultation must not wait on it in the page's own loop, and a call
already sent cannot be taken back, only its result dropped. Nothing is
built for this now. Stage 6 also ties each model_call row to its
consultation (version 3) and shows a failed call's reason on screen.

Measurements:
- 141 tests, 3.5 s, none skipped (98 test functions; the parametrised
  cases counted as pytest counts them).
- App code about 2,230 lines in openconsult without the bench; the bench
  about 780; the start check 79. Templates and the style sheet 265.
  Tests 2,070 lines. Largest file bench/score.py, 292 lines; largest
  function, its marks table, 64 lines. CLAUDE.md 99 lines.
- The word check, no model: 1,898 of 1,898 assessment and 1,898 of 1,898
  alarm calls of arm D rebuilt exactly (495 and travel from Task 5, the
  13 scripts from Task 5b); Task 5's single-run script calls 242 of 242.
- The run: 16 cases, 13 chains each, 208 chains, 1,898 passes, 3,796
  calls, none failed, no cap hit, no thinking text; 2 h 24 min; the
  card's memory 17,379 to 17,846 MiB. Ollama 0.33.3; Gemma 4 QAT digest
  2dd70431...c4e4, as Tasks 5 and 5b; the two prompt hashes as v1's.
- Marks: hard 7 of 7; time 2 of 2 (495 median pass 4.63 s, slowest
  7.01 s, two calls); soft 8 of 9. The miss is S15 on script 15: 11
  chains of 13 passed the restraint verdict against a mark of 12 (arm N
  and arm D 13). In chains A2 and A3 the assessment at the last update
  gave an empty differential list, so no leader could be judged; the
  alarm fired and cleared in all 13. Task 5b saw four such empty lists
  in arm D, three of them on script 15. The owner and Cowork decide.
- The private word check printed nothing before every commit.
- A1, A2 and A3 gave the same answers throughout on 2 of 16 cases:
  temperature 0 with seed 42 is not reproducible on this machine
  (V1_LESSONS 9.1, seen again).

Made untrue by this stage:
- CLAUDE.md, Running it: the switch and the bench commands added here.
  README: now says the door exists. Both fixed in this commit.
- V2_SPEC.md 15.7, the details: "the model's profile holds ... keep_alive"
  is no longer so (it lives in the Ollama engine); "a request in Ollama's
  shape" nowhere, but the joint is now the plain parts; the two This
  machine lines are on a suitable card only; the record's prompt hash is of
  the text sent. Cowork folds these into the spec at the next brainstorm.
- Spec 15.7 says the assessment's frames and the alarm's frame live in
  the prompts folder as "the fixed words": they are the three .frame.txt files.

Next: the owner's check on port 8001 (the browser opens by itself; This
machine shows the two lines), then push; the GitHub check must be green
on all three systems. Then the stage 3b brainstorm, the engine bench.
