OpenConsult v2.0, run 9a2: the gate call to DeepInfra, then the bench of its Gemma 4 26B on every bench the local model has run, report only

WHAT THIS IS
Run 9a (commits 234ee26 and af831c9, not pushed) built a cloud kind for Ollama cloud and stopped at its first call: that service does not hold a reply to the form the request carries, so the door refused the reply (R30). The owner ruled the same day (15.13, ruling 11): another host of Gemma 4, DeepInfra, replaces it if ONE GATE CALL passes; otherwise there is no cloud Gemma in v2.0 and Claude is next. Its pages disagree on whether it holds a reply to a JSON form, so nothing is planned on the page's word. This run: first the gate call; only if it passes, a short plan, the owner's approval, the kind for this host, Ollama cloud's kind taken out, the one-case trial, and the four benches of ruling 8. What it is for: a doctor on a machine with no suitable card needs a cloud model that does every job and keeps to the form on every call. Nothing is offered on any page (R31). No word a model reads changes. Done when the owner sees: the gate's result; and, if it passed, the bench report checked by Cowork, and has ruled on it.
The spec is V2_SPEC.md. Read 15.13 ruling 11 and the details headed for run 9a2, then the details headed for run 9a. Then, in this repo, stage-prompts/STAGE_09A.md: EVERY RULE AND FOLDER OF THAT PROMPT STANDS IN THIS RUN except where this prompt changes it. Then, in LOGS, STAGE9A_PLAN.md (approved), STAGE9A_PLAN_REVIEW.md (its five points stand), STAGE9A_TRIAL.md and STAGE9A_REPORT.md. Where this prompt and the spec differ, the spec wins: stop and report.
OpenConsult is a research and education prototype. Never real patients. Every consultation is acted.

MODEL
This runs on Fable 5.1 at high effort. Say in your first line which model you are. If you are not Fable 5.1, stop there.

WHAT CHANGES FROM STAGE_09A.md
1. Names. Every file and folder you make in LOGS begins stage9a2- or STAGE9A2_. The files and folders of 9a in LOGS (stage9a- and STAGE9A_) are read only; you may run the scripts 9a left there from copies under a stage9a2- name. The two copied data folders, stage9a-data-letters and stage9a-data-guideline, you may use as they are; they hold nothing of a run.
2. The spec. Check it with sha256sum before anything else. It must be:
   858a68153f9974a9426ca1acd9ea48ce1c5c843447dc11ca13f83b94b062e6a8  V2_SPEC.md
   HEAD holds 3aab9a83; the disk holds ruling 11 of 15.13, the details for run 9a2 and four small dated changes in 10.1, 10.3 and the row of stage 9 in 15.4. The branch is v2 and HEAD is af831c9. git status --porcelain must print only V2_SPEC.md as modified. Otherwise stop and report.
3. The host. What may reach outside this machine: uv to the package index; and the gate, the trial and the bench to the host's own API, https://api.deepinfra.com, and to no other address. No web page of the host or of anyone is read. Nothing is sent to ollama.com in this run.
4. The key. In the KEY folder's file .env under the name DEEPINFRA_API_KEY, put there by the owner's own hand before he gave you this prompt. Every rule of the KEY folder stands: you never open, print, copy or list that file; the key is read by openconsult/settings/keys.py inside the process and is never in a shell variable, a command line, a log, a stored request, a result, a report or a commit. If the name is not found, stop and say so, naming the name and never a value.
5. The model. google/gemma-4-26B-A4B-it, as the host's own list of models names it on the day; read the name from that list, never guess it. It is the local model's size at another precision than the local build: say so in the plan and beside every comparison in the report.
6. The kind. The app's chat engine, the one the vLLM engine is, with the Authorization header and the host's address; the bench's alone (R31), as rule 6 of STAGE_09A.md says. The address and the path are the ones the host's API answers at. On 6 Nov 2026 its reference gave POST https://api.deepinfra.com/v1/chat/completions with a Bearer key; an older form of the same API sits under /v1/openai. The gate finds which answers; write down what you find.
7. The local line. Set the cloud's figures beside the local runs on vLLM, whose request is the same shape (the prompts bench of 15 Oct for stage 3; 7b, 8a's fourth bench and 8b as the plan of 9a names them). The proof of rule 4 compares messages with those runs' stored requests.

PART 0. THE GATE CALL, BEFORE ANY PLAN AND BEFORE ANY CODE IS COMMITTED
Two commits first, as always:
Commit 1. Subject: Run 9a2: the spec with ruling 11 of the stage 9 brainstorm
   V2_SPEC.md alone, as it stands on disk, checksum proven.
Commit 2. Subject: Run 9a2: the run prompt
   Copy this file to V2/stage-prompts/STAGE_09A2.md. Prove with cmp that it is identical.
Then the gate. Write a script in LOGS, stage9a2-gate.py, run from V2 with uv run, that:
1. Takes the stored local request of the first call of the stage 3 bench on vLLM (the alarm, case 01_chest_pain_en, the first point, chain A1, in LOGS/prompts-bench), and builds for the same Call the request the app's chat engine builds (ChatEngine.build_request), with the model's name changed to the host's. Prove by code that the messages and the form are equal, character for character, to the stored local request's. Print counts and booleans, never a word of them.
2. Reads the key through keys.py from the KEY folder, in the process.
3. Asks the host's list of models once, which sends nothing of ours, and finds the model's name in it.
4. Sends the request and stores the request, the reply and the status under LOGS/stage9a2-gate, the key in none of them.
5. Judges the reply by the app's own check of the form for that job, the check the door runs, with nothing added and nothing loosened: PASS when the content is the JSON the form describes and nothing else, and the reply holds no thinking.
6. The tries, each ONE call, in this order, stopping at the first that passes: (a) the request as the chat engine sends it; (b) the same with the form marked strict as the host's reference gives it; (c) as (b) with the host's own switch for thinking set to none; (d) as (a) with that switch alone. Only fields of the engine differ between tries. No word of the messages or of the form changes in any try. Four calls at most.
Write LOGS/STAGE9A2_GATE.md: the address and path that answered; the model's name and what the host gives to identify its build; for each try made, the engine fields that differed, the status, the milliseconds, the tokens read and written, whether the content was the form's JSON, whether thinking was present, and the app's verdict; which try passed, or that none did; the tokens read beside the local count for the same call (723 on vLLM); the cost at 0.07 dollars a million tokens read and 0.34 written; that the key is in no stored file (count the words Authorization and Bearer).
IF NO TRY PASSES: stop. Build nothing. Make one commit for the documents (a HANDOVER entry: the gate's figures, that this host does not hold the form either, that Ollama cloud's kind still stands in the repo and its removal waits for the next run). Final message, then this line: Tell Cowork: Run 9a2 gate failed. Do not push yet.
IF A TRY PASSES: go on to PART 1.

PART 1. THE PLAN, THEN STOP
Write LOGS/STAGE9A2_PLAN.md. It is short: only what differs from STAGE9A_PLAN.md, which stands for everything else with the review's five points. It holds:
1. The gate's result in three lines, and the engine fields of the try that passed: those fields are what the kind sends on every call.
2. The kind: its module beside the bench, a subclass of the chat engine; the address rule; the key; the stop after a refused key or used-up credit, as 9a built it; what it records for R20; how thinking off is proven per reply.
3. What is removed of Ollama cloud's kind (15.13, ruling 11): the module, its name among the kinds, its line in the example settings file, the change it needed in the local Ollama engine; which tests move to the new kind and which go, each with what it pinned; that nothing is left that nothing uses.
4. The four bench commands with the kind, the model, the key folder and the --out folders changed, and nothing else; the marks as numbers, unchanged from the plan of 9a; the local vLLM results each is set beside.
5. The one-case trial and its three conditions (no failed call; the whole run under 10 dollars; thinking off in every reply), and the seed test. The host says determinism is not guaranteed; the seed test measures it.
6. Your estimate of the dollars and the hours.
7. The commits and the tests, each test with what it pins.
Then stop. Wait for the owner. He will type: Approved. Go.
He may first tell you to read a review file in LOGS. If so, read it and follow it.

PART 2. BUILD
As PART 3 of STAGE_09A.md, with the kind of this host: the kind and the removal with their tests (one commit, or two if the removal is its own logical change); the trial and LOGS/STAGE9A2_TRIAL.md; then, if its three conditions hold, the four benches in order (stage 3, 7b, 8a, 8b), each scored and record-checked before the next, all output to LOGS/stage9a2-run.log; the seed test; the proof of rule 4 on the stored records (the review's point 2); your judgement under ruling 8; the report; one commit for the documents (CLAUDE.md's bench line names the new kind and no longer the old; HANDOVER gains the entry; both under their limits). The run is unattended once approved: start the benches in the background and wait.

THE REPORT
LOGS/STAGE9A2_REPORT.md, as STAGE_09A.md's part THE REPORT says, led by what matters most for a patient, with the gate's result first among the figures, the cost of a 15-minute consultation beside the estimate of 3 to 5 cents (15.13, ruling 11), and the line on the model's precision beside every comparison with the local model. There is no room run.

FINAL MESSAGE
Eight lines at most: the spec's checksum as given and committed; the gate, which try passed; the model name; the four benches, each passed or missed, with the mark missed; what the whole run cost and what a 15-minute consultation would cost; the typical seconds of a pass beside the local figure; the number of commits, the last hash and the suite's count; then this line for the owner: Tell Cowork: Run 9a2 built, passed (or missed). Do not push yet.
