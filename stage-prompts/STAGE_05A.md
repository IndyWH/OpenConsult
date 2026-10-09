STAGE 5a of OpenConsult v2.0: the transcription door

WHAT THIS IS
OpenConsult v2.0 is a rewrite, built on the branch v2 in its own folder.
Stage 5 is about speech. It is built in five steps, 5a to 5e. This is 5a, the first.
5a builds the one door through which every word of speech reaches the app,
the first speech choice behind it (WhisperX with pyannote), the rule that no words are written
where nobody spoke, and the self-test that finds a broken install at once.
From the patient's side: every word the patient says must reach the page, or the doctor must be
shown where it did not. A word that was never said must not reach the page at all.
No consultation, no recording from a microphone, no bench and no Alba yet.
The spec is V2_SPEC.md. Stage 5 is section 15.9 of it. Read that section first and build what it says for 5a.
This prompt gives the order of work and the rules. Where the two differ, the spec wins: stop and report.
OpenConsult is a research and education prototype. Never real patients.

MODEL
This stage runs on Fable 5.1 at high effort.
Say in your first line which model you are. If you are not Fable 5.1, stop there.

THE FOLDERS
V2    /home/indy/Projects/OpenConsult2
      The repo. Branch v2. All code and all commits are made here.
LOGS  /home/indy/Work/openconsult-review/v2-logs
      Private. Your plan, your log, your report and your working data folder go here.
      This prompt is here.
V1    /home/indy/Projects/consultation-ai
      Read only. A reference. Change nothing. The only git command allowed there is:
      git -C /home/indy/Projects/consultation-ai rev-parse HEAD
      Never read V1/.env or any other file that holds a key or a token.
OLD   /home/indy/Work/openconsult-review/v1.1-logs
      Read only. The record of v1's speech benches. Change nothing there. Run nothing there.

WHAT TO READ IN V1 AND IN OLD
V1/app/transcription.py
   The live Whisper: the model, its settings, and the line of text it is given to read.
   That line of text is NOT carried into v2 (spec 15.9, ruling 3).
V1/app/live.py and V1/app/live_segments.py
   How sound becomes live lines, and when a line is final.
V1/app/finalize.py
   transcribe_and_diarise, raw_segment_records and merge_into_turns: the pass at Stop.
   Leave the parts about Alba, about roles and about the note. They belong to later stages.
V1/speech_nemotron/worker.py and V1/app/speech_pipeline.py
   How v1's app and its one separate speech worker talk. This is the reference for every worker of v2.
V1/pyproject.toml
   The speech libraries, their versions, the three overrides, and the reason given for each.
V1/tests/data/jfk.wav
   The test clip. 11.0 seconds, 16 kHz, one channel.
   sha256 59dfb9a4acb36fe2a2affc14bacbee2920ff435cb13cc314a08c13f66ba7860e
V1/LESSONS_FOR_V2.md
OLD/TASK17_SCRIPTED_BENCH.md, OLD/TASK18_DROPPED_SPEECH.md, OLD/TASK19_PROMPT.md
   What v1's speech benches found, and how the pass at Stop was fixed on 4 Oct.
   Read the reports. Open no recording and no raw result file: 5a needs none of them.

BEFORE YOU START
1. Read V2/CLAUDE.md and V2/HANDOVER.md.
   Read V2/V2_SPEC.md sections 4, 5, 6, 11, 13.4, 15.3, 15.4 and 15.9.
   Read the details of 15.6 and 15.7 for the ways of working already set (This machine, the data folder, the door of stage 3).
   Read V2/V1_LESSONS.md: the twelve that matter most, then sections 1, 2, 7, 8 and 15.
2. Check the spec with sha256sum. It must be:
   d47183c808de41203712270cfda9a236292116c0d9fbb6c38a299bf521992289  V2_SPEC.md
   If it differs, stop and report. Do not go on.
3. Check V2. The branch is v2. HEAD is b85d05402541a76377469cb6b525fe6e33d14009.
   git status --porcelain shows one line only: V2_SPEC.md modified.
   If anything else is changed or untracked, stop and report.
4. Run the one allowed command in V1. It must give b2e61d0705ec593cfde70638429e287e68c56f1c.
   Keep the value. You check it again at the end.
5. Check that uv is installed: uv --version. If it is not, stop and report.
6. Look, read only, and write what you find in your log:
   whether anything answers on http://127.0.0.1:8000 (that is the v1 service);
   the graphics card's memory, used and free (nvidia-smi);
   the free space on the disk that holds LOGS and on the disk that holds the user's data folder.
   Change nothing. Do not stop here whatever you find: the gate for the card is in Part 4.
7. Look, read only, whether the models that the WhisperX with pyannote choice needs are already
   in this machine's shared model cache. Write the names and sizes you find in your log.
   Never print a token. Never read a file that holds one.

RULES
1. Write only in V2 and in LOGS. Never in V1. Never in OLD.
2. Do not change one character of V2_SPEC.md or V1_LESSONS.md. If the spec is wrong or silent, report it.
3. If a choice is a product or clinical judgement, stop and report it. Do not decide it.
4. No git push. No sudo. No service command. Nothing in V1 is written, not even by git.
   Install no system software. Pull, delete, create and change no model in Ollama.
5. Never use the owner's real data folder, and never use port 8000 or port 8001.
   Port 8000 is v1. Port 8001 and the real data folder are for the owner's own check.
   Your own working data folder is LOGS/stage5a-data. When you run the app yourself, give it that folder,
   a spare port and --no-browser, and stop it afterwards. Never open a browser on this machine.
6. The v1 service may be running on this machine while you work. Do nothing that could disturb it.
   Until the gate of Part 4 is passed: load no model on the graphics card, build no speech environment,
   and download no model. Parts 1 to 3 need none of these.
7. The only sound that enters V2 is the test clip. No recording of a consultation is opened in 5a,
   and no word a patient said goes into V2 or into a commit.
   Silence and noise for your checks are made by code, never taken from a recording.
8. No text is given to any speech model: no prompt, no hint, no list of words (spec 15.9, ruling 3).
   No prompt file of stage 3 changes. The two prompt hashes of stage 3 stay as they are.
9. Before each commit, run the private word check on the staged files. It must print nothing:
   git diff --cached --name-only -z | xargs -0 grep -n -i -w -F -f /home/indy/Work/openconsult-review/v2-logs/private-words.txt
   If it prints a line, stop and report. Do not edit a file to make it pass.
   Never copy the word list, or any word from it, into V2 or into a commit message.
10. Each commit: one logical change, the suite green before it, the why in the message.
    No personal names and no host names in a message.
    Each commit message ends with this line, after one empty line (spec 15.6, ruling 3):
    Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
    That is the only address allowed in a commit message.
11. Commands and short results go to LOGS/stage5a.log. Long output never goes into chat.
12. Nothing is built switched off, and nothing is built for a later stage (R31).
    5a builds no Nemotron, no cloud, no replay bench, no scoring, no check at Stop for missing speech,
    nothing that tells who spoke by the voice or by the words, no mark on a drug name, no consultation,
    no recording from a microphone, no unloading of the language model at Stop,
    no control to choose a speech choice, and no download from a page.
13. Nothing in the base app assumes Linux. The door, the made-up worker and the suite must run on Windows and macOS.
    The suite needs no graphics card and no speech library. It must pass on GitHub's machines, which have neither.
    The base app gains no heavy library: no PyTorch and nothing that brings it (spec 5.1; V1_LESSONS 7.1).
    Keep the list of every place where the three systems differ, and say for each how you know it works.
14. The size targets of spec section 5 hold: no file over 600 lines, no function over 80,
    tests no larger than the app, the suite under a minute.
    If a target cannot be met, report it and say why. Do not squeeze code to fit a number.
15. What a speech model hears is never asserted in the suite. It is checked in Part 4, on the real model (spec 5.2).
16. In the shared model cache, delete nothing and change nothing that is already there.
17. If a step fails, stop and report.

PART 1. TWO COMMITS BEFORE THE PLAN
Commit 1. Subject: Stage 5a: the spec as the stage 5 brainstorm left it
   V2_SPEC.md only. The spec is committed before the code (V1_LESSONS 11.3).
Commit 2. Subject: Stage 5a: the stage prompt
   Copy this file to V2/stage-prompts/STAGE_05A.md. Prove with cmp that it is identical.

PART 2. THE PLAN, THEN STOP
Write your plan to LOGS/STAGE5A_PLAN.md. It holds:
1. The files you will write, each with its job in one line and its expected size.
2. The libraries. For the base app: any you add, with name, version, licence and why. Expect none or very few.
   For the speech environment: each library with name, version and licence, and its Python version.
   Start from v1's versions as Task 19 left them. For each of v1's three overrides, say whether v2 still needs it and why.
   Nothing may patch a library for the whole process (V1_LESSONS 1.11). Say how v2 avoids v1's patch of the model loader.
3. The door: exactly what the app hands to it and what it gets back (spec 11.4),
   what a speech choice declares about itself (spec 11.5, rule 5), and the failures with their reasons.
   Say in three lines how a second speech choice would be added in 5b. Do not build it.
4. The worker: how the app and the worker talk, how the worker starts, how the app knows it is ready,
   what happens when it dies, and how it is stopped. Say what you keep of v1's way and what you change.
5. The speech environment: where it lives, how the command builds it from the committed lock file,
   its size on disk and the time to build it. Say what the command does when it is run a second time.
6. The models: each with its name, its revision, its size and where it is stored.
   pyannote's model needs its makers' terms to be accepted. Say how it is reached on this machine
   with no secret read or printed. If the owner must do something, give it as one step.
7. The live path: how sound becomes lines, when a line is final, and the delay you expect from a word to its line.
   Say which parts are ported from v1 and which are written fresh.
8. No words from silence: where the rule sits in the door, what it measures, the threshold and its source,
   and what is kept of the text it refuses. Say plainly that the threshold is not yet measured on raw sound (spec 15.9, the details).
9. The pass at Stop: its steps, how the number of speakers is given to it, how the raw segments are kept,
   and the merge of segments into turns as a plain function.
   Say how you will prove that no text is given to either Whisper model (rule 8).
10. The self-test: the clip with its source, its licence and its checksum, the words you expect,
    the rule for a pass, the command, and where the result is stored.
    If a table or a column is added: the step from table version 2 to version 3.
    The owner's real database is at version 2, with his user in it. Say how it is brought forward with nothing lost.
11. This machine: the new lines, word for word, for each state: not installed, installed and not yet tested,
    passed, failed. Say what a machine with no suitable card shows.
12. Every test you intend, each with the rule, the ruling or the incident it pins (spec 5.2; V1_LESSONS 8.8).
13. Every new sentence the app will show to the user, in one list, so the owner can correct the wording.
    They live in openconsult/words.py, and no test holds its own copy of one.
14. The commits you will make, in order.
15. The list for rule 13: where the three systems differ.
16. What Part 4 will load on the graphics card, in what order, and the memory you expect at the highest point.
17. Anything in the spec that is wrong, silent or in conflict. Do not fix it yourself.
18. Whether 5a fits in one session. If you judge it does not, name the point where you would split it.
Then print five lines at most, and stop.
Wait for the owner. He will type: Approved. Go.
He may first tell you to read a review file in LOGS. If so, read it and follow it. It may change your plan.

PART 3. THE BUILD
Build what spec 15.9 says for 5a. This is the suggested order. Your plan may change the order and say why.
1. The door, with the made-up worker behind it for the suite. One result: lines, or a failure with its reason.
   If the speech choice is absent or its worker has died, the door says so. Nothing else is tried (spec 10.4).
2. The rule against words from silence, in the door, as a plain function with its own tests.
   What it refuses is kept and marked. It is never thrown away.
3. The worker frame: start, ready, talk, death, stop. Then the WhisperX with pyannote worker on it.
   The worker's code is in V2. It is run only by the speech environment's own Python.
   The app never imports it. Prove that with a test in a fresh Python, as stage 3b proved it for the bench engines.
4. The pass at Stop: the number of speakers given, the raw segments kept, the merge as a plain function.
5. The lock file of the speech environment, committed, and the command that builds the environment from it.
   Do not run the build yet. It waits for the gate of Part 4.
6. The test clip, copied from V1 with its checksum proven, with a narrow exception in the ignore list
   in the same commit, and its entry in NOTICE. Then the self-test and its command.
7. This machine: the new lines. The page reads the stored result. It loads no model and never hangs.
8. The documents, in the last commit:
   CLAUDE.md: under Running it, the new commands. It is 99 lines today and must stay under 100: make room, lose nothing a builder needs.
   README.md: the line that says what this version can do so far. Draft it. The owner corrects it.
   NOTICE: one entry for each library added, in the commit that adds it.
   HANDOVER.md: a new entry at the top. What was done, the rulings of spec 15.9 in one line each,
   the measurements, and what this stage has made untrue. It must stay under 500 lines:
   move the oldest entries to HANDOVER_ARCHIVE.md if needed.
   The last commit is made after Part 4, so that the measurements are in it.

PART 4. THE CHECKS
Item 1. The suite is green. Give the number of tests, the time, and the number skipped, which must be none.
Item 2. A fresh Python with only the base app installed: the app starts, answers and stops, and no speech library can be imported.
   Run the start step of the GitHub check as it is: uv run python .github/scripts/start_check.py
Item 3. If the tables changed: open a database made by today's code at version 2, with a made-up user in it,
   using the new code. The user must still log in. On a temporary folder, never on the real one.

THE GATE FOR THE CARD. Items 4 to 9 load models and build the environment. Before item 4:
   Ask http://127.0.0.1:8000 once. If anything answers, the v1 service is running.
   Then print exactly this line and stop: Waiting for v1 to be switched off.
   The owner will type: v1 is off. Go.
   When nothing answers on port 8000, read the card's free memory. You may then ask Ollama to unload
   gemma4:26b-a4b-it-qat, and nothing else. If the free memory is still less than your plan's figure
   plus 1,000 MiB, stop and report.
Item 4. Build the speech environment with your command, into LOGS/stage5a-data. Write the time and the size on disk in your log.
   Run the command a second time and write what it did.
Item 5. Run the self-test with your command, on LOGS/stage5a-data. It must pass.
   While it runs, a sampler writes the graphics card's memory use to LOGS every 2 seconds (nvidia-smi, read only).
   Write in your log: the seconds to load, the seconds from the end of a piece of sound to its line,
   the seconds of the pass at Stop, the words heard live, the words of the transcript at Stop, and the card's memory at its highest.
Item 6. Start the app on LOGS/stage5a-data with a spare port and --no-browser. Set up a made-up user.
   Read This machine: it must say that the choice is installed and that the self-test passed, with the date.
   Stop the app.
Item 7. Silence. Feed the live path 60 seconds of made silence, then 60 seconds of made low noise. No line may be accepted.
   Then run the pass at Stop on the same two sounds. Write in your log what each model wrote and what the rule refused.
   If any text is accepted, stop and report.
Item 8. No text to a model. Run the self-test again with a record of every argument that reaches the two Whisper models.
   No prompt, no hint and no list of words may be set. Give the record's lines in your report.
Item 9. Kill the worker in the middle of the clip. The door must give a failure with its reason, the app must stay up,
   and nothing else may be tried. Then a new start must work.
Item 10. git status --porcelain is empty. git log --oneline lists your commits on v2.
   V1 HEAD is the value you kept. Nothing in the shared model cache was deleted or changed: list what you added to it.
   Port 8000 and port 8001 were never used by you.
Item 11. Write LOGS/STAGE5A_REPORT.md. Put the most important finding for the patient first:
   did the self-test pass, yes or no, and was any word written in silence, yes or no. Then:
   the figures of item 5; what the rule refused in item 7; the record of item 8; the result of item 9;
   the models with their names, revisions and sizes; the libraries of the speech environment with versions and licences;
   the environment's size and build time; the card's memory at its highest;
   the commits with their hashes; the files with their line counts; any target missed;
   the tests, each with what it pins; every new sentence shown to the user; the list for rule 13;
   the exact commands for the owner's own check, as one block with no quotation marks, in the order he runs them:
   build the speech environment in his real data folder, run the self-test, start the app on port 8001;
   the size of LOGS/stage5a-data and the one command that removes it;
   anything you flagged.

FINAL MESSAGE
Ten lines at most:
the self-test, passed or not, and whether any word was written in silence,
the number of commits and the last hash,
the number of tests, the suite time, none skipped,
that the private word check printed nothing before every commit,
that V1 HEAD is unchanged and that ports 8000 and 8001 were never used,
any target missed,
anything you flagged,
then this line for the owner: Tell Cowork: Stage 5a done. Do not push yet.
