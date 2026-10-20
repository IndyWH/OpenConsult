OpenConsult v2.0, stage 6a: the live consultation without Alba, from Start to Stop

WHAT THIS IS
Stage 6 is the first consultation in the room. A patient's name goes in, the doctor confirms the consultation is acted, presses Start and talks. The words appear live, the differentials and the alarm reach a screen for the first time, a quiet clock runs. At Stop the app asks who spoke, runs the label check, checks that nothing heard was lost, and shows the final transcript with its warnings. The owner split stage 6 into two runs on 19 Oct 2026 (15.10, ruling 16). This is 6a, from Start to Stop. The note and the review page are 6b, a later session, and nothing of them is built here (R31).
The spec is V2_SPEC.md. Read, in this order: section 15.10 whole, rulings and details; 15.4 the row of stage 6; sections 8.2, 9.8 (the clock for the doctor only), 11.4, 11.5 and 4; 15.7 the details headed The pass; 15.8 rulings 5, 31 and 38 and the part headed Stage 3c; 15.9 rulings 4, 7, 12, 13, 17 and 26, and in its details The check for missing speech and the 5a paragraph headed What the plan review and the build of 5a settled. Then V1_LESSONS.md: the twelve, sections 1, 2, 3.13, 3.14 and 5. Where this prompt and the spec differ, the spec wins: stop and report.
OpenConsult is a research and education prototype. Never real patients. Every consultation is acted.

MODEL
This runs on Fable 5.1 at high effort. Say in your first line which model you are. If you are not Fable 5.1, stop there.

THE FOLDERS
V2    /home/indy/Projects/OpenConsult2
      The repo. Branch v2. All code and all commits are made here.
LOGS  /home/indy/Work/openconsult-review/v2-logs
      Private. Your plan, your log and your report go here. This prompt is here.
      Every file and folder you make in LOGS has a name that begins stage6a- or STAGE6A_.
ENG   /mnt/fastdata/openconsult-engine-bench
      The engines and the model files, as 3c left them. You do not start or stop vLLM: the owner does, by hand, with LOGS/stage3c_engines.sh. You install nothing there, delete nothing there and change no file there.
OLDER Every other folder in LOGS whose name begins stage3, stage5, prompts- or PROMPTS_. Read only. Write nothing there and delete nothing there. Never open LOGS/stage5c1-data/.env.
V1    /home/indy/Projects/consultation-ai
      Read only. Change nothing. Never read V1/.env or any file that holds a key or a token. Its live page, its Stop and its who-spoke question are the reference for how the pieces fit; its code is not copied, it is rewritten to the spec (6.1, 6.5).

THE RULES
1. Check the spec with sha256sum before anything else. It must be:
   3c1ac7e1dc786534e49bc21cbf7b7322c2ec4293b4241424c266def012da5f3a  V2_SPEC.md
   If it differs, stop and report. Do not go on. Do not change a character of the spec.
2. Check the branch is v2 and HEAD is ca0eb60. git status --porcelain must show one line only, V2_SPEC.md modified. If anything else is changed or untracked, stop and report.
3. No git push. No sudo. No service command. Install no system software. uv may reach the package index; nothing else reaches outside this machine. The suite needs no card, no worker, no model, no microphone, no browser and no internet.
4. You never write or change a word a model reads (15.3; 15.8, ruling 1). 6a adds no prompt. The label check uses the prompt of 15.9, ruling 17 byte for byte, as the bench has it, with its answer form; prove it with sha256sum against the hash the ruling gives. The two prompts of rulings 41 and 42, their frames and their forms are not touched. The note prompt of 15.10, ruling 3 is 6b's: do not write it.
5. Every rule of section 4 that this stage touches is pinned by one test named with its number. No test of an earlier stage is weakened or deleted. What a model says is never asserted in a test (5.2). The two functions of the check for missing speech are not changed (15.9, the details of 5c): 6a shows their result.
6. The data folder for your own runs is a throwaway folder under LOGS/stage6a-data, never the owner's data folder and never a test folder of an older stage. Tests write only to a temporary folder (R18). A recording is written once and never overwritten.
7. Before each commit, run the private word check on the staged files. It must print nothing:
   git diff --cached --name-only -z | xargs -0 grep -n -i -w -F -f /home/indy/Work/openconsult-review/v2-logs/private-words.txt
   If it prints a line, stop and report. Never copy the word list, or any word from it, into V2 or into a commit message. Nothing you write for a commit names a folder of this machine that V2 does not name already, and nothing names the machine.
8. Each commit: one logical change, the suite green before it, the why in the message. Each commit message ends with this line, after one empty line:
   Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
   That is the only address allowed in a commit message.
9. Size targets of section 5: no file over 600 lines, no function over 80, the live consultation a class with named fields in its own file, page scripts in their own files, state logic in importable files run by tests. If a target cannot be met, report it and say why (5.4).
10. Do not touch V2_SPEC.md after commit 1. Cowork does not touch it while you run.
11. A product or clinical choice that the spec does not settle is not yours: stop and report it, with the choice you would make and why.

PART 1. TWO COMMITS BEFORE THE PLAN
Commit 1. Subject: Stage 6a: the spec, with section 15.10 and the rows of stages 6 and 11
   V2_SPEC.md only. The spec is committed before the code (V1_LESSONS 11.3).
Commit 2. Subject: Stage 6a: the stage prompt
   Copy this file to V2/stage-prompts/STAGE_06A.md. Prove with cmp that it is identical.

PART 2. THE PLAN, THEN STOP
Write your plan to LOGS/STAGE6A_PLAN.md. It holds:
1. The new tables as a new schema version, column by column, from the detail headed The record, 6a's part only, and how an existing data folder is brought forward.
2. The live consultation as a class: its named fields, and one small module for each job (the microphone and the recording, the transcript, the passes, Stop). Which code of 3c and stage 5 it calls, and that none of it changes.
3. The page: the new-patient form, the Start screen as ruling 9 and 8.2 say, the live page as the detail headed The live page says, and the final transcript page with its warnings. Every new sentence shown to the user, in the one file of 15.6, listed in the plan. How Start is disabled with its reason (R15) when parts.decisions.start_offered is false or the language model or the speech choice cannot be reached (10.4).
4. The microphone: how the page captures sound with echo cancellation, noise suppression and automatic gain off, how the three values reach the record, the rate sent to the door, and how the recording file is written as the sound arrives (R18; 15.9, ruling 7).
5. When a pass runs: the interval you take from v1 and its constant; how the whole transcript is sent each pass with the patient line and the stale list; how a result that arrives after Stop is recorded and not shown; the three alarm states on screen and the kept list with its mark (15.10, rulings 1 and 2).
6. Stop in order, as the detail headed Stop, in order says: the who-spoke question that waits; the label check as a job of the language model door with the ruling 17 prompt and its answer form, the proof that no word changed, the mark on each changed label, the unsure rule of ruling 14; the two checks for missing speech on the stored lines and the stored loudness; the gate of ruling 8 with its three constants named and their sources; a second Stop that waits.
7. The quiet clock of ruling 10 and typing as use with the unsaved edit rule of ruling 12.
8. The room run you will leave for the owner: the exact steps, in his hands' order, with vLLM already started by him and Nemotron the speech choice, the screensaver off, one acted consultation, and the three figures to report (the wait from a spoken word to the page, the typical pass, the seconds from Stop to the final transcript).
9. The commits you will make, in order, and the HANDOVER entry you will write.
10. The tests you will add, each with what it pins. Expected: R1, R2 for the audit of Stop and who-spoke, R9, R11, R12, R15, R17, R18, R20, R29, R30, rulings 1, 2, 7, 8, 9, 10, 12 and 14 of 15.10, 11.5 rules 2, 3 and 5, V1_LESSONS 2.2, 3.6 for number words where they apply, 5.2 and 5.3.
Then stop. Wait for the owner. He will type: Approved. Go.
He may first tell you to read a review file in LOGS. If so, read it and follow it. It may change your plan.

PART 3. BUILD
Build in the order of the plan, one commit per item: the tables; the consultation class and its modules; the patient form and the Start screen; the microphone and the recording; the live page with the passes; Stop with who-spoke and the label check; the checks and the gate; the final transcript page; the documents. The suite green before each commit.
Then prove on this machine, with the owner's vLLM up and the Nemotron worker started by the app, that the app starts on a throwaway data folder, that Start is offered, and that one short spoken test of your own (you speaking a few sentences, or the self-test clip fed through the page's path if speaking is not possible) reaches the page live and reaches Stop with a final transcript. Record the three figures. Then stop the worker and leave vLLM running. Nothing of what you said goes into any file in V2.
Before the last commit: git status --porcelain is empty but your commits; nothing private in the added lines (rule 7, and no home path, no ENG path, no machine name); the suite green three times; HANDOVER under 500 lines with older entries moved to archive/HANDOVER_ARCHIVE.md if needed; CLAUDE.md under 100 lines with the new commands.

THE REPORT
Write LOGS/STAGE6A_REPORT.md: the spec's checksum as given; the new schema version and its tables; the label check prompt's hash proven; the constants you set with their sources; the three figures of your own proof; every new sentence shown to the user; the tests, each with what it pins; the commits with their hashes; the size targets met or not; the room run steps for the owner, in his hands' order; what the stage has made untrue in any document; and what 6b should know. Plain words.

FINAL MESSAGE
Eight lines at most: the spec's checksum as given; the schema version; the label check hash proven; the three figures; the number of commits and the last hash; that the private word check printed nothing before every commit; then this line for the owner: Tell Cowork: Stage 6a built. Do not push yet.
