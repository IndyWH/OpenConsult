# HANDOVER

The record for OpenConsult v2: decisions and measurements, newest first.
It stays under 500 lines. Older entries move to HANDOVER_ARCHIVE.md.
The spec is V2_SPEC.md. The record for v1 is the HANDOVER.md on the main branch.

## 2026-10-13. Stage 3c: the engine setting

Built and run on 13 Oct 2026. The plan was reviewed by Cowork the same
day (three changes and five answers); all are in. The proof ran on the
one machine with the v1 service off and Funnel off. The report is
STAGE3C_REPORT.md in the private log folder.

The rulings it builds, one line each (spec 15.8):
- 30: on Linux with a suitable card the engine is vLLM first, Ollama the
  fallback everywhere; vLLM is asked on Linux only, and its room is set
  where it is started (1,400,000,000 bytes of cache for 16,384 tokens).
- 31: the two calls of a pass are sent together on every engine, as the
  pass's own way; the bench keeps one after another for its arms.
- 32: EmbeddingGemma 2 sits on the card when the first sum fits, else on
  the processor; nothing is loaded for it yet.
- 33: Nemotron is the speech choice on a shared card; the WhisperX choice
  is offered only when the second sum fits, else shown as not available.
- 35: all of it in one session, before 5e; the engine bench not run again.
- 36: three things read once at start, never during a consultation; one
  plain sentence for each decision on This machine, the figures in the
  audit log.
- 37: vLLM asked once with the short wait, then Ollama; the choice held
  for the run; a failed call fails and says so with no switch; both
  missing means Start is not offered (the element records it) and the
  app still runs; the app starts no engine.
- 38: each decision is a named element with a state, a reason and its
  figures; nothing is drawn.
- 39: Ollama stays at 0.33.3; nothing of the service changed.
- 40: the suite needs no card, no engine and no model; made-up ones stand in.

What was built (the app without the bench 7,062 lines, from 6,491; the
tests 10,004, from 9,537):
- llm/chat_engine.py and llm/vllm.py, moved from the bench: the vLLM
  engine behind the joint with the request of 7 Oct; the compact answer
  form is set where vLLM is started, so nothing travels in a request.
  The shared engine refuses a call only when the server's context is
  smaller than the call's; the bench's run command refuses an arm unless
  the server runs at exactly 16,384 (the plan review).
- llm/profile.py names the model for each engine in its one place:
  Ollama's own tag, the default, and the repack of ruling 7 on vLLM.
- llm/choose.py: the order of trying, the fit rule (answers, holds the
  model, context at least 16,384), and the stand-in engine when none is fit.
- settings/store.py: ollama_address and vllm_address (127.0.0.1:8172),
  fixed at start; no setting to pick an engine by hand.
- settings/decisions.py and settings/room.py: the three elements, the
  constants with their 5d sources (the language model 18,316 MiB on vLLM
  and 16,568 on the service, Nemotron 3,384, the WhisperX choice 2,452
  live and 9,464 at Stop, EmbeddingGemma 2 1,010, a margin of 1,000),
  the two sums, the programs on the card read with nvidia-smi, the app's
  own engines told apart by name (vllm, ollama, as 5d's sampler recorded
  them), one audit line for each element with the card's total and free.
- consult/cds_pass.py: run_pass sends the two calls at the same moment,
  the alarm first; bench/one_after_another.py keeps the other way.
- web: the language model row, the guideline search row and the speech
  choice row, from the held decisions, on a suitable card only (the
  Ollama lines of 15.7 became the one line); no engine asked at a view.
- bench/cli.py: run and repeat take --data-folder, refused as a result
  folder (R18), and the refusal exits 6.
- words.py: 20 new sentences and 2 changed (the language model row, the home page), drafts for the owner.

Decided in the plan review (Cowork, 13 Oct), as decisions of this stage:
the two context rules kept apart (at least for the app, exactly for an
arm); on a Mac, a small card or no card the three rows are not shown and
the elements are held in state; the audit log's lines at start are the
decisions, and three tests compare against them; the alarm is submitted
first and both calls are in flight at once; the test user's password of
the proof is a throwaway kept in the log folder only.

Measurements, 13 Oct 2026, RTX 4090, v1 off:
- 556 tests, 19.6 to 19.8 s, none skipped; green under Cowork's Windows
  tool (20.95 s). No file over 600 lines (the largest bench/shared/
  judge.py 527, unchanged), no function over 80 (the longest 64). CLAUDE.md
  99 lines. The word check of stage 3: 1,898 of 1,898 for each call
  (143 + 182 + 598 + 975), mismatches 0; the 121 calls a call of task 5's
  own script run also matched, 4,038 of 4,038 in all.
- A fresh Python with the base app alone (18 packages, no torch) starts,
  answers and stops; the GitHub start step as it is passed.
- On vLLM (started by the script copy with its room; 23.3 s to answer;
  18,212 MiB on the card, 18,912 in all): This machine said the language
  model runs on vLLM 0.31.0 with Gemma 4 QAT present, the guideline
  search on the graphics card, and the WhisperX choice not available
  because the card has no room for its pass at Stop. The sums on this machine:
  70 + 18,316 + 3,384 + 1,010 + 1,000 = 23,780 of 24,564 (784 to spare);
  70 + 18,316 + 1,010 + 9,464 + 1,000 = 29,860 (5,296 over).
- The three chains of 495 at temperature 0 through the app's pass,
  together, on vLLM: 33 passes, no call failed, H1 and H2 met in every
  chain (both first at pass 2); the typical pass 2.78 s (chains 2.79,
  2.81, 2.75), the slowest 3.08 s; beside 5d's 2.73 and the app's 5.11
  before 3c. The record carries vllm 0.31.0, the repack's name and the
  revision 2096d38d.
- With vLLM stopped: This machine said the language model runs on Ollama
  0.33.3, because vLLM did not answer at its address, Gemma 4 QAT
  present; the same two room sentences (sums 22,040 and 28,120). One
  chain of 495 on the service, together: 11 passes, no call failed, H1
  at pass 2 and H2 at pass 3; the typical pass 4.99 s, the slowest 5.34:
  the service queues the two calls, so nothing is gained there until it
  is set for two at once (OLLAMA_NUM_PARALLEL), the install advice of
  stage 15.
- The run command refused a result folder inside the repo and inside
  the test data folder, exit 6, nothing written.
- Nothing left the machine: vLLM ran with its usage reports and its reach
  to the hub off; no key and no token was read; the Ollama service is
  as it was, model for model and digest for digest; no model file or
  engine file in the engine folder changed. The private word check
  printed nothing before every commit.

Made untrue by this stage: CLAUDE.md's running lines (the engine order,
the room check, --data-folder on run), fixed in this commit; the
README's line and the home page's sentence, fixed in this commit; the
Ollama lines of 15.7 and the settings store's line about stage 3b, which
3c replaced as the details say. The 5d entry's one wrong sentence is
corrected above (2.77 to 3.29 s alone; 0.89 s on vLLM together with the
first EmbeddingGemma on the processor; at most 0.07 s between halves),
and the same in the 5d report. The two 5c entries moved to the archive.

Departures from the plan: the engine sentences went into words.py with
commit 3 and the room sentences with commit 5, not in one commit; the
language model's row on This machine came with commit 3, the two room
rows with commit 6.

For stage 15: the app does not start vLLM, so until the installer the
owner starts it by hand with the block in the report; on the Ollama
service as installed the two calls queue, so the gain of ruling 31 on
Ollama needs the service set for two calls at once; a vLLM whose process
name on the card held neither "vllm" nor "ollama" would be counted as
another program and as its own need, and the sums would put the
guideline search on the processor. For 5e and stage 6: the WhisperX
decision is parts.decisions.whisperx_choice; Start is offered only when
parts.decisions.start_offered. For stage 8: the guideline search's place
is parts.decisions.guideline_search. For stage 9: the three elements are
the data of the control panel of ruling 38.

Next: the owner's check at port 8001 (the steps are in the report), then
push; the GitHub check must be green on all three systems. Then Cowork
checks the report from the raw files.

## 2026-10-13. Stage 5d: the three models together on one graphics card

Built and run on 13 Oct 2026. The plan was reviewed by Cowork the same day
(five changes); all are in. A report only: nothing of the app changed, no
engine setting was built (R31), and the owner has no check of his own to
run for 5d. The report is STAGE5D_REPORT.md in the private log folder.

The rulings it answers, one line each:
- 15.8 ruling 29: the engine is chosen only after all three models have
  been tested together on the card; this is that test.
- 15.9 ruling 23: a setup works when it meets four lines (all on the card
  and nothing moved; no call fails and 495's hard marks hold; the typical
  pass less than 0.5 s longer than alone; the live transcript keeps up,
  less than 1.0 s more wait); not working names the first line missed.
- 15.9 ruling 24: EmbeddingGemma on the processor is a full arm, on both
  engines; a setup that fails with it on the card points to its twin.
- 15.9 ruling 25: both EmbeddingGemma models are tested; version 2 runs as
  a worker of the bench in an environment of its own, from a lock file.

What was built (openconsult/bench/shared, 1,783 lines; 1,289 lines of tests):
the 11 lists of names as a file, hashed and marked -text; the two ways to
an embedding (the service, with keep_alive and num_gpu 0 for the
processor; the worker of EmbeddingGemma 2 over the speech frames); the
searches every 5 s and the side reading of 250 public pieces; the watch of
Ollama's list, the engine's health and the card's programs; three switches
of the speech replay (the started file, the moment Stop was asked, a pause
before Stop); the judge of the four lines and the tables, the same bytes
twice; five commands, each refusing the repo, a data folder and the
recordings. The worker's environment is 63 packages at the versions in
its lock; pillow and torchvision are in it because the model's processor
imports them even text-only.

Measured, on the one machine, 32 setups between two sets of base lines,
then the way round on each engine (every figure of the card in MiB):
- Every setup with Nemotron works, 16 of 16, on Ollama and on vLLM, with
  either embedding model on the card or on the processor. Every setup
  with the WhisperX choice is not working at line one, 16 of 16: it runs
  live beside the other two (2,306 to 2,452 on the card) and runs out of
  memory at Stop, when its Stop models load (its pass at Stop reached
  9,464 with the language model off).
- The way round at Stop works on both engines: the language model is taken
  off the card when Stop is asked and put back after it. Ollama: unloaded
  in under a second, Stop 8.06 s, the chain after Stop 5.07 s typical.
  vLLM: the engine stopped in 1.0 s, Stop 8.08 s, the engine back in 23 s.
  Both met all four lines. Kept apart in the tables, never counted.
- Sharing the card costs, typical pass alone against shared with
  Nemotron: Ollama one after another 5.11 against 4.80 to 4.83; the
  private Ollama 3.76 against 3.84 to 3.93; vLLM one after another 3.45
  against 3.46 to 3.54; vLLM together 2.73 against 2.82 to 2.84. With the
  WhisperX choice live the cost is up to 0.28 s. No setup came within 0.2 s
  of the half-second line.
- The live transcript kept up everywhere: Nemotron's typical wait 2.23 to
  2.25 s against 2.18 to 2.20 alone; the WhisperX choice 3.29 to 4.03
  against 2.77 to 3.29 alone (the largest difference 0.89 s, on vLLM
  together with the first EmbeddingGemma on the processor), and the
  growth between halves never more than 0.07 s over alone.
- The base lines of the four ways were 0.00, 0.01, 0.00 and 0.09 s apart,
  all within the steadiness rule of 0.25 s. 1,132 searches, none late,
  none failed. No model was ever split or evicted. No call failed; the
  hard marks held in every chain.
- vLLM's room: --kv-cache-memory-bytes 1,400,000,000 gives a cache of
  16,531 tokens at a context of 16,384 (1.01x), and the engine takes
  18,212 of the card at start. A call of 15,002 tokens came back; 17,500
  and 78,000 were refused with the engine's own message; the two longest
  calls of 495 sent at once both came back. The largest pass of this run
  read and wrote 2,812 tokens; the public bench's largest, 4,104.
- The card at its fullest: 23,251 of 24,564 (vLLM one after another, the
  first EmbeddingGemma on the card, as Nemotron starts). The language model holds
  16,526 to 16,568 in the service, 17,246 to 17,288 in the private Ollama,
  18,212 to 18,316 in vLLM. Nemotron 3,172 to 3,384.
- EmbeddingGemma on the processor frees 1,083 (the first) or 1,010
  (version 2) of the card. A search of one list alone: the first 0.102 s
  on the card, 0.140 on the processor; version 2 0.064 and 0.105. In a
  setup, 0.105 to 0.159 on the card and 0.113 to 0.250 on the processor.
  250 pieces into vectors: the first 2.98 s on the card and 16.35 on the
  processor; version 2 0.36 and 16.54.
- The judge was wrong once and was fixed from the stored results: the
  worker of EmbeddingGemma 2 lives only while its searches run, which end
  with the chains, and the judge had read its planned exit as a model
  moved. The driver was wrong once too: its vLLM restart emptied the
  service two seconds after Stop, which cost the first try of vLLM's way
  round its first line; that step alone was run again with the driver
  fixed, and the first try is kept beside it. Both are in the report.
- Nothing left the machine: the workers' connection records hold only
  the bench's own calls to the service on this machine. No key and no
  token was read; the one fetch ran with no token. The Ollama service is
  as it was, model for model and digest for digest.

Made untrue: the sum of 13 Oct in ruling 24, that the three models on
vLLM are a few hundred MiB over the card, is a sum and not a measurement;
measured, they fit with Nemotron and either embedding model on the card,
1,313 to spare at the fullest. CLAUDE.md's running lines were shortened
to keep the file under 100 lines: the three app commands are one line,
speech-voice and speech-calls share a line, and the optional switches of
speech-voice, speech-drugs, speech-calls and speech-score are not shown
(their help pages show them). README.md's "so far" names the second bench.

Departures from the plan: the tidy-up of reads names utf-8 in five reads,
not four; the plan's commits 9 and 10 (the tables; the commands and the
sentences) became one, because the tables are what the judge command
writes; the sampler's two files and the load log are shared with the
proofs of Part 4, so their first lines are from before the run. The
suite: 521 tests in 19 to 21 s, none skipped, green under Cowork's
Windows tool. No size target was missed.

For the session on the engine choice: every Nemotron setup works on both
engines, vLLM together is the fastest way (2.73 s alone, 2.82 shared) and
Ollama one after another the slowest (5.11); the WhisperX choice needs
the way round at Stop on either engine, about 8 s with the language model
off and, on vLLM, 23 s more for the engine to come back, or a lighter
Stop. For the stage that builds the guideline search: the worker of
EmbeddingGemma 2 is cheaper on the card (1,010 against 1,083) and faster
(0.064 against 0.102 s a search; 0.36 against 2.98 s for 250 pieces); on
the processor both take about 16 s for 250 pieces, so an index is built
on the card. For the stage that installs: the search's form and the
passage's form are in bench/shared/searches.py, and a vector has 768
numbers in both models.
