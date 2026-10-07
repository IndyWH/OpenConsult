STAGE 3B of OpenConsult v2.0: the publish step, after the bench of 7 Oct 2026

Cowork, 7 Oct 2026, evening. For Claude Code. A new session in /home/indy/Projects/OpenConsult2.
This runs on Fable 5.1 at high effort. Say in your first line which model you are. If you are not Fable 5.1, stop there.

WHAT THIS IS
The engine bench ran twice. The first bench, of 6 Oct, was published locally in two commits and never pushed.
Its seconds are tainted. The second bench, of 7 Oct, ran clean, and the owner has ruled that it is the one public bench.
From the patient's side nothing changes in the app. This step gives the people who asked in issue 1 of the repo
an answer with data that anyone can check: the same figures, from the public folder, with one command.
Four things are done, in this order:
1. the two local publish commits of 6 Oct come out of the local history;
2. the rules of 7 Oct are built into the bench's own scorer, with tests;
3. the public folder is written again for the bench of 7 Oct, first into the private log folder, and checked by Cowork;
4. it is published locally, and the documents are written again. The owner pushes. You never push.
The spec is V2/V2_SPEC.md, section 15.8. Read rulings 2, 5, 8 to 11 and 13 to 28, and the details bullets,
above all the last one: The publish step, settled by Cowork (rulings 24 to 28). Build what they say.
Where this prompt and the spec differ, the spec wins: stop and say so in three lines.
OpenConsult is a research and education prototype. Never real patients. Every case is acted or scripted.

THE FOLDERS
V2    /home/indy/Projects/OpenConsult2            the repo, branch v2
LOGS  /home/indy/Work/openconsult-review/v2-logs  private; this prompt is here
V1    /home/indy/Projects/consultation-ai         read only; the one command allowed is git rev-parse HEAD
ENG   /mnt/fastdata/openconsult-engine-bench      the engines; not used and not touched in this step

WHAT TO READ
In V2: CLAUDE.md, HANDOVER.md, V2_SPEC.md sections 4, 5, 15.3, 15.7 and 15.8, V1_LESSONS.md sections 3 and 9,
openconsult/bench and its tests.
In LOGS: STAGE3B_PROMPT.md (its rules stand), STAGE3B_BENCH2_PROMPT.md, STAGE3B_BENCH2_PLAN.md, STAGE3B_BENCH2_REPORT.md,
stage3b-bench2.log, stage3b_bench2_facts.py with stage3b-bench2-facts.json, STAGE3B_PUBLISH_REVIEW.md,
and your own scripts of 6 Oct that wrote the public folder: stage3b_after.sh, stage3b_docs.py, stage3b_facts.py.
The results of 7 Oct are in LOGS/stage3b-bench2. The public folder of 6 Oct is LOGS/stage3b-public.

RULES
Every rule of LOGS/STAGE3B_PROMPT.md and of V2/CLAUDE.md stands, with what follows.
1. No push. No sudo. No service command. No engine is started. Nothing is loaded in Ollama. The card is not used.
   Nothing is installed and nothing is downloaded.
2. Do not change one character of V2_SPEC.md or V1_LESSONS.md. If the spec is wrong or silent, report it.
3. No word a model reads changes. The two prompt hashes of rule 10 of STAGE3B_PROMPT.md stay what the door sends.
   Nothing the app does in a consultation changes: the app's pages, its profile and its pass are not touched.
4. In LOGS nothing that exists is changed or written over: not a result, not a log, not a script, not a report,
   not the public folder of 6 Oct. Every new file in LOGS has a name that begins with stage3b-publish2,
   stage3b_publish2 or STAGE3B_PUBLISH2. Your log is LOGS/stage3b-publish2.log. Long output goes there, never into chat.
5. No chain is run again. No reply and no case file is ever edited.
6. The cases and the replies enter V2 in one place only, the folder engine-bench, and only in Part 5, after the second gate.
   Every test uses made-up text. No line of a case or of a reply goes into a test.
7. LOGS/stage3-cases/task3-transcripts.jsonl holds two consultations. Only the rows of consultation 495 may ever be published.
8. Before each commit, the private word check on the staged files must print nothing:
   git diff --cached --name-only -z | xargs -0 grep -n -i -w -F -f /home/indy/Work/openconsult-review/v2-logs/private-words.txt
   If it prints a line, stop and report. Do not edit a file to make it pass.
   Never copy the word list, or a word from it, into V2 or into a commit message.
   The one exception is in Part 5: the case files and the reply files of engine-bench, which Cowork clears at the second gate.
9. Each commit: one logical change, the suite green before it, the why in the message, no personal name and no host name.
   Each commit message ends with this line, after one empty line:
   Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
10. If a choice is a product or clinical judgement, stop and report it. If a step fails, stop and report. Do not improvise.

PART 1. CHECKS, THE SPEC COMMIT AND THE SAFETY COPY
1. sha256 of V2/V2_SPEC.md must be
   c89ad09d59b1bcb653ca49da4e646e2d438d9210fe2385269a404fd9be4aa5a9
   Branch v2. HEAD da3a995. git status --porcelain shows one line only: V2_SPEC.md modified. If not, stop.
2. These must hold, read only. Write each into the log. If one differs, stop.
   git log --oneline -5 gives, newest first: da3a995, da5a992, 23198ab, 8a6961d, 6167d89.
   origin/v2 is e736326. V1 HEAD is b2e61d0705ec593cfde70638429e287e68c56f1c.
   git show --stat 8a6961d names 64 files, all under engine-bench.
   git show --stat 23198ab names CLAUDE.md, HANDOVER.md and README.md and nothing else.
   da5a992 and da3a995 each name V2_SPEC.md and nothing else.
   V2/engine-bench and LOGS/stage3b-public are identical (diff -r).
   The suite is green. Give the number of tests, none skipped.
3. Commit V2_SPEC.md alone. Subject: Stage 3b: the spec for the publish step, rulings 24 to 28
4. Take the sha256 of every file in LOGS/stage3b-bench2, LOGS/stage3b-public and LOGS/stage3-cases.
   Keep the list in LOGS/stage3b-publish2-sources-before.sha256. You check it again at the end.
   If opening a record of calls could change its file, read a copy under a new name and never the file itself.
5. The safety copy (ruling 27), into LOGS:
   stage3b-publish2-before.bundle, made with git bundle create and all refs, then proved with git bundle verify;
   stage3b-publish2-before-refs.txt, every ref with its commit;
   stage3b-publish2-before-CLAUDE.md, -HANDOVER.md and -README.md, the three documents as they stand now.
   Write the hash of HEAD after the spec commit into the log. Below it is called OLD.

PART 2. THE PLAN, THEN STOP
Write LOGS/STAGE3B_PUBLISH2_PLAN.md. At most 150 lines. It holds:
1. The exact commands that take the two commits out, and the checks after them, as Part 3 says.
2. The scorer: which files change, what each new function works out, the one command a reader will type and what it prints
   and writes, how the rounds reach the tool as data, and what becomes of the compare command, of the old line
   of 1 second and of the old meaning of candidate.
   The count of lines before and after, against the size targets of spec section 5.
   If it does not fit, say so and propose what stays out. Do not squeeze code to fit a number.
3. The exporter: how the card's memory of an arm is taken over that arm's own steps, and anything else that must change.
4. Every test you intend, each with the ruling it pins.
5. The public folder: every file and folder, its form and its expected size; the name of the folder that carries the date
   of 6 Oct; how you prove that the kept parts and the cases are byte for byte those of LOGS/stage3b-public.
6. The headings of the public report and of the page on how the bench was run, with one line on what each section says.
   The paragraph on what a pass is, word for word. Every new sentence the tool will show to a user.
7. The private scripts you will write in LOGS, and which script of 6 Oct each is copied from.
8. The commits you will make, in order.
9. Anything in the spec or in this prompt that is wrong, silent or in conflict. Anything you need from the owner.
10. Whether the step fits in one session. If not, name the point where you would split it.
Then say: Plan ready. Wait for the owner. He will type: Approved. Go.
He may first tell you to read a review file in LOGS. If so, read it and follow it. It may change your plan.

PART 3. THE TWO COMMITS COME OUT
One step, before anything is built:
   git rebase --onto 6167d89 23198ab v2
If it stops for any reason, run git rebase --abort, and stop and report. Do not resolve anything by hand.
Then prove each of these, and write each into the log. If one fails, stop and report.
a. git log --oneline -4 gives three spec commits on top of 6167d89, with their subjects unchanged and their co-author lines kept.
b. git diff --name-only 6167d89 HEAD gives V2_SPEC.md and nothing else.
c. git diff --name-only OLD HEAD gives the 64 files of engine-bench, CLAUDE.md, HANDOVER.md and README.md, and nothing else.
d. sha256 of V2_SPEC.md is the value of Part 1.
e. git merge-base --is-ancestor e736326 HEAD succeeds, so that the owner's push needs no force.
f. No branch and no tag holds 8a6961d or 23198ab: git branch -a --contains and git tag --contains print nothing for each.
g. The folder engine-bench is gone from V2. The suite is green. git status --porcelain is empty.
Write the three new hashes into the log, and say the new HEAD in chat in one line.

PART 4. THE BUILD, THE PUBLIC FOLDER, THEN THE SECOND GATE
Build what your approved plan says. The suggested order:
1. The two stage prompts of 7 Oct, in one commit. Copy this file to V2/stage-prompts/STAGE_03B_PUBLISH.md and
   LOGS/STAGE3B_BENCH2_PROMPT.md to V2/stage-prompts/STAGE_03B_BENCH2.md. Prove each with cmp.
2. The scorer (ruling 26, and the details bullet). What it must do:
   - The marks of 15.7 and their scoring over 13 chains do not change.
   - The temperature of a chain is read from the data, never from its name.
   - Rule A: the hard marks over the chains at temperature 0, 3 of 3 where the mark says 13 of 13 and none where it says none,
     and no such chain failed. The stress test at 0.5: the same count over its chains, apart. It bars nothing.
   - Rule B: the typical pass of a round is the median of the passes of consultation 495 in that round's chain at temperature 0.
     Faster means a candidate, and at least 0.50 s shorter than the arm it is held against in each of the three rounds.
     The seven judgements of the details bullet The bench of 7 Oct.
   - Steadiness: if Ollama's rounds, calls one after another, differ by more than 0.25 s, no arm is called faster.
   - Beside the wait: the tokens written and the time for each token, all in and writing only.
   - What the report states from the replies: failed chains by temperature, replies cut mid-sentence by the rule of the
     details bullet, empty lists and kept lists, time critical with no action, the pass of the first alarm,
     and the cases where the three chains at 0 gave the same answer.
   - It works from the public folder alone: no engine, no private file. It gives the same figures from the private result folders.
   - The code holds one rule for faster, that of ruling 17. The word candidate means ruling 18 wherever the tool writes it.
3. The exporter: the card over an arm's own steps. Nothing published is ever written over, as before.
4. The suite is green. Give the number of tests, the time, and the number skipped, which must be none.
   The suite still needs no card and no engine, and nothing in V2 assumes Linux.
5. Write the public folder into LOGS/stage3b-publish2-public, exactly as it would go into the repo. Do not put it in V2.
   It holds what the details bullet says: the report; how the bench was run; the cases; the six arms of 7 Oct;
   the figures of the tool as data; the rounds as data; the small data files for the figures that come from the machine;
   and the folder of 6 Oct with the two kept parts.
   - The six arms are exported from LOGS/stage3b-bench2. Every public reply equals its record.
   - The cases are byte for byte those of LOGS/stage3b-public/cases. Prove it with diff -r.
   - The kept parts of 6 Oct are copied, not exported again, from LOGS/stage3b-public/arms: vllm-repack, ollama-repeat,
     llamacpp-repeat, llamacpp-repeat-no-cache, vllm-repeat and vllm-repeat-batch-invariant. Prove each file by its sha256.
     Nothing else of 6 Oct goes in: not the arm of 4 Oct on Ollama's own tag, not the first Ollama and llama.cpp arms,
     not the together arms of 6 Oct, not the second vLLM arm of that night, not compare.json or compare.md (ruling 25).
   - The two documents are written by a script from the tool's own output and from your records of the run.
     No figure is typed by hand. Where a figure is rounded, it is worked from the milliseconds and rounded once.
6. The public report. For a reader who has never seen OpenConsult. Plain words, short sentences, the figures first.
   It carries the standing line: a research and education prototype, never real patients, every case acted or scripted.
   It opens with the date of the run, that it answers issue 1, and one short paragraph on what a pass, a chain and a round are.
   That paragraph makes no claim. Then the six lines of ruling 28, numbered, word for word. Do not change a word of them.
   Work out each figure in those lines with the tool, as ruling 28 says where they come from.
   If a figure of yours would change a digit in a line, stop and report. Do not change the line.
   Then the sections the details bullet lists. It makes no case and praises nothing. It names no person,
   except the makers of the model versions by their public account names. It gives the one command.
   Two points to state plainly. The vLLM arm of 6 Oct failed 14 chains, and at which temperature; say what that arm
   would be under Rule A, whatever the answer is. The repeat test is of 6 Oct, and its vLLM arms ran without the switch.
   A sentence quoted from an outside page gives its address. You may reuse the quotations of the public pages of 6 Oct,
   which Cowork read at their sources that day. Where you say which version of an engine is the newest, say on which date.
7. Run the tool's one command on LOGS/stage3b-publish2-public and, by the same code, on the private result folders.
   The two outputs must be the same. Keep both in LOGS. If they differ, stop and report.
   Set your figures beside LOGS/stage3b-bench2-facts.json. A difference is reported, not smoothed.
8. The private word check over LOGS/stage3b-publish2-public, the plain files and the unpacked text of each packed file,
   into LOGS/stage3b-publish2-word-hits.txt: the file, the line number and the line.
   The documents and every data file that is not a case file or a reply file must have no hit. If one has, stop and report.
   A hit in a case file or in a reply file is listed and left as it is.
   Then search everything public for /home/, /mnt/, the user name and the host name: none.
   No row and no line of the other consultation of rule 7 is anywhere in the folder.
   The folder's size and its number of files go into LOGS/stage3b-publish2-files.txt. It stays under 30 MB.
9. Write LOGS/STAGE3B_PUBLISH2_REPORT.md, for Cowork. Short. What was built, with the commits and their hashes;
   the files with their line counts, and any size target missed; the tests, each with what it pins;
   the public folder, file by file with sizes; the six lines of ruling 28, each beside the figures you worked out;
   every place where your figures differ from STAGE3B_BENCH2_REPORT.md; anything you flag.
Then stop. This is the second gate. Your message, ten lines at most:
   the new HEAD and the number of commits; the number of tests, none skipped;
   that the six lines hold, digit for digit; the size of the public folder and the number of word hits;
   that nothing is published and git status --porcelain is empty; anything you flag;
   then this line for the owner: Tell Cowork: Publish step ready. Nothing is published yet.

PART 5. AFTER THE SECOND GATE
Wait for the owner. He will type: Publish. Go.
He may first tell you to read a review file in LOGS. If so, read it and follow it.
1. Copy LOGS/stage3b-publish2-public to V2/engine-bench. Prove with diff -r that the two are identical.
2. The private word check for this commit: on every staged file that is not a case file or a reply file of engine-bench
   it must print nothing. For the case files and the reply files, run it and compare its output with
   LOGS/stage3b-publish2-word-hits.txt. The two must be the same, line for line. If not, stop and report.
3. Commit the folder. Subject: Stage 3b: the engine bench of 7 Oct, published
4. The documents, in the last commit:
   CLAUDE.md: the bench commands made true, with the new command. It stays under 100 lines.
   README.md: one line that points to engine-bench. Use the line of 6 Oct from LOGS/stage3b-publish2-before-README.md
   unless it has become untrue. The owner corrects it.
   HANDOVER.md: one new entry at the top for stage 3b as a whole. The file stays under 500 lines.
   What was built on 6 Oct and today, the rulings of 15.8 in one line each, and what this stage has made untrue.
   The parts of LOGS/stage3b-publish2-before-HANDOVER.md that are about the code are still true and may be carried over.
   Every figure of the bench comes from the public report of 7 Oct only.
   No figure of the first bench is written, except where the public report itself gives it.
   NOTICE: one entry for each library added. None is expected.
5. The suite is green. git status --porcelain is empty. git log --oneline lists your commits on v2.
   V1 HEAD is unchanged. Nothing that existed in LOGS before this session has changed: prove it for LOGS/stage3b-bench2,
   LOGS/stage3b-public and LOGS/stage3-cases with the sha256 list of Part 1, taken again now.

FINAL MESSAGE
Eight lines at most:
the number of commits and the last hash;
the number of tests, the suite time, none skipped;
that the private word check passed as Part 5 says;
that V1 HEAD and the sources in LOGS are unchanged;
the README line, word for word;
any target missed, anything you flagged;
then this line for the owner: Tell Cowork: Stage 3b published locally. Do not push yet.
