# CLAUDE.md

Orientation for Claude Code working on OpenConsult v2.
Read V2_SPEC.md next. It is the one document for v2.0.
Then read the part of V1_LESSONS.md that your stage prompt names.

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
2. The build model is Fable 5.1 at high effort, or Fable 5.5 when it is out.
   If you are any other model, say so and stop.
3. Your first commit is V2_SPEC.md as the brainstorm left it, if it has changed.
4. Write your plan. List every test you intend, with the rule number or the
   incident it pins. Then stop and wait for the owner to type: Approved. Go.
5. Build. The suite is green before each commit. One logical change in each
   commit. The why goes in the commit message.
   Each commit ends with the co-author line your stage prompt gives.
6. Add a HANDOVER.md entry. Say which document your work has made untrue.
7. Never push. Never start, stop or restart a service. No sudo. The owner
   does these himself.

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
    uv run openconsult [--data-folder DIR --port 8765] [--no-browser]   # start, on 8001; a development run; without a browser
    uv run openconsult reset-password [--data-folder DIR]
    uv run openconsult install-speech [--data-folder DIR]   # the speech environment and its models, into the data folder
    uv run openconsult self-test [--data-folder DIR]        # the clip through the speech door; the result is stored
    uv run pytest                                      # the suite
    uv run python .github/scripts/start_check.py       # start, answer, stop
    uv run openconsult-bench wordcheck --cases DIR --out DIR --v1-calls FILE...  # no model
    uv run openconsult-bench run --cases DIR --out DIR --digest ID [--kind ollama|llamacpp|vllm --engine URL --model NAME] [--together] [--chains A1 ...]
    uv run openconsult-bench score --out DIR | --replies FILE     # the marks of one arm
    uv run openconsult-bench figures --public engine-bench        # the figures of the public report; no engine

The bench writes only under --out, never to the app's data. Its published form is engine-bench; other cases and results stay in the log folder. install-speech and self-test write only in the data folder they are given.

Data folder: Linux $XDG_DATA_HOME/openconsult or ~/.local/share/openconsult; macOS ~/Library/Application Support/OpenConsult; Windows %LOCALAPPDATA%\OpenConsult.
