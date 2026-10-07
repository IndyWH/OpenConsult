# HANDOVER

The record for OpenConsult v2: decisions and measurements, newest first.
It stays under 500 lines. Older entries move to HANDOVER_ARCHIVE.md.
The spec is V2_SPEC.md. The record for v1 is the HANDOVER.md on the main branch.

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

## 2026-10-04. Stage 2: the skeleton

What was done:
- The app starts. One person accepts the statement, sees This machine,
  sets up a title, a name and a password, and logs in. The settings page
  has This machine and You. The log page shows the audit log. The reset
  command resets the password. Nothing of a patient, a model or sound.
- One package, openconsult, on Python 3.12 with the lock file committed.
  Libraries: fastapi, uvicorn, jinja2; for tests pytest and httpx2. All
  pure Python or prebuilt wheels; nothing needs a compiler or a card.
- SQLite, from Python's own library. Four tables at version 1:
  schema_version, app_user, audit_log, first_run. Triggers make the audit
  log append-only.
- A GitHub check on Linux, Windows and macOS at every push to v2:
  install from the lock, run the suite, start the app, check it answers,
  stop it. Outside steps pinned: actions/checkout v7.0.1 at
  3d3c42e5aac5ba805825da76410c181273ba90b1; astral-sh/setup-uv v9.0.0 at
  c771a70e6277c0a99b617c7a806ffedaca235ff9; uv 0.12.10.

The rulings of spec 15.6, each in one line:
1. CLAUDE.md now says only documents are limited at the root. Done.
2. CITATION.cff is stage 16. Nothing to do here.
3. Every commit from stage 2 ends with the co-author line. Done.
4. The statement comes first and is audited; no user before it. Done.
5. The 30 minute lock, a named value in logins.py; a consultation holds
   it off through a flag stage 6 will set. Done.
6. The app listens on 127.0.0.1 only, with no flag to change it. Done.
7. The You section: title, name, password, current password first,
   every change audited from what to what. Done.
8. v1's look, the style sheet cut from 195 to about 90 lines. Done.
9. Cloud services with a free trial: later stages. Nothing here.
10. The engine choice: stage 3 brainstorm. Nothing here.

Decided in the plan review of 4 Oct 2026 (Cowork), as decisions of this stage:
- The settings store holds only the data folder and the port; no table,
  no page and no change method until a page-changeable setting exists.
- No page script in stage 2. The refusal helper is server-side Python:
  the page is sent back with the message under the control pressed, and
  the helper raises if the message would land nowhere.
- The wrong-password wait: 1 second after the first wrong try, doubling,
  capped at 5 minutes, cleared by a right password or a restart. A design
  choice, not a measurement; named in logins.py with the review as source.
- A card is suitable when its memory rounds to 24 GB or more.
- After set-up the user goes to the login page.
- The Mac sentence and the card-could-not-be-read sentence are drafts.
- A reset in another process ends the app's logins through a generation
  number on the user row; each login remembers the one it was made under.
- The This machine step is done when its Continue is pressed.
- No test holds its own copy of a sentence. Every sentence is in
  openconsult/words.py; tests take it from there or check which case the
  code chose. The owner corrects wording in that one file.
- The lock clears a screen nobody is using: every page behind the login
  carries a plain refresh instruction to itself with ?quiet after the
  time left. A ?quiet request never counts as use. If another tab kept
  the login alive the page waits again for the time left; otherwise the
  lock line is written then and the page goes to login with the reason.

For stage 6: when a page has text being typed, typing must count as use.
That needs a page script and is that stage's work. The quiet refresh also
re-renders a page, so a page with a form in progress needs the script to
hold the refresh off while typing. The consultation_running flag on
Logins is the hook for the live page.

Three fixes after Cowork's check, same day (stage-prompts/STAGE_02_FIXES.md):
- A page sent back by a form post now names its own GET address for the
  timed move, so a refused Settings form left alone locks to the login
  page and writes the lock line, instead of ending on a 405.
- A wrong current password in Settings is written to the log and counts
  on the same growing wait as the login page; while the wait runs both
  forms refuse and change nothing. The refusal sentence now says the wait.
- No test runs the real nvidia-smi: the command takes the machine like
  its saying and serving functions, and its test gives a made-up one.

Measurements (after the fixes):
- 76 tests, 1.9 s, none skipped. The twins and the parametrised cases
  are counted as pytest counts them.
- App code about 1,350 lines in 20 Python files; largest routes.py, 209 lines.
  Templates and the style sheet, 261 lines. Tests 959 lines.
- Largest function: well under 80 lines. No file near 600.
- The private word check printed nothing before every commit.

Not in the plan: the plan's commits 10 and 11 became one commit, because
the login tests need a set-up user and the only honest way to one is
through the first-run screens. Two drafted sentences were not used:
"Accept the statement first." and "OpenConsult is already set up.",
because a form sent at the wrong step goes back to the right step
instead.

Made untrue by this stage:
- CLAUDE.md, Running it: rewritten here. README: no longer says the app
  does not run. Both are fixed in this commit.
- V2_SPEC.md 15.6 "the settings store ... a change is written to the
  audit log": true from the first page-changeable setting, not in stage 2.
  And "plain pages, with their scripts in their own files": there are no
  scripts yet. Cowork folds both into the spec at the next brainstorm.

Next: the owner's check on port 8001, then push; the GitHub check must be
green on all three systems. Then the stage 3 brainstorm.

## 2026-10-04. Stage 1: the v2 branch is opened

What was done:
- A new branch, v2, in its own folder. It shares no history with main.
- Three commits: the spec and the lessons; the licence, the notice and the
  ignore list; CLAUDE.md, this file, a holding README and the stage prompt.
- No code. Nothing runs yet.

Decided by the owner on 4 Oct 2026 (spec 15.5):
- The spec is approved. It changes only by a dated ruling of his.
- A privacy pass before anything is public. Nothing committed names a
  family member, a colleague, a home or a place.
- One spec, and it lives in this folder.
- The licence stays as v1: AGPL-3.0-or-later.

Waiting for later stages:
- The community files (CONTRIBUTING, SECURITY, the code of conduct,
  CITATION.cff, the issue templates) cross from v1 in stage 16, before the
  join of spec 14.3.
- NOTICE gains an entry in the same commit as each third-party component.

Made untrue by this stage: nothing.

Next: stage 2, the skeleton, after its brainstorm.
