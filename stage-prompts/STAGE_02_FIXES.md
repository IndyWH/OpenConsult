STAGE 2 of OpenConsult v2.0: three small fixes after Cowork's check

WHAT THIS IS
Cowork checked the 14 commits of stage 2. On a clean copy made from the last commit,
it installed from the lock file, ran the suite (74 passed, none skipped) and ran the start check.
It confirmed both pinned commit hashes of the GitHub check against their tags.
The work is good. Three small things need fixing before the owner's own check and the push.
This runs in the same session, on Fable 5.1 at high effort. No plan gate: the fixes are small.
Every rule of stage-prompts/STAGE_02.md still holds. If a fix needs a product judgement, stop and report.

FIRST
Copy this file to V2/stage-prompts/STAGE_02_FIXES.md. Prove with cmp that it is identical.
Commit it by itself. Subject: Stage 2: the prompt for the fixes

FIX 1. A refused form in Settings locks to an error page.
What happens now: after a refusal on /settings/you or /settings/password, the page's own timed move
goes to that same address with a GET, and the app answers 405, Method Not Allowed.
So a screen left on a refused form shows a bare error after the 30 minutes.
It does not show the login page, and no lock line is written.
Cowork saw it by running the app: the refused page carried a refresh to /settings/you?quiet, and a GET of that gave 405.
Wanted: the timed move from any page behind the login, a refused one included, ends on the login page
with the reason and writes the lock line. It never ends on an error page.
The three conditions of the plan review, change 2, still hold.
Pin it with one test: a refused Settings form, then the page's own timed move after the 30 minutes.

FIX 2. A wrong current password in Settings leaves no trace and has no wait.
What happens now: /settings/you and /settings/password check the current password.
A wrong one is not written to the log, and it does not count towards the growing wait.
Spec 15.6 says the log records each wrong password.
And someone at an unlocked screen could guess the password there without limit.
Cowork saw it by running the app: five wrong current passwords in Settings left no line in the log.
Wanted: a wrong current password in Settings is treated like a wrong password at login.
It is written to the log, and it makes the next try wait longer, on the same counter as the login page.
While the wait runs, both Settings forms refuse on the control that was pressed, and change nothing.
A right current password clears the counter, as at login.
Pin it with one test, or two if a twin is needed. Take every sentence from words.py.

FIX 3. No test runs the real nvidia-smi.
This is your own flag 4. In test_ruling_6, give the app a made-up machine, as the other tests do.
A test must give the same result on every machine.

THEN
1. One commit for each fix. The suite is green before each. The private word check before each.
   Each commit message ends with the co-author line.
2. In HANDOVER.md, add the three fixes to the stage 2 entry, in a few lines. Correct the test count.
   Commit it with the last fix, or by itself.
3. At the end of LOGS/STAGE2_REPORT.md, add a short part headed: Fixes after Cowork's check.
   Give the new commits with their hashes, the new tests with what each pins, and the new test count and time.
   If the owner's commands for port 8001 have changed, say so there.
4. Check again: git status --porcelain is empty, and V1 HEAD is unchanged.

FINAL MESSAGE
Five lines at most:
the new commits and the last hash,
the number of tests, the suite time, none skipped,
that the private word check printed nothing before every commit,
anything you flagged,
then this line for the owner: Tell Cowork: Stage 2 fixes done. Do not push yet.
