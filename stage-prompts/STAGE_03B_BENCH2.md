STAGE 3B of OpenConsult v2.0: the engine bench, run again on 7 Oct 2026

Cowork, 7 Oct 2026, morning. For Claude Code. A new session in /home/indy/Projects/OpenConsult2.
This runs on Fable 5.1 at high effort. Say in your first line which model you are. If you are not Fable 5.1, stop there.

WHAT THIS IS
From the patient's side: which engine brings the alarm and the assessment soonest, with the same clinical safety?
The bench of 6 Oct answered the safety part. Its seconds are tainted: the engines ran at different hours of the day,
a screensaver slowed the start, and Cowork's own look slowed part of one arm.
Today all three engines run again in one sitting, in three rounds, with nobody at the desk. About 8.5 hours.
The owner leaves for the day once the run has started. He is back at 18:00.
The spec is V2/V2_SPEC.md, section 15.8: rulings 17 to 23, and the details bullet named The bench of 7 Oct.
Read rulings 8, 10, 13, 14 and 16 to 23 and that bullet before anything else. Build what they say.
Where this prompt and the spec differ, the spec wins: stop and say so in three lines.
OpenConsult is a research and education prototype. Never real patients. Every case is acted or scripted.

TIME MATTERS THIS MORNING
The run must start by about 08:15, or it will not end before the owner is home.
So the plan is one page, and you reuse your own private scripts of 6 Oct. Copy them to new names and change as little as you can.
Do not improve anything. Do not look anything up on the web: nothing new is installed and no version changes.
If anything here does not match what you find, stop and say so in three lines. Do not improvise.

THE FOLDERS
V2    /home/indy/Projects/OpenConsult2            the repo, branch v2
LOGS  /home/indy/Work/openconsult-review/v2-logs  private; this prompt is here
ENG   /mnt/fastdata/openconsult-engine-bench      the engines and the model files, as you left them on 6 Oct
V1    /home/indy/Projects/consultation-ai         read only; the one command allowed is git rev-parse HEAD

WHAT STANDS
Every rule of LOGS/STAGE3B_PROMPT.md and of V2/CLAUDE.md stands: no push, no sudo, no service command, the Ollama service
and the owner's models untouched, one engine on the card at a time, long output to a file and never into chat.
No code in V2 changes today. No document of the repo is written. The one commit is the spec.
No word a model reads changes. The two prompt hashes of rule 10 of STAGE3B_PROMPT.md must be what the door sends.
Nothing is exported. LOGS/stage3b-public and V2/engine-bench are not touched. Nothing is published and nothing is pushed.
Nothing of 6 Oct is written over. Every new file in LOGS has a name that begins with stage3b-bench2, stage3b_bench2
or STAGE3B_BENCH2. The results go to LOGS/stage3b-bench2. The log is LOGS/stage3b-bench2.log, a new file.
Nothing is installed and nothing is downloaded. The engines are those in ENG, at the versions of 6 Oct.
No chain is run again to get a better figure. A chain that is complete is never run again and never written over.
A stopped run carries on from its step markers.

PART 1. CHECKS AND THE SPEC COMMIT
1. sha256 of V2/V2_SPEC.md must be
   6130c86a7c5adfd6b68a2b7505e49dfabe80924876247a505b8ff104cabdd3a3
   Branch v2, HEAD da5a992, and git status --porcelain shows one line only: V2_SPEC.md modified. If not, stop.
   Commit that file alone. Subject: Stage 3b: the spec for the bench of 7 Oct, rulings 17 to 23
   The suite green and the private word check printing nothing, the co-author line as in your commits of 6 Oct.
2. The machine is as it was on 6 Oct. Check each, read only, and write each into the log:
   Ollama 0.33.3; in the service and in the private Ollama's folder the model openconsult-bench-gemma4:26b-google-q4_0
   with digest 9813ae3a5cf9ef2c1f20472d76c3b012b7b0a7bab2285c2f825244331d1db89c;
   the owner's gemma4:26b-a4b-it-qat with digest 2dd70431afed94dd3688d790443768c1487ed086b57147ff083851116ae4c4e4;
   llama.cpp build b11429; Google's file with sha256 3eca3b8f6d7baf218a7dd6bba5fb59a56ee25fe2d567b6f5f589b4f697eca51d
   (the checksum you recorded on 6 Oct is enough if the size and the time of the file are unchanged);
   vLLM 0.31.0; the repack at revision 2096d38dad51a19b8e982b44241c47102a8bbb00;
   the bench code of V2 is the code of the published run: git diff 23198ab HEAD names V2_SPEC.md and nothing else;
   V1 HEAD b2e61d0705ec593cfde70638429e287e68c56f1c; every case in LOGS/stage3-cases against cases.json.
   If one differs, stop.
3. The desk: the card free and nothing loaded in Ollama; what is open on the desktop; whether stay-awake is on.

PART 2. THE PLAN, ONE PAGE, THEN STOP
Write LOGS/STAGE3B_BENCH2_PLAN.md. At most 80 lines. It holds only:
- the driver's order, turn by turn, with the exact bench command of each step and your estimate of its minutes;
- the five starts, each named with the start of 6 Oct it copies, and that nothing in them changed;
- the files you will make, and the files of 6 Oct you copy them from;
- how a failed step, the clock limit and the end are handled, as Part 4 says;
- anything that does not match this prompt or the spec, and anything you need from the owner.
Then say: Plan ready. Wait for the owner. He will type: Approved. Go.

PART 3. BEFORE THE FIRST ROUND
4. The five starts are those of 6 Oct, word for word. Use the start names of stage3b_engines.sh:
   the Ollama service as installed (calls one after another, the model loaded for it and unloaded after it);
   ollama-private (the together arm; ruling 13); llamacpp-1 (one after another); llamacpp-2 (together);
   vllm-compact (both ways; the start of the second vLLM arm of 6 Oct, 21:06:58, with the backend named as xgrammar
   and disable_any_whitespace true; ruling 22). vLLM runs on no other start today.
5. The proofs of 6 Oct, made again on each of the five starts, one engine on the card at a time: no thinking text,
   the reply fits its form, a reply asked for 5 tokens comes back cut, about 15,000 tokens in is answered,
   an oversize input is refused, and the tokens read are those of 6 Oct on the same calls.
   On vllm-compact also: its own log names backend xgrammar and disable_any_whitespace True, and outside a string the only
   blank space in a reply is one single space after a colon or a comma.
   Outputs: LOGS/stage3b-bench2-proofs-NAME.out. If a proof fails on a start, stop and say so. Do not go on without that engine.
6. Stay-awake must be on, so that no screensaver and no lock can start. If it is off, switch it on with Omarchy's own command,
   with the owner's leave for this run, and say so. Leave it on at the end: the owner switches it back at the desk.
7. Write into the log, with the time, BEFORE the first chain:
   rulings 17 to 23 in one line each; the rounds and the order of the engines; the chains of each round;
   Rule A as it now reads: a candidate meets every hard mark of 15.7 on its three chains at temperature 0, and none of them fails;
   Rule B as it now reads: faster means the typical pass is at least 0.50 s shorter than Ollama's in each of the three rounds,
   the typical pass of a round being the median of the 11 passes of consultation 495 in that round's chain at temperature 0;
   the four judgements of Rule B and the two extra comparisons of the details bullet;
   the steadiness line: if Ollama's own typical pass, calls one after another, differs between its three rounds by more
   than 0.25 s, no engine is called faster;
   the marks of 15.7 as numbers, unchanged, copied from item 6 of stage3b.log;
   and the state of the machine: what is open, stay-awake, the monitor.

PART 4. THE RUN
8. The sampler of the card and the load log run from the first turn to the last, into new files.
   The load log names the screensaver if it is ever among the busiest processes.
9. The driver, started with setsid nohup so that it does not depend on this session. Three rounds, nine turns:
   Round 1: Ollama, llama.cpp, vLLM.      Chains A1, then B1 B2 B3, then A1 sent together.
   Round 2: llama.cpp, vLLM, Ollama.      Chains A2, then B4 B5 B6, then A2 sent together.
   Round 3: vLLM, Ollama, llama.cpp.      Chains A3, then B7 B8 B9 B10, then A3 sent together.
   A turn is one engine in one round, all 16 cases, in this order:
   a. start the engine for calls one after another; its chain at temperature 0 (--chains A1, or A2, or A3);
   b. on the same start, its chains at 0.5 of this round;
   c. the start for two calls at once (for vLLM the same start); the check that two calls overlap; the same chain at 0 with --together;
   d. stop the engine, see it gone, see the card free.
   Each engine has two result folders for the whole day, so that each ends in the form of 6 Oct:
   stage3b-bench2/ollama-google-file and ollama-together, llamacpp-google-file and llamacpp-together,
   vllm-repack-compact and vllm-together-compact. A round adds its chains to them.
   The bench's own first call of a run, not measured, stays as it is.
   One line in the log for every step: the round, the engine, the chains, the start and the end with the time,
   the exit code, the card, stay-awake, and a NOTE if a screensaver is running.
   A step that fails ends that engine's turn: the driver stops that engine, sees the card free, writes a line that begins
   FAILED, and goes on with the next engine. If the card cannot be freed, the driver stops the whole run and says so.
   No turn starts after 16:45. What did not run is written as NOT RUN.
   At the end the driver itself stops every engine it started, unloads the bench model from the Ollama service,
   sees the card free, stops the sampler, and writes: THE BENCH OF 7 OCT has ended.
10. When round 1 has the result file of its first chain of 495, and no screensaver is running, tell the owner in one line:
    The bench has started. You can switch off the monitor now.
    After that, look at no result and run nothing on this machine until the driver has ended.
    Wait with one quiet background command that only sleeps and tests for the driver's end marker.
    If your session ends before then, the owner will start you again with this file and the words: go on from Part 5.

PART 5. AFTER THE RUN
11. Score once, with a private script in LOGS, from the result files and the call records. No code of V2 changes.
    The facts, for each engine and each of its two ways:
    - at temperature 0: each hard mark of 15.7 over the three chains, the chains that failed, candidate or not (Rule A);
    - the typical pass of each round, and beside it the median over all 16 cases of that round's chain at 0;
    - Rule B, in each round and as a verdict: llama.cpp and vLLM one after another against Ollama one after another;
      llama.cpp and vLLM together against Ollama together; and every together arm, Ollama's included, against Ollama one after another;
    - the steadiness of each engine: the largest difference between its three rounds, and whether Ollama's is within 0.25 s;
    - the stress test at 0.5, apart: every mark over the ten chains, the chains that failed, named;
    - every mark over all 13 chains, as on 6 Oct, for comparison, with the slowest pass;
    - replies whose reasoning is cut mid-sentence, by temperature; empty lists and kept lists;
    - passes that say time critical and name no action, by temperature;
    - for each case, the pass at which the alarm first shows, by temperature;
    - the tokens written and the time for each token written, for each round;
    - the card: lowest, typical and highest; the time from start to ready of each start;
    - the machine, minute by minute: the screensaver, the busiest processes, any slow minute.
12. Write LOGS/STAGE3B_BENCH2_REPORT.md. Short, for the patient first: who is a candidate, who is faster by Rule B,
    whether the day was steady, then the figures. Say plainly what did not run, and anything you flag.
    Say that vLLM's answers are shorter because of its switch, and give the time for each token beside the wait (ruling 22).
    It makes no case: the figures do the work.
13. Do not export. Write no document of the repo. git status --porcelain is empty. No engine running, the card free,
    nothing loaded in Ollama, stay-awake left on.
    Your last line: Tell Cowork: Bench of 7 Oct done. Nothing is published.
