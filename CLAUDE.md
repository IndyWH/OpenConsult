# CLAUDE.md

Orientation for Claude Code working on OpenConsult v2. Read V2_SPEC.md next:
it is the one document for v2.0. Then the part of V1_LESSONS.md your stage prompt names.

## What this is

OpenConsult transcribes an acted doctor and patient consultation live, offers
clinical decision support while it runs, and drafts a cited note that the
doctor edits and approves. v2.0 is a rewrite, built on this branch.
v1 is on the main branch. It is not touched from here.

**It is a research and education prototype. It is not a medical device. It
must never be used with real patients or real patient data. Every consultation
is acted or scripted.** That belongs in anything you write here.

## The team, and whose decision it is

- The owner, a GP. He makes every product and clinical decision.
- Cowork, an orchestration assistant. It designs, writes the spec and the
  stage prompts, and checks your work.
- You. You build.

If a choice is a product or clinical judgement, stop and report it. Do not
decide it. Decisions already made are in V2_SPEC.md: section 16, and the
section for each stage. Implement them. Do not reopen them.

Think from the patient's side. In teaching mode, from the learner's side.

## How a stage runs

1. One stage or sub-stage in one session. Its prompt is a file in stage-prompts/.
2. The build model is Fable 5.2 at high effort, by the owner's ruling of 10 Nov 2026.
   If you are any other model, say so and stop.
3. Your first commit is V2_SPEC.md as the brainstorm left it, if it has changed.
4. Write your plan. List every test you intend, with the rule number or the
   incident it pins. Then stop and wait for the owner to type: Approved. Go.
5. Build. The suite is green before each commit. One logical change in each
   commit, the why in its message, and the co-author line your stage prompt gives at its end.
6. Add a HANDOVER.md entry. Say which document your work has made untrue.
7. Never push, no sudo, never the Ollama service. A run may stop and start vLLM with the owner's engine script when its approved plan says so (15.13, ruling 1), each written to its log with the card's reading before and after, and leaves the engine as it found it.

## Hard rules

- The rules in section 4 of the spec (R1 to R33). Each is pinned by one test
  or one check, named with its rule number.
- The size targets in section 5. If a target cannot be met, report it and say
  why. Do not squeeze code to fit a number.
- Every test names what it pins. Never weaken or delete a test to make the
  suite pass. Tests never read the user's settings and never write outside a
  temporary folder. What a model says is measured in a bench, not asserted
  in a test.
- Nothing is built switched off (R31).
- The v1 folder, /home/indy/Projects/consultation-ai, is a read-only
  reference. Change nothing there, and run no git command there that writes.
- Nothing committed names a family member, a colleague, a home or a place.
  Never the real tailnet host name or address (R23). No secret in any file.
  The example settings hold no real value. Before a commit that adds or
  changes a document, run the private word check your stage prompt gives.
- The help pages are the owner's words (R22). Flag a page that has become
  untrue. Never edit it.
- No instruction names a guideline publisher (R21). No prompt names a
  country (R13).
- Long output goes to a log file, never into chat.

## Where the writing goes

- V2_SPEC.md is the one spec. Only Cowork edits it, on the owner's ruling.
  You commit it. You do not change it. If it is wrong or silent, report that.
- V1_LESSONS.md is what v1 taught. Read the sections your stage prompt names.
- HANDOVER.md holds decisions and measurements, newest first, under 500
  lines. Older entries move to archive/HANDOVER_ARCHIVE.md, which you do not
  read unless asked.
- A comment says why, in one or two lines. History goes in HANDOVER.md,
  never in the code.
- The only documents at the repo root are README.md, CLAUDE.md, V2_SPEC.md,
  V1_LESSONS.md, HANDOVER.md, LICENSE and NOTICE. Add no other document
  there. Code, tests and their set-up files are not documents.

## Running it

    uv sync                                            # once, from the lock file
    uv run openconsult [--data-folder DIR --port 8765] [--no-browser]   # start, on 8001; a development run; without a browser. At start, on Linux with a suitable card, vLLM at 127.0.0.1:8172 is tried first, then Ollama (the order is the setting). Recordings go to DIR/recordings, written once
    uv run openconsult reset-password | install-speech [--choice NAME] | self-test [--choice NAME] | install-guidelines  [--data-folder DIR]   # a choice's environment and models into the data folder; the clip through the door, stored. NAME: whisperx_pyannote (the default), nemotron, speechmatics (assemblyai is the bench's alone since run 9b). install-guidelines: the embedding worker's environment from its lock file and EmbeddingGemma 2 fetched once with no token (with --reranker the reranker too, for the bench alone), skipped when the weights are there and match
    uv run pytest; uv run python .github/scripts/start_check.py   # the suite; then start, answer, stop
    uv run openconsult-bench ...   # every bench command, with its flags and cautions, is in the bench-commands skill (.claude/skills/bench-commands/SKILL.md); load it before any bench run

The benches write only under --out or --write, never to the app's data, the repo, a workers' data folder or where recordings are kept (guideline-load alone writes into the bench data folder it is given); a recording of the doctor's voice alone (voice_only) is learnt from and never replayed. The engine bench's published form is engine-bench; other cases, recordings and results stay in the log folder. install-speech, self-test, install-guidelines and shared-install write only in the data folder they are given. A cloud choice needs no install: the app reads its key from the system's secure store first (the connect screen puts it there), then the environment, then .env in the data folder (see .env.example; a developer's way), and its self-test sends the clip to the service's EU address. The bench reads a key from the key folder alone. The suite and the start check reach no real store: the package's own switch, PYTHON_KEYRING_BACKEND, goes to every child.

Data folder: Linux $XDG_DATA_HOME/openconsult or ~/.local/share/openconsult; macOS ~/Library/Application Support/OpenConsult; Windows %LOCALAPPDATA%\OpenConsult.
