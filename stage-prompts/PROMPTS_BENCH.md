OpenConsult v2.0: the two carried prompts, changed by rulings 41 to 43 of 15.8, benched on vLLM before they are kept

WHAT THIS IS
The model sometimes writes a plain double quote inside its reasoning, usually in the sentence that says there are no red flags. Inside the answer form that quote ends the reasoning. On vLLM the compact form keeps the reply alive, but the reasoning stops mid-sentence and the fields after it come from a thought never finished; a cut alarm has said time critical and named no action. On 15 Oct 2026 the owner and Cowork read the two prompts word for word (15.8, ruling 1). Both prompts showed the model that habit: quoted examples, two in the assessment and fourteen in the alarm. The owner ruled that every double quote comes out of both prompts and that one sentence is added to each, asking the model never to write one. The spec holds the approved wording of both prompts, word for word, in rulings 41 and 42. Ruling 43 says the frames and the forms stay as they are, and that the change is kept only after this bench.
Your job: commit the spec; write the two prompt files byte for byte as the spec has them; change the two pinned hashes and the word check so that they prove the files equal the spec; run the bench of stage 3 on vLLM with the changed prompts; count the cut replies, the empty lists and the alarms with no action against the vLLM arm of 7 Oct; and report. A prompt change is a bench of its own (V1_LESSONS 3.7).
The spec is V2_SPEC.md. Read, in this order: 15.8 rulings 41, 42 and 43; 15.8 rulings 1, 16, 22 and 24; 15.7 ruling 3 and, in its details, Prompts are files and The word check; 15.8 rulings 18, 30 and 31; the part of 15.8 headed Stage 3c with its details. Where this prompt and the spec differ, the spec wins: stop and report.
OpenConsult is a research and education prototype. Never real patients.

MODEL
This runs on Fable 5.1 at high effort. Say in your first line which model you are. If you are not Fable 5.1, stop there.

THE FOLDERS
V2    /home/indy/Projects/OpenConsult2
      The repo. Branch v2. All code and all commits are made here.
LOGS  /home/indy/Work/openconsult-review/v2-logs
      Private. Your plan, your log, your report and your result folders go here. This prompt is here.
      Every file and folder you make in LOGS has a name that begins prompts- or PROMPTS_.
      LOGS/approved-prompts-15-oct holds Cowork's copies of the two approved texts, for your cmp in step 4. The spec is the source; if a copy and the spec differ, stop and report.
ENG   /mnt/fastdata/openconsult-engine-bench
      The engines and the model files, as 3c left them. You start and stop vLLM only with LOGS/stage3c_engines.sh, as 3c did. You install nothing there, you delete nothing there, and you change no file there.
CASES /home/indy/Work/openconsult-review/v2-logs/stage3-cases
      Read only. The 16 cases of the bench of stage 3.
OLD   /home/indy/Work/openconsult-review/v1.1-logs
      Read only. v1's recorded calls for the word check: task5-calls.jsonl and task5b-calls.jsonl.
OLDER Every other folder in LOGS whose name begins stage3-, stage3b, stage3c, stage5a, stage5b, stage5c1, stage5c2 or stage5d. Read only. Write nothing there and delete nothing there. Do not use an older data folder as your own; make LOGS/prompts-data.
      LOGS/stage5c1-data holds a copy of the owner's two keys. Do not open LOGS/stage5c1-data/.env.
V1    /home/indy/Projects/consultation-ai
      Read only. Change nothing. Never read V1/.env or any file that holds a key or a token.

THE RULES
1. Check the spec with sha256sum before anything else. It must be:
   4be807fcb123435753d18bfcc29a41db11ef343d1fc60baeb8c473c2cfa0652a  V2_SPEC.md
   If it differs, stop and report. Do not go on. Do not change a character of the spec.
2. Check the branch is v2 and HEAD is 850e0b7. git status --porcelain must show one line only, V2_SPEC.md modified. If anything else is changed or untracked, stop and report.
3. No git push. No sudo. No service command. Install no system software. uv may reach the package index; nothing else reaches outside this machine.
4. You never write or change a word a model reads except by copying the two blocks of rulings 41 and 42 exactly (15.3). The three frames and the two forms are not touched. The loader reads a prompt file less its final line break, so each file is the block followed by one line break, nothing else. Prove each with sha256sum of the text as the loader reads it, against the hash the ruling gives, and with cmp against the copy in LOGS/approved-prompts-15-oct.
5. The two pinned hashes in tests/test_prompts.py change to the two hashes of rulings 41 and 42, and the test's name and comment say what they now pin: the prompt sent is the spec's approved wording, word for word. The word check of 15.7, ruling 3, still runs against OLD and still compares the message, the form, the model, the thinking switch and the options call for call; for the prompt it now compares against the approved texts, not v1's, and its count is still so many of so many. Say in your plan how, with the smallest change, and keep the check honest: it must still fail if a prompt file differs from the spec.
6. No test of an earlier stage is weakened or deleted beyond rule 5. What the model says is never asserted in a test (5.2). The suite needs no card, no vLLM and no Ollama.
7. Before each commit, run the private word check on the staged files. It must print nothing:
   git diff --cached --name-only -z | xargs -0 grep -n -i -w -F -f /home/indy/Work/openconsult-review/v2-logs/private-words.txt
   If it prints a line, stop and report. Never copy the word list, or any word from it, into V2 or into a commit message. Nothing you write for a commit names a folder of this machine that V2 does not name already, and nothing names the machine.
8. Each commit: one logical change, the suite green before it, the why in the message. Each commit message ends with this line, after one empty line:
   Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
   That is the only address allowed in a commit message.
9. Nothing from the bench goes into V2 but the figures in HANDOVER. No case text, no reply text and no result file enters the repo. The public folder engine-bench is not touched and is not run again.
10. Do not touch V2_SPEC.md after commit 1. Cowork does not touch it while you run.

PART 1. TWO COMMITS BEFORE THE PLAN
Commit 1. Subject: Carried prompts: the spec, with rulings 41 to 43 of 15.8
   V2_SPEC.md only. The spec is committed before the code (V1_LESSONS 11.3).
Commit 2. Subject: Carried prompts: the stage prompt
   Copy this file to V2/stage-prompts/PROMPTS_BENCH.md. Prove with cmp that it is identical.

PART 2. THE PLAN, THEN STOP
Write your plan to LOGS/PROMPTS_BENCH_PLAN.md. It holds:
1. The two hashes of rulings 41 and 42, and the exact command that proves each file against its ruling.
2. The change to tests/test_prompts.py and to the word check (rule 5), with the lines that change.
3. The bench run: the exact commands, on vLLM at 127.0.0.1:8172 started with LOGS/stage3c_engines.sh start vllm-5d, the model xbill9/gemma-4-26B-A4B-it-qat-q4_0-w4a16-ct at revision 2096d38dad51a19b8e982b44241c47102a8bbb00, with the compact form of ruling 22 exactly as 3c sends it; all 16 cases; the 13 chains of 15.7 (A1 A2 A3 at temperature 0 with seed 42, B1 to B10 at 0.5 with seeds 1 to 10); the two calls of a pass sent together (--together), as the app runs a pass since 3c; results under LOGS/prompts-bench; the data folder LOGS/prompts-data. The time you expect, from the vLLM together arm of 7 Oct.
4. The hard marks of 15.7 as numbers, taken from the spec's details of 15.7: on 495, ectopic pregnancy on the list at some pass, 3 of 3 at temperature 0 (and 13 of 13 reported); on 495, the alarm names a pregnancy test or hCG, 3 of 3; on the first travel case, dengue on the list by turn 20, 3 of 3; on the second, malaria on the list by turn 16 and the alarm fired by turn 16, 3 of 3 each; each of the seven emergency scripts fires, 3 of 3; in the male cases no differential and no urgent action names pregnancy, ectopic, ovarian or hCG. Temperature 0 decides (ruling 18); the ten chains at 0.5 are the stress test, reported apart. A chain in which any call failed is a failed chain.
5. The three counts of ruling 43, and how you count each from the raw result files, with the same rule applied to the raw files of the vLLM arm of 7 Oct (V2/engine-bench/arms/vllm-together-compact for the together way; V2/engine-bench/arms/vllm-repack-compact for the thirteen chains): a reply whose reasoning was cut by a stray quote; an assessment whose list of differentials came back empty; a pass in which the alarm said time critical and named no action. Give the 7 Oct figures you get from the public files before the run, and say if they differ from the spec's (21 cut at 0.5 and none at 0; no empty list; 73 alarms with no action, 10 at temperature 0). The rule that keeps the change: every hard mark met at temperature 0 with no failed chain, and fewer cut replies than 7 Oct at either temperature.
6. The commits you will make, in order, and the HANDOVER entry you will write.
7. The tests you will add or change, each with what it pins.
Then stop. Wait for the owner. He will type: Approved. Go.
He may first tell you to read a review file in LOGS. If so, read it and follow it. It may change your plan.

PART 3. BUILD
1. The two prompt files, byte for byte (rule 4), and the hashes and the word check (rule 5), in one commit. The suite green. Run the word check against OLD/task5-calls.jsonl and OLD/task5b-calls.jsonl with --out under LOGS/prompts-wordcheck-1898 and LOGS/prompts-wordcheck-5b; both counts complete.
2. vLLM up with LOGS/stage3c_engines.sh start vllm-5d. Prove it answers at 8172 and serves the model and revision above. Prove thinking is off, as 3c did.
3. The bench run of the plan. Its output to LOGS/prompts-bench.log. Nothing else runs on the card meanwhile.
4. The marks with the repo's own tool (openconsult-bench score) and again from the raw files by your own count; the three counts of ruling 43 from the raw files; both for 7 Oct from the public files. A missed hard mark at temperature 0 stops you: write the report and the final message; do not run again to get a pass.
5. vLLM stopped with LOGS/stage3c_engines.sh stop vllm-5d and seen gone from the card.
6. The documents, in the last commit: HANDOVER.md gains an entry at the top: the two prompt hashes, the hard marks as numbers, the three counts beside 7 Oct's, the typical pass, and whether the change is kept by ruling 43's rule. CLAUDE.md changes only if a command changed. HANDOVER stays under 500 lines, CLAUDE.md under 100.
7. Before the last commit: git status --porcelain is empty but your commits; nothing private in the added lines (rule 7, and no home path, no ENG path, no machine name); the suite green three times.

THE REPORT
Write LOGS/PROMPTS_BENCH_REPORT.md: the two hashes proven; the word check counts; the hard marks as numbers, temperature 0 first, then 0.5 apart; the three counts of ruling 43 beside 7 Oct's, with the commands that counted both; the typical pass at temperature 0 beside 2.73 s of 5d; the commits with their hashes; the files left in LOGS and which are removable. Plain words. No reply text in the report beyond one example of a cut reasoning if one occurred, with the case and the chain.

FINAL MESSAGE
Eight lines at most: the spec's checksum as given; the two prompt hashes proven; the word check counts; every hard mark at temperature 0 met or which was missed; the three counts beside 7 Oct's; the number of commits and the last hash; that the private word check printed nothing before every commit; then this line for the owner: Tell Cowork: Prompts bench done. Do not push yet.
