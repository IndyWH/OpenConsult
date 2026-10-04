STAGE 2 of OpenConsult v2.0: the skeleton

WHAT THIS IS
OpenConsult v2.0 is a rewrite, built on the branch v2 in its own folder.
Stage 2 is the floor every later stage stands on. The app starts. One person sets it up
with a name and a password, and logs in. The app describes the machine it runs on.
No patient, no model and no sound yet.
The spec is V2_SPEC.md. Stage 2 is section 15.6 of it. Read that section first and build what it says.
This prompt gives the order of work and the rules. Where the two differ, the spec wins: stop and report.
OpenConsult is a research and education prototype. Never real patients.

MODEL
This stage runs on Fable 5.1 at high effort.
Say in your first line which model you are. If you are not Fable 5.1, stop there.

THE FOLDERS
V2    /home/indy/Projects/OpenConsult2
      The repo. Branch v2. All code and all commits are made here.
LOGS  /home/indy/Work/openconsult-review/v2-logs
      Private. Your plan, your log and your report go here. This prompt is here.
V1    /home/indy/Projects/consultation-ai
      Read only. A reference. Change nothing. The only git command allowed there is:
      git -C /home/indy/Projects/consultation-ai rev-parse HEAD

BEFORE YOU START
1. Read V2/CLAUDE.md.
   Read V2/V2_SPEC.md sections 4, 5, 6, 7.1, 7.3, 14.1, 15.3, 15.4 and 15.6.
   Read V2/V1_LESSONS.md: the twelve that matter most, then sections 5, 6.2, 6.3, 7, 8, 10 and 11.
2. Check the spec with sha256sum. It must be:
   f82b5cffcc8645226fac80ee79cf57d0a7e0d4954283d2508b094977311b1dbe  V2_SPEC.md
   If it differs, stop and report. Do not go on.
3. Check V2. The branch is v2. HEAD is ccc80acd7bf5fb2e2a6de78b6b4c48d02af5b571.
   git status --porcelain shows one line only: V2_SPEC.md modified.
   If anything else is changed or untracked, stop and report.
4. Run the one allowed command in V1 and keep the value. You check it again at the end.
5. Check that uv is installed: uv --version. If it is not, stop and report.

RULES
1. Write only in V2 and in LOGS.
2. Do not change one character of V2_SPEC.md or V1_LESSONS.md. If the spec is wrong or silent, report it.
3. If a choice is a product or clinical judgement, stop and report it. Do not decide it.
4. No git push. No sudo. No service command. Nothing in V1 is written, not even by git.
5. Never use the owner's real data folder, and never use port 8000 or port 8001.
   Port 8000 is v1, which keeps running. Port 8001 and the real data folder are for the owner's own check.
   When you run the app yourself, give it a temporary data folder and a spare port, and stop it afterwards.
   Never set up the real user. The owner does that himself.
6. Before each commit, run the private word check on the staged files. It must print nothing:
   git diff --cached --name-only -z | xargs -0 grep -n -i -w -F -f /home/indy/Work/openconsult-review/v2-logs/private-words.txt
   If it prints a line, stop and report. Do not edit a file to make it pass.
   Never copy the word list, or any word from it, into V2 or into a commit message.
7. Each commit: one logical change, the suite green before it, the why in the message.
   No personal names and no host names in a message.
   Each commit message ends with this line, after one empty line (spec 15.6, ruling 3):
   Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
   That is the only address allowed in a commit message.
8. Commands and short results go to LOGS/stage2.log. Long output never goes into chat.
9. Nothing is built switched off, and nothing is built for a later stage (R31).
   Stage 2 builds no patient, no consultation, no model call, no speech and no connect screen.
10. Nothing assumes Linux. The same code must start on Windows and macOS.
    You can only run Linux here. So keep a list of every place where the three systems differ,
    and say for each one how you know it will work. The list goes in your report.
11. The size targets of spec section 5 hold: no file over 600 lines, no function over 80,
    tests no larger than the app, the suite under a minute.
    If a target cannot be met, report it and say why. Do not squeeze code to fit a number.
12. If a step fails, stop and report.

PART 1. TWO COMMITS BEFORE THE PLAN
Commit 1. Subject: Stage 2: the spec as the stage 2 brainstorm left it
   V2_SPEC.md only. The spec is committed before the code (V1_LESSONS 11.3).
Commit 2. Subject: Stage 2: the stage prompt
   Copy this file to V2/stage-prompts/STAGE_02.md. Prove with cmp that it is identical.

PART 2. THE PLAN, THEN STOP
Write your plan to LOGS/STAGE2_PLAN.md. It holds:
1. The files you will write, each with its job in one line and its expected size.
2. The libraries you will add: name, version, licence, and why each is needed.
   Keep them few and light (spec 5.1). No PyTorch, no NVIDIA library, nothing that needs a compiler.
3. The tables, and how the table version is kept.
4. The pages and the addresses the app answers on.
5. Every test you intend, each with the rule, the ruling or the incident it pins (spec 5.2).
   Follow the policy in V1_LESSONS 8.8. Say how the shared helper for refusals (R15) is tested
   by running it, not by reading its text, and how that runs on all three systems with no silent skip.
6. Every sentence the app will show to the user, in one list, so the owner can correct the wording.
7. The commits you will make, in order.
8. The list for rule 10: where the three systems differ.
9. Anything in the spec that is wrong, silent or in conflict. Do not fix it yourself.
Then print five lines at most, and stop.
Wait for the owner to type: Approved. Go.

PART 3. THE BUILD
Build what spec 15.6 says. This is the suggested order. Your plan may change the order and say why.
1. The project set-up: Python 3.12, the lock file committed, the package openconsult, the tests folder,
   and the guard that fails any test which reads the user's own settings or writes outside its
   temporary folder (R18; V1_LESSONS 8.5, 10.1). The app is put together fresh at each start and for each test.
2. The database module: one place opens it, one file lists the tables, a version number for changes.
3. The audit recorder, and the page that shows the log.
4. The settings store.
5. The user: the password hash ported from V1 app/auth.py, the login kept in the app's own memory,
   the 30 minute lock, the growing wait after a wrong password, logout.
6. The guards: the app listens on this computer's own address only, it answers only when addressed
   as this computer, and a request that changes anything must come from its own pages.
7. The first run: the statement, This machine, the user. In that order. Set-up only from this computer (D20).
8. This machine: the system, the graphics card and its memory, and the sentence.
9. The settings page with its two sections, This machine and You. The home page.
10. The look: V1 app/static/theme.css, cut to what these pages use. No page loads anything from the internet.
11. The command: openconsult starts the app, openconsult reset-password resets the password.
    A taken port is said in plain words and the app stops.
12. The GitHub check: .github/workflows, on every push to v2, on Linux, Windows and macOS.
    Install from the lock file, run the suite, start the app with a temporary data folder, check that it answers, stop it.
    A test skipped by accident fails the check. No secret. Read-only rights.
    Each outside step is pinned to a full commit hash, with its version in a comment.
    Write the start-and-answer step so that it can also be run here, and run it here.
13. The documents, in the last commit:
    CLAUDE.md: the three changes given below. It must stay under 100 lines.
    README.md: the text between the README markers below.
    NOTICE: one entry for each library added. If you added them in earlier commits, the entry goes in that commit.
    HANDOVER.md: a new entry at the top. What was done, the rulings of spec 15.6 in one line each,
    the measurements (tests, suite time, largest file), and what this stage has made untrue.

WORDS GIVEN BY THE OWNER'S SIDE
These are drafts. The owner corrects them when he sees them on screen. Use them exactly.

The statement, on the first screen:
STATEMENT TEXT START
OpenConsult is a research and education prototype. It is not a medical device.
It must never be used with real patients or real patient data.
Every consultation in it is acted or scripted.
STATEMENT TEXT END
The tick beside it:
I agree. I will never use OpenConsult with real patients or real patient data.

The sentence on This machine is in spec 15.6. Use those words, with the real figure for the card.

Every other sentence on a page is yours to draft: short, plain words, no developer terms.
List them all in the plan (Part 2, item 6).

CHANGES TO CLAUDE.md
Change 1. In How a stage runs, item 5, add this sentence at the end:
   Each commit ends with the co-author line your stage prompt gives.
Change 2. In Where the writing goes, replace the last bullet with this one:
   - The only documents at the repo root are README.md, CLAUDE.md, V2_SPEC.md,
     V1_LESSONS.md, HANDOVER.md, LICENSE and NOTICE. Add no other document
     there. Code, tests and their set-up files are not documents.
Change 3. Replace the text under Running it with ten lines at most:
   how to start the app from source, how to run the suite, how to run the reset command,
   and where the data folder is on each system. Commands only, no story.

README TEXT START
# OpenConsult v2 (in development)

This branch is where OpenConsult v2.0 is being built.

- The working app, v1, is on the main branch.
- The plan for v2 is in V2_SPEC.md.
- So far v2 starts, sets up its one user, and describes the machine it runs on.
  It cannot run a consultation yet.

OpenConsult is a research and education prototype. It is not a medical
device. It must never be used with real patients or real patient data.

Licence: AGPL-3.0-or-later. See LICENSE and NOTICE.
README TEXT END

PART 4. CHECKS AT THE END
Item 1. The suite is green. Give the number of tests, the time it took, and the number skipped, which must be none.
Item 2. Start the app with a temporary data folder and a spare port. Walk the first run with a made-up user,
   log in, change the name in You, read the log page, log out. Run the reset command against the same
   temporary folder and log in with the new password. Then stop the app and remove the temporary folder.
Item 3. Start the app a second time on the same spare port while the first is running.
   It must say in plain words that the port is taken, and stop.
Item 4. git status --porcelain is empty. git log --oneline lists your commits on v2.
Item 5. Run the V1 command again. HEAD must be the value you kept.
Item 6. Write LOGS/STAGE2_REPORT.md:
   the commits with their hashes;
   the files with their line counts, the largest file, and any target missed;
   the tests, each with what it pins;
   the libraries added, with licences;
   every sentence shown to the user;
   the list for rule 10;
   the result of each check above;
   the exact commands for the owner's own check on port 8001;
   anything you flagged.

FINAL MESSAGE
Ten lines at most:
the number of commits and the last hash,
the number of tests, the suite time, none skipped,
that the private word check printed nothing before every commit,
that V1 HEAD is unchanged,
any target missed,
anything you flagged,
then this line for the owner: Tell Cowork: Stage 2 done. Do not push yet.
