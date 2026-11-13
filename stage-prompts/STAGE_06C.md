OpenConsult v2.0, step 6c: the build at Stop

WHAT THIS IS
The speech bench of 5e, on three recordings of real voices, left two things to build, and the owner ruled on both on 13 Nov 2026. From the patient's side this run does two things. One: a medicine name that speech recognition wrote wrongly is the error most likely to harm, and on the default speech choice 41 of them stood on one page. At Stop the language model now reads the final transcript once and marks the drug names it doubts. The doctor sees each mark in three places, on the line, as a warning and on every note entry that draws on that line, and one line says that a name with no mark is not proven right. No guess is ever shown. Two: the check of who spoke made well labelled pages worse, so it no longer runs at Stop. The doctor asks for it with one control on the review page, sees what it changed, and can undo it; and it is made able to take a long page, which it could not. Beside the build there are two benches: parts against whole pages for the who-spoke check, and Claude Haiku on both jobs, because a cloud model is offered only after it has run every bench the local model has run.
The spec is V2_SPEC.md. Read in 15.10 rulings 6, 7, 11, 14 and 18 to 23, and THE DETAILS OF STEP 6C that follow ruling 23: they are the design of this run and you build them as written. Read in 15.9 rulings 17, 18, 37 and 39, and in 15.13 rulings 8, 21 and 24. Then, in this repo, stage-prompts/STAGE_05E.md for the rules on the private pages and STAGE_09D.md for the rules on the Claude service: each holds here where this prompt names it. Where this prompt and the spec differ, the spec wins: stop and report.
OpenConsult is a research and education prototype. Never real patients. Every consultation is acted.

MODEL
This runs on Fable 5.2 at high effort. Say in your first line which model you are. If you are not Fable 5.2, stop there.

THE FOLDERS
V2    /home/indy/Projects/OpenConsult2
      The repo. Branch v2. All commits are made here.
LOGS  /home/indy/Work/openconsult-review/v2-logs
      Private. This prompt is here. Every file and folder you make in LOGS has a name that begins stage6c- or STAGE6C_. Everything else in LOGS is read only, the files and folders of 5e and 5e2 included: copy what you reuse under a stage6c- name. Files whose names begin cowork- are not yours to change. Never open any .env file in LOGS.
KEY   /home/indy/.local/share/openconsult
      The owner's own data folder. The rule of STAGE_09A.md holds word for word: you never open, print, copy, list or write its .env or anything else in that folder; a key reaches the bench in one way only, by the bench command being given this folder as the place of the key file. No copy of a key is made anywhere. No test and no command of yours writes there.
ENG   The owner's engine script LOGS/stage3c_engines.sh (15.13, ruling 1): start vllm-5d and stop vllm-5d, each written to your log with the card's reading before and after. Never the Ollama service. Never sudo. Leave the engine as you found it.

BEFORE YOU START
1. Read V2/CLAUDE.md and the newest entry of V2/HANDOVER.md.
2. Check the spec with sha256sum. It must be:
   cf560f65d1e70f1fc10cb748954492cc7f236747fdacb776e1ba02d3311cff8f  V2_SPEC.md
   HEAD holds 3f54f75c; the disk holds rulings 18 to 23 of 15.10 with one opening paragraph, and the details of step 6c. If it differs, stop and report.
3. The branch is v2 and HEAD is 8c53d893ed969093ec19a12aef5a208f9e3bc1e7. git status --porcelain prints one line only: V2_SPEC.md modified. Otherwise stop and report.
4. Make an empty file LOGS/stage6c-start.marker.
5. Look, read only, and write what you find in your log: whether anything answers on 127.0.0.1 at ports 8000, 8001 and 8172; the card's memory, used and free. Change nothing. The gate is in Part 2.
6. The stored pages and readings of 5e are LOGS/stage5e-run (results and calls) and LOGS/stage5e-tables3 (scores.json and report.md); the list of recordings is in LOGS/stage5e-recordings; scripts 14 and 15 are in V2/engine-bench/cases and script 19 in LOGS/stage4-scripts. All read only. No sound is read in this run.

THE RULES OF THIS RUN
1. WHAT LEAVES THE MACHINE. Nothing, until Part 4. In Part 4, to https://api.anthropic.com and to no other address: the two approved prompts, their forms, and the text of the 24 stored pages as the heading and the numbered lines. No sound, no file, no name of a recording or of a person, no patient line. A record of every connection attempt and every name lookup is kept for the whole run, as in 5e, and set beside this rule at the end.
2. WHAT STAYS PRIVATE, as rule 8 of STAGE_05E2.md: no word that a person said in a recording goes into V2, a commit or chat; nor a transcript, a note, a model's reply on a page, or any word of script 19. The second reader is never named anywhere, and the owner is the owner. Chat gets counts. A figure by recording stays in LOGS.
3. NO WORD A MODEL READS IS NEW. The label check's prompt, frame and form and the drug-name prompt and form keep their bytes, by the sha256 the details give; the drug-name files move into the app's prompts folder with their bytes proven before and after; the drug-name frame is the label check's bytes. If you find that a call needs a word the details do not give, stop and report.
4. THE SENTENCES. Those of rulings 18, 19 and 20 are the owner's: copy each from the spec letter for letter into the file of words. The drafts are named in the details. Any other sentence a person would read that you find you need: give it in full in your plan, and add none after the plan without saying so in the report.
5. THE CLAUDE SERVICE, as STAGE_09D.md and STAGE_09D2.md say: claude-haiku-5-5, the Messages API request the kind sends today, the effort field not sent, the rate kept by the headers, no call sent a second time, three refusals for rate in a row stop the bench.
6. A product or clinical choice the details leave open is not yours: stop and report it. The details name what is not built; build none of it (R31).
7. Each commit: one logical change, the suite green before it, the why in the message. Each commit message ends, after one empty line, with: Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>
8. Before each commit the private word check of STAGE_05C2.md, rule 12, on the staged files. It must print nothing.
9. Long output goes to LOGS/stage6c-run.log, never into chat.

PART 1. TWO COMMITS, THEN THE PLAN, THEN STOP
Commit 1. Subject: Stage 6c: the spec with rulings 18 to 23 of stage 6 and the details of the step
   V2_SPEC.md alone, as it stands on disk, checksum proven.
Commit 2. Subject: Stage 6c: the stage prompt
   Copy this file to V2/stage-prompts/STAGE_06C.md. Prove with cmp that it is identical.
Then write LOGS/STAGE6C_PLAN.md. Keep it short. It holds, in this order:
1. THE LOCAL FIGURES, as numbers, read from the stored results of 5e and from no report: for the label check on the joined lines, each of the 24 pages with its lines, whether its reply was taken or refused, and its words under the right speaker, under the wrong speaker and unsure; the sums; the pages judged for P1 and P2, their words, and the allowance of P2 as a number. For the drug-name call, each page with its drug names written wrongly, how many were marked, its marks on a word that was written rightly, and its entries dropped; the sums. The engine version and the model digest stored with those calls.
2. THE PARTS: the one function for the app and the bench, the three named figures, and the commands of the parts reading with their exact words and folders. How you prove that the stored whole reading is from today's engine and model, and what you run if it is not.
3. THE BUILD: the tables of version 9 and how a folder of version 8 comes forward; the functions and pages touched; how the review page waits while a check runs and what a restart leaves; how a mark's places are stored and found again after an edit; how the page of the calls leaves the named drug out (ruling 23). Every sentence a person would read that is new or changed, in full, each marked as the owner's or as a draft.
4. EVERY TEST you intend, each with the ruling or the rule it pins.
5. THE BENCH OF CLAUDE HAIKU: what speech-calls gains; the commands with their exact words and folders; the first call; the number of calls, the minutes and the cost you expect by the service's page; the marks H1, H2 and D1 to D3 as numbers; how you prove that only the text of a page is sent.
6. The card and the engine: each start and stop of vLLM, and how the engine is left as it was found.
7. Anything in the spec or in this prompt that is wrong, silent or in conflict: do not fix it yourself.
Then print five lines at most, and stop. Wait for the owner. He will type: Approved. Go.
He may first tell you to read a review file in LOGS. If so, read it and follow it. It may change your plan.

PART 2. THE BENCH OF PARTS AGAINST WHOLE
Item 1. The suite as it stands: the number of tests, the time, none skipped.
Item 2. The lines and the parts: the bench's rule for joined lines moved to where the app and the bench both read it, the function that cuts a page into parts, and the parts reading as a job of speech-calls, each with its tests. One commit or two. No page of the app changes yet.
Item 3. THE GATE FOR THE CARD. Ask 127.0.0.1 at port 8000 and at port 8001 once each. If anything answers on 8000, print exactly: Waiting for v1 to be switched off. If anything answers on 8001, print exactly: Waiting for the app on port 8001 to be closed. Then stop. The owner will type: Closed. Go. When neither answers: write down whether vLLM is up and read the card.
Item 4. vLLM by the engine script. The whole reading again if your plan called for it; then the parts reading on the 24 pages, 48 calls, into LOGS/stage6c-parts. The engine left as item 3 found it, the card read.
Item 5. The count, from the stored results alone, twice, byte for byte the same; then P1 and P2. Write LOGS/STAGE6C_PARTS.md: the two marks, and the figures by kind of page.
Item 6. If P1 or P2 is missed: build nothing more. Make the last commit of Part 5 for what stands, and let your final message begin with this line for the owner: Tell Cowork: the parts missed their mark. If both hold, go on without waiting.

PART 3. THE BUILD
As the details give it, in commits of one logical change each. A good order: the tables of version 9; Stop without the label check; the drug-name job with its files moved, the call at Stop and the marks; the marks on the review page and the signs on the note; the who-spoke check on the review page with its runs, Undo and Undo all; the line of ruling 18; the page of the calls; the words and the home page's account. What a model writes is never asserted in a test.

PART 4. THE BENCH OF CLAUDE HAIKU
Item 1. The suite, green. Then the first call: one page through the label check with the app's own form. If it does not come back to the form, stop and report; nothing more is sent.
Item 2. The label check on the joined lines of the 24 pages, whole; the parts reading; the drug-name call. Into LOGS/stage6c-haiku. A failed call is kept as failed and never sent again.
Item 3. The count by the bench's own counting of 5e, from the stored results alone, twice, byte for byte the same. Then H1, H2 and D1 to D3 against the numbers of your plan, and the two counts of invents nothing.
Item 4. Read your own tables as a doubter would, and by hand on the stored pages: every drug name the local model marked and Haiku did not, and every Haiku mark on a word that was written rightly. If the counting is wrong, say so plainly.
Item 5. If a mark is missed: no word of a prompt is changed and nothing is run again. HANDOVER says that the two jobs are not offered in cloud mode until the owner has ruled. You do not choose for the owner.

PART 5. THE CHECKS AND THE LAST COMMIT
Item 1. The suite: the number of tests, the time, none skipped. Then uv run python .github/scripts/start_check.py.
Item 2. The prompt files by their sha256, and git diff 8c53d89 --stat -- openconsult/prompts openconsult/bench/speech/prompts shows the two drug-name files moved and the new frame, and no other change.
Item 3. The record of connections set beside rule 1: every address named, none but the Claude service's outside this machine, and none before Part 4. No key was read by you.
Item 4. The files of LOGS that are not yours unchanged: no file older than your start marker has a newer time of change, the engine script's own log aside, which you name. Nothing private in V2, searched by a script that prints counts only. Every count 0.
Item 5. The last commit: HANDOVER under 500 lines with the run's entry and the measurements as counts, and which document your work has made untrue; CLAUDE.md with the new commands, under 100 lines; the README. Then git status --porcelain is empty.

THE REPORT
LOGS/STAGE6C_REPORT.md. It is private. First, for the patient, in plain words: what a doctor now sees at Stop when a drug name is in doubt, and what the page says of a name with no mark; what the check of who spoke does now and when. Then, each under its own heading: the bench of parts, the two marks and the figures by kind of page, and that halves are a harder test than the app's parts; the bench of Claude Haiku, each mark with the local figure beside it, the two counts of invents nothing, what item 4 of Part 4 found, the calls, the cost and the wait; the build, commit by commit; every sentence that is new or changed, in full, the owner's and the drafts apart; the tables of version 9; the engine's stops and starts; what left the machine; what in LOGS may now be removed, without removing anything yourself. Last: anything you flagged.

FINAL MESSAGE
Eight lines at most: the spec's checksum as given and committed; the parts, passed or missed, with the two sums; the build, with the suite's count; Claude Haiku on each job, passed or missed, with the mark missed; the calls sent, what they cost, and that nothing went to any other host and no key was read by you; the number of commits and the last hash; anything you flagged; then this line for the owner: Tell Cowork: Step 6c built. Do not push yet.
