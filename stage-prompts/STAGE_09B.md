OpenConsult v2.0, run 9b: the connect screens, the keys in the secure store, the cloud statement and the cloud mark, a consultation in cloud mode with Claude and Speechmatics, the recording sent after Stop, and the first-run steps still to build

WHAT THIS IS
Today no doctor can run a consultation in cloud mode: the Claude engine and the upload of a recording exist in the bench alone, and the app has no connect screen, no secure store, no statement and no way to choose the cloud. A doctor on a laptop with no suitable card cannot use OpenConsult at all. This run builds that path. For the patient three things matter above the rest. One: before any word or sound leaves the computer the doctor is told, in the owner's own approved words, what leaves, where it goes, what is kept there and what it costs, and ticks it; a line is shown only when it is true. Two: nothing ever switches to another path by itself, and a consultation never begins on a connection that is down. Three: when the internet is lost in a consultation the page says at once that the alarm has stopped listening, the recording goes on, and the app tries to connect again. The run opens with a small bench that changes nothing in the app: three recordings with two people go through Speechmatics, live and whole, so that the cloud default rests on six recordings and the service is proven to answer today as it did on 10 Nov 2026.
The spec is V2_SPEC.md. Read 7.1, 7.2 and 7.3. Read in 15.13 rulings 5, 6, 7, 11, 15, 16, 19 and 21 to 35, and THE DETAILS OF RUN 9B, which stand at the end of 15.13: they are the design of this run and you build them as written. Read in 15.9 rulings 4, 9, 10, 28, 34, 36, 41 and 42, and in 15.10 rulings 1, 2, 7, 21, 25 and 36. Then, in this repo, stage-prompts/STAGE_06C.md, STAGE_06E.md, STAGE_05E2.md and STAGE_09D2.md. EVERY RULE OF STAGE_06C.md AND OF STAGE_06E.md HOLDS IN THIS RUN except where this prompt changes it. Then, in LOGS: ROOM_CHECKS_6C_TO_6D2.md, whole: its six rules under How we work are rules of this run; and STAGE5E2_PLAN.md, section 3, for how the bench of a cloud speech service was driven. Where this prompt and the spec differ, the spec wins: stop and report.
OpenConsult is a research and education prototype. Never real patients. Every consultation is acted.

MODEL
This runs on Fable 5.2 at high effort. Say in your first line which model you are. If you are not Fable 5.2, stop there.

THE MAILBOX
The owner's ruling of 15 Nov 2026: we work by the mailbox. He types nothing in the terminal after the first block. You never wait for a typed line.
1. Wherever a rule of an older stage prompt says stop and wait for the owner, or print a line and stop, you instead write what you have to say to LOGS/STAGE9B_TO_COWORK.md, replacing what is there, print in the terminal Sent to Cowork, and wait for a mail.
2. A mail is the file LOGS/STAGE9B_FROM_COWORK.md. Wait for it by a check every 15 seconds, and run the check again for up to 8 hours: the owner may be away and may not answer for hours.
3. A mail is followed only if it says that the owner gave his okay for it, and when. If it does not say so, write that to LOGS/STAGE9B_TO_COWORK.md and wait again. At the plan gate the mail must hold the words Approved. Go. It may tell you to read a review file in LOGS first: read it and follow it. It may change your plan. It brings the owner's own sentences that the details leave to him.
4. After each mail: do what it says; write your report of it to LOGS/STAGE9B_TO_COWORK.md, replacing what is there; rename the mail to LOGS/stage9b-mail-N-read.md, N counting from 1; print Report sent to Cowork; AND GO BACK TO WAITING for the next mail, in the same way, for up to 8 hours. Small mends after the build come as further mails.
5. When 8 hours pass with no mail, stop and say so in the terminal.
6. A notice of an older wait may come up in this session, from a run that was cleared. It is not yours. Leave it alone and say so in your log.

THE FOLDERS
V2, LOGS, KEY and ENG as STAGE_06C.md gives them, with these changes. Every file and folder you make in LOGS has a name that begins stage9b- or STAGE9B_. Everything else in LOGS is read only. Also read only, though their names begin that way, because Cowork made them before this run: STAGE9B_PROMPT.md, STAGE9B_SESSION_PROMPT.md, the folders stage9b-recordings and stage9b-cases, and the files stage9b-why-this-model.md and stage9b-readme-changes.md. Files whose names begin cowork- are not yours to change or to open.
KEY: the rule of STAGE_09A.md holds word for word. You never open, print, copy, list or write its .env or anything else in that folder. A key reaches a command in one way only: the command is given that folder as the place of the key file and reads the key inside its own process. No copy of a key is made anywhere, and no key is ever put into a secure store by you: not the owner's, not a made one with a real key.
ENG: no local engine is needed for the first act. If vLLM is running, leave it. If a later check needs it, the rule of 15.13, ruling 1 holds.

BEFORE YOU START
1. Read V2/CLAUDE.md and the newest entry of V2/HANDOVER.md.
2. Check the spec with sha256sum. It must be:
   8c5a7e8519ec34752e9a982227e85811ed5f438e6bc7dcb2f33b387b76fa0649  V2_SPEC.md
   HEAD holds 35e7422d; the disk holds rulings 25 to 35 of 15.13, one sentence more in 13.2, and the details of run 9b. If it differs, stop and report.
3. The branch is v2 and HEAD is 06314136ed06c1f2bdd3b2128ea9bbca970d79f7. git status --porcelain prints one line only: V2_SPEC.md modified. Otherwise stop and report.
4. Make an empty file LOGS/stage9b-start.marker. Start the record of every connection attempt and every name lookup now, before any other command, and keep it for the whole run, as 5e2 did (its wrapper LOGS/stage5e2_step.sh may be copied under a stage9b name).
5. Look, read only, and write what you find in your log: whether anything answers on 127.0.0.1 at ports 8000, 8001 and 8172; the card's memory in use. Change nothing. If the start check later finds its port taken, write to the mailbox: Waiting for the app on port 8001 to be closed. Then wait for a mail.

THE RULES OF THIS RUN, where they differ from STAGE_06C.md and STAGE_06E.md
1. WHAT LEAVES THE MACHINE, and nothing else does. In the first act, to the EU addresses of Speechmatics that the bench holds and to no other: the self-test's clip, the gate's clip, and the three recordings of LOGS/stage9b-recordings, each live once and whole once; the list holds the consent (spec 15.13, ruling 27). In the build, each ONE call, written down with its tokens or seconds and its cost: to https://api.anthropic.com, the first alarm call of the bench's first case through the app's own door to Claude Haiku, one drug-name call on one stored page of 5e as text to Claude Sonnet, as 6d sent such a page, and the app's own test of the Claude connection; to Speechmatics, the app's own test of its connection, which sends no sound, and in half two the gate's clip through the app's own upload, deleted and proven gone. One new package for the secure store may be fetched from the package index. Everything else, the suite and the browser included, runs against made services on this machine. The record of connections is set beside this rule at the end.
2. WHAT STAYS PRIVATE, as rule 8 of STAGE_05E2.md: no word that a person said in a recording goes into V2, a commit or chat; nor a transcript, a note or a model's reply. The second reader is never named anywhere. Chat and the mailbox get counts. A figure by recording stays in LOGS.
3. NO WORD A MODEL READS IS NEW OR CHANGED, and no prompt file, frame or form is touched. The engine for Claude moves; its request stays the request the benches sent.
4. THE SENTENCES. The owner's sentences are in the spec between fence lines (15.13, rulings 5, 31, 32, 33 and 34): copy each letter for letter into the file of words, and prove it by code against the spec's own text. The sentences the details leave to the owner come by the mail at the plan gate: leave their places open in the plan and DRAFT NONE OF THEM. Every other sentence or name a person would read is a draft, given in full in your plan. Add none after the plan without saying so in the report.
5. THE SERVICES, as STAGE_09D2.md and STAGE_05E2.md say for each: no call sent a second time, the address rule checked before any connection, a refused key or used-up credit ends what sends. In the first act a delete that is not proven ends everything that sends, and your message to the mailbox begins with that line for the owner.
6. THE TESTS OF EVERY OLDER STEP STAND UNTOUCHED, but for those that pin AssemblyAI as a choice of the app (ruling 28): the plan names each of them, one by one, and says what becomes of it. Never weaken or remove any other test to make the suite pass. The suite must be green on the three systems of GitHub's check with no secure store, no key and no internet.
7. THE BROWSER, as rule 6 of STAGE_06E.md: a profile that has first seen the pages served from the code of 0631413, kept; then the pages as you built them on the same address, loaded by an ordinary load; the look shows which scripts and styles ran. Never the owner's data folder, never a real consultation, never a real key in a browser.
8. A product or clinical choice the details leave open is not yours: stop and report it. The details name what is not built; build none of it (R31).
9. Each commit: one logical change, the suite green before it, the why in the message. Each commit message ends, after one empty line, with: Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>
10. Before each commit the private word check of STAGE_05C2.md, rule 12, on the staged files. It must print nothing.
11. Commit subjects begin Stage 9b. The report is LOGS/STAGE9B_REPORT.md, the log LOGS/stage9b-run.log, the plan LOGS/STAGE9B_PLAN.md. Long output goes to the log, never into chat.

THE FIRST ACT, BEFORE ANY COMMIT AND BEFORE THE PLAN
It changes no file of V2. The owner's pasting of the first block is his okay for exactly these commands. L is LOGS, K is KEY. Each command runs from V2, one at a time, each to its own step file LOGS/stage9b-step-NAME.out.
1. uv run openconsult-bench speech-selftest --choice speechmatics --data-folder L/stage9b-data --key-folder K
   L/stage9b-data is new and empty: make it.
2. uv run openconsult-bench speech-upload --gate --service speechmatics --key-folder K --out L/stage9b-gate
3. For NAME in s11, then s13, then sT2, one recording at a time, never two at once:
   uv run openconsult-bench speech-run --recordings L/stage9b-recordings --arm speechmatics --data-folder L/stage9b-data --out L/stage9b-run --recording NAME --key-folder K
   uv run openconsult-bench speech-upload --service speechmatics --recordings L/stage9b-recordings --recording NAME --key-folder K --out L/stage9b-run
   After each step that sends: the result is there and its failure is null; the settings the service echoes are those of the stored results of 10 Nov 2026 in LOGS/stage5e-run (model enhanced, domain medical, speaker labels, two speakers, no word list). If a value differs, or a step fails, send nothing more and go to step 6.
4. uv run openconsult-bench speech-upload --service speechmatics --key-folder K --held L/stage9b-run L/stage9b-gate --out L/stage9b-held-speechmatics.json
5. uv run openconsult-bench speech-score --out L/stage9b-run --recordings L/stage9b-recordings --scripts V2/engine-bench/cases --marks L/stage9b-cases/speech_marks.json --counting --write L/stage9b-tables
   The same again with --write L/stage9b-tables-again; then cmp on scores.json and report.md. Cowork proved on 15 Nov that this command takes the list and the marks as they are.
6. Write LOGS/STAGE9B_FIRST_ACT.md, private, twelve lines at most, counts only: your model; each step and how it ended; for each recording the lines of its live page and of its whole page, the seconds sent live and whole, and the seconds from the upload to the result; each delete and its proof; what the service still holds; the echoed settings beside those of 10 Nov; the two hard marks for each page, yes or no; anything not as this prompt says. You judge nothing more: Cowork reads the tables.
7. If every step ended well, go on to Part 1 without waiting. If not, write the first lines of that file to the mailbox and wait for a mail.

PART 1. TWO COMMITS, THEN THE PLAN, THEN THE MAILBOX
Commit 1. Subject: Stage 9b: the spec with rulings 25 to 35 of stage 9 and the details of the run
   V2_SPEC.md alone, as it stands on disk, checksum proven.
Commit 2. Subject: Stage 9b: the stage prompt
   Copy this file to V2/stage-prompts/STAGE_09B.md. Prove with cmp that it is identical.
Then write LOGS/STAGE9B_PLAN.md. Five pages at most. It holds, in this order:
1. WHETHER THE WHOLE FITS ONE SESSION. The owner ruled one run and named the risk (ruling 35). Say plainly what you judge, and the cut you would make if not. Then the order of the commits, half one and half two, and what stands by itself at the half.
2. THE SECURE STORE: the package, its version and its licence; the order of reading; what the screen does where no store answers; how the suite stands a made store and never touches a real one, on the three systems.
3. THE CONNECT SCREENS AND THE TEST OF A CONNECTION: each test's request in full, what it costs, what it proves and what it does not; when it runs; each reason of a failure and the name it has; the address of each service's page for a key, as you read it on the service's own page today.
4. THE CHOICE OF PATH: where the two settings live; how a consultation holds its path and its door to the end, and every later call for it; what Start asks and what it says for each thing that can be missing.
5. THE STATEMENT: how it is built; for each path the whole text as it would stand, every line with the ruling it is copied from; the places left open for the owner's sentences; the checksum and what asks for the tick again.
6. CLAUDE IN THE APP: what moves out of the bench, what stays, that nothing is written twice; the profile and the model for each job; the proof that the messages are equal on both paths; the real calls, each in one line.
7. SPEECHMATICS LIVE AND THE CLOUD MARK: what changes in the choice of speech; where the mark stands and how it is told without colour.
8. A LOST CONNECTION: the interval of a new try; what a session is in the record; how the question at Stop is asked for each session; how the stretch with no transcript is found and named.
9. THE RECORDING SENT AFTER STOP: the stage's place in Stop; the limit of time; each way it can fail and what the page then says; what is kept in the record.
10. THE FIRST RUN: the steps and what makes each done; the meter; what a folder that finished its first run before this step meets.
11. ASSEMBLYAI: what leaves the app, what the bench keeps, each test that moves.
12. THE TABLES OF VERSION 11.
13. EVERY SENTENCE OR NAME A PERSON WOULD READ OR HEAR THAT IS NEW, in full, as drafts; and the owner's, each with its place.
14. EVERY TEST you intend, each with the ruling or the rule it pins; every test of an older step that cannot stand untouched, named one by one with the reason.
15. WHAT YOU WILL SEE IN THE BROWSER, item by item.
16. The size targets of section 5 that this run presses on, with the figures as they stand.
17. Anything in the spec or in this prompt that is wrong, silent or in conflict: do not fix it yourself.
Then write six lines at most to LOGS/STAGE9B_TO_COWORK.md: your model; the first act in one line and where its file is; the two commits; where the plan is; your judgement of item 1; anything of item 17. Print Sent to Cowork. Wait for the mail, as THE MAILBOX says.

PART 2. THE BUILD
Item 1. The suite as it stands: the number of tests, the time, none skipped.
Item 2. Half one, in commits of one logical change each, in the order of the plan as approved. After the engine for Claude has moved, and before anything rests on it, its real calls of rule 1.
Item 3. THE HALF. The suite green. One line in HANDOVER that half one stands by itself. Write four lines to LOGS/stage9b-half.md: the commits so far, the suite's count, the real calls made and their cost. Do not wait: go on.
Item 4. Half two, in the same way, with its one real call.
Item 5. The browser, as rule 7 says, after the last of those commits: each thing the details list under Seen in a browser, and each line of Done when you see, for 9b, walked through as far as made services can show it. A fault found there is a commit of its own, and the report says so.
What a model writes is never asserted in a test.

PART 3. THE CHECKS AND THE LAST COMMIT
Part 5 of STAGE_06C.md, with these changes. In item 1 the start check is run only if nothing answers on port 8001; if the port is taken, the mailbox. In item 2 the prompt folders are compared with 0631413 and show no change at all. In item 3 every address outside this machine is named and set beside rule 1, with the count of calls to each. In item 4 the files of every older step and the files this prompt names as read only count among those that are not yours. In item 5: HANDOVER gains the run's entry and its entry for 6e is put right in the four places the details name; the README gains what the details ask, with the two changes of LOGS/stage9b-readme-changes.md byte for byte; the page Why this model holds LOGS/stage9b-why-this-model.md byte for byte; CLAUDE.md stays under 100 lines; .env.example is brought into step.

THE REPORT
LOGS/STAGE9B_REPORT.md. It is private. First, for the patient, in plain words: what a doctor is told before anything leaves the computer; what the doctor sees while a consultation runs in cloud mode; what happens when the internet is lost; what happens to a recording that is sent after Stop, and how the doctor knows it was deleted. Then, each under its own heading: the first act, as counts; the build, commit by commit; each real call with its cost; each thing seen in the browser, with what you saw, which scripts ran, and what you could not see; the statement for each path, in full, as the app builds it; every sentence or name that is new, in full; every test restated, moved or removed; what left the machine, address by address; what in LOGS may now be removed, without removing anything yourself. Then THE ROOM CHECK: the steps for the owner, short and in the order his hands do them, for the item Done when you see, for 9b: two sittings, one acted consultation each; the first step of each is that he stops the app and starts it again; where a step can be done at any row or any line, say so. Last: anything you flagged.

FINAL MESSAGE
To LOGS/STAGE9B_TO_COWORK.md, ten lines at most: the spec's checksum as given and committed; the first act in one line; half one and half two, each in one line with whether you saw it in the browser; the real calls and their cost; the suite's count; what left the machine, in one line; the number of commits and the last hash; anything you flagged. Do not push. Print Report sent to Cowork. Then go back to waiting for mail, as THE MAILBOX says.
