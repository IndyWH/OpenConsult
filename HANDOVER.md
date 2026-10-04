# HANDOVER

The record for OpenConsult v2: decisions and measurements, newest first.
It stays under 500 lines. Older entries move to HANDOVER_ARCHIVE.md.
The spec is V2_SPEC.md. The record for v1 is the HANDOVER.md on the main branch.

## 2026-10-04. Stage 2: the skeleton

What was done:
- The app starts. One person accepts the statement, sees This machine,
  sets up a title, a name and a password, and logs in. The settings page
  has This machine and You. The log page shows the audit log. The reset
  command resets the password. Nothing of a patient, a model or sound.
- One package, openconsult, on Python 3.12 with the lock file committed.
  Libraries: fastapi, uvicorn, jinja2; for tests pytest and httpx2. All
  pure Python or prebuilt wheels; nothing needs a compiler or a card.
- SQLite, from Python's own library. Four tables at version 1:
  schema_version, app_user, audit_log, first_run. Triggers make the audit
  log append-only.
- A GitHub check on Linux, Windows and macOS at every push to v2:
  install from the lock, run the suite, start the app, check it answers,
  stop it. Outside steps pinned: actions/checkout v7.0.1 at
  3d3c42e5aac5ba805825da76410c181273ba90b1; astral-sh/setup-uv v9.0.0 at
  c771a70e6277c0a99b617c7a806ffedaca235ff9; uv 0.12.10.

The rulings of spec 15.6, each in one line:
1. CLAUDE.md now says only documents are limited at the root. Done.
2. CITATION.cff is stage 16. Nothing to do here.
3. Every commit from stage 2 ends with the co-author line. Done.
4. The statement comes first and is audited; no user before it. Done.
5. The 30 minute lock, a named value in logins.py; a consultation holds
   it off through a flag stage 6 will set. Done.
6. The app listens on 127.0.0.1 only, with no flag to change it. Done.
7. The You section: title, name, password, current password first,
   every change audited from what to what. Done.
8. v1's look, the style sheet cut from 195 to about 90 lines. Done.
9. Cloud services with a free trial: later stages. Nothing here.
10. The engine choice: stage 3 brainstorm. Nothing here.

Decided in the plan review of 4 Oct 2026 (Cowork), as decisions of this stage:
- The settings store holds only the data folder and the port; no table,
  no page and no change method until a page-changeable setting exists.
- No page script in stage 2. The refusal helper is server-side Python:
  the page is sent back with the message under the control pressed, and
  the helper raises if the message would land nowhere.
- The wrong-password wait: 1 second after the first wrong try, doubling,
  capped at 5 minutes, cleared by a right password or a restart. A design
  choice, not a measurement; named in logins.py with the review as source.
- A card is suitable when its memory rounds to 24 GB or more.
- After set-up the user goes to the login page.
- The Mac sentence and the card-could-not-be-read sentence are drafts.
- A reset in another process ends the app's logins through a generation
  number on the user row; each login remembers the one it was made under.
- The This machine step is done when its Continue is pressed.
- No test holds its own copy of a sentence. Every sentence is in
  openconsult/words.py; tests take it from there or check which case the
  code chose. The owner corrects wording in that one file.
- The lock clears a screen nobody is using: every page behind the login
  carries a plain refresh instruction to itself with ?quiet after the
  time left. A ?quiet request never counts as use. If another tab kept
  the login alive the page waits again for the time left; otherwise the
  lock line is written then and the page goes to login with the reason.

For stage 6: when a page has text being typed, typing must count as use.
That needs a page script and is that stage's work. The quiet refresh also
re-renders a page, so a page with a form in progress needs the script to
hold the refresh off while typing. The consultation_running flag on
Logins is the hook for the live page.

Three fixes after Cowork's check, same day (stage-prompts/STAGE_02_FIXES.md):
- A page sent back by a form post now names its own GET address for the
  timed move, so a refused Settings form left alone locks to the login
  page and writes the lock line, instead of ending on a 405.
- A wrong current password in Settings is written to the log and counts
  on the same growing wait as the login page; while the wait runs both
  forms refuse and change nothing. The refusal sentence now says the wait.
- No test runs the real nvidia-smi: the command takes the machine like
  its saying and serving functions, and its test gives a made-up one.

Measurements (after the fixes):
- 76 tests, 1.9 s, none skipped. The twins and the parametrised cases
  are counted as pytest counts them.
- App code about 1,350 lines in 20 Python files; largest routes.py, 209 lines.
  Templates and the style sheet, 261 lines. Tests 959 lines.
- Largest function: well under 80 lines. No file near 600.
- The private word check printed nothing before every commit.

Not in the plan: the plan's commits 10 and 11 became one commit, because
the login tests need a set-up user and the only honest way to one is
through the first-run screens. Two drafted sentences were not used:
"Accept the statement first." and "OpenConsult is already set up.",
because a form sent at the wrong step goes back to the right step
instead.

Made untrue by this stage:
- CLAUDE.md, Running it: rewritten here. README: no longer says the app
  does not run. Both are fixed in this commit.
- V2_SPEC.md 15.6 "the settings store ... a change is written to the
  audit log": true from the first page-changeable setting, not in stage 2.
  And "plain pages, with their scripts in their own files": there are no
  scripts yet. Cowork folds both into the spec at the next brainstorm.

Next: the owner's check on port 8001, then push; the GitHub check must be
green on all three systems. Then the stage 3 brainstorm.

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
