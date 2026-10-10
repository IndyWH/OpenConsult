STAGE 5b of OpenConsult v2.0: the Nemotron choice and the two cloud choices

WHAT THIS IS
OpenConsult v2.0 is a rewrite, built on the branch v2 in its own folder.
Stage 5 is about speech. It is built in five steps, 5a to 5e. This is 5b, the second.
5a built the one door through which every word of speech reaches the app, and the first speech choice behind it.
5b puts three more choices behind the same door:
Nemotron, which runs on the graphics card, and two cloud services, Speechmatics and AssemblyAI,
for a user whose computer has no suitable graphics card.
Each is proven by the self-test of 5a.
From the patient's side: whichever choice the doctor uses, every word the patient says must reach the page,
and a word that was never said must not. With a cloud choice the patient's words leave the room,
so they go only where the owner has ruled, and nowhere else, and never without it being said.
No consultation, no recording from a microphone, no bench and no Alba yet.
The spec is V2_SPEC.md. Stage 5 is section 15.9 of it. Read that section first:
rulings 1 to 11, the details of the stage and of 5a, and then the details of 5b. Build what it says for 5b.
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
V1/speech_nemotron/worker.py, nemotron_stream.py, setup.sh and README.md
   v1's Nemotron worker. It runs the PAIR: the 3.5 model tied to the speaker model.
   That pairing is NOT carried into v2 (spec 15.9, ruling 8).
   Carry what is sound in the handling of the stream: how sound is fed, when a line is final, the order of lines.
   setup.sh pins the NeMo commit and the revision of the speaker model.
OLD/task14_run.py and OLD/task17_nemo.py
   How the English model was loaded and run on its own (arm 2 of Task 14, arm 3 of Task 17),
   with its revision and its setting. This is the reference for the words of the Nemotron choice.
OLD/TASK13_NEMOTRON.md, OLD/TASK14_NEMOTRON_WER.md, OLD/TASK17_SCRIPTED_BENCH.md
   What v1 measured: the card's memory, the delay before the second voice is heard, the errors of each arm.
   Read the reports. Open no recording and no raw result file: 5b needs none of them.
v1 has its own Nemotron environment in the home folder, built by setup.sh. Do not use it and do not change it.

BEFORE YOU START
1. Read V2/CLAUDE.md and V2/HANDOVER.md.
   Read V2/V2_SPEC.md sections 4, 5, 6, 7.2, 7.3, 10.4, 11, 15.3, 15.4 and 15.9.
   Read V2/V1_LESSONS.md: the twelve that matter most, then sections 1, 2, 7, 8 and 15.
   Read the code of 5a: everything in V2/openconsult/speech, the speech lines of settings/machine.py,
   cli.py, and their tests. 5b is built on it and in its way.
2. Check the spec with sha256sum. It must be:
   a402d9f36d960089d58244c6e43da31a8839cc868db1269fa656afe513403b9a  V2_SPEC.md
   If it differs, stop and report. Do not go on.
3. Check V2. The branch is v2. HEAD is 7ca52608070a3580be14d2195cb17c21ce1db974.
   git status --porcelain shows one line only: V2_SPEC.md modified.
   If anything else is changed or untracked, stop and report.
4. Run the one allowed command in V1. It must give b2e61d0705ec593cfde70638429e287e68c56f1c.
   Keep the value. You check it again at the end.
5. Check that uv is installed: uv --version. If it is not, stop and report.
6. Look, read only, and write what you find in your log:
   whether anything answers on http://127.0.0.1:8000 (that is the v1 service; it should be off);
   the graphics card's memory, used and free (nvidia-smi);
   the free space on the disk that holds LOGS and on the disk that holds the user's data folder;
   whether LOGS/stage5a-data still exists (the working data folder of 5a, with the WhisperX environment in it).
   Change nothing. Do not stop here whatever you find: the gates are in Part 4.
7. Look, read only, whether the two Nemotron models are already in this machine's shared model cache,
   and at which revisions. Write the names, revisions and sizes you find in your log.
   Never print a token. Never read a file that holds one.

RULES
1. Write only in V2 and in LOGS. Never in V1. Never in OLD.
2. Do not change one character of V2_SPEC.md or V1_LESSONS.md. If the spec is wrong or silent, report it.
3. If a choice is a product or clinical judgement, stop and report it. Do not decide it.
4. No git push. No sudo. No service command. Nothing in V1 is written, not even by git.
   Install no system software. Pull, delete, create and change no model in Ollama.
5. Never use the owner's real data folder, and never use port 8000 or port 8001.
   Port 8000 is v1. Port 8001 and the real data folder are for the owner's own check.
   Your own working data folder is LOGS/stage5b-data. When you run the app yourself, give it that folder,
   a spare port and --no-browser, and stop it afterwards. Never open a browser on this machine.
   There is one exception to this rule, and it is in the gate for the keys in Part 4: one copy of one file.
6. Until the gate for the card in Part 4 is passed: load no model on the graphics card,
   build no speech environment, and download no model. Parts 1 to 3 need none of these.
   Until the gate for the keys in Part 4 is passed: open no connection to either cloud service.
   Parts 1 to 3 need none: a made-up service stands in for both, inside the suite.
7. THE KEYS. The owner's two keys are secrets. Never print one. Never read the file that holds them into chat,
   into your log, into your report or into a commit. Never put a key on a command line.
   You may count lines in that file by name. You may not show a value.
   No key, and no part of one, goes into V2, into LOGS/stage5b.log, into the plan or into the report.
8. THE ADDRESS. Sound goes to a cloud service through its EU address and through no other (spec 15.9, ruling 9).
   Speechmatics: eu.rt.speechmatics.com. Never its global address, which may send a connection to any region.
   AssemblyAI: streaming.eu.assemblyai.com.
   Confirm both on the makers' own pages in your plan. The address is a named constant in code.
   No setting, no file and no value of the environment can change it.
9. WHAT LEAVES THE MACHINE. The only sound you send to a cloud service is the test clip of the self-test,
   and silence and noise made by code. No recording of a consultation is opened in 5b,
   and no word a patient said goes into V2, into a commit or to a service.
10. No text is given to any speech model or service: no prompt, no hint, no list of words, no custom dictionary,
    no key terms (spec 15.9, rulings 3 and 9). No prompt file of stage 3 changes. The two prompt hashes of stage 3 stay as they are.
11. The rules of ruling 9 are never worked round. If a service cannot do what the ruling says through its EU address
    (the medical option, live speaker labels), stop and report. Do not switch an option off, and do not use another address.
12. Before each commit, run the private word check on the staged files. It must print nothing:
    git diff --cached --name-only -z | xargs -0 grep -n -i -w -F -f /home/indy/Work/openconsult-review/v2-logs/private-words.txt
    If it prints a line, stop and report. Do not edit a file to make it pass.
    Never copy the word list, or any word from it, into V2 or into a commit message.
13. Each commit: one logical change, the suite green before it, the why in the message.
    No personal names and no host names in a message.
    Each commit message ends with this line, after one empty line (spec 15.6, ruling 3):
    Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
    That is the only address allowed in a commit message.
14. Commands and short results go to LOGS/stage5b.log. Long output never goes into chat.
15. Nothing is built switched off, and nothing is built for a later stage (R31).
    The list of what 5b does not build is in the details of 5b in the spec. Read it before you plan.
16. Nothing in the base app assumes Linux. The door, the cloud workers, the made-up workers and the suite
    must run on Windows and macOS. A cloud choice must work with the base app alone:
    for a laptop user that is the whole install (spec 6.4).
    The suite needs no graphics card, no speech library, no key and no internet. It must pass on GitHub's machines.
    The base app gains no heavy library: no PyTorch and nothing that brings it (spec 5.1; V1_LESSONS 7.1).
    Keep the list of every place where the three systems differ, and say for each how you know it works.
17. The size targets of spec section 5 hold: no file over 600 lines, no function over 80,
    tests no larger than the app, the suite under a minute.
    If a target cannot be met, report it and say why. Do not squeeze code to fit a number.
18. What a speech model or a service hears is never asserted in the suite. It is checked in Part 4 (spec 5.2).
    What the app SENDS to a service is asserted in the suite, against the made-up service.
19. In the shared model cache, delete nothing and change nothing that is already there.
20. The WhisperX with pyannote choice of 5a must behave exactly as it does today. No test of 5a is weakened or deleted.
    If a test of 5a must change because the door gains something, say which and why in your plan.
21. No comment, no test name and no message cites a private plan review or this prompt by a private name.
    A comment gives the reason itself, or cites the spec or V1_LESSONS.
22. If a step fails, stop and report.

PART 1. TWO COMMITS BEFORE THE PLAN
Commit 1. Subject: Stage 5b: the spec as the 5b brainstorm left it
   V2_SPEC.md only. The spec is committed before the code (V1_LESSONS 11.3).
Commit 2. Subject: Stage 5b: the stage prompt
   Copy this file to V2/stage-prompts/STAGE_05B.md. Prove with cmp that it is identical.

PART 2. THE PLAN, THEN STOP
Write your plan to LOGS/STAGE5B_PLAN.md. It holds:
1. The files you will write or change, each with its job in one line and its expected size.
2. The tidy-up commit (ruling 11): every file with a comment or a test name that cites a private plan review,
   with the count in each. Say how you will prove that the commit changes comments and names only.
3. The three points carried from 5a (the details of 5b, What opens 5b): how each is put right, in two lines each.
4. The door: exactly what changes in open, feed and stop, and in what a choice declares.
   The number of speakers given at open for a choice whose labels are live.
   What Stop gives back for a choice with one transcript, and how code makes sure it is the lines already given.
   The new failures, each with the sentence the user would read.
   Say how you know the choice of 5a behaves as before (rule 20).
5. The Nemotron worker.
   The libraries of its environment, each with name, version and licence, and its Python version.
   NeMo pinned to one commit: say which, and how the committed lock file makes the build repeatable.
   The two models, each with its name, its revision, its size, its licence and where it is stored.
   The English model at the revision and the setting of arm 3 of Task 17: confirm both from OLD/task14_run.py.
   The speaker model at v1's revision. Its streaming setting: quote the row of its own card that you take, and say why that row.
   How the two models are fed the same sound and share nothing else.
   The join: what it takes, what it gives, when a word has no speaker, and the tests that pin it.
   When a line is final, and the delay you expect from a word to its line.
   What is carried from v1's worker and what is written fresh.
6. The cloud workers. For each of the two services:
   the library for the connection, with name, version and licence, and why no maker's kit, or why one;
   the EU address, with the page that gives it;
   the opening message, word for word, with the medical option on, speaker labels on and no word list;
   how the service's text that is final and its text that is not yet final become lines and partial text;
   how its speaker labels become speakers, and which of its labels become no speaker;
   for AssemblyAI, what a revised label does, and how code makes sure that no word and no time changes;
   whether it gives a confidence score, and of what;
   the sample rates it takes, with the page that says so, and what the worker does with a rate it does not take;
   how the session is ended at Stop so that the last words arrive;
   each failure of the service (a refused key, no credit, no internet, the service down, a limit reached)
   and the reason the door gives for it;
   what happens when the connection drops in the middle of a session. Expect a plain failure. Nothing reconnects in silence.
   THE FOUR CONFIRMATIONS, each with the address of the page and the sentence quoted (the details of 5b):
   Speechmatics' medical option runs live, with speaker labels, through the EU address;
   a free account may use that address;
   AssemblyAI's medical mode and speaker labels run on its EU address for live speech;
   the sample rates each takes.
   If one is not so, or you cannot find a page that says it, say so plainly in the plan. Do not guess.
7. The keys: the one module that reads them, the file and the two names, how a key reaches its worker
   without a command line, and the tests that pin that a key appears nowhere.
8. The address rule: how it is pinned, and how the suite tests a worker against the made-up service
   without leaving any way for a setting, a file or the environment to change the address.
9. Never silent, in both directions: the tests.
10. The self-test for the three new choices: the number of speakers given for the clip, the commands with their exact words,
    and what a command does when no choice is named. The owner already runs: uv run openconsult self-test
11. This machine: the new lines, word for word, for each choice and each state.
    Say what a machine with no suitable card shows.
12. If a table or a column is added: the step from table version 3 to version 4.
    The owner's real database is at version 3, with his user in it. Say how it is brought forward with nothing lost.
13. Every test you intend, each with the rule, the ruling or the incident it pins (spec 5.2; V1_LESSONS 8.8).
14. Every new sentence the app will show to the user, in one list, so the owner can correct the wording.
    They live in openconsult/words.py, and no test holds its own copy of one.
15. The commits you will make, in order.
16. The list for rule 16: where the three systems differ.
17. What Part 4 will load on the graphics card, in what order, and the memory you expect at the highest point.
    What Part 4 will send to each cloud service, in seconds of sound.
18. Anything in the spec that is wrong, silent or in conflict. Do not fix it yourself.
19. Whether 5b fits in one session. If you judge it does not, name the point where you would split it.
Then print five lines at most, and stop.
Wait for the owner. He will type: Approved. Go.
He may first tell you to read a review file in LOGS. If so, read it and follow it. It may change your plan.

PART 3. THE BUILD
Build what spec 15.9 says for 5b. This is the suggested order. Your plan may change the order and say why.
1. The tidy-up commit of ruling 11. Comments and names only.
2. The three points carried from 5a.
3. The door: what the new choices need, with made-up workers behind it for the suite.
4. The keys: the one module, the example file with empty values, and the tests.
5. The cloud workers on the worker frame of 5a, against the made-up service: Speechmatics, then AssemblyAI.
   The address rule and never silent in both directions, each with its tests.
6. The Nemotron choice: the join as a plain function with its tests, then the worker, the fetch script,
   and the committed lock file. Do not run the build of the environment yet. It waits for the gate for the card.
7. The self-test and the commands for the three new choices.
8. This machine: the new lines. The page reads stored results. It makes no connection, loads no model and never hangs.
9. The documents, in the last commit:
   CLAUDE.md: under Running it, the new commands. It is 99 lines today and must stay under 100: make room, lose nothing a builder needs.
   README.md: the line that says what this version can do so far. Draft it. The owner corrects it.
   NOTICE: each library added, in the commit that adds it; the two Nemotron models with their licences; the two services by name.
   HANDOVER.md: a new entry at the top. What was done, rulings 8 to 11 in one line each, the measurements,
   and what this stage has made untrue. It is 422 lines today and must stay under 500:
   move the oldest entries to archive/HANDOVER_ARCHIVE.md if needed.
   The last commit is made after Part 4, so that the measurements are in it.

PART 4. THE CHECKS
Item 1. The suite is green. Give the number of tests, the time, and the number skipped, which must be none.
Item 2. A fresh Python with only the base app installed: the app starts, answers and stops, and no speech library can be imported.
   Run the start step of the GitHub check as it is: uv run python .github/scripts/start_check.py
   In the same fresh Python, start one cloud worker against the made-up service and stop it: the base app alone is enough.
Item 3. If the tables changed: open a database made by today's code at version 3, with a made-up user in it,
   using the new code. The user must still log in. On a temporary folder, never on the real one.

THE GATE FOR THE CARD. Items 4 to 10 build the Nemotron environment and load models. Before item 4:
   Ask http://127.0.0.1:8000 once. If anything answers, the v1 service is running.
   Then print exactly this line and stop: Waiting for v1 to be switched off.
   The owner will type: v1 is off. Go.
   When nothing answers on port 8000, read the card's free memory. You may then ask Ollama to unload
   gemma4:26b-a4b-it-qat, and nothing else. If the free memory is still less than your plan's figure
   plus 1,000 MiB, stop and report.
Item 4. Build the Nemotron environment with your command, into LOGS/stage5b-data. Write the time and the size on disk in your log.
   Run the command a second time and write what it did.
Item 5. Run the Nemotron self-test with your command, on LOGS/stage5b-data. It must pass.
   While it runs, a sampler writes the graphics card's memory use to LOGS every 2 seconds (nvidia-smi, read only).
   Write in your log: the seconds to load, the seconds from the end of a piece of sound to its line,
   the seconds at Stop, the words heard, the speaker given to each line, and the card's memory at its highest.
Item 6. The words are untouched by the speaker model. With a script kept in LOGS, never in V2,
   run the English model on its own on the clip, in the same setting, and set its words beside the worker's words.
   They must be the same, word for word. If they differ, stop and report.
Item 7. Silence. Feed the Nemotron choice 60 seconds of made silence, then 60 seconds of made noise at -50 dBFS,
   then 60 seconds at -30 dBFS, and Stop after each. No line may be accepted.
   Write in your log what the model wrote and what the rule refused. If any text is accepted, stop and report.
Item 8. No connection. Run the Nemotron self-test once more with every connection attempt and every name lookup
   of the worker recorded, as in 5a. The record must be empty.
Item 9. Kill the Nemotron worker in the middle of the clip. The door must give a failure with its reason,
   the app must stay up, and nothing else may be tried. Then a new start must work.
Item 10. If LOGS/stage5a-data still exists: run the self-test of the WhisperX with pyannote choice on it,
   with the code as it now is. It must pass as it did in 5a. Never write into that folder beyond what the self-test stores.
   If the folder is gone, say so. The owner's own check covers it.

THE GATE FOR THE KEYS. Items 11 to 16 reach the two cloud services. Before item 11:
   The owner puts his two keys in a file named .env in his real data folder. On this machine that is
   /home/indy/.local/share/openconsult/.env
   Count, without showing any value, the lines that give each name a value:
   grep -c -E '^SPEECHMATICS_API_KEY=.+' /home/indy/.local/share/openconsult/.env
   grep -c -E '^ASSEMBLYAI_API_KEY=.+' /home/indy/.local/share/openconsult/.env
   If the file is absent, or either count is not 1, print exactly this line and stop: Waiting for the two keys.
   The owner will type: Keys are in. Go.
   When both counts are 1, make the one copy that rule 5 allows, and nothing else in that folder:
   cp /home/indy/.local/share/openconsult/.env /home/indy/Work/openconsult-review/v2-logs/stage5b-data/.env
   then chmod 600 on the copy. Never open either file. Never print a line of either.
Item 11. For each cloud service: run its self-test with your command, on LOGS/stage5b-data. It must pass.
   Write in your log: the seconds to connect, the seconds from the end of a piece of sound to its line,
   the words heard, the speaker given to each line, whether a confidence score came, and the stamp.
Item 12. One address only. Run each self-test once more with every connection attempt and every name lookup
   of the worker recorded. The record must hold the service's EU address and nothing else.
Item 13. What was sent. For each service, record the opening message as it was sent, with the key taken out
   before it is written anywhere. It must show the medical option on, speaker labels on, and no list of words.
   Give both in your report.
Item 14. Silence. Send each service 60 seconds of made silence, then 60 seconds of made noise at -50 dBFS,
   then 60 seconds at -30 dBFS. No line may be accepted.
   Write in your log what the service wrote and what the rule refused. If any text is accepted, stop and report.
Item 15. Failures on the real service. With a made-up key that is plainly wrong, each service's self-test must fail
   with the plain reason for a refused key, and nothing else may be tried.
   Kill one cloud worker in the middle of the clip: a failure with its reason, the app stays up, a new start works.
Item 16. The keys appear nowhere. With a script that reads the copy and prints counts only,
   search LOGS/stage5b-data (but not the copy itself), LOGS/stage5b.log, the plan, the report and the whole of V2
   for each key's value. Every count must be 0.
Item 17. Start the app on LOGS/stage5b-data with a spare port and --no-browser. Set up a made-up user.
   Read This machine: it must give a line for Nemotron and a line for each cloud service,
   each saying that the self-test passed, with the date. Stop the app.
Item 18. git status --porcelain is empty. git log --oneline lists your commits on v2.
   V1 HEAD is the value you kept. Nothing in the shared model cache was deleted or changed: list what you added to it.
   Port 8000 and port 8001 were never used by you. Nothing in the owner's real data folder was read or changed
   but the one copy of the one file.
Item 19. Write LOGS/STAGE5B_REPORT.md. Put the most important finding for the patient first:
   did each of the three self-tests pass, yes or no; was any word written in silence, by any of the three, yes or no;
   did sound go anywhere but the two EU addresses, yes or no. Then:
   the figures of items 5 and 11; the result of item 6; what the rule refused in items 7 and 14;
   the records of items 8, 12 and 13; the results of items 9, 10, 15 and 16;
   the four confirmations with their pages;
   the models with their names, revisions, sizes and licences; the libraries added, with versions and licences;
   the Nemotron environment's size and build time; the card's memory at its highest;
   the seconds of sound sent to each service;
   the commits with their hashes; the files with their line counts; any target missed;
   the tests, each with what it pins; every new sentence shown to the user; the list for rule 16;
   the exact commands for the owner's own check, as one block with no quotation marks, in the order he runs them:
   build the Nemotron environment in his real data folder, run the self-test of each of the four choices,
   start the app on port 8001;
   the size of LOGS/stage5b-data, a line saying that it holds a copy of the keys, and the one command that removes it;
   anything you flagged.

FINAL MESSAGE
Twelve lines at most:
each of the three self-tests, passed or not, and whether any word was written in silence,
that sound went to the two EU addresses and nowhere else,
that the keys appear nowhere (item 16),
the number of commits and the last hash,
the number of tests, the suite time, none skipped,
that the private word check printed nothing before every commit,
that V1 HEAD is unchanged and that ports 8000 and 8001 were never used,
any target missed,
anything you flagged,
then this line for the owner: Tell Cowork: Stage 5b done. Do not push yet.
