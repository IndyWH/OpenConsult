STAGE 3 of OpenConsult v2.0: the language model door

WHAT THIS IS
OpenConsult v2.0 is a rewrite, built on the branch v2 in its own folder.
Stage 3 builds the one door through which every call to the language model goes.
Each call has a limit on its length and on its time. Each call is recorded word for word.
From the patient's side: a missed alarm must be traceable to exactly what the model read.
The stage is proven by a bench. v2 must send the model the same words as v1 did, and reach v1's marks.
One small item comes first: the app opens the browser by itself.
No consultation, no patient list and no sound yet.
The spec is V2_SPEC.md. Stage 3 is section 15.7 of it. Read that section first and build what it says.
This prompt gives the order of work and the rules. Where the two differ, the spec wins: stop and report.
OpenConsult is a research and education prototype. Never real patients.

MODEL
This stage runs on Fable 5.1 at high effort.
Say in your first line which model you are. If you are not Fable 5.1, stop there.

THE FOLDERS
V2    /home/indy/Projects/OpenConsult2
      The repo. Branch v2. All code and all commits are made here.
LOGS  /home/indy/Work/openconsult-review/v2-logs
      Private. Your plan, your log, your report, the bench cases and the bench results go here.
      This prompt is here.
V1    /home/indy/Projects/consultation-ai
      Read only. A reference. Change nothing. The only git command allowed there is:
      git -C /home/indy/Projects/consultation-ai rev-parse HEAD
OLD   /home/indy/Work/openconsult-review/v1.1-logs
      Read only. The record of v1's benches. Change nothing there. Run nothing there.

WHAT TO READ IN V1 AND IN OLD
V1/app/cds.py
   The two prompts (ASSESSMENT_PROMPT and URGENCY_PROMPT, each with ASR_CAVEAT inside it),
   the two answer forms, assessment_message, patient_line, with_patient,
   the request built in _chat_raw, and the bookkeeping in update.
V1/app/mock_scripts.py
   How a script is read and made into a transcript, and the age and sex of each script's patient.
V1/scripts/evaluate_urgency.py and V1/scripts/evaluate_cds_restraint.py
   How a script is replayed, what is expected of each script, and the two verdicts.
OLD/task5_bench.py, task5_analyse.py, task5.log, TASK5_AGE_SEX.md
OLD/task5b_bench.py, task5b_analyse.py, task5b.log, TASK5B_HARNESS.md
   The two benches that are v1's marks today. Arm D is the arm with the patient line. It is the reference.
OLD/task5-calls.jsonl and OLD/task5b-calls.jsonl
   Every call v1 made in those benches, with what came back.
OLD/task3-transcripts.jsonl
   The transcript of consultation 495, pass by pass.
OLD/travel/
   The two travel cases.

BEFORE YOU START
1. Read V2/CLAUDE.md and V2/HANDOVER.md.
   Read V2/V2_SPEC.md sections 4, 5, 6, 10, 15.3, 15.4, 15.6 and 15.7.
   Read V2/V1_LESSONS.md: the twelve that matter most, then sections 3, 6.2, 6.3, 8 and 9.
2. Check the spec with sha256sum. It must be:
   270f468cd4705f094a80203fe3f43849ad22020d9b93a99e792ee2943462ca54  V2_SPEC.md
   If it differs, stop and report. Do not go on.
3. Check V2. The branch is v2. HEAD is 26667e5155f399e210712da79e9efdeaa899c98c.
   git status --porcelain shows one line only: V2_SPEC.md modified.
   If anything else is changed or untracked, stop and report.
4. Run the one allowed command in V1. It must give b2e61d0705ec593cfde70638429e287e68c56f1c.
   Keep the value. You check it again at the end.
5. Check that uv is installed: uv --version. If it is not, stop and report.
6. Ask Ollama two things, read only, at http://127.0.0.1:11434: its version, and its list of models.
   The model gemma4:26b-a4b-it-qat must be there, with this digest:
   2dd70431afed94dd3688d790443768c1487ed086b57147ff083851116ae4c4e4
   That is the digest v1's benches ran on. Write the version and the digest in your log.
   If Ollama does not answer, the model is absent, or the digest differs: stop and report.
7. Take the sha256 of every file in OLD and in V1/mock_consultations that you will read for the cases
   and for the word check. Keep the list in LOGS/stage3-sources-before.sha256. You check it again at the end.

RULES
1. Write only in V2 and in LOGS. Never in V1. Never in OLD.
2. Do not change one character of V2_SPEC.md or V1_LESSONS.md. If the spec is wrong or silent, report it.
3. If a choice is a product or clinical judgement, stop and report it. Do not decide it.
4. No git push. No sudo. No service command. Nothing in V1 is written, not even by git.
   Install no system software. Pull, delete, create and change no model in Ollama.
   You may ask Ollama to load or unload gemma4:26b-a4b-it-qat. Leave every other loaded model alone.
5. Never use the owner's real data folder, and never use port 8000 or port 8001.
   Port 8000 is v1, which keeps running. Port 8001 and the real data folder are for the owner's own check.
   When you run the app yourself, give it a temporary data folder, a spare port and --no-browser,
   and stop it afterwards. Never open a browser on this machine. The owner checks that himself.
6. No word a patient said goes into V2 or into a commit. The cases, the transcripts, the model's replies,
   the bench results and the bench's record of calls stay in LOGS. V2 holds the bench code and the marks only.
7. No prompt word is changed in this stage. The two prompts cross from V1 exactly.
   The text the door sends as the system message must have these sha256 values, as v1 recorded them:
   assessment  6cc315afcf2c8570a7486bb8adb84885a8c043612e54bd2da158fa7814ad9308
   alarm       c98ef427c4e26609e5e6f88c4401e2b3fd851d33ded3f1a03d32b5f2dc533d41
8. Before each commit, run the private word check on the staged files. It must print nothing:
   git diff --cached --name-only -z | xargs -0 grep -n -i -w -F -f /home/indy/Work/openconsult-review/v2-logs/private-words.txt
   If it prints a line, stop and report. Do not edit a file to make it pass.
   Never copy the word list, or any word from it, into V2 or into a commit message.
9. Each commit: one logical change, the suite green before it, the why in the message.
   No personal names and no host names in a message.
   Each commit message ends with this line, after one empty line (spec 15.6, ruling 3):
   Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
   That is the only address allowed in a commit message.
10. Commands and short results go to LOGS/stage3.log. Long output never goes into chat.
11. Nothing is built switched off, and nothing is built for a later stage (R31).
    Stage 3 builds no cloud model, no Qwen, no second engine, no affect call, no end-of-turn call,
    no note, no letter, no consultation, no patient, no speech, and no page that changes a model.
12. Nothing assumes Linux. The same code must start on Windows and macOS.
    Keep the list of every place where the three systems differ, and say for each how you know it works.
    The suite needs no graphics card and no Ollama. It must pass on GitHub's machines, which have neither.
13. The size targets of spec section 5 hold: no file over 600 lines, no function over 80,
    tests no larger than the app, the suite under a minute.
    If a target cannot be met, report it and say why. Do not squeeze code to fit a number.
14. What the model says is never asserted in a test. It is measured in the bench (spec 5.2).
15. If a step fails, stop and report.

PART 1. TWO COMMITS BEFORE THE PLAN
Commit 1. Subject: Stage 3: the spec as the stage 3 brainstorm left it
   V2_SPEC.md only. The spec is committed before the code (V1_LESSONS 11.3).
Commit 2. Subject: Stage 3: the stage prompt
   Copy this file to V2/stage-prompts/STAGE_03.md. Prove with cmp that it is identical.

PART 2. THE PLAN, THEN STOP
Write your plan to LOGS/STAGE3_PLAN.md. It holds:
1. The files you will write, each with its job in one line and its expected size.
2. The libraries you will add: name, version, licence, and why each is needed. Keep them few and light.
   The door needs a way to make a web request at run time. Say which you chose and why.
3. The table for the record of model calls, and the step from table version 1 to version 2.
   The owner's real database is at version 1, with his user in it. Say how it is brought forward with nothing lost.
4. The table of jobs: for the assessment and for the alarm, the prompt file, the answer form,
   the limit on length, the limit on time, and what happens when the call fails.
5. The joint between the door and the engine: exactly what crosses it.
   Say in three lines how a second engine would be added later. Do not build it.
6. How a call whose input did not fit the context size is detected on Ollama (V1_LESSONS 3.3).
7. The word check: how you match each of v1's recorded calls, what you compare, and how many calls you expect.
   Cowork counts 1,898 assessment calls and 1,898 alarm calls in arm D of the two benches. Confirm or correct it.
8. The bench: the cases with their checksums, the chains, the order of the run, the time you expect it to take,
   where each result goes, and what the writer refuses to do.
9. The marks, as numbers, each with its scoring rule and its list of terms, taken from OLD/task5.log and OLD/task5b.log.
   Where a v1 rule is unclear, say so. Do not settle it yourself.
   Task 5 marked the scripts on one run each. Task 5b marked them on 13 chains.
   For the scripts, Task 5b's marks stand. Give arm D's own figures from OLD beside each mark, as the reference.
10. Every test you intend, each with the rule, the ruling or the incident it pins (spec 5.2; V1_LESSONS 8.8).
11. Every new sentence the app will show to the user, in one list, so the owner can correct the wording.
    They live in openconsult/words.py, and no test holds its own copy of one.
12. The commits you will make, in order.
13. The list for rule 12: where the three systems differ.
14. Anything in the spec that is wrong, silent or in conflict. Do not fix it yourself.
15. Whether the stage fits in one session. If you judge it does not, name the point where you would split it.
Then print five lines at most, and stop.
Wait for the owner. He will type: Approved. Go.
He may first tell you to read a review file in LOGS. If so, read it and follow it. It may change your plan.

PART 3. THE BUILD
Build what spec 15.7 says. This is the suggested order. Your plan may change the order and say why.
1. The browser (ruling 2). The command opens the system's default browser once the app answers,
   and still prints the address. The switch is --no-browser. A machine with no browser or no screen is not an error.
   No test opens a real browser. The start step of the GitHub check uses the switch.
2. The record of model calls: the table, and the step from version 1 to version 2 with nothing lost.
3. The prompts folder: the two prompts as files, and the fixed words that go around the transcript.
   One loader. The app and the bench read the same files. R13 and R21 are checked over every prompt file.
4. The door: the table of jobs, the model's profile, the one result, the limits, and the Ollama engine behind the joint.
   The door writes the record itself, so no call can skip it.
   If Ollama or the model is absent, the call fails and says so. Nothing else is tried (spec 10.4).
5. The pass: the alarm first, then the assessment. The patient line on both. The stale list of names for the assessment.
   The bookkeeping in code. If one call fails, the other still gives its result.
   The message builders, the patient line and the bookkeeping are ported from V1 as plain functions.
6. This machine: two new lines. Whether Ollama is running, with its version. Whether Gemma 4 QAT is present.
   The page must never hang if Ollama does not answer.
7. The bench kit: the replay, the scoring, the writer that cannot write over an existing result,
   and the word check. It goes through the same door as the app. It can be pointed at any engine by its address.
   It never writes to the app's data. Its results and its own record of calls go to LOGS.
   A run that was stopped can be carried on: chains already complete are kept, never run again and never written over.
8. The cases. Copy them to LOGS/stage3-cases: the 13 scripts, the two travel cases, and the passes of 495.
   Write one list beside them. For each case: its file, its sha256, the patient's age and sex,
   what is expected of it, and where the transcript is cut. The bench chooses its cases from this list only.
9. The documents, in the last commit:
   CLAUDE.md: under Running it, the switch and the bench commands. It must stay under 100 lines.
   README.md: the line that says what this version can do so far. Draft it. The owner corrects it.
   NOTICE: one entry for each library added, in the commit that adds it.
   HANDOVER.md: a new entry at the top. What was done, the rulings of spec 15.7 in one line each,
   the measurements, and what this stage has made untrue.

PART 4. THE CHECKS, THE PROOF AND THE RUN
Item 1. The suite is green. Give the number of tests, the time, and the number skipped, which must be none.
Item 2. Start the app with a temporary data folder, a spare port and --no-browser. Set up a made-up user.
   Read This machine: it must say Ollama is running and Gemma 4 QAT is present. Stop the app. Remove the folder.
Item 3. Open a database made by stage 2's code at version 1, with a made-up user in it, using the new code.
   The user must still log in. This is a check on a temporary folder, never on the real one.
Item 4. The word check, with no model. For every assessment call and every alarm call of arm D
   in OLD/task5-calls.jsonl (495 and the travel cases) and OLD/task5b-calls.jsonl (the 13 scripts),
   build v2's request from the same case, the same point in it and the same earlier answer.
   It must match v1's in the prompt, the message, the answer form, the model, the thinking switch and the options.
   v1 kept a sha256 of each message and of each whole request. Use both where you can rebuild them.
   Give the count: so many of so many. If one call differs, stop and report. Do not start the run.
Item 5. One chain of one script through the real model, to prove the door works live.
   Check its rows in the bench's record: what was sent, the reply, the tokens, the times, the tag and the digest.
Item 6. Write the marks and the scoring rules into LOGS/stage3.log, with the time, before the run. They do not change after.
Item 7. The run. All cases, 13 chains each: 3 at temperature 0 with seed 42, then 10 at temperature 0.5 with seeds 1 to 10.
   Start it so that it carries on if this session ends, with its output in LOGS.
   While it runs, a sampler writes the graphics card's memory use to LOGS every 5 seconds (nvidia-smi, read only).
   Look at it no more than once every 10 minutes. Put nothing long into chat.
   If a chain fails, it is logged and scored as failed, and the run carries on, as in Task 5b.
Item 8. Score the run by the rules of item 6.
   If a hard mark is missed, stop and report. Do not run again to get a pass. The owner and Cowork decide.
Item 9. git status --porcelain is empty. git log --oneline lists your commits on v2.
   V1 HEAD is the value you kept. The sha256 list of item 7 of BEFORE YOU START is unchanged.
Item 10. Write LOGS/STAGE3_REPORT.md. Put the most important finding for the patient first:
   were the hard marks met, yes or no, and the word check's count. Then:
   each mark, with v2's figure beside arm D's from OLD;
   the seconds for each call and for each pass, beside arm D's for the same two calls;
   the graphics card's memory during the run;
   Ollama's version, the model's tag and digest, the hash of each prompt file;
   the commits with their hashes; the files with their line counts; any target missed;
   the tests, each with what it pins; the libraries added, with licences;
   every new sentence shown to the user; the list for rule 12;
   the exact commands for the owner's own check on port 8001;
   anything you flagged.

FINAL MESSAGE
Ten lines at most:
the hard marks, met or not, and the word check's count,
the number of commits and the last hash,
the number of tests, the suite time, none skipped,
that the private word check printed nothing before every commit,
that V1 HEAD and the sources in OLD are unchanged,
any target missed,
anything you flagged,
then this line for the owner: Tell Cowork: Stage 3 done. Do not push yet.
