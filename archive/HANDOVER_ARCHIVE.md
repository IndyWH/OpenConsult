# HANDOVER archive

The older entries of HANDOVER.md, moved here as it passed 500 lines
(spec 5.3). Newest first. Not read by default.

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
