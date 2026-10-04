STAGE 1 of OpenConsult v2.0: open the v2 branch

WHAT THIS IS
OpenConsult v2.0 is a rewrite. It is built on a new branch called v2, in its own folder.
Stage 1 makes that folder and commits nine files. No code. No tests. Nothing runs yet.
The spec is V2_SPEC.md. Stage 1 is section 15.5 of it. Sections 5.3, 14 and 15 also bear on it.
OpenConsult is a research and education prototype. Never real patients.

MODEL
This stage runs on Fable 5.1 at high effort.
Say in your first line which model you are. If you are not Fable 5.1, stop there.

THE FOLDERS
REVIEW  /home/indy/Work/openconsult-review
        Read V2_SPEC.md and V1_LESSONS.md here. Write only inside REVIEW/v2-logs.
V1      /home/indy/Projects/consultation-ai
        Read only. Change nothing. You may read files there and copy LICENSE from it.
        The only git commands allowed there are the three named below.
V2      /home/indy/Projects/OpenConsult2
        The new folder. It is empty. All commits are made here.

BEFORE YOU START
1. Read REVIEW/V2_SPEC.md sections 5.3, 14, 15 and 15.5.
   Read REVIEW/V1_LESSONS.md sections 10.6 and 11.3.
2. Check the two files with sha256sum. They must be:
   516fff8e644eaa7a3d1c470bb7fd0cb3226ae331973d0981c1f4bcd00e80aeec  V2_SPEC.md
   36416cabe8cdd6adebda4b8cf6a69f443100bcf252427120651ffb49c8d03934  V1_LESSONS.md
   If either differs, stop and report. Do not go on.
3. Check that V2 holds no files, apart from a .claude folder if Claude Code has made one.
   If it holds anything else, stop and report.
4. Run these three read-only commands, and no others, in V1:
   git -C /home/indy/Projects/consultation-ai rev-parse HEAD
   git -C /home/indy/Projects/consultation-ai remote get-url origin
   git -C /home/indy/Projects/consultation-ai log -1 --format=%an,%ae
   The remote must be https://github.com/IndyWH/OpenConsult.git
   Keep the HEAD value. You check it again at the end.
5. Check that git config user.name and git config user.email, run in V2,
   give the same name and email as the V1 log line. If not, stop and report.
6. Write your plan to REVIEW/v2-logs/STAGE1_PLAN.md.
   The plan lists every command you will run and every file you will write.
   If you think any file text below is wrong or untrue, say so in the plan. Do not fix it yourself.
   Then print five lines at most, and stop.
   Wait for the owner to type: Approved. Go.

RULES
1. Write only in V2 and in REVIEW/v2-logs.
2. Do not change one character of V2_SPEC.md or V1_LESSONS.md. You copy them. You do not edit them.
3. No code, no tests, no settings files. Only the nine files listed below.
4. No git push. No sudo. No service command.
5. Before each commit, run the private word check on the staged files. It must print nothing:
   git diff --cached --name-only -z | xargs -0 grep -n -i -w -F -f /home/indy/Work/openconsult-review/v2-logs/private-words.txt
   If it prints a line, stop and report. Do not edit the file to make it pass.
   Never copy the word list, or any word from it, into V2 or into a commit message.
6. Commands and short results go to REVIEW/v2-logs/stage1.log. Long output never goes into chat.
7. Write the why in each commit message. No personal names, no email addresses, no host names.
8. If a step fails, stop and report.

PART 1. THE FOLDER AND THE BRANCH
Item 1. In V2: git init -b v2
   Then: git remote add origin https://github.com/IndyWH/OpenConsult.git
   Do not fetch. The branch shares no history with main (spec 14.1).

PART 2. THREE COMMITS
Commit 1. Subject: Stage 1: the spec and the lessons
   Copy V2_SPEC.md and V1_LESSONS.md from REVIEW into V2.
   Check both copies with sha256sum against the values above.
   The spec is committed before anything else (V1_LESSONS 11.3).

Commit 2. Subject: Stage 1: the licence, the notice and the ignore list
   LICENSE: copy it from V1. Prove with cmp that the copy is identical.
   NOTICE: the text between the NOTICE markers below.
   .gitignore: the text between the GITIGNORE markers below.
   Prove the ignore list with git check-ignore:
   ignored: .env, .env.local, data/x.db, openconsult.db, take1.wav, models/a.gguf, .claude/settings.local.json
   not ignored: .env.example, V2_SPEC.md, stage-prompts/STAGE_01.md

Commit 3. Subject: Stage 1: CLAUDE.md, HANDOVER, a holding README and the stage prompt
   CLAUDE.md: the text between the CLAUDE markers below. It must be under 100 lines.
   HANDOVER.md: the text between the HANDOVER markers below.
   README.md: the text between the README markers below.
   stage-prompts/STAGE_01.md: a copy of this prompt file. Prove with cmp that it is identical.

PART 3. CHECKS
Item 2. git ls-files in V2 must list exactly these nine and nothing else:
   .gitignore, CLAUDE.md, HANDOVER.md, LICENSE, NOTICE, README.md,
   V1_LESSONS.md, V2_SPEC.md, stage-prompts/STAGE_01.md
Item 3. git log --oneline shows three commits on branch v2. The working tree is clean.
Item 4. Run the first V1 command again. HEAD must be the value you kept.
Item 5. Write REVIEW/v2-logs/STAGE1_REPORT.md: the three commit hashes, the nine files with their
   sha256, the result of each check, and anything you flagged.

FINAL MESSAGE
Eight lines at most:
the three commit hashes,
that the nine files and no others are tracked,
that the private word check printed nothing three times,
that V1 HEAD is unchanged,
anything you flagged,
then this line for the owner: Tell Cowork: Stage 1 done. Do not push yet.

NOTICE TEXT START
NOTICE - third-party components used by OpenConsult v2
======================================================

OpenConsult is a research and education prototype. It is not a medical device.

The project's own code is licensed AGPL-3.0-or-later (see LICENSE).

This branch holds no third-party component yet. Each stage that adds one
records it here, in the same commit: the component, where it comes from,
its version, its licence, and how it relates to this code (bundled, linked,
or run as a separate process).

The NOTICE file on the main branch is the record for v1. It is the starting
point for any component that v2 carries from v1.

Nothing here is legal advice.
NOTICE TEXT END

GITIGNORE TEXT START
# OpenConsult v2: the ignore list, from the first commit (V1_LESSONS 10.6).

# Secrets and settings. Never commit these.
# The example file is the one exception, and it holds no real value.
.env
.env.*
!.env.example

# The user's data: the database file, recordings, anything the app writes.
/data/
*.db
*.db-journal
*.db-wal
*.db-shm
*.sqlite
*.sqlite3
*.sqlite3-journal
*.sqlite3-wal
*.sqlite3-shm

# Audio. Recordings never enter the repo.
# A stage that needs a small test clip adds a narrow exception for that one
# folder, in the same commit as the clip.
*.wav
*.flac
*.mp3
*.ogg
*.opus
*.webm
*.m4a

# Model files and downloaded packs.
/models/
*.gguf
*.onnx
*.safetensors
*.pt

# The guideline corpus is fetched locally and never committed (copyright).
/corpus/

# Working documents that may name a live weakness.
/*FINDINGS*.md
/*REVIEW*.md
/*AUDIT*.md

# Logs.
/logs/
*.log

# Python.
__pycache__/
*.py[cod]
.venv/
venv/
*.egg-info/
.pytest_cache/
.ruff_cache/
dist/

# Editors, the system, and the coding assistant's per-machine settings.
.vscode/
.idea/
.DS_Store
Thumbs.db
.claude/
GITIGNORE TEXT END

CLAUDE TEXT START
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
  lines. Older entries move to HANDOVER_ARCHIVE.md, which you do not read
  unless asked.
- A comment says why, in one or two lines. History goes in HANDOVER.md,
  never in the code.
- The repo root holds README.md, CLAUDE.md, V2_SPEC.md, V1_LESSONS.md,
  HANDOVER.md, LICENSE and NOTICE. Nothing else.

## Running it

Nothing runs yet. Stage 2 writes this section.
CLAUDE TEXT END

HANDOVER TEXT START
# HANDOVER

The record for OpenConsult v2: decisions and measurements, newest first.
It stays under 500 lines. Older entries move to HANDOVER_ARCHIVE.md.
The spec is V2_SPEC.md. The record for v1 is the HANDOVER.md on the main branch.

## 2026-10-04. Stage 1: the v2 branch is opened

What was done:
- A new branch, v2, in its own folder. It shares no history with main.
- Three commits: the spec and the lessons; the licence, the notice and the
  ignore list; CLAUDE.md, this file, a holding README and the stage prompt.
- No code. Nothing runs yet.

Decided by the owner on 4 Oct 2026 (spec 15.5):
- The spec is approved. It changes only by a dated ruling of his.
- A privacy pass before anything is public. Nothing committed names a
  family member, a colleague, a home or a place.
- One spec, and it lives in this folder.
- The licence stays as v1: AGPL-3.0-or-later.

Waiting for later stages:
- The community files (CONTRIBUTING, SECURITY, the code of conduct,
  CITATION.cff, the issue templates) cross from v1 in stage 16, before the
  join of spec 14.3.
- NOTICE gains an entry in the same commit as each third-party component.

Made untrue by this stage: nothing.

Next: stage 2, the skeleton, after its brainstorm.
HANDOVER TEXT END

README TEXT START
# OpenConsult v2 (in development)

This branch is where OpenConsult v2.0 is being built. It does not run yet.

- The working app, v1, is on the main branch.
- The plan for v2 is in V2_SPEC.md.

OpenConsult is a research and education prototype. It is not a medical
device. It must never be used with real patients or real patient data.

Licence: AGPL-3.0-or-later. See LICENSE and NOTICE.
README TEXT END
