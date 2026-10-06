STAGE 3B of OpenConsult v2.0: the engine bench

WHAT THIS IS
OpenConsult v2.0 is a rewrite, built on the branch v2 in its own folder.
Stage 3 built the one door to the language model and proved it on Ollama.
Stage 3b sends the same cases through two more engines, llama.cpp and vLLM, and compares them with Ollama.
From the patient's side: would another engine bring the alarm and the assessment sooner, with the same clinical safety?
It is a report only. No setting to choose an engine is built. The result is then published in the repo,
because people asked for it in issue 1 of the repo and the owner wants to answer with data.
Two small items come first: an empty list keeps the earlier list, and one line of words in the terminal.
The spec is V2_SPEC.md. Stage 3b is section 15.8 of it. Read 15.7 and 15.8 first and build what they say.
This prompt gives the order of work and the rules. Where the two differ, the spec wins: stop and report.
OpenConsult is a research and education prototype. Never real patients.

MODEL
This stage runs on Fable 5.1 at high effort.
Say in your first line which model you are. If you are not Fable 5.1, stop there.

THE FOLDERS
V2    /home/indy/Projects/OpenConsult2
      The repo. Branch v2. All code and all commits are made here.
LOGS  /home/indy/Work/openconsult-review/v2-logs
      Private. Your plan, your log, your reports, the results and the public folder before it is cleared go here.
      This prompt is here. Every new file you make here has a name that begins with stage3b or STAGE3B.
      The files of stage 3 here are read only: change none of them.
ENG   A folder you propose in your plan, for the engines and the model files.
      Outside V2 and outside LOGS, on the drive where Ollama keeps its models.
V1    /home/indy/Projects/consultation-ai
      Read only. A reference. Change nothing. The only git command allowed there is:
      git -C /home/indy/Projects/consultation-ai rev-parse HEAD
OLD   /home/indy/Work/openconsult-review/v1.1-logs
      Read only. Change nothing there. Run nothing there.

WHAT TO READ
In V2: openconsult/llm, openconsult/consult, openconsult/bench, openconsult/prompts, openconsult/words.py, and their tests.
In LOGS: STAGE3_PLAN.md, STAGE3_PLAN_REVIEW.md, STAGE3_REPORT.md, and stage3.log for the marks as they were written before the run.
In LOGS: stage3-cases, with cases.json. These are the cases of this bench too.
In LOGS: stage3-bench/run. This is stage 3's own run on Ollama's own tag. It is the reference arm. It is not run again.

BEFORE YOU START
1. Read V2/CLAUDE.md and V2/HANDOVER.md.
   Read V2/V2_SPEC.md sections 4, 5, 6.5, 10, 15.3, 15.4, 15.7 and 15.8.
   Read V2/V1_LESSONS.md: the twelve that matter most, then sections 3 and 9.
2. Check the spec with sha256sum. It must be:
   7269449bbd1e035af300cfcb92704ac7f48a8d55d454f64fed07e90d8f18bb04  V2_SPEC.md
   If it differs, stop and report. Do not go on.
3. Check V2. The branch is v2. HEAD is e736326eac0152927d97c631b42f871782fefec0.
   git status --porcelain shows one line only: V2_SPEC.md modified.
   If anything else is changed or untracked, stop and report.
4. Run the one allowed command in V1. It must give b2e61d0705ec593cfde70638429e287e68c56f1c.
   Keep the value. You check it again at the end.
5. Check that uv is installed: uv --version. If it is not, stop and report.
6. Ask Ollama two things, read only, at http://127.0.0.1:11434: its version, and its list of models.
   The model gemma4:26b-a4b-it-qat must be there, with this digest:
   2dd70431afed94dd3688d790443768c1487ed086b57147ff083851116ae4c4e4
   Write the version and the digest in your log. You check the digest again at the end.
   If Ollama does not answer, the model is absent, or the digest differs: stop and report.
7. Check every case in LOGS/stage3-cases against the sha256 in cases.json.
   Take the sha256 of every file in LOGS/stage3-cases and in LOGS/stage3-bench/run.
   Keep the list in LOGS/stage3b-sources-before.sha256. You check it again at the end.

RULES
1. Write only in V2, in LOGS and in ENG. Never in V1. Never in OLD. Never change a file of stage 3 in LOGS.
2. Do not change one character of V2_SPEC.md or V1_LESSONS.md. If the spec is wrong or silent, report it.
3. If a choice is a product or clinical judgement, stop and report it. Do not decide it.
4. No git push. No sudo. No service command: the Ollama service is not stopped, restarted or set up differently.
   Install nothing for the whole system. The engines are installed into ENG only.
   If something cannot be done without sudo or a system install, do not work around it.
   Say so in your plan, with the one block the owner would run himself, and why.
5. In Ollama: never change and never delete a model that is there. You may make one new model from Google's file,
   under a name of its own that begins with openconsult-bench. You may load and unload models.
6. Never use the owner's real data folder, and never use port 8000 or port 8001.
   Every engine you start listens on 127.0.0.1 only, on a spare port. Never open a browser on this machine.
7. One engine holds the graphics card at a time. Before an arm starts, stop the other engines or unload their model,
   and check with nvidia-smi that the card is free. Write the reading in your log.
8. The cases and the model's replies enter V2 in one place only: the folder engine-bench,
   and only in Part 6, after the second gate. Until then they stay in LOGS.
   Every test uses made-up text. No line of a case or of a reply goes into a test.
9. LOGS/stage3-cases/task3-transcripts.jsonl holds two consultations: 495 and another one.
   Only the rows of consultation 495 are part of this bench. Only those rows may ever be published.
   No row of the other consultation is copied anywhere, not into the public folder and not into V2.
10. No prompt word is changed in this stage. The text the door sends as the system message keeps these sha256 values:
   assessment  6cc315afcf2c8570a7486bb8adb84885a8c043612e54bd2da158fa7814ad9308
   alarm       c98ef427c4e26609e5e6f88c4401e2b3fd851d33ded3f1a03d32b5f2dc533d41
11. Before each commit, run the private word check on the staged files. It must print nothing:
   git diff --cached --name-only -z | xargs -0 grep -n -i -w -F -f /home/indy/Work/openconsult-review/v2-logs/private-words.txt
   If it prints a line, stop and report. Do not edit a file to make it pass.
   Never copy the word list, or any word from it, into V2 or into a commit message.
   One exception, in Part 6 only: the data files of engine-bench, which Cowork clears at the second gate. Part 6 says how.
12. Each commit: one logical change, the suite green before it, the why in the message.
   No personal names and no host names in a message.
   Each commit message ends with this line, after one empty line:
   Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
   That is the only address allowed in a commit message.
13. Commands and short results go to LOGS/stage3b.log. Long output never goes into chat.
14. Nothing is built switched off, and nothing is built for a later stage (R31).
    Stage 3b builds no setting to choose an engine, no second engine in the app, nothing on a page, no cloud,
    and nothing for ruling 6 of 15.8. The app's profile and the app's pages do not change.
    The two new engines are modules of the bench. The app cannot reach them. Prove that with a test.
15. Nothing in V2 assumes Linux. The bench's engine modules must load and pass their tests on Windows and macOS.
    The suite needs no graphics card and no engine. It must pass on GitHub's machines, which have neither.
    The scripts that start and stop engines on this machine are private scripts in LOGS.
16. The size targets of spec section 5 hold. If a target cannot be met, report it and say why.
17. What the model says is never asserted in a test. It is measured in the bench (spec 5.2).
18. Be fair to every engine. Each gets its newest release, the settings its own documents advise for this use,
    and the same care. Write down everything you do to make an engine work.
    If an engine needs something that is not in its own documents, stop and report.
19. Never run an arm again to get a better figure. An arm that was stopped is carried on from where it stopped:
    chains already complete are kept, never run again and never written over.
20. If a step fails, stop and report.

PART 1. TWO COMMITS BEFORE THE PLAN
Commit 1. Subject: Stage 3b: the spec as the stage 3b brainstorm left it
   V2_SPEC.md only. The spec is committed before the code (V1_LESSONS 11.3).
Commit 2. Subject: Stage 3b: the stage prompt
   Copy this file to V2/stage-prompts/STAGE_03B.md. Prove with cmp that it is identical.

PART 2. A LOOK AT THE MACHINE AND AT THE MAKERS' PAGES
Read only. Change nothing. Write what you find into your plan, with the address of each page you used.
1. The machine: free space on each drive; where Ollama keeps its models; the NVIDIA driver; what holds card memory now;
   which of these are present: docker with the NVIDIA container toolkit, the CUDA toolkit, cmake, a C++ compiler.
   Reading Ollama's set-up is allowed, with commands that only read.
2. The makers' own pages, as they are today:
   the newest release of llama.cpp and of vLLM, and how each is installed for an NVIDIA card on Linux without sudo;
   how each switches thinking off for Gemma 4;
   how each holds an answer to a JSON form;
   how each sets the context size, and what each does with an input that does not fit;
   how each takes two calls at the same moment;
   the page of the repack named in spec 15.8, ruling 7, and what it says about serving it;
   whether Ollama as installed takes two calls for one model at the same moment, and how that is set.
   Spec 15.7 and 15.8 hold what Cowork found on 4 and 6 Oct. Check it. Where a page now says otherwise, say so.

PART 3. THE PLAN, THEN STOP
Write your plan to LOGS/STAGE3B_PLAN.md. It holds:
1. ENG: its path, the free space there, and what goes into it with the size of each.
2. For each engine: the version, where it comes from, the exact install commands,
   and the exact start command with every option and the reason for each.
   Whether anything needs the owner. If so, the one block for him and why.
3. Ollama on Google's file: how the new model is made, what is copied from Ollama's own tag,
   and how you show that the file is the only thing that differs.
   The fingerprint of the file behind Ollama's own tag, beside the fingerprint of Google's file.
4. The two engine modules of the bench: the files, what each sends, how each reads the four endings
   (complete, cut, did not fit, error), where they sit, and how the bench command is pointed at an engine.
   How each arm records which version of the model it ran.
5. The four proofs for each engine, and how you make each: no thinking text in a reply;
   a reply that fits its form; a call at the full context of 16,384 accepted; an oversize input refused and not cut.
6. For each engine, every sampling setting in effect, its value, and where the value comes from.
7. The token comparison: which calls you compare, and what you found on the makers' pages about how each engine wraps the words.
8. The clock: what is measured, the one call that is not measured, and the time from start to first answer.
9. The together arm: how the two calls of a pass are sent at the same moment through the door,
   and the setting each engine gets for two calls at once.
   What Ollama as installed does with two calls. If it takes one at a time, your proposal for a fair setting
   that does not touch the service.
10. The repeat test: the exact calls, the call sent in between, and the one thing you would try on each engine.
11. The marks, as numbers, copied unchanged from LOGS/stage3.log, and the two rules of spec 15.8, ruling 10,
    in the words you will write into the log.
12. The order of the arms, the time you expect for each and in all, how the run carries on if this session ends,
    and how the card is freed and checked between arms.
13. The public folder: every file, its form and its expected size. The whole folder stays under 30 MB.
    How the reference arm is put into the same form. The headings of the public report.
14. Every test you intend, each with the rule, the ruling or the incident it pins (spec 5.2).
15. Every new or changed sentence the app or the bench will show to a user.
16. The commits you will make, in order.
17. The list for rule 15: where the three systems differ.
18. Anything in the spec that is wrong, silent or in conflict. Do not fix it yourself.
19. Whether the stage fits in one session. If you judge it does not, name the point where you would split it.
Then print five lines at most, and stop.
Wait for the owner. He will type: Approved. Go.
He may first tell you to read a review file in LOGS. If so, read it and follow it. It may change your plan.

PART 4. THE BUILD
Build what spec 15.8 says. This is the suggested order. Your plan may change the order and say why.
1. Ruling 5, in the pass. When the assessment returns an empty list of differentials and an earlier list exists,
   the earlier list stays as the list and is handed to the next pass. The result of the pass says the list was kept.
   The record still holds the model's own reply. At the first pass an empty list stays empty.
   The word check is not changed.
2. Ruling 12, in openconsult/words.py. The second line the command prints when the browser will open by itself becomes:
   Your browser will open by itself. If it does not, open that address in a browser on this computer. Press Ctrl+C to stop.
   The old line stays for a start with --no-browser. No test holds its own copy of a sentence.
3. The two engine modules of the bench, behind the joint of stage 3, and the way to point the bench command at an engine.
   Every call still goes through the door, so the limits, the form check and the record are the same for every engine.
4. The together sender: the two calls of a pass sent at the same moment, both recorded, and one failing does not lose the other.
5. The repeat test.
6. The scoring: the two rules of ruling 10, the count of empty replies and of kept lists for each arm,
   and one table that sets the arms side by side.
7. The exporter: it writes the public form of an arm from its result files and its record of calls.
   From the 495 file it takes the rows of consultation 495 only (rule 9). Pin that with a test on made-up rows.
Commit as you go, by rule 12. The documents come in Part 6.

PART 5. THE PROOFS AND THE RUN
Item 1. The suite is green. Give the number of tests, the time, and the number skipped, which must be none.
Item 2. The word check of stage 3, with no model, on the same files as then.
   It must give 1,898 of 1,898 assessment calls and 1,898 of 1,898 alarm calls. If not, stop and report.
Item 3. Install the engines into ENG and fetch the two sets of model files, as your approved plan says.
   Google's file must have this sha256: 3eca3b8f6d7baf218a7dd6bba5fb59a56ee25fe2d567b6f5f589b4f697eca51d
   The repack is taken at this revision: 2096d38dad51a19b8e982b44241c47102a8bbb00
   If either differs, stop and report.
Item 4. Make the Ollama model from Google's file. Write both fingerprints in your log.
   Show that the file is the only thing that differs from Ollama's own tag.
Item 5. For each engine in turn: start it, make the four proofs, make the token comparison,
   and write the sampling settings the engine itself reports. Stop the engine.
   If a proof fails on an engine and its own documents give no remedy, do not run that engine's arms.
   Say why in the report. The other engines go on.
Item 6. Write the marks and the rules into LOGS/stage3b.log, with the time, before the first arm. They do not change after.
Item 7. The run. For each engine in turn: the full arm (all 16 cases, 13 chains), then the together arm, then the repeat test.
   Start it so that it carries on if this session ends, with its output in LOGS.
   A sampler writes the card's memory to LOGS every 5 seconds through every arm (nvidia-smi, read only).
   Look at the run no more than once every 10 minutes. Put nothing long into chat.
   If a chain fails, it is logged and scored as failed, and the run carries on.
   If this session ends, the owner starts you again and types: Carry on. Then read LOGS/stage3b.log and go on from there.
Item 8. Score every arm by the rules of item 6. A missed hard mark is a finding, not a stop:
   the arm is reported as not a candidate, and the work goes on.
Item 9. Stop every engine you started. Unload the model you made. Check that the card is free.
   Check: git status --porcelain is empty; V1 HEAD is the value you kept; the sha256 list of item 7 of BEFORE YOU START
   is unchanged; the digest of gemma4:26b-a4b-it-qat is unchanged.
Item 10. Write LOGS/STAGE3B_REPORT.md, for Cowork. Put the most important finding for the patient first:
   for each engine, were the hard marks met, and is its typical pass at least 1 second shorter than Ollama's.
   Then, for each arm: every mark beside the reference arm's; the seconds for each call and each pass,
   typical and slowest; the together arm; the repeat count; the time from start to first answer; the card's memory;
   the empty replies and the kept lists. Then: the four proofs and the token comparison for each engine;
   every version, option and command; the sampling settings; what you did to make each engine work;
   the commits with their hashes; the files with their line counts; any target missed; the tests, each with what it pins;
   the sizes of what is in ENG and the one command that removes it; anything you flagged.
Item 11. Write the public folder into LOGS/stage3b-public, exactly as it would go into the repo. Do not put it in V2.
   The public report in it is for a reader who has never seen OpenConsult.
   Plain words, short sentences, the figures first. Its first lines answer two questions:
   do the clinical marks hold on each engine, and is either engine faster in a way that matters to the patient.
   It says what the bench is: one machine, one card, one model, one user, and a vLLM arm that ran a version
   of the model made by an individual. It says what was not tested. It makes no case. It praises nothing.
   It names no person, except the makers of the model versions by their public account names.
   It carries the standing line: a research and education prototype, never real patients, every case acted or scripted.
Item 12. Run the private word check over LOGS/stage3b-public and write its output to
   LOGS/stage3b-public-word-hits.txt: the file, the line number and the line.
   The report and every other document in the folder must have no hit. If one has, stop and report.
   A hit in a case file or in a reply file is listed and left as it is. Never edit a case or a reply.
Then stop. This is the second gate. Your message, ten lines at most:
   for each engine, the hard marks met or not, and the typical pass beside Ollama's;
   the number of commits and the last hash; the number of tests, none skipped;
   that nothing is published and git status is empty; anything you flagged;
   then this line for the owner: Tell Cowork: Stage 3b run done. Nothing is published yet.

PART 6. AFTER THE SECOND GATE
Wait for the owner. He will type: Publish. Go.
He may first tell you to read a review file in LOGS. If so, read it and follow it.
1. Copy LOGS/stage3b-public to V2/engine-bench. Prove with diff -r that the two are identical.
2. The private word check for this commit: run it on every staged file that is not a case file or a reply file
   of engine-bench. It must print nothing. For the case files and the reply files, run it and compare its output
   with LOGS/stage3b-public-word-hits.txt. The two must be the same, line for line. If not, stop and report.
3. Commit the folder. Subject: Stage 3b: the engine bench, published
4. The documents, in the last commit:
   CLAUDE.md: the bench commands for a second engine, and the line about where cases and results live, made true.
   It must stay under 100 lines.
   README.md: one line that points to engine-bench. Draft it. The owner corrects it.
   NOTICE: one entry for each library added to V2, in the commit that adds it. None is expected.
   HANDOVER.md: a new entry at the top. What was done, the rulings of spec 15.8 in one line each,
   the measurements, and what this stage has made untrue.
5. The suite is green. git status --porcelain is empty. git log --oneline lists your commits on v2.

FINAL MESSAGE
Eight lines at most:
the number of commits and the last hash,
the number of tests, the suite time, none skipped,
that the private word check passed as Part 6 says,
that V1 HEAD and the sources in LOGS are unchanged,
any target missed, anything you flagged,
then this line for the owner: Tell Cowork: Stage 3b published locally. Do not push yet.
