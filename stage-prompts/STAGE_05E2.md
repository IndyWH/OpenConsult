OpenConsult v2.0, step 5e2: a second look at AssemblyAI on its updated medical mode

WHAT THIS IS
Step 5e ran the speech bench on three recordings of real voices on 10 Nov 2026. On that run AssemblyAI's live stream wrote one drug as another real drug three times, and the notes carried it. That same day AssemblyAI updated its medical mode: a pass that finds medical terms the model heard and spelt wrong and corrects them from the words around them, for live and for recorded sound, given to every account that already sends the mode. The bench ran that morning, and nobody can say whether it met the old mode or the updated one. On 13 Nov 2026 the owner ruled that he does not choose the default cloud speech service until AssemblyAI has been run again (15.9, ruling 35). This run is that second look, and nothing more. From the patient's side it asks one thing: on the same three recordings, does AssemblyAI today write a drug as another real drug, and how many of the 61 spoken drug names does it catch, live and on the whole recording, set beside its own figures of 10 Nov. It is a run of the bench as it stands. Nothing of the app changes. Done when the owner sees the report's first table, checked by Cowork from the raw files.
The spec is V2_SPEC.md. Read in 15.9 rulings 9, 10, 16, 28, 29, 31 and 34 to 40, and the details of 5e. Then, in this repo, stage-prompts/STAGE_05E.md: EVERY RULE OF THAT PROMPT HOLDS IN THIS RUN except where this prompt changes it, and through it the rules of STAGE_05C1.md, STAGE_05C2.md and STAGE_09A.md that it names. Then, in LOGS, STAGE5E_REPORT.md: its first table, What each cloud service keeps, the uploads, and Flags. Where this prompt and the spec differ, the spec wins: stop and report.
OpenConsult is a research and education prototype. Never real patients. Every consultation is acted.

MODEL
This runs on Fable 5.2 at high effort. Say in your first line which model you are. If you are not Fable 5.2, stop there.

THE FOLDERS
V2    /home/indy/Projects/OpenConsult2
      The repo. Branch v2. All commits are made here.
LOGS  /home/indy/Work/openconsult-review/v2-logs
      Private. This prompt is here. Every file and folder you make in LOGS has a name that begins stage5e2- or STAGE5E2_. Everything else in LOGS is read only, the files and folders of 10 Nov included: copy what you reuse under a stage5e2- name. Never open any .env file in LOGS.
REC   /home/indy/oc-recordings
      The three recordings. Read only. Write nothing there, and change no file's time. The bench works on copies in LOGS/stage5e2-recordings.
KEY   /home/indy/.local/share/openconsult
      The owner's own data folder. The rule of STAGE_09A.md holds word for word: you never open, print, copy, list or write its .env or anything else in that folder; a key reaches a worker in one way only, by the bench command being given this folder as the place of the key file. No copy of a key is made anywhere.
ENG   The owner's engine script LOGS/stage3c_engines.sh (15.13, ruling 1): start vllm-5d and stop vllm-5d, each written to your log with the card's reading before and after. Never the Ollama service. Never sudo. Leave the engine as you found it.

BEFORE YOU START
1. Read V2/CLAUDE.md and the newest entry of V2/HANDOVER.md.
2. Check the spec with sha256sum. It must be:
   ac50fcbccc3fee77c94015ec4eb8636f3ba2a5c17c29f67f0304ed6f0f82d37b  V2_SPEC.md
   HEAD holds 66469965; the disk holds rulings 34 to 40 of 15.9 with one opening paragraph, and one paragraph under Done when you see for 5e. If it differs, stop and report.
3. The branch is v2 and HEAD is 1746325b6336f4e4117d0e73125a4fb80275d839. git status --porcelain prints one line only: V2_SPEC.md modified. Otherwise stop and report.
4. Make an empty file LOGS/stage5e2-start.marker. Write LOGS/stage5e2-rec-before.txt, the names, sizes and times of last change of every file in REC. You compare it at the end.
5. Look, read only, and write what you find in your log: whether anything answers on 127.0.0.1 at ports 8000, 8001 and 8172; the card's memory, used and free. Change nothing. The gate is in Part 3.
6. The figures of 10 Nov that stand are LOGS/stage5e-tables3 (scores.json and report.md) and the stored results under LOGS/stage5e-run. They are read only. You read them for the comparison and change nothing there.

WHAT CHANGES FROM THE PROMPT OF 5e
1. ONE SERVICE. Only AssemblyAI is run: its live arm (assemblyai) and its whole recording arm (speech-upload with the service assemblyai). Nothing is sent to Speechmatics. No local speech arm runs, so no speech model is loaded on the card.
2. WHAT LEAVES THE MACHINE. The three recordings and the clip of the self-test, to AssemblyAI's EU addresses, live and whole, and nothing else of ours to anywhere. The list holds the consent for each recording, as before. A record of every connection attempt and every name lookup is kept for the whole run and set beside this rule at the end. A file sent is named by a plain word and a number.
3. THE SAME SETTINGS AS 10 NOV, not one changed: the live model and the upload model the bench sent that day, the medical mode on, who spoke on, no word list and no prompt. The medical mode is not switched off in any arm. If the service now refuses a setting, or its reply names another model or mode than on 10 Nov, stop and report; do not work round it.
4. THE LIVE ARM RUNS TWICE. A single new page set beside a single old page cannot tell a change of the service from chance. So each recording goes through the live arm a second time, into a second folder. The report says how far the two live pages of today differ from each other, in words and in drug names, beside how far each differs from the page of 10 Nov.
5. THE LANGUAGE MODEL is the local one, on vLLM, as on 10 Nov, for the pages of round one and the whole recording pages: the label check as the app sends it, the label check on the joined lines, the call for doubtful drug names, the notes in two rounds, and two notes from each of the three scripts. The prompt files keep their bytes: at the end git diff 1746325 --name-only -- openconsult/prompts openconsult/bench/speech/prompts prints nothing. The voice method is not run (15.9, ruling 38).
6. NO CODE OF THE APP CHANGES, and by intent no code of the bench either. If the scoring command cannot score a folder that holds two arms only, say so in your plan with the smallest change of the bench that mends it and its test; do not copy results of 10 Nov into the new folder to get round it. The comparison with 10 Nov is made by a private script of yours in LOGS, from the two sets of stored scores, and never goes into V2.
7. NOT BUILT (R31): nothing of rulings 36, 37 and 39 (no pass at Stop in the app, no change to the label check in the app, no drug-name marks in the app); no change of any default; no test with a silence (ruling 40); nothing of the later report-only run; nothing of 9b or 9c.
8. WHAT STAYS PRIVATE, as in 5e: no word that a person said in a recording goes into V2, a commit or chat; nor a transcript, a note, the key-fact file, or any word of script 19. The second reader is never named anywhere, and the owner is the owner. Chat gets counts.
9. Each commit message ends, after one empty line, with: Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>
10. Before each commit the private word check of STAGE_05C2.md, rule 12, on the staged files. It must print nothing.

PART 1. TWO COMMITS, THEN THE PLAN, THEN STOP
Commit 1. Subject: Stage 5e: the spec with rulings 34 to 40 of stage 5, the owner's choices after the bench
   V2_SPEC.md alone, as it stands on disk, checksum proven.
Commit 2. Subject: Stage 5e2: the stage prompt
   Copy this file to V2/stage-prompts/STAGE_05E2.md. Prove with cmp that it is identical.
Then write LOGS/STAGE5E2_PLAN.md. Keep it short. It holds, in this order:
1. What AssemblyAI's own pages say today, with their addresses, of the medical mode: what changed and when, which models have it, and whether a reply names the mode or a version of it. What its pages say today that it keeps of a live stream and of an upload on a free account, where that differs from what STAGE5E_REPORT.md recorded.
2. The copies of the three recordings into LOGS/stage5e2-recordings, proven against LOGS/stage4-recordings.sha256, and the list, made as on 10 Nov before the voices were added.
3. The commands of the run with their exact words, in order, with the folders: round one live into LOGS/stage5e2-run; each recording whole into the same folder, the delete and its proof after each; round two live into LOGS/stage5e2-run-b; the calls; the scoring, twice, byte for byte the same. Whether the scoring command takes these folders as they are (rule 6). The minutes you expect for each step, the minutes of sound sent, and what that costs by the service's page.
4. The comparison script: which figures of LOGS/stage5e-tables3 it sets beside which of today, and how the two live pages of today are compared with each other.
5. The card and the engine: each stop and start of vLLM, and how the engine is left as it was found.
6. Anything in the spec or in this prompt that is wrong, silent or in conflict: do not fix it yourself.
Then print five lines at most, and stop. Wait for the owner. He will type: Approved. Go.
He may first tell you to read a review file in LOGS. If so, read it and follow it. It may change your plan.

PART 2. THE BUILD
Only if your approved plan holds a change of the bench under rule 6: that change with its test, one commit, the suite green before it. Otherwise nothing is built.

PART 3. THE CHECKS AND THE RUN
Item 1. The suite: the number of tests, the time, none skipped. Then uv run python .github/scripts/start_check.py.
Item 2. THE GATE FOR THE CARD. Ask 127.0.0.1 at port 8000 and at port 8001 once each. If anything answers on 8000, print exactly: Waiting for v1 to be switched off. If anything answers on 8001, print exactly: Waiting for the app on port 8001 to be closed. Then stop. The owner will type: Closed. Go. When neither answers: write down whether vLLM is up and read the card.
Item 3. The self-test of the assemblyai choice with the key kept apart. It must pass. Then THE GATE CALL on the upload route: the clip of the self-test sent whole, the result read, the transcript deleted, asked for again and found gone by the rule of 10 Nov (the service's own words for deleted, and no three words in a row of our result in any answer). If the result does not come, if the delete fails, or if the service does not say that it is gone: stop and report. No recording has been sent at this point.
Item 4. The copies of the three recordings, proven, and the list.
Item 5. THE RUN. A driver that needs nobody, one job at a time, every command under the recorder of connections. Print exactly: The second look has started. In this order:
   the three recordings through the live arm, into LOGS/stage5e2-run;
   each recording whole to the service; after each one the delete and its proof, before the next is sent;
   the three recordings through the live arm a second time, into LOGS/stage5e2-run-b;
   vLLM started with the engine script; on the six pages of LOGS/stage5e2-run the calls of rule 5; the engine left as item 2 found it, the card read;
   the scoring and the tables of each folder with the one command from the stored results alone, then a second time into another folder: each pair must be the same, byte for byte;
   the comparison script.
   If a step or a call fails, its failure is kept and the driver goes on, with one exception: if a delete fails or cannot be proven, the driver sends nothing more to the service, finishes the local steps, and your last message begins with this line for the owner: Tell Cowork: an upload could not be proven deleted. Expect about an hour and a quarter.
Item 6. When every upload is done, ask the service once more for every transcript of this run, the gate's included, and read the account's list: nothing of this run may still be held. Write the answers, as counts and states, in LOGS/stage5e2-deletes.txt.
Item 7. Read your own tables as a doubter would, and by hand on the stored pages: every speech of script 19 where the drug that was written as another on 10 Nov is spoken, and every drug name the tables call not caught, on each of today's three kinds of page. If the scoring is wrong, say so plainly.
Item 8. REC proven against LOGS/stage4-recordings.sha256, and its list made now equal to LOGS/stage5e2-rec-before.txt, line for line. The prompt folders unchanged (rule 5). The record of connections set beside rule 2: every address named, and none outside it, and none of Speechmatics. The files of 10 Nov in LOGS unchanged: no file older than your start marker has a newer time of change. Nothing private in V2, searched by a script that prints counts only. Every count 0.
Item 9. The last commit: HANDOVER under 500 lines with a short entry and the measurements as counts; CLAUDE.md untouched unless a command changed. Then git status --porcelain is empty.

THE REPORT
LOGS/STAGE5E2_REPORT.md. It is private. Its first line: THE FIGURES OF THIS REPORT COUNT: A SECOND LOOK AT ASSEMBLYAI ON THE THREE RECORDINGS OF 21 OCT 2026. Then, for the patient, one table. Its rows: AssemblyAI live on 10 Nov; AssemblyAI live today, round one; AssemblyAI live today, round two; AssemblyAI whole recording on 10 Nov; AssemblyAI whole recording today. Its columns: any passage of speech missing with no sign; words where nobody spoke; a drug written as another real drug, and in how many notes; drug names caught of 61; words under the wrong speaker by the choice's own labels; speeches of the patient that run on into the doctor's words, of 49; the usual wait of the line for Alba by the sound. Under it, in plain words: whether the wrong drug of 10 Nov is written today, on each kind of page; how far the two live pages of today differ from each other; and that one run on each day cannot prove what the update did. Then, each under its own heading: each drug name not caught today, with what was written, beside what was written on 10 Nov; what each reply names as its model and its mode, beside 10 Nov; what the service's pages say of the update; that every upload was deleted and proven gone, with the count, and what could not be proven; the minutes sent and the cost by the page's price; the calls to the language model; the engine's stops and starts; what item 7 found; the commits; what in LOGS may now be removed, without removing anything yourself. Last: anything you flagged. You do not choose for the owner.

FINAL MESSAGE
Eight lines at most: the spec's checksum as given and committed; whether the run went from start to end; for each of today's three kinds of page, whether a drug was written as another real drug and the drug names caught of 61, with the figures of 10 Nov beside them; that every upload was deleted and proven gone, with the count; that nothing went to any other host and no key was read by you; the number of commits, the last hash and the suite's count; anything you flagged; then this line for the owner: Tell Cowork: Stage 5e2 built. Do not push yet.
