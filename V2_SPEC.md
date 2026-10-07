# OpenConsult v2.0: the spec

Status: APPROVED by Wajira, 4 Oct 2026. From here it changes only by a dated ruling of his, made in a brainstorm. Written by Cowork, 4 Oct 2026. Revised the same day, eleven times. First: the installer, cloud as the default without a suitable NVIDIA card, the connect screens, and SQLite. Second: single user only, the patient list with search, and context from earlier consultations. Third: Alba asks one question at a time (section 9). Fourth: signposting, to keep Alba on course (section 9.7). Fifth: the intended consultation time, and Alba using it well (section 9.8). Sixth: Alba's share set at 75 %, and how we work (section 15.1). Seventh: the time is a guide, and the rules for a brainstorm (9.8, 15.2). Eighth: the lessons from v1 (V1_LESSONS.md), the code layout reassessed (5 and 6.5), and the model rule (15.1). Ninth: the stand-in patient, for room tests without an actor, and consultations with no person that run while you are away (section 13.5). Tenth: the player for past recordings (section 8.8). Eleventh: the lessons of the Task 19 session (LESSONS_FOR_V2.md) folded in (11.3, 11.5, 13.3, 13.4), and v1.1 development stopped (14.2). Twelfth: the decisions session. All 54 decisions in section 16 are now closed: six by your ruling (D2, D5, D17, D25, D32, D35), and the other 32 that were open on their defaults. Thirteenth: the brainstorm for stage 1. The spec is approved, and the rulings for stage 1 are in section 15.5. Fourteenth: the brainstorm for stage 2. Its rulings are in section 15.6. Fifteenth: the brainstorm for stage 3. Its rulings are in section 15.7. Sixteenth: the brainstorm for stage 3b, on 6 Oct 2026. Its rulings are in section 15.8. Seventeenth: the rulings you made during and after the run of stage 3b, on 6 Oct 2026, folded in after Claude Code's last commit of that run (15.8, rulings 13 onward).
This is the one document for v2.0. It is in the order the work will be done.

OpenConsult is a research and education prototype. It is not a medical device. It must never be used with real patients or real patient data. Every consultation in it is acted or scripted.

---

## 1. What v2.0 is for

**For the patient** (acted, in this project):

- Nothing said in the room is lost from the record. For eleven weeks v1's final pass dropped passages with no sign on the page, two safety nets among them. The cause was found and fixed on 4 Oct (Tasks 17 to 19, not yet checked by Cowork). v2 makes a missing passage visible, whatever the speech model, and chooses its speech model on this measure first.
- Questions come quickly. Gemma 4 QAT took about 5 s a pass in the Task 3i benchmark, against about 18 s for MedGemma. Auto mode depends on that.
- No long wait at Stop, where the speech choice allows it.
- The model calls that read or write about the patient know the patient's age and sex. The one exception for now is the note (decision D3).
- Alba works to the time the doctor has set, and asks the most important questions first. The patient is never hurried.
- In auto mode, each of Alba's questions follows from what the patient has just said. The model reads every answer beside the question that drew it.
- A returning patient is not a stranger. The notes the doctor approved at earlier consultations are in front of the doctor, and can be given to the decision support.

**For the learner:**

- A mock patient to practise on, at any time, on any topic of the RCGP curriculum.
- Feedback that says what was asked well, and names the one most important thing that was missed.

**For a colleague who wants to try it:**

- One download and one installer, on Windows, macOS or Linux. No database to install first.
- It works on an ordinary laptop. With no suitable NVIDIA card, it uses cloud models.

**For us, who build it:**

- Code small enough that Claude Code can read a whole area in one session.
- A test suite where every test has a reason to exist.
- A settings menu, so that changing a model is a choice on a page and not an edit to a file.

## 2. Decisions taken on 4 Oct 2026

| Question | Wajira's decision |
|---|---|
| GitHub route | A clean v2 branch inside the OpenConsult repo. Not a second repo. |
| What v2.0 carries from v1 | The core scribe, auto mode, the face and the guideline corpus. You first kept the front desk and three roles as well, then replaced them the same day: see the next row. |
| Users | Single user only, because the app is installed on the user's own PC or laptop. At the start the user gives a name and a title and sets a password. |
| Patients | The user can search for a patient seen before and add a new consultation under that patient. |
| Earlier consultations | OpenConsult can take context from a patient's earlier consultations when required. |
| Time | The user picks the intended consultation time from a list: 15, 30, 45 or 60 minutes. Alba can take 75 % of it, for now. The model gets a countdown of the time remaining, so Alba chooses the areas and asks the most important questions with the passing time in mind. |
| v1.1 | Development of v1.1 stops on 4 Oct. v2.0 starts. |
| The model for the build | v2 is built only on Fable 5.1 at high effort, or Fable 5.5 when it comes out. This is for Cowork and for Claude Code. |
| Listening back | On a past consultation, you can play the recording and drag to any point, to check the quality of the audio. |
| Room tests without an actor | A stand-in patient: the teaching mode's patient speaks in the room in its own voice, so a consultation can be run and recorded with no second person. |
| How we work | Wajira, then Cowork, then Claude Code, as before. Our thinking is patient focused, or learner focused in teaching mode. Every stage starts with a brainstorming session, and so does every sub-stage. |
| Keeping Alba on course | Signposting, as GPs use it. The model is asked which other areas of the systems review this presentation requires, and Alba works through them. |
| Alba's questions | One at a time. Gemma 4 writes a question, Alba asks it, the patient answers, and the question and the answer go back to Gemma 4 for the next question. |
| Nemotron | Speech only. The language model list is cloud (Claude), Gemma 4 QAT and Qwen. |
| Teaching mode | The learner speaks to the mock patient. Typing is the fallback. |
| Recordings | New two-actor recordings, made from scratch. |
| Installing | A downloaded installer, as ComfyUI does it. Linux, Windows and macOS. |
| With no suitable NVIDIA card | Cloud models are the default. |
| Cloud models | A connect screen for each service, with a test that the connection works. |

Single user removes a real block of v1: the three roles, registration and approval of users, the users page, and the walk-in queue. Beyond that, v2.0 gets smaller by how the code, the tests and the documents are written. Section 5 sets the rules for that.

## 3. Scope

### 3.1 Carried from v1

1. Live transcript during the consultation.
2. Clinical decision support: differentials, questions to ask, signs to look for.
3. The urgency alarm, judged by its own model call, with the earlier alarm kept on screen.
4. Stop, then the final transcript with speaker labels.
5. The transcript quality gate, which refuses or flags an untrustworthy transcript.
6. The cited draft note. Review, edit, approve. The raw transcript view and the speaker corrections (Who spoke?, Swap, per-line label) stay with it.
7. Referral letters, drafted from the approved note only.
8. Alba's voice: tap-to-ask, the sound check, and auto mode. The way auto mode makes its questions is new (section 9).
9. The face.
10. The guideline panel, which answers only from a local corpus. It ships empty.
11. The audit log, audio retention, and deleting a consultation (decision D44).

Not carried, by your decision: the receptionist, doctor and admin roles, user registration, and the walk-in queue.

### 3.2 New in v2.0

1. A settings menu (section 7.3).
2. A choice of language model: cloud, Gemma 4 QAT or Qwen (section 10).
3. A choice of transcription: WhisperX with pyannote, Nemotron, or cloud (section 11).
4. Teaching mode (section 12).
5. A record, on every consultation, note and letter, of which models made it.
6. A confirmation before Start that the consultation is acted. This was on the v1 list after consultation 469 and was never built.
7. An installer for Linux, Windows and macOS (section 6.4).
8. A first-run setup, with connect screens for the cloud services (sections 7.1 and 7.2).
9. SQLite in place of Postgres, so there is no database to install (section 6.3).
10. One user, with a name, a title and a password (section 7.1).
11. A patient list with search, and new consultations filed under a patient seen before (section 8).
12. Context from a patient's earlier consultations (section 8).
13. Alba asks one question at a time, with signposting and a time budget (section 9).
14. The intended consultation time, and a quiet clock for the doctor (section 9.8).
15. A check at Stop that nothing heard live is missing from the final transcript, and a first-run self-test (section 11.5).
16. A player for the recording of a past consultation (section 8.8).
17. The stand-in patient, for consultations with no second person, or no person at all (section 13.5).

### 3.3 Small parts not carried

These are inside the four big parts you kept. Each one is switched off, measure-only, or was judged a wrong design. Leaving them out is where real lines are saved. Decided 4 Oct, on the default (D1): all are left out.

| Part | Why it is left out |
|---|---|
| The barge-in detector | Built and switched off. Closed with a negative result on 18 Aug. The hard mute stays. One thing to know: v1.1 Task 4, the barge-in re-check on Omarchy, was still owed when v1.1 stopped. The detector is not carried (D1), so v2 does not run that re-check. |
| The question queue, the re-ranker, the topic call and the lay-wording rewrite | Replaced by one question at a time (section 9). This one is your decision of 4 Oct, not a default. |
| Signal S1, the language check | Measures only. Nothing acts on it. v2 is English only. |
| The public monitoring pulse | Built for a public demo on mlrig. The app is no longer open to the internet. |
| MedGemma-only options | MedGemma is history. |
| The Docker demo | Not carried. The installer replaces it (6.4). |
| Sinhala scripts and evaluations | Stay in the v1 branch as a research record. |

### 3.4 Not in v2.0

- The second-opinion call and the management plan (v1.1 Tasks 9 and 10). The design leaves a place for each. They wait for v2.1: your ruling of 4 Oct (D2). The history scaffold (Task 8) is now in v2.0, as signposting (9.7).
- Multi-user mode.
- Local models on a Mac. A Mac uses cloud models in v2.0. See decision D19.
- A desktop window of its own. The app opens in the browser. See decision D15.
- Automatic updates.
- llama.cpp or vLLM in place of Ollama. Both are benched against Ollama in stage 3, as a report only. A setting to choose the engine waits for that report (15.7, ruling 5).

## 4. Rules carried from v1

A rewrite can lose what the room taught us. These rules stop that. Each one is pinned by one test or one check in v2, named with its rule number.

| # | Rule | Where it came from |
|---|---|---|
| R1 | Never real patients. The doctor confirms before Start that the consultation is acted. | Consultation 469 |
| R2 | Every AI output is a draft. Nothing enters the record until the doctor approves it. Every approval is audited. | Founding rule |
| R3 | Refusal is a feature. The gate refuses to draft from a bad transcript. The corpus refuses when it does not cover a topic. Neither is softened for a demo. | Consultation 70 |
| R4 | Every claim in the note cites the transcript lines it came from. Code checks the citations. A note with too few valid citations is refused. | Consultation 78 |
| R5 | Letters are drafted from the approved note only, and cite its lines. | 24 Jul design |
| R6 | The system's own voice never enters the transcript. This is done by construction: the server knows when it is speaking. Not by a prompt, and not by filtering afterwards. | Phase 7a hard rule |
| R7 | To the patient, Alba asks and acknowledges. She never advises, reassures, interprets or hints at a diagnosis. Code enforces it. Her fixed phrases, such as telling the patient they are talking to a machine, the invitation and the handover, are written in advance and never by the model. One addition, decided 4 Oct (D34): Alba may speak a signpost that code builds from a fixed list (9.7). | Phase 7 hard rule 1 |
| R8 | When the alarm fires, auto mode pauses. The doctor always wins: one tap stops Alba at once. | Phase 7 hard rules 2, 3 |
| R9 | The alarm is judged by its own call, fresh at every pass. An alarm that drops out stays on screen as an earlier alarm. | Task 3k |
| R10 | The alarm is never wired to the face. | 1 Aug decision |
| R11 | Every model call that reads or writes about the patient carries the patient line (age and sex). A patient cannot be saved without a date of birth and a sex. One exception for now: the note call (D3). | 3 Oct ruling |
| R12 | Every pass reads the transcript in a fresh context. It is given the earlier differentials as names only. | Tasks 3d, 3f |
| R13 | No prompt names a country. No prompt change may discriminate against a patient. | 30 Sep, 1 Oct rulings |
| R14 | The list of questions already asked holds only what Alba actually spoke. | 2 Oct ruling |
| R15 | The three interface rules. Never swallow an action. A control that can act must not look as if it cannot. A control the doctor must reach must be where they are looking. | Consultations 447 to 450 |
| R16 | The patient is told they are talking to a machine. Alba's voice is never cloned from a real person. | Phase 7 hard rule 4; 19 Sep |
| R17 | A consultation is filed under a patient only after the user has seen that patient's name, date of birth and sex on screen and confirmed them. | New. Guards against the wrong patient. |
| R18 | Tests never write to the recordings folder or the live database. A recording is written once and never overwritten. Banked recordings are read-only and are backed up apart from the app. | Task 16 |
| R19 | One context size for every local model call, so the model never reloads between calls. | 28 Jul; Task 3m |
| R20 | The model name and version are stored with every consultation, note and letter. | 1 Oct review |
| R21 | No instruction in the repo names a guideline publisher. The corpus ships empty. | NICE reply, 15 Aug |
| R22 | The help pages are Wajira's words. An implementer flags a page that has become untrue and never edits it. | 1 Aug decision |
| R23 | The real tailnet host name and address never go into a committed file. | Standing rule |
| R24 | Teaching mode is separate by construction. It has its own tables. It can never produce a clinical note or a record. The stand-in patient (13.5) is a test tool outside the app: the app hears it as a voice in the room, like any patient. | 4 Aug design note |
| R25 | Only notes the doctor has approved are given to a model as earlier context. They go in their own block, marked as background, apart from today's transcript. Today's note cites today's transcript only. | New. Follows from R2 and R4. |
| R26 | In auto mode, silence is judged by code, from sound. A model may shorten a wait. It may never lengthen one, and it can never leave Alba silent. | Consultations 482 to 485 |
| R27 | Alba's own voice never counts as the patient speaking, and never cancels a turn end. | Consultations 482, 485, 491 |
| R28 | Code refuses a question that matches one Alba has already spoken. The prompt alone did not stop repeats. | Consultations 486, 491 |
| R29 | An alarm the doctor has acknowledged never pauses Alba again. Only a new alarm does. The history of alarms is held in code. | Consultations 482, 485, 486 |
| R30 | Every model call has a limit on its length and on its time, and fails without stopping the consultation. The alarm goes first, then Alba's question, then the assessment. | Consultation 486 |
| R31 | Nothing is built into v2 switched off. A feature is built when it ships. | The barge-in detector |
| R32 | In auto mode, a turn must start before it can end. If the patient says nothing for 12 seconds, Alba asks once more, then moves on. | Consultation 486 |
| R33 | Auto mode does not show as on until the patient has heard, in full, that they are talking to a machine. | Consultation 488 |

One open item travels with R11. The note call does not carry the patient line today: Task 5d failed its marks and was reverted, and the cause is parked. v2 carries that state as it is. The note gets the line only after a bench passes. See decision D3.

## 5. Keeping it small

These are the rules that answer the bloat. Where v1 stands on GitHub (commit b4cd9b9). The copy on mlrig is larger: the suite there reached 1,381 tests after Task 13.

| | v1 on GitHub |
|---|---|
| App code (Python) | 15,116 lines |
| Largest file | app/main.py, 5,654 lines |
| Tests | 27,513 lines, 1,103 tests, 88 files |
| Settings | 105 in .env.example |
| HANDOVER.md | 8,602 lines |
| Documents at the repo root | 22 |

### 5.1 Code

- No file over 600 lines. No function over 80 lines.
- The live consultation is a class with named fields, in its own file. Not one long function.
- One module talks to language models. One talks to speech models. One holds settings. No other part of the code reads the settings directly.
- Prompts are files, one prompt in one file. The app and every bench read the same file. A prompt change is then one small, visible change, measured before it is kept.
- Page scripts live in their own files, not inside the HTML.
- The base app starts on a machine with no graphics card. The heavy libraries (PyTorch, Whisper, Nemotron) load only inside the speech workers, never in the app itself.
- Nothing assumes Linux. File paths, the data folder and starting a worker all work the same on Windows and macOS.
- A comment says why, in one or two lines. The long story goes in HANDOVER. In v1 about a third of the app's lines are comments, and more than half of the comment blocks are history.
- Nothing is built switched off (R31). In v1 the barge-in detector is about 1,060 lines and 1,228 lines of tests, and it is off.
- No setting without behaviour. No threshold without a measured source.
- No part of the app keeps hidden shared values. The app is put together fresh each time it starts, and fresh for each test.

### 5.2 Tests

- Every test names what it pins: a rule number from section 4, or a fault that really happened. A test with no such reason is not written.
- Claude Code lists the tests it plans in its plan, before writing any. You or Cowork can strike them.
- No test reads a source file as text to check that a line exists. In v1, 188 tests did, and 137 tests never ran any of the app's code.
- A test checks what the code gives back: a message to the page, a stored row, the result of a function. It does not check how the code works inside.
- A property is tested once, at the lowest level that can pin it. v1 tested the same property again at each layer.
- Timing faults in auto mode are tested through one harness that replays a consultation as a timeline, with a clock the test controls. No real waiting.
- Tests never read the user's own settings, and never write outside a temporary folder. A guard fails the test if they try.
- A test that is skipped by accident fails the GitHub check.
- What a model says is measured in a bench, not asserted in a test.
- Target: the tests are no larger than the app, and the audit of v1 suggests far fewer: about 250 to 280 tests would pin every rule and every incident. The suite without a GPU runs in under a minute.
- The v1 rule stays: a test is never weakened or deleted to make the suite pass.

### 5.3 Documents

- The documents at the repo root: README, CLAUDE.md, V2_SPEC.md (this file), V1_LESSONS.md, HANDOVER.md, and the licence files. No other document. The root also holds what is not a document: the ignore list, the folder of stage prompts, and from stage 2 the code, its tests and their set-up files (15.6). One addition in stage 16: CITATION.cff, which GitHub and Zenodo read only from the root (15.5).
- V1_LESSONS.md is the detailed list of what v1 taught. It is for Cowork and Claude Code to apply. You do not need to read it.
- Every task says which document it has made untrue.
- A promise in a help page needs a test behind it. v1's help said a transcript with missing speech is refused. Only speech missing at the end was.
- LESSONS_FOR_V2.md, written in the v1 repo on 4 Oct, is folded into V1_LESSONS.md. v2 has one lessons file.
- CLAUDE.md is under 100 lines.
- HANDOVER.md holds decisions and measurements, newest first, and stays under 500 lines. Older entries move to an archive file that Claude Code does not read by default.
- The v1 specs and the v1 HANDOVER stay in the v1 branch. They are the research record for the paper.

### 5.4 If a target cannot be met

Claude Code reports it and says why. It does not squeeze code to fit a number. The targets exist to make growth visible, not to force bad code.

## 6. How the code is arranged

The stack changes in one place: SQLite replaces Postgres (6.3). The rest stays: Python, FastAPI, Ollama for local models, Piper for Alba's voice, plain web pages, with nothing to compile.

| Folder | What it holds |
|---|---|
| settings | The one settings store. |
| llm | The one door to language models: Ollama and the cloud. The table of jobs and which model does each. |
| prompts | One file for each prompt. |
| speech | The one door to transcription. One worker for each choice. |
| voice | Alba's speech, and the list of what she is allowed to say. |
| consult | The live session, the CDS, the alarm, Alba's question loop, auto mode, the face. |
| record | Finalising, the quality gate, the note, the letters, the guideline panel. |
| teach | Teaching mode. |
| patients | The one user's login, the patient list, audit, retention, and deleting a consultation. |
| web | The routes and the pages. |
| bench | The harnesses. They read recordings and write reports. They never write to app data. |

### 6.1 Ported or written fresh

Some v1 modules are small and proven, and they only work things out: they do not touch the database, the network or the clock. They are ported: moved across with only the tests that pin a rule. The rest is written fresh from this spec, with the v1 code open beside it as a reference.

| Ported | Written fresh |
|---|---|
| The auto-mode state machine (auto_mode.py), made simpler | The live session (today inside main.py) |
| Alba's speech and the check on what she may say (speech.py) | Settings |
| The quality gate measures (transcript_quality.py) | Every model call |
| The note and letter citation checks | Every speech call |
| Password hashing, sessions, audit (audited in July) | The pages' scripts |
| The face: what is carried depends on decision D43 | Finalising |
| Guideline chunking | Teaching mode |

### 6.2 Speech choices run as separate workers

Each transcription choice runs in its own process with its own Python environment. The app talks to all of them in one way. This matters because the Whisper stack and the Nemotron stack need different library versions. v1 carries three version pins for that reason. Task 13 already runs Nemotron this way.

### 6.3 Database

**Postgres is not a must. v2 uses SQLite.** See decision D14.

SQLite is a database that is part of Python itself. There is nothing to install and no service to start. The whole database is one file in the user's data folder.

Why it fits OpenConsult:

- v1 uses 14 tables and simple requests to the database. The one thing it takes from Postgres that SQLite lacks is a search add-on, used for the guideline corpus in two places.
- The corpus is small. It held 1,301 passages in July. At that size the app can compare the question with every passage in a few thousandths of a second, in ordinary code. No add-on is needed.
- OpenConsult has one user and runs one consultation at a time. SQLite allows many readers and one writer at a time, which is enough.
- A backup is a copy of one file.
- Tests get simpler. Each test run uses a throwaway file. Nothing to start and no special permission, and the free GitHub check needs no database set up.

What is given up, said plainly:

- Many doctors writing at the same moment. That is multi-user mode, which is not in v2.0. All the database code is in one place, so Postgres could be added later if a clinic-sized install ever needs it.
- Postgres has no built-in encryption and neither does SQLite. On both, protection at rest comes from an encrypted disk, as on mlrig.

One engine only. mlrig runs SQLite too. Supporting two engines would double the testing.

v1 consultations are not moved across. The v1 Postgres database stays as it is, as a research record. See decision D4.

### 6.4 The installer

How ComfyUI does it: its desktop app sets up its own self-contained Python, with the right libraries for the graphics card it finds. The user never installs Python.

OpenConsult does the same, in two parts.

**Part 1, the base app. Small, the same for everyone.**

- One installer for each system: Windows, macOS, Linux.
- It carries its own Python, the app, and the light libraries. No PyTorch.
- It starts the app on this computer and opens it in the browser. The microphone works there, because browsers trust a page served from the same computer.
- The app listens on this computer only. Reaching it from a second device, as you do over the tailnet, is an advanced setup for the help pages, not a default.
- With cloud models, this is the whole install.
- Data (the database file, recordings, settings) lives in the user's data folder, not in the install folder. An update or a reinstall does not touch it.

**Part 2, the local pack. Large, only for a machine that can use it.**

- On a machine with a suitable NVIDIA card, the settings page offers to download the local speech models. Each choice shows its size before the download starts. Nothing downloads without a click.
- Each speech choice installs into its own environment (6.2), so one cannot break another.
- The local language models run in Ollama. The app looks for Ollama. If it is absent, the page gives the link and the steps. If a model is absent, the page offers the download, with its size.
- The WhisperX with pyannote choice has one extra step that cannot be removed: pyannote's makers require the user to accept their terms on Hugging Face. The page gives the steps on the control itself.

**Suitable NVIDIA card** means, for everything local at once, 24 GB of graphics memory. Task 13 measured a peak of 22.4 GB with Gemma 4 QAT and the Nemotron pair loaded. A smaller card may still run local speech with a cloud language model. Such a machine starts on cloud for both, and the settings page offers local speech where it fits. The This machine section works this out and says it in plain words.

**How the installers are built.** GitHub builds all three on its own machines, free for a public repo, each time a version is tagged. This is the only practical way to make the macOS and Windows installers, because mlrig is Linux.

**Three gates, checked before any plan is built on them:**

1. **Windows warns about unsigned installers.** Microsoft's cheap signing service takes individual developers only in the USA and Canada, not the UK. The other route is a certificate at about $150 to $300 a year, kept on a hardware key. Even a signed installer shows the warning until enough people have run it. Many open-source projects ship unsigned and document the two clicks: More info, then Run anyway.
2. **macOS blocks unsigned apps more firmly.** Signing needs Apple's developer programme, US$99 a year. Without it the user must allow the app by hand in System Settings.
3. **A Mac installer needs a Mac to test it.** GitHub can build it, but someone must run it. You have a MacBook Air M1, and you test the Mac installer on it before the release (D17, your ruling of 4 Oct). It has an Apple chip, so the test covers Macs with Apple chips. Whether v2.0 also offers an installer for older Macs with Intel chips, which would be untested, is settled in the brainstorm for stage 15.

See decisions D16 and D17. Cowork also checks, before the installer stage, that the licences of everything bundled (Piper, Alba's voice model, the face engine) allow it.

### 6.5 What v1's layout teaches

Cowork measured v1 on 4 Oct. The full list is in V1_LESSONS.md, section 6. These are the findings that change the layout.

| v1 today | Figure |
|---|---|
| The one function that runs the live consultation | 3,328 lines, with 62 smaller functions inside it |
| Auto mode's share of the largest file | about half |
| The live state | two loose collections with 82 named entries, used about 570 times |
| Places that open a new database connection | 84 |
| Places that build a request to the language model | 5, with five different time limits |
| Settings | 112 names read in 21 files, almost all fixed when the app starts |
| Comments and docstrings | about a third of the app |

What v2 does about it:

1. **One class for the live consultation, and one small module for each of its jobs:** the connection, the transcript, the assessment, Alba's speech, the face, auto mode. Each job can then be tested on its own.
2. **One database module.** One place opens the database, and one file lists its tables.
3. **One recorder for the audit log.** It adds the consultation and the time itself. In v1 the same two details are typed out at every one of 97 places.
4. **One way to acknowledge a warning.** v1 has five banners, four near-identical routes and four near-identical store functions.
5. **Audio is saved as it arrives.** v1 has a protocol to resume a dropped connection. On one computer that is not needed.
6. **A record of every model call:** what went in, what came out, how long it took. v1 never stored the assessments, so the live run of 495 could not be replayed as the model saw it.
7. **One shared kit for the benches:** replay, scoring, and a writer that cannot overwrite a baseline.

About what this saves, in lines of app code, from the audit:

| Change | Saved, about |
|---|---|
| Single user | 2,180 |
| History out of the code | 1,500 to 2,000 |
| One question at a time | 1,610 |
| The barge-in detector not carried | 1,060 |
| One database module | 500 to 600 |
| One language model module | 250 to 300 |
| One acknowledgement, one audit recorder, one settings store | about 600 |

Together that is roughly half of v1's 15,116 lines, before the new features are added. The figures overlap a little, so it is a rough guide and not a sum.

What v1 did well and v2 copies: the auto-mode state machine with its table of legal moves; checks kept apart from the model call that feeds them; small modules that look after one table each; and the rule that a failed model call never stops the consultation.

## 7. First run, connecting, and the settings menu

### 7.1 First run

The first time the app opens, it walks the user through these steps, in this order. Each step is one screen.

1. **The statement.** Research and education prototype. Never real patients. The user ticks to accept.
2. **This machine.** The app looks at the computer and says what it found, in plain words. For example: no suitable NVIDIA card, so OpenConsult will use cloud models.
3. **Connect the language model.** Only shown when the choice is cloud. See 7.2.
4. **Connect transcription.** Only shown when the choice is cloud. See 7.2.
5. **Self-test.** The app transcribes a short clip that comes with it and checks the words. A broken install is found here (decision D46).
6. **Microphone test.** The user speaks a sentence and sees the level move on a meter.
7. **The user.** A title and a name, for example Dr Herath, and a password. The app uses the title and name wherever it names the doctor: Alba's handover line, and the letters.

About the one user:

- There is one user and no roles. There is no registration page, no users page and no admin.
- Step 7 works only from the computer the app is installed on, never over a network. On 4 Aug you removed the rule that made the first person to register an admin, because of the risk when the app is exposed. This keeps that protection. See decision D20.
- The app asks for the password each time it is opened.
- A forgotten password is reset by a command run on the computer itself. The patients and consultations are kept. See decision D26.
- The audit log stays. With one user it records what was done and when: every approval, every settings change, every deletion.

The user can leave after any step and come back. The app does not let a consultation start until the steps that its choices need are done, and it says which one is missing on the Start control itself (R15).

### 7.2 Connecting a cloud service

1. The screen names the service and gives the link where the user gets a key.
2. The user pastes the key.
3. The user presses Test connection. The app sends one very small request.
4. The screen shows Connected, or the exact reason it failed: wrong key, no credit, no internet, service down.
5. Only a key that passed the test is saved.

Three things to know:

- **Signing in is by key.** The Anthropic API uses a key from the Anthropic Console. It does not accept a Claude.ai username and password. So the connect screen is where the key goes in. It is not a username and password page. The same is true of the speech services.
- **The key is kept in the system's own secure store**: Credential Manager on Windows, Keychain on macOS, the Secret Service on Linux. It is never written to the database and never shown again. The page shows only Connected or Not connected, with a Test and a Remove button.
- **The test runs again** each time the app starts, and before each consultation starts. A consultation never begins on a connection that is down.

### 7.3 The settings menu

There is one user, so the settings belong to that user.

**A change takes effect at the next consultation. Never during one.** A consultation records the choices it started with.

| Section | What is in it |
|---|---|
| This machine | Read only. The graphics card and its memory, the local models present, the microphone. |
| Language model | Cloud, Gemma 4 QAT, or Qwen. With a local model, one model does every job. With cloud, an advanced view sets the Claude model for each job. |
| Transcription | WhisperX with pyannote, Nemotron, or cloud. |
| Connections | Each cloud service: Connected or Not connected, with Test and Remove (7.2). |
| Local models | What is installed on this machine, and the downloads on offer, each with its size (6.4). |
| Alba | Voice on or off. Auto mode allowed or not. Face on or off. |
| Teaching | Default difficulty. The timer. The cases a learner has flagged as wrong. |
| Thresholds | The gate thresholds, the retention days, Alba's share of the consultation time. Each shows its default. |
| You | Your title and name, and a change of password. Any change asks for the current password first (15.6). |

Rules for the page:

1. A choice this machine cannot run is shown, disabled, with the reason on the control itself (R15). For example: needs 24 GB of graphics memory, this machine has 8.
2. Choosing any cloud option shows one plain statement before it is saved: with this choice, the words spoken in the consultation leave this machine. The live page then shows a small cloud mark for the whole consultation.
3. API keys are handled as 7.2 says. A developer running from source may still put a key in the .env file.
4. Every change is written to the audit log: when, from what, to what.
5. The page holds about 30 settings at most. The many tuning values of v1 (auto mode alone has 36) become named constants in one file, each with its reason. They are not settings.

## 8. Patients and earlier consultations

### 8.1 The Patients page

It replaces v1's Today tab and the walk-in queue. See decision D21.

- **Search.** One box. The user types part of a name, or a date of birth. Each result shows the name, the date of birth, the sex, and the date last seen.
- **New patient.** Name, date of birth and sex. All three are required. R11 needs the date of birth and the sex. The app works out the age on the day of each consultation. See decision D22.
- **The patient's page.** The details, then every consultation, newest first, each with its date and its state: approved, or waiting for review. Each one opens, with its note, its transcript and its recording (8.8). One button: New consultation.
- The page carries the standing statement: acted patients only (R1).

### 8.2 Starting a consultation: the Start screen

Every consultation passes through this screen, for a new patient and for one seen before.

1. The user searches and opens the patient's page, or makes a new patient.
2. The user presses New consultation.
3. The Start screen shows the name, date of birth and sex in large type. The user confirms this is the right patient (R17), and that the consultation is acted (R1).
4. If the patient has earlier approved notes, the screen lists them by date, with one switch: use earlier consultations as background. The switch is on, and the user can turn it off for this consultation: your ruling of 4 Oct (D25).
5. The user picks the intended consultation time from a list: 15, 30, 45 or 60 minutes (9.8). The list opens on the time used last. See decision D38.
6. The user presses Start.

### 8.3 What the earlier context is

- **Only notes the doctor approved** (R25). A draft or a refused note is never used. A deleted consultation is gone from the context too.
- **The last three approved notes**, newest first, each with its date. They are cut to a fixed length, so they do not crowd out today's transcript. See decision D23.
- **No summary written by a model.** A running summary would be one more draft for the doctor to check, and one more place for an error to hide. The approved notes are already checked.

### 8.4 Who gets it

| | Gets the earlier notes? | Why |
|---|---|---|
| The doctor's screen | Always | A panel on the live page shows the earlier notes, whatever the switch says. |
| The assessment call | Yes, when the switch is on | Past history and regular medicines change the differential. |
| The alarm call | Yes, when the switch is on | The same history can change what is urgent. |
| Alba's area and question calls | Yes, when the switch is on | The history changes which areas matter and which questions come first. |
| The note | No | Today's note records what was said today, and cites today's transcript (R4). |
| The letters | No | A letter is drafted from today's approved note only (R5). |

See decision D24.

### 8.5 How the model is told

The earlier notes go in their own block, after the patient line and before today's transcript. The block is headed as background from earlier consultations, approved by the doctor, and each note carries its date.

The prompt says two things and no more: this is background, and today's problem may be new and unrelated to it. It does not tell the model to keep an earlier diagnosis. On 30 Sept you ruled that locking on an earlier answer is not how a good doctor thinks. The same holds across consultations.

While the switch is on, the decision support panel shows a small mark: earlier notes in use.

### 8.6 Measured before it is kept

This changes what the model reads, so your standing rule applies: it is measured before it is kept.

1. You write or approve at least two follow-up cases. In one, the history is the key to the diagnosis. In the other, the history is a distraction and today's problem is new. See decision D27.
2. You set the pass marks before any run.
3. The bench runs each case with the background and without it.
4. The marks: does the background help where it should, does it mislead where it should not, and does the alarm still fire when it must.

If the bench fails, v2.0 ships with the doctor's panel only. The doctor sees the earlier notes and the model does not.

### 8.7 Risks, said plainly

- **It looks more like a record system.** A patient list with search is what a clinical system has. OpenConsult is not one. That makes R1 matter more, so the statement is on the Patients page and the acted confirmation is on every Start.
- **The wrong patient.** A consultation filed under the wrong person puts the wrong history in front of the model. R17 is the guard.
- **Cloud.** With a cloud model, the earlier notes leave the machine with the transcript. The cloud statement says so.

### 8.8 Listening to a past consultation

Your request of 4 Oct. When you open a consultation from a patient's list, you can read the note and the transcript, and you can also hear it.

- **A player on the consultation's page.** Play, pause, and a bar you can drag to any point. The time is shown.
- **Press a line, hear that line.** Every line of the transcript knows when it was spoken. Pressing a line plays the recording from there, and the line being played is marked as it goes. This is the quickest way to check a doubtful word against what was really said.
- **A loudness strip.** A simple picture of how loud the recording is along its length. Silence, a voice that is too quiet, and distortion show at a glance.
- **Alba's parts are marked** on the bar. The recording holds everything the microphone heard, her voice included, even though her words are kept out of the transcript (R6).
- **Warnings link to the sound.** Where the page warns that a passage may be missing (11.5), one press plays that stretch.
- **When the audio has gone.** Recordings are deleted after the retention time. The player then says so, with the date, in the place where the player would be (R15).

The audio is played only to you, from this computer. See decision D51.

## 9. Alba's questions in auto mode

### 9.1 What changes, and why

In v1, each decision support pass proposed up to four questions. A queue merged them, a re-ranker ordered them, and Alba asked from the head of the queue. It was built that way because a MedGemma pass took about 18 s. Questions had to be made ahead of time, or the patient would wait.

Gemma 4 answers in a few seconds. So the queue is no longer needed. Alba asks one question at a time, and each question is made after the last answer.

### 9.2 The loop

1. Alba gives the invitation. The patient tells their story, uninterrupted. This part does not change.
2. The patient stops. The end-of-turn check decides the turn is over. This does not change either.
3. The question call runs. It is given:
   - the patient line;
   - the patient's opening story;
   - every question Alba has asked, with the answer it drew;
   - the current differential, by name;
   - the area of the history Alba is in (9.7);
   - the time left for questions (9.8);
   - whether this is the time for open or closed questions.

   It gives back one question, or it says there is nothing more worth asking in this area.
4. Code checks the question. It must be one sentence, it must be a question, and it must not advise, reassure, interpret or name a diagnosis (R7). It must not match a question Alba has already spoken (R28). A question that fails is never spoken. The call is tried once more. If that fails too, Alba hands over to the doctor.
5. Alba speaks the question. The server records the exact words it sent to the speaker (R14).
6. The patient answers. Code waits for the final text of the whole answer before it goes on; in v1 a turn could end before its last words had been written down. The wait has a short fixed limit, so it can never leave Alba silent (R26). The answer is then paired with the question.
7. Back to step 3.

The loop ends when every area has been covered and the model has nothing more to ask, when the time for questions is used and nothing justifies more (9.8), or when the doctor takes over. Alba then hands over, naming the doctor: thank you, Dr Herath will examine you now.

The alarm does not end the loop. It pauses it (R8). The doctor then chooses: Alba carries on, or the doctor takes over.

The decision support panel still shows the assessment's own list of questions. In a consultation without Alba, the doctor taps one to have it asked, as now.

### 9.3 What this fixes that v1 could not see

In v1 the model never saw Alba's questions. R6 keeps Alba's words out of the transcript, and no model call was given them another way. So in auto mode the assessment read the patient's answers with no questions beside them. A bare No, or About two weeks, tells a reader very little.

Your design fixes this at the root. The model reads each answer beside its question.

The same gap exists in two other places, and the pairs can close it there too:

- **The assessment and alarm calls** in auto mode. See decision D29.
- **The note.** Today the note model also reads the answers without the questions. See decision D30.

### 9.4 R6 stays, and is said more exactly

The question in a pair comes from the server's own record of the words it sent to the speaker. It never comes from the microphone. The transcript still holds only what people said, and a claim in the note can still cite only what a person said. What changes is that the server's own record of a question may be shown beside the answer it drew, to a model and to the doctor.

### 9.5 A fresh request every time

Each question call is a fresh request that carries every pair so far. This fits two of your rulings. Task 3f closed the kept window. And on 2 Oct you ruled that with a fresh window the whole list of asked questions goes each time.

Your words, the answer goes back to Gemma 4 with the question, could also be built as one running conversation. Task 3f tested that shape for the assessment and the alarm, not for a question call. See decision D28.

### 9.6 The wait the patient feels

This is where the new design costs something, so it is said plainly.

In v1 the next question was ready before the patient finished. On run 492 Alba spoke 2.3 s after the turn ended. In the new design the question is made after the answer, so the patient waits for the end-of-turn check, then the call, then the voice.

Three ways to keep the wait short. Each is measured, not assumed.

1. **Start early.** The question call starts at the first pause, while the end-of-turn check is still deciding. If the patient goes on talking, the result is thrown away.
2. **Keep the call small.** It writes one sentence. A full assessment pass writes far more. So it should take well under the time of a full pass.
3. **A short acknowledgement.** Alba may say a word or two the moment the turn ends, such as Okay or I see. R7 already allows it. v1 teaches caution here: its filler phrases landed into finished answers, and one set itself off again and again. So at most one in each wait, and it never counts as the patient speaking (R27).

The target, by your ruling of 4 Oct (D32): Alba starts speaking within 3 s of the patient's last word, and may say one short acknowledgement while the question is made.

### 9.7 Keeping Alba on course: signposting

One question at a time follows the conversation better. Its risk is that it wanders and never asks the question that matters. Run 495 failed in exactly that way: the gynaecological history was never asked.

Your answer is the one GPs use, and the name is right. Signposting comes from the Calgary-Cambridge guide to the consultation. The doctor tells the patient what comes next: I would now like to ask about your general health. It gives the interview a structure that both people can see.

For Alba it does two jobs. It keeps the model inside one area at a time, so it cannot drift. And it makes sure the areas this presentation needs are each opened.

**How it works**

1. **The area call.** After the patient's opening story, one small call reads the patient line, the story and the current differential. It lists the areas of the history that this presentation requires, the most important first. The areas come from a fixed list (below). This is the context-aware systems review you named on 29 Sept as the thing that was missing.
2. **One area at a time.** Each question call is told the current area and asks within it. It still prefers the question that would rule the most serious diagnosis in or out.
3. **Closing an area.** When the model has nothing more to ask in the area, the area is closed.
4. **Looking again.** The area call then runs again on everything said so far. An answer can make a new area necessary, and the list is allowed to change.
5. **The signpost.** Before the first question of a new area, Alba says where she is going. Code builds the sentence: a fixed opening, then your wording for the area. For example: I would now like to ask about your periods. The model chooses the area. It never writes the sentence.
6. **No early handover.** Alba does not hand over to the doctor until every area on the list has been opened. There are three exceptions: the time for questions is used and nothing justifies more (9.8), the question call fails twice (9.2), or the doctor takes over.
7. **The doctor sees the plan, and can change it.** The live page shows the list of areas: done, current, to come. One tap adds an area or takes one off. This gives back what the queue gave the supervising doctor in v1, a view of what Alba will do next.

**Why code builds the sentence**

R7 says Alba asks and acknowledges, and nothing else. A signpost is a statement, so it widens R7, and that is your decision (D34). Building it in code from a fixed list keeps the rule safe: a signpost can name an area of the history, and it cannot carry advice, reassurance or a diagnosis, because the model never writes it.

**The list of areas**

This is clinical ground, so the list and its spoken wording are yours (D35). Your ruling of 4 Oct: the draft stands. It stays yours to correct at any time. The draft is the usual systems review, plus the other parts of a history. You named Gray and Toghill as your model for the clinician's approach.

| Area | A draft of the spoken wording |
| --- | --- |
| The presenting problem in detail | this problem in a bit more detail |
| General health | your general health |
| Heart and circulation | your heart and circulation |
| Chest and breathing | your chest and breathing |
| Stomach and bowels | your stomach and bowels |
| Urinary | your waterworks |
| Periods and pregnancy | your periods |
| Sexual health | your sexual health |
| Nerves, head and senses | headaches, your eyesight and your nerves |
| Joints and muscles | your joints and muscles |
| Skin | your skin |
| Mood and mental health | how you have been feeling in yourself |
| Past illnesses and operations | your health in the past |
| Medicines and allergies | your medicines and any allergies |
| Family history | your family's health |
| Home, work, smoking and alcohol | home, work and day to day life |
| Ideas, concerns and expectations | what you have been thinking about all this |

The draft had 16 areas. It now has 17. Sexual health was sharing a row with periods and pregnancy. It applies to men too, and Alba's signpost for a man must not say periods. So the two are separate rows.

**The model chooses the relevant areas from this list.** This is your ruling of 4 Oct. The area call is given the whole list and the patient line, and it picks the areas that are relevant to this patient and this presentation. An area that cannot apply is simply never picked: a male patient is not asked a gynaecological history. No code filter does this.

There is evidence the model uses age and sex in this way. In Task 5b, the patient line stopped the ectopic pregnancy alarm in the boy with testicular torsion.

The doctor keeps the last word. The list of areas is on the live page, and the doctor can add an area or take one off with one tap. See decision D37.

**No code rule for which areas are required, or for which are left out.** The model decides both, from the patient line and the presentation. That follows your 30 Sept ruling: a code rule to keep the dangerous diagnosis on the list was parked, because the prompt should do it and the bench will show whether it does. The same holds here. Two things are different from run 495: the model now has the patient's age and sex, and the bench marks this directly (9.9). If the bench shows the model opening an area that cannot apply, or missing one that must be opened, that is the moment to think about a rule in code. Not before.

**The cost to the patient.** Too many areas makes an interrogation. The area call is asked for the areas this presentation requires, not every area. The bench counts areas opened that were not needed.

This is the history scaffold of v1.1 Task 8, brought into v2.0 in this form. See decision D31.

### 9.8 Using the time well

A GP works to the clock. So does Alba.

**The box.** Before Start, the user picks the intended consultation time from a list: 15, 30, 45 or 60 minutes.

One change from your wording. You placed the box where the patient's details are entered. The details are entered once, and the same patient may have a 15 minute visit one day and a 45 minute visit the next. So the box is on the Start screen (8.2), which every consultation passes through, for a new patient and for one seen before. See decision D38.

**Alba's share.** The intended time covers the whole consultation: the history, the examination, the explanation and the plan. Alba does only the history. Your ruling of 4 Oct, for now: Alba can take 75 % of the intended time.

| Intended time | Alba's time for the history | Left for the doctor |
|---|---|---|
| 15 minutes | 11 minutes 15 seconds | 3 minutes 45 seconds |
| 30 minutes | 22 minutes 30 seconds | 7 minutes 30 seconds |
| 45 minutes | 33 minutes 45 seconds | 11 minutes 15 seconds |
| 60 minutes | 45 minutes | 15 minutes |

The share is one value on the settings page, under Thresholds. You can change it there without any change to the code. See decision D39.

This is a guide, not a target. When every relevant area is covered sooner, she hands over sooner. She may also run over, as set out below.

**Code keeps the clock. The model gets a countdown.** A language model cannot feel time passing. So code measures it and puts the time remaining, as one plain line, into each call:

- The area call is told how long Alba has. With little time it picks fewer areas, the most important first.
- Each question call is told how many minutes are left, and about how many more questions that allows. Code works that out from how long the questions and answers have taken so far in this consultation.

**What the model is asked to do with it.** Ask the most important question first: the one that would rule the most serious diagnosis in or out. Leave the less important areas for last, so that if time runs out, those are the ones not reached.

**The patient is never hurried.** Time changes which questions Alba asks. It never changes how long the patient may speak. Alba does not interrupt, and the patient's uninterrupted opening story is not shortened.

**The time is a guide, not a wall.** This is your ruling of 4 Oct. The model sees the countdown, and it is told that Alba may run over when the consultation needs it. Two cases:

- **The patient needs the time.** For example, a patient who is crying and goes on to describe detailed psychological and social symptoms. Alba does not cut this short to keep to the clock.
- **High priority questions are still to be asked.** Alba asks them before she hands over.

What does not justify running over: low priority areas. Those are left, and shown to the doctor as not reached.

When Alba is over time, the live page tells the doctor so, with the reason in a few words. The doctor can stop her with one tap, as always (R8). There is one upper limit: the whole of the intended time. At that point Alba hands over to the doctor, whatever is left to ask. The doctor can also take over at any point before that. Both are your ruling of 4 Oct. See decision D42.

**When Alba's time is used and nothing justifies more.** Alba hands over to the doctor. The live page then shows the doctor which areas were not reached, and the consultation keeps that list. Nothing is skipped silently. See decision D41.

**The alarm takes no notice of the clock.** It runs at every pass as before.

**For the doctor.** The live page shows a quiet clock in every consultation, with or without Alba: time used, against the time intended. See decision D40.

### 9.9 Measured before it is kept

The bench needs a patient who can answer any question. Teaching mode builds exactly that: a patient who answers only from a case card (section 12). So the question call interviews the case-card patient, with no room and no actor, as many times as needed. This is a bench. It runs outside the app's own consultations, so teaching mode stays apart from the clinic (R24).

1. The cases: the three auto-mode scripts (16, 17 and 18, the ectopic pregnancy), and others you choose.
2. You set the pass marks before any run.
3. Each case is run at a short time and at a long time, for example 15 and 60 minutes. One case has a distressed patient, to check that Alba gives the time and does not cut the patient short.
4. The marks:
   - at the short time, whether the questions that must be asked were asked before the time ran out;
   - at the long time, whether Alba added areas that were not needed;
   - how much of the script's marking scheme the interview drew out;
   - whether the area that must be opened was opened, and how soon (on script 18, the periods area);
   - any area opened that cannot apply to this patient;
   - questions repeated;
   - seconds for each call.

Then the room, in two steps. First with the stand-in patient (13.5), as often as needed. Then one consultation with Alba and a human actor.

### 9.10 What goes and what stays

Goes: the queue and its merging rules, the re-ranker, the topic call, the lay-wording rewrite, and making the next question's audio ahead of time. In v1 the queue module alone is 557 lines, and its two test files are 2,239 lines.

Stays: the state machine (the invitation, the patient's uninterrupted story, open then closed questions, the pause on the alarm, the handover), the end-of-turn check, and the check on what Alba may say.

Carried from the room. Each of these was learnt in consultations 482 to 496, and the new loop keeps them as rules (R26 to R30, R32 and R33):

- Silence is judged by code, from sound. The model can never leave Alba silent.
- Alba's own voice never counts as the patient speaking.
- A turn must start before it can end. If the patient says nothing for 12 seconds, Alba asks once more, then moves on.
- Code refuses a question already asked.
- Auto mode does not show as on until the patient has heard that they are talking to a machine.
- An acknowledged alarm never pauses Alba again.
- The alarm goes first, then Alba's question, then the assessment.

The two frozen v1 documents, the evaluation plan for auto mode and the open-to-closed rule, describe the v1 design. They stay in the v1 branch. If the study is run on v2, it gets a new plan written before any run.

## 10. Language models

### 10.1 The list

| Choice | Model | Runs |
|---|---|---|
| Local, default | Gemma 4 QAT (gemma4:26b-a4b-it-qat) | Ollama |
| Local | Qwen3.6-35B-A3B | Ollama |
| Cloud | Claude | Anthropic API |

The list is curated. A model enters it only after it passes the bench on the v2 cases, with pass marks you set before the run. Qwen enters once its answer order is fixed, as you ruled on 2 Oct.

### 10.2 The jobs

| Job | Needs |
|---|---|
| Assessment (differentials, questions, signs) | Fast. Every pass. |
| Alarm | Fast. Every pass. Its own call. |
| Alba's next question | Very fast, small. After every answer. |
| The areas of the history this presentation requires | Fast, small. After the opening story, and after each area closes. |
| End of turn, affect | Very fast, small. |
| Note | Careful. Not time-critical. |
| Letters | Careful. Not time-critical. |
| Guideline summary | Careful. |
| Teaching: writing the case | Careful. The strongest model available. |
| Teaching: the patient's replies | Fast. |
| Teaching: feedback | Careful. |

With a local model, one model does every job, so nothing reloads. With cloud, each job uses the most practical Claude model for that job, as you ruled on 29 Sep. Which Claude model suits which job is settled by a bench, not by this spec.

### 10.3 Which is the default

- On a machine with a suitable NVIDIA card (6.4): local, Gemma 4 QAT.
- On any other machine, and on every Mac: cloud.

The app never switches by itself after that. The user changes it on the settings page.

### 10.4 Rules

- A local model keeps the settings that make it answer as steadily as it can (temperature 0, seed 42). Where a cloud model cannot do the same, the consultation records that.
- A cloud model is never the silent fallback for a local one, or the other way round. If the chosen model cannot be reached when a consultation is about to start, the app says so on the Start control and does not start (R15). Once a consultation is running, a failed call never stops it (R30).

## 11. Transcription

### 11.1 The three choices

| Choice | During the consultation | At Stop |
|---|---|---|
| WhisperX with pyannote | faster-whisper gives the live text | The language model unloads, WhisperX and pyannote load, and the recording is transcribed again with speaker labels. |
| Nemotron | Nemotron speech and Nemotron speaker labels run live | Nothing loads or unloads. The transcript is complete at Stop. |
| Cloud | A cloud service returns text and speaker labels live | Nothing loads. Works on a laptop with no graphics card. |

### 11.2 Cloud is feasible

Several services now return live text with speaker labels. Two candidates to bench:

- Speechmatics. A UK company. It has a medical model and speaker labels.
- AssemblyAI. Live speaker labels and a medical mode.

Before either is used, Cowork checks where each one stores and processes audio, and what their terms say. This is the lesson of the 15 Sept Show HN: check the gate before building the plan.

### 11.3 Which is the default

On a machine with no suitable NVIDIA card (6.4), the default is cloud. That includes a smaller card that could run speech alone: it starts on cloud, and the user may switch speech to local in settings. Which cloud service is decided by the bench.

On a machine with a suitable card, the default is not decided here. It is decided by the bench on the new recordings (section 13), judged by your 4 Oct principle: what matters is the clinical outcome, not small snippets of speech that differ.

What Task 17 reported on seven recordings. It is not yet checked by Cowork, and it is to be confirmed on the new recordings:

- WhisperX changed the meaning in the fewest places (31). But it dropped whole passages on six of the seven recordings, with no sign on the page. Task 18 found the cause: a hint text given to the final pass since 17 July. Task 19 removed the hint, and the lost safety nets came back. The count of 31 has not yet been repeated on the fixed WhisperX.
- The Nemotron English streaming model, on its own, came closest (34) and dropped no whole line. Its errors show on the page as garble.
- The Nemotron live pair that Task 13 put in the app changed the meaning in the most places (71).
- Neither set of speaker labels is good. Pyannote put 75.5 % of words with the right speaker. The Nemotron live pair put 62.2 %.

So if Nemotron is used, its English model runs on its own for the words. That is the advice of LESSONS_FOR_V2, lesson 10. The bench on the new recordings confirms it or not.

**Drug names are not solved.** The hint that caused the drops was there to help with drug names. Without it, WhisperX catches 37 of 53 drug and test names, and missed gliclazide 3 times out of 3. v2 needs its own answer. The ideas so far: correct names when the note is written, check the transcript against a drug list, or listen again to a short piece. This is settled in the brainstorm for stage 5, and the bench counts drug names (13.3).

Which is worse for the patient, fewer errors that include silent drops, or more errors that show as garble, is a clinical judgement. It is yours.

Nemotron gives no confidence score. So the quality gate cannot measure it, and every Nemotron transcript is flagged for the doctor. That was your Task 13 ruling and it stays.

### 11.4 One rule for all three

Every choice gives the app the same thing: lines of text, each with a speaker, a start and end time, and a confidence score or none. The gate, the note and the review page work from that and do not know which choice made it.

### 11.5 What v1 taught about speech

Each of these is a rule for every speech choice. The evidence is in V1_LESSONS.md, sections 1, 2 and 7.

1. **No words from silence.** v1's live transcript wrote Thank you. into silent stretches, about fifteen times in one consultation. Alba now acts on the live text, so this matters more.
2. **Nothing dropped without a sign, whatever the speech model.** With WhisperX there are two transcripts: the live one and the final one made at Stop. The final is set against the live, and any passage heard live and missing from the final is shown to the doctor. v1 gained this check on 4 Oct (Task 19), for gaps of 5 seconds or more. With Nemotron and cloud there is only one transcript, so the check is made against the sound itself: a stretch where someone is clearly speaking and no words were written is shown to the doctor. See decision D45.
3. **The microphone settings are chosen, not left to the browser.** In v1 the browser's own noise and volume processing was on by default, and every loudness threshold was measured on processed sound. v2 sets them on purpose and records them with every recording.
4. **Who spoke is asked, not guessed.** Three ways of guessing were tried in one day in July and each failed somewhere. The question is asked at Stop, before the transcript is made final, and the app waits for the answer. One idea to bench, because v2 has one user: the doctor's voice is learnt once, at first run, and every line is then marked doctor or not doctor. See decision D53.
5. **Each choice says what it can provide.** Nemotron gives no confidence score. The gate measures what it can and flags what it cannot.
6. **A first-run self-test.** The app transcribes a short clip that comes with it and checks the words. A broken install is then found at once, not at the first Stop. See decision D46.
7. **Every change to the speech path is tested on whole recordings for dropped speech.** The July hint was checked for drug names only. Nobody looked for missing speech for eleven weeks.
8. **Alba's words are removed word by word, never as a whole stretch.** v1's rule dropped the patient's words that fell between Alba's sentences. With one question at a time this matters more.

## 12. Teaching mode

### 12.1 What the learner does

1. The learner picks a topic from the RCGP curriculum list, or asks for a surprise. They pick a difficulty.
2. The app presents the patient: name, age, sex, and what the patient says first.
3. The learner takes the history by speaking. The patient answers in a voice. Typing works too.
4. The learner says what they would examine. The app gives the findings for what was asked. A button then shows the rest. See decision D10.
5. The app asks three questions, one at a time: What is your differential diagnosis? What investigations would you order? What is your plan, and does this patient need a referral?
6. The app gives feedback.

### 12.2 The case card

Before the patient speaks, the app writes a hidden case card. Everything afterwards comes from the card.

The card holds: who the patient is; the opening words; the history; the patient's ideas, concerns and expectations; any hidden agenda; the examination findings; the results of any tests; the expected differential, with the diagnosis that must not be missed; the expected investigations; the expected plan, with referral and urgency; the safety-net advice; and the marking points.

### 12.3 Rules that protect the learner

A learner who is taught something wrong is harmed. So:

1. **The patient never invents a positive finding.** If the learner asks about something that is not on the card, the patient answers as a patient would when the answer is no.
2. **The patient answers what was asked.** An open question gets the story. A detail comes out only when asked for. Ideas, concerns and expectations come out only if the learner asks or picks up a cue.
3. **The patient never gives medical advice and never names the diagnosis.**
4. **Feedback comes from the card, and quotes the learner's own words.** It does not come from the model's opinion on the day.
5. **Every case is labelled.** A case written by the model shows: AI-written, not reviewed by a clinician. When a clinician approves a case, it joins a bank and loses the label.
6. **The first bank is yours.** The 16 mock scripts already in the repo were written by a clinician and have marking schemes. They become the first approved cases.
7. **The learner can flag a case as wrong.** The flag is kept with the case, and the settings page lists the flagged cases.

### 12.4 Feedback

In this order:

1. The most important thing that was missed. One item. A red flag not asked about comes before everything else.
2. What was done well. Up to three items.
3. The differential, the investigations and the plan, each set against the card.
4. The marking points, grouped under the three headings the RCGP uses in the SCA: data gathering and diagnosis; clinical management and medical complexity; relating to others.
5. Whether the learner signposted. See decision D36.

v2.0 gives no pass or fail and no grade. A grade from a language model would look more certain than it is. Your ruling of 4 Oct: yes, for now (D5).

### 12.5 The RCGP curriculum

The topic menu uses the titles of the RCGP topic guides. There are 22 clinical topics, from Allergy and clinical immunology to Urgent and unscheduled care, and four life-stage topics.

The curriculum is the RCGP's copyright. v2 uses the topic titles as a menu and ships no curriculum text. The page says that OpenConsult is not affiliated with or endorsed by the RCGP. Before stage 10 starts, Cowork reads the RCGP's reuse terms and reports to you, as was done with NICE.

### 12.6 Voices and timing

- The patient speaks in a Piper voice chosen to fit the case. Alba's voice stays Alba's.
- The examiner's three questions appear on screen and are spoken in a second voice.
- A timer of 12 minutes can be switched on, as in the SCA.
- The face is not used in teaching mode in v2.0. See decision D6.

### 12.7 Kept apart

Teaching mode has its own tables and its own pages (R24). In the clinic the machine's voice is kept out of the transcript. In teaching the machine is the patient. The two must never share code paths that could confuse them.

## 13. The new recordings

### 13.1 Why

Every speech choice and every model is judged on the same clean set. The old recordings were made through the app, some before the capture fix of 29 July, and several were later overwritten.

### 13.2 How

1. **Who:** two actors. You as the doctor, a second actor as the patient. Friday 9 Oct.
2. **What is read:** the mock scripts. Start with the five where the most is at stake: 15 cauda equina, 14 giant cell arteritis, 01 chest pain, 03 diabetes review (drug names), 18 ectopic pregnancy. See decision D7.
3. **How it is captured:** a plain recorder on the computer in the room. One microphone. WAV, 48 kHz. Noise suppression and automatic gain switched off. Not through the app. The recording is then the same raw sound for every model.
4. **The first recording is a test.** Record one script. Play it back. Check both voices are clear. Only then record the rest.
5. **After each one:** note any line that was read differently from the script. Two minutes, while it is fresh.
6. **Banking:** the files go to a folder outside the repo. A small list records, for each file: the script, the date, the room, the microphone, who read which part, the length, and a checksum. The folder is then made read-only (R18).
7. **Consent:** both actors agree to the recording and to its use in benches. The recordings stay out of the public repo, as you decided on 4 Aug.

### 13.3 The marks, set before any run

1. Passages dropped. Safety nets are counted on their own.
2. Words where the meaning changed. Lost and added negations are counted on their own.
3. Drug names caught, out of drug names spoken.
4. Lines given to the wrong speaker, where it changes the clinical meaning.
5. Seconds from a word being spoken to it showing on the page.
6. What reaches the note. The note is written from each transcript, at least twice, and the notes are compared. Your principle: the clinical outcome is what matters.

You set the pass mark for each before the first run.

### 13.4 Replay

A bench feeds a banked recording into any speech choice, at the speed of a real consultation or faster. So one afternoon of recording serves every later comparison.

How the speech bench is run. These come from LESSONS_FOR_V2, lessons 8 and 9:

1. The recording is fed straight in, in pieces the size the live page sends. It is never played through a speaker for this. A speaker and a second microphone would change the sound and blur the comparison.
2. Only recordings made with the current microphone settings are used.
3. Recordings are chosen from the banked list, never by searching for a file type. A search for one file type once missed the best recordings.
4. One recording is not a test.
5. Where every model agrees against the script, it is taken as spoken that way.
6. Each note is written at least twice, to measure chance.

This does not clash with the stand-in patient (13.5), which does speak through the speaker. That is a different test. It checks the whole chain in the room, and it is never used to score a speech model.

### 13.5 The stand-in patient: room tests without an actor

Your idea of 4 Oct. A second actor is hard to find, and is free only on some days. So the teaching mode's patient stands in.

**What it is.** The case-card patient of teaching mode (12.2), given a voice of its own, speaking out loud in the room. The app's microphone hears it as it would hear a person.

**What it lets you do, alone, on any day:**

- Run an auto-mode consultation: Alba asks, the stand-in answers.
- Run an ordinary consultation: you are the doctor, the stand-in is the patient.
- Run a whole consultation with no person at all: a second voice plays the doctor and reads the doctor's lines from a mock script, and the stand-in patient reads the patient's. The app hears two voices in the room and treats them as two people. Because the script is known word for word, the transcript can be checked exactly.
- Record either one, and run it again exactly the same way after a change. A human actor can never repeat a consultation exactly. The stand-in can.

**How it stays honest.**

1. **It is a test tool, outside the app.** The app does not know the patient is a machine. It hears a voice in the room. So nothing in the clinic's code changes for it, and teaching mode stays apart (R24).
2. **Alba's voice is still kept out of the transcript (R6). The stand-in's voice is not,** because it is the patient. This is why it must be a separate tool: the app mutes only what it speaks itself.
3. **The two voices are different voices, and neither is played by the app itself.** Both come from the test tool. If the app played one of them, it would mute it as its own speech and that side of the conversation would be missing.
4. **Every consultation with a stand-in is marked as one,** on the Start screen and in the record. Results with a stand-in are never mixed with results from human actors.

**What it cannot do. Said plainly.**

A machine voice is clear, even and tidy. A real patient hesitates, trails off, mumbles, talks over the doctor, and cries. So:

- **It cannot choose the speech model.** Speech models will score better on a machine voice than on a person. The two-actor recordings (13.2) are still what that choice rests on.
- **It flatters turn-taking.** Its answers end cleanly. Some pauses and hesitations can be written into its answers to make it harder, but it is not a person.
- **It cannot stand for a distressed patient.**

So there are three steps, each cheaper than the next:

| Step | What it is | What it finds |
|---|---|---|
| 1. The bench | Text only, no sound | Wrong questions, missed areas, repeats |
| 2. The stand-in patient | Sound in the room, no actor | Delays, Alba's voice being heard as the patient, timing faults, the whole chain from microphone to note |
| 3. A human actor | A real second voice | What only a person shows: hesitation, overlap, real speech |

The rule that the room finds what the tests cannot (V1_LESSONS, the first of the twelve) is now cheap to follow. Step 2 can be run after every sub-stage. Step 3 is kept for the end of a stage, and for the recordings.

**Running with nobody there.** Your point of 4 Oct: a consultation with no person can run while you are away. So it must start, run and finish by itself.

- It is started from a distance, by Claude Code or on a timer. Nobody presses anything in the room.
- Many can run in a row: every mock script, after every change.
- Each run leaves its recording, its transcript, its note and a short report in the log folder. The report puts the most important finding for the patient first.
- You read one summary when you are back. Cowork reads the rest.

**Two ways the sound can travel.**

| Way | What it is | What it needs | What it tests |
|---|---|---|---|
| Through the air | The voices play from a speaker and the microphone hears them | The speaker and microphone left switched on at home | Everything, including the room and whether Alba's own voice is heard as the patient |
| Through the wire | The voices are fed straight into the app, with no speaker | Nothing | Everything except the room |

Through the air is the one you chose on 4 Oct, because it best copies the room. It is the normal way, with you in the room or with nobody there. Through the wire is kept as a small extra for the cases where sound is not wanted.

**Where the voices come from.** Both virtual actors speak through the monitor's speaker, to keep things simple. This is the same whether you are in the room or out. The computer may speak in the empty room while you are away. Your rulings of 4 Oct; see decisions D49 and D50.

See decisions D47 and D48.

## 14. GitHub

### 14.1 During the build

1. A new branch called v2 is made inside the OpenConsult repo. It starts empty. It shares no history with main.
2. It is checked out in its own folder on mlrig: /home/indy/Projects/OpenConsult2.
3. v1 stays in /home/indy/Projects/consultation-ai. Nothing in that folder is touched by v2 work. Since 4 Oct the v1 service on mlrig is stopped and no longer starts at boot (15.8, ruling 3). Its files, its database and its recordings are kept, and it can be switched back on.
4. v2 runs on port 8001 with its own database file. On mlrig it runs from the source folder, not from the installer.
5. Only one of the two apps holds models on the graphics card at a time. With the v1 service off, v2 has the card to itself. If v1 is ever switched back on, it is stopped again before v2 runs.
6. You push after every stage and sub-stage, as now.

### 14.2 What happens on main meanwhile

**v1.1 development stopped on 4 Oct, by your decision.** main takes no new work. Everything up to Task 19 is on GitHub (commit b2e61d0).

What may still happen on v1:

- **One last release.** The v1.0.0 release on GitHub still has the fault that drops speech. The fix is on main. A last tagged release, with a short note to users, closes v1 cleanly. See decision D52.
- **Report-only benches.** Until v2 has its own bench (stage 5), a bench may still run on v1's code. It changes nothing in v1.

Loose ends in v1 that are yours to close or to leave:

- The seven approved records with gaps: regenerate their transcripts, or leave them.
- The audio of one lost consultation: restore it from its copy among the mock recordings, or leave it.
- The service restart, so that the Task 19 fixes are live on mlrig.

The prompts and the lessons move to v2 as files. See decision D8.

### 14.3 At release

1. The last v1 commit is tagged v1-final. A branch called v1 is made there, for any later fix.
2. Claude Code makes one commit that joins v2 to the v1 history and keeps only the v2 files.
3. You push, and main moves forward to the join commit. No force push. Every existing clone keeps working.
4. You tag v2.0.0 and publish a GitHub release. Zenodo then adds a new version under the same concept DOI, provided its link to the repo is still switched on. Cowork checks that before the release.

Before step 2, v2 must hold the community files: CONTRIBUTING, SECURITY, the code of conduct, CITATION.cff and the issue templates, brought up to date in stage 16. The join keeps only the v2 files, so anything missing would vanish from main.

Cowork tested steps 2 and 3 on a scratch repo on 4 Oct. The push went through as a normal push, and main held only the v2 files.

After this, main holds the v2 code, and the whole v1 history is still behind it. The paper's evidence is untouched.

## 15. Build order

### 15.1 How we work

The team is as before: Wajira, then Cowork, then Claude Code. Wajira decides. Cowork designs, writes the prompts and checks the work. Claude Code builds.

**The model.** v2 is built only on Fable 5.1 at high effort, or on Fable 5.5 when it comes out. This holds for Cowork and for Claude Code. Every prompt for Claude Code names the model and the effort. It is your ruling of 4 Oct, and for v2 it replaces the earlier rule of Opus 5.5.

This rule is about the models that build OpenConsult. Which Claude model the app itself uses for each job is a separate matter (10.2).

Our thinking is patient focused. In teaching mode it is learner focused. Every design question is asked in that form first: what does this do for the patient, or for the learner?

**Every stage starts with a brainstorming session. So does every sub-stage.** This is your rule of 4 Oct. Its purpose is that your knowledge and skill go into the design before anything is built, not after.

A sub-stage is a part of a stage. A stage is split into sub-stages when it is too large for one Claude Code session.

### 15.2 The brainstorming session

It is a Cowork session with you, at the start of the stage or sub-stage. Nothing is built in it.

Your rules for it, 4 Oct:

- **Cowork is very brief and to the point.** A lot of text is overwhelming.
- **Higher concepts, not detailed specifics.** The concepts are what you bring and want to debate. The specifics are Cowork's job, and they go into the spec, not into the conversation.
- **Plain words.** No developer terms. Where one cannot be avoided, it is explained in a sentence.

1. Cowork opens with what the stage is for, in one or two sentences, from the patient's or the learner's side.
2. Cowork says what is already decided, and what the code and the benches have shown. Briefly.
3. Cowork puts the open questions to you, one at a time.
4. You bring what you know: how a GP does this, what goes wrong in a real room, what the patient or the learner needs.
5. Cowork writes the decisions into this spec, under the stage they belong to, with the date. One document, as always.
6. Only then does Cowork write the prompt for Claude Code.

**Prompts are discussed here, word for word.** This is your rule of 4 Oct (15.8, ruling 1). When a stage adds or changes a prompt that a model reads, Cowork puts it to you in this session in full, one prompt at a time. Nothing a model reads is built before you have approved its words.

The session of 4 Oct was the brainstorm for v2.0 as a whole. It was also the first brainstorm on Alba's questions: one at a time, signposting, and the use of time.

### 15.3 The cycle for every stage and sub-stage

1. The brainstorming session (15.2).
2. Cowork writes the prompt for Claude Code, as one block.
3. A new Claude Code session in the OpenConsult2 folder. One stage or sub-stage only. Its first commit is this spec as the brainstorm left it (15.5, ruling 3).
4. Claude Code writes its plan, including the tests it intends. You approve it.
5. Claude Code builds, with the suite green before each commit, and adds a HANDOVER entry.
6. Cowork checks the commits with git log and git show.
7. You do the one check named in the table below, and push.
8. Only then the next one.

Three rules from v1 sit on top of this cycle:

- **A room run early.** v1's auto mode was built in six stages with no room run, and the first run failed. Every stage that changes what happens in a consultation gets one consultation in the room as soon as its first part works. The stand-in patient (13.5) makes this possible on any day; a human actor closes the stage.
- **No stage builds on a report Cowork has not checked.**
- **Before each stage, Cowork and Claude Code read the part of V1_LESSONS.md that bears on it.**

One rule of yours, of 4 Oct, sits on top as well: **Claude Code never writes or changes a word a model reads.** The prompt for a stage gives the exact text, or says that no prompt changes (15.8, ruling 1).

### 15.4 The stages

| # | Stage | Done when you see |
|---|---|---|
| 1 | Open the v2 branch. This spec, V1_LESSONS.md, a short CLAUDE.md, a new HANDOVER, the licence files. | The v2 branch on GitHub, holding a handful of files. |
| 2 | The skeleton. The app starts, the SQLite database, the screen that sets up the one user, login, the password reset command, the audit log, and the settings store with the This machine section. A free GitHub check starts the base app on Windows, macOS and Linux at every push. | You set up your name, title and password on port 8001, log in, and the page describes mlrig correctly. The GitHub check is green on all three systems. |
| 3 | The language model door, the prompts as files, and the record of every model call. The CDS benches run through it. | The bench on Gemma 4 QAT gives the same marks as v1 does today. That is the proof the rewrite lost nothing. |
| 3b | The engine bench: the same cases on llama.cpp and on vLLM, against Ollama. A report only, then published in the repo (15.8). | The report, checked by Cowork. Then the folder engine-bench on GitHub. |
| 4 | The new recordings (9 Oct). Needs no v2 code. | The banked folder and its list. |
| 5 | The transcription door, the three workers, the microphone settings, the self-test, and the replay bench. | The bench report on the new recordings. You choose the default. |
| 6 | The live consultation, without Alba. A simple new-patient form and the Start screen with the acted confirmation and the intended time. Then transcript, CDS, alarm, the quiet clock, Stop, the who-spoke question, the check of final against live, the gate, note, review with the player for the recording (8.8), approve. | You run one acted consultation from Start to an approved note. |
| 7 | Patients: the list, search, the patient's page, a new consultation under a patient seen before. The earlier notes on the doctor's screen, then to the model once the bench of 8.6 passes. Retention, and deleting a consultation (D44). | You find a patient seen before, start a second consultation under them, and see the earlier note on the live page. |
| 8 | Letters and the guideline panel. | One letter drafted from an approved note. |
| 9 | The rest of the first run, the connect screens with their test, the cloud statement and mark, and the settings menu, complete. | You connect a cloud model, see Connected, then change the model on the page. The next consultation uses it and records it. |
| 10 | Teaching mode, typed. The case card, the patient, the three questions, the feedback. | You work through one case by typing. |
| 11 | Alba's voice: tap-to-ask and the sound check, with R6 proven. Then the stand-in patient (13.5): the case-card patient with a voice of its own, as a test tool. | One consultation where Alba asks a tapped question and her words are not in the transcript. Then one where you are the doctor and the stand-in is the patient. |
| 12 | Auto mode, as section 9 sets out: the state machine, one question at a time, signposting, the time budget, and each answer shown to the model beside its question. Benched first against the case-card patient from stage 10. | The bench report. Then auto-mode consultations in the room with the stand-in patient, alone. Then one with a human actor. |
| 13 | The face. | One consultation with the face on. |
| 14 | Teaching mode, spoken. | You work through one case by voice. |
| 15 | The installers. GitHub builds one each for Windows, macOS and Linux. The local pack download. | You install it on a Windows PC, connect a cloud model, and run one consultation. Then the same on your MacBook Air M1. |
| 16 | The help pages (your words), the README, the community files carried from v1 (15.5), and the release steps of 14.3. | v2.0.0 on GitHub, with the three installers attached. |

Stages 6, 12, 14 and 15 are the large ones. They are split into sub-stages. How they are split is settled in the stage's own brainstorming session.

The installer comes late, but it cannot be an afterthought. Three things keep it honest from stage 2 onwards: SQLite from the start, the base app that starts with no graphics card (5.1), and the GitHub check on all three systems at every push.

Typed teaching (stage 10) comes before Alba because it needs only the language model door. It also gives colleagues something to look at early. See decision D9.

### 15.5 Stage 1: opening the v2 branch

The brainstorm for stage 1 was on 4 Oct 2026. These are your rulings, in the order you gave them.

1. **The spec is approved.** 4 Oct 2026. From here it changes only by a dated ruling of yours, made in a brainstorm.
2. **A privacy pass before anything is public.** 4 Oct 2026. The repo is public, so this spec and V1_LESSONS.md are public from your first push. Cowork took the personal details out of both on 4 Oct: names became roles, and places went. No decision changed. The rule from here: nothing committed to v2 names a family member, a colleague, a home or a place. Before every commit that adds or changes a document, Claude Code checks it against a private word list that Cowork keeps outside the repo.
3. **One spec, and it lives in the v2 folder.** 4 Oct 2026. After stage 1 the copies of this spec and of V1_LESSONS.md in /home/indy/Projects/OpenConsult2 are the only ones. Cowork writes your rulings there and checks the file on disk by checksum. Claude Code commits them as the first step of the next stage, so the spec is always committed before the code (V1_LESSONS 11.3) and you have nothing extra to do. The copies in the review folder are retired once Cowork has checked the stage 1 commit: they move into that folder's v2-logs, marked retired. From the next brainstorm on, Cowork is given the OpenConsult2 folder.
4. **The licence stays as v1.** 4 Oct 2026. AGPL-3.0-or-later. You are the sole copyright holder. Issues and discussions only, no outside code. The LICENSE file crosses from v1 unchanged.

**The details, settled by Cowork.** They are here for Claude Code. You do not need to read them.

- **How the branch is made.** A new, empty repository in /home/indy/Projects/OpenConsult2, with one branch called v2, pointed at the same GitHub repo as v1. It shares no history with main. Nothing in the v1 folder is written to, not even by git.
- **What stage 1 commits.** V2_SPEC.md and V1_LESSONS.md first, so the spec is committed before anything else. Then LICENSE (from v1, unchanged), a new short NOTICE, and the ignore list. Then CLAUDE.md, HANDOVER.md, a short README, and the stage prompt.
- **The ignore list, from the first commit** (V1_LESSONS 10.6). Secrets and settings files, the database file, recordings and all audio, model files, the corpus, Claude Code's per-machine settings, and working documents that may name a weakness.
- **NOTICE starts short.** v2 holds no third-party part yet. Each stage that adds one records it in the same commit.
- **A short README now.** It says v2 is being built on this branch, that it does not run yet, that the working app is on main, and never real patients. The full README is stage 16.
- **Prompts for Claude Code are files in the repo** (V1_LESSONS 11.3), in a folder called stage-prompts. They are public, so they carry no personal detail. Plans, logs and reports stay private, in the review folder's v2-logs. One exception, by your ruling: the engine bench is published (15.8, ruling 2).
- **The community files wait.** CONTRIBUTING, SECURITY, the code of conduct, CITATION.cff and the issue templates are not in stage 1. GitHub reads them from main while v2 is being built. They cross in stage 16, before the join of 14.3, or the join would remove them from main.
- **The plan gate.** Claude Code writes its plan to a file in v2-logs and stops. Cowork reads it. You then type: Approved. Go.
- **Claude Code never pushes.** You push: git push -u origin v2.

**Done when you see:** the v2 branch on GitHub, holding these and nothing else: README.md, CLAUDE.md, V2_SPEC.md, V1_LESSONS.md, HANDOVER.md, LICENSE, NOTICE, .gitignore, and the folder stage-prompts.

### 15.6 Stage 2: the skeleton

The brainstorm for stage 2 was on 4 Oct 2026. These are your rulings, in the order you gave them.

1. **The wording about the repo root is tidied.** 4 Oct 2026. Owed from stage 1. Section 5.3 said the root holds seven files and nothing else. That was untrue from the first commit, which also held the ignore list and the stage prompts. The rule is about documents: no document at the root beyond the seven. Section 5.3 now says so, and stage 2 makes the same change in CLAUDE.md.
2. **One label for one event.** 4 Oct 2026. Owed from stage 1. Section 5.3 said CITATION.cff is added at release, and 15.5 said stage 16. Both now say stage 16.
3. **Commits carry the co-author line again, as in v1.** 4 Oct 2026. Owed from stage 1. From stage 2, each commit Claude Code makes ends with the line that names the model that built it: Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>. That address is the only one allowed in a commit message.
4. **The statement is built now, and it comes first.** 4 Oct 2026. Stage 2 builds three of the first-run steps of 7.1, in the spec's order: the statement (research and education prototype, never real patients, a tick to accept), then This machine, then the user. Nobody can set up a user before accepting the statement. The acceptance is written to the audit log. The other steps of 7.1 arrive with their own stages.
5. **The app locks itself after 30 minutes with no use.** 4 Oct 2026. It then asks for the password again. It never locks during a live consultation, so the doctor is never shut out in front of a patient. The password is also asked for each time the app is opened, as 7.1 says. The 30 minutes is a named value in the code with this ruling as its source. It is not a setting.
6. **This computer only, during the build too.** 4 Oct 2026. v2 on mlrig answers only to the computer it runs on, exactly as a colleague's install does (6.4). You do the screen checks sitting at mlrig. Nothing is built in stage 2 for reaching the app from a second device. That stays an advanced setup, decided with the help pages. One need was added on 6 Oct: showing the app somewhere else (15.8, ruling 6).
7. **You can change your own details on the settings page.** 4 Oct 2026. A small section called You: the title, the name, and a change of password. Any change asks for the current password first, and every change is written to the audit log. The table in 7.3 gains this row. The reset command (D26) stays, for a forgotten password.
8. **v2 keeps v1's look.** 4 Oct 2026. The warm cream page, the plum buttons and the same type, as you approved for v1 in July. The pages underneath are written fresh and smaller. The style sheet is carried from v1 and cut to what v2 uses.
9. **Cloud services on a laptop: a free trial and a simple sign-up.** 4 Oct 2026. This is for later stages, not stage 2. On a machine that uses cloud models, the app offers only cloud services that give a new user a free trial and have a simple sign-up. The bench still comes first: a service that fails its marks is not offered, free or not (10.1). Before the stage that adds a service (stages 3, 5 and 9), Cowork checks the service's own pages for three things: the free trial, the sign-up steps, and what the service does with the words it is sent. If a free trial lets a service keep or learn from what it is sent, the cloud statement of 7.3 says so plainly. A first look on 4 Oct: both speech candidates of 11.2 state a free credit with no card needed. A free credit for the Claude API is reported, but was not confirmed on its maker's own pages. It is checked before stage 3.
10. **A choice of engine for local models is a question for stage 3.** 4 Oct 2026. You asked for a setting to choose between Ollama, llama.cpp and vLLM. It is not decided today. It goes to the stage 3 brainstorm, where the one door to language models is built. Until then 3.4 stands: v2.0 uses Ollama. Stage 3 builds the door so that a second engine can be added without rework. What Cowork brings to that brainstorm: each engine needs its own bench, because each model behaves differently on each engine (V1_LESSONS 3.8); llama.cpp is light and could ship inside the installer; vLLM in practice runs on Linux only and is built for many users at once.

**The details, settled by Cowork.** They are here for Claude Code. You do not need to read them.

- **Stage 2 in one line.** The app starts, one person sets it up and logs in, and it describes the machine. No patient, no model and no sound yet.
- **The package.** One Python package called openconsult at the repo root, with a tests folder beside it. Of the folders in section 6, only those stage 2 fills are made: settings, patients (the one user, login and the audit log) and web. The one database module (6.5) sits at the top of the package, beside them. A folder is made by the stage that first fills it (R31).
- **Python and its libraries.** Python 3.12, as v1. The lock file is committed (V1_LESSONS 7.5). The base app's libraries are light and declared: no PyTorch, no NVIDIA library, nothing that needs a graphics card or a compiler (5.1; V1_LESSONS 7.1, 7.2). Each library added is recorded in NOTICE in the same commit.
- **One command.** openconsult starts the app. openconsult reset-password is the reset command.
- **Where the data lives.** In the user's data folder for the system, never in the source folder or the install folder (6.4). In stage 2 that is the database file. One override exists for a development run. Tests always use a temporary folder, with the guard of 5.2: a test that reads the user's own settings, or writes outside its temporary folder, fails (R18; V1_LESSONS 8.5, 10.1).
- **The database.** SQLite, from Python's own library. One module opens it, one file lists the tables, and the tables change by version number (6.5; V1_LESSONS 6.2). Stage 2 makes only the tables it uses.
- **How a login is kept.** By the app itself, in its own memory, with a long random value in a cookie that lasts only for the browser session. So a login cannot outlive the app, and there is no signing secret to store or to leak (V1_LESSONS 10.2). v1's signed cookie is not carried, because it could not end a login when the app stops or after a reset. The password hashing is ported from v1, as 6.1 says.
- **Other web pages cannot drive the app.** The app answers only when it is addressed as this computer, and a request that changes anything must come from the app's own pages. This closes the two known ways a page on another site can reach an app that listens on this computer.
- **The first run in stage 2.** Three screens, in this order: the statement, This machine, the user (ruling 4). The user can leave and come back, and the app resumes at the first step not done. Until all three are done, every other page leads back to the first run.
- **Setting up the user works only from this computer (D20).** Two guards, so that one mistake does not open it. The app listens only on this computer's own address (ruling 6). And the set-up screen refuses any request that did not come from this computer.
- **The user.** A title, a name and a password. The title is free text and may be left empty, for a learner who has none. The name is required. The password has at least 8 characters, as in v1, and is typed twice. It is stored only as a hash, with the method ported from v1 (6.1).
- **Logging in.** A login ends when the user logs out, when the browser is closed, when the app is stopped, or after 30 minutes with no use (ruling 5). When the app asks again, the page says why (R15). A live consultation will count as use: stage 2 builds the rule so that stage 6 can tell it a consultation is running, and builds nothing of the consultation itself (R31). Each wrong password makes the next try wait longer. The one user is never locked out for good, because the reset command is the way back. After a change of password, or a reset, every other login ends.
- **Logging in: what the plan review of stage 2 settled (15.7, ruling 1).** The wait is 1 second after the first wrong try. It doubles with each wrong try, up to 5 minutes. A right password or a restart clears it. These figures are design choices, not measurements. A wrong current password in the You section counts as a wrong password: it is logged and it makes the next try wait. A reset run from the command ends the logins of the running app too: the user's row carries a number that goes up at each change of password, and each login remembers the number it was made under. A screen nobody is using locks itself: each page behind the login refreshes itself quietly when the time is up, and a quiet refresh never counts as use. For stage 6: typing must count as use, and that needs a page script.
- **The reset command (D26).** It is run in a terminal on the computer itself. It asks for the new password twice without showing it, and never takes the password as part of the command, so it is not kept in the terminal's history. It changes the password and nothing else. It writes a line to the audit log.
- **The audit log.** One recorder, which adds the time itself (6.5). The app only adds lines. It never changes or removes one, and never writes a password or a secret into one. Stage 2 records: the statement accepted, the user set up, each login, each wrong password, each logout and each lock, each change in the You section, and each password reset. One page shows the log, newest first, read only.
- **The settings store.** One module, and no other code reads a setting directly (5.1). Each setting has a name, a default and a reason. A change is written to the audit log, from what to what (7.3). That holds from the first setting a page can change. Stage 2 has none: its store holds only the data folder and the port (15.7, ruling 1). The store is put together fresh at each start and for each test. No setting without behaviour: stage 2 adds only the settings its own behaviour uses.
- **The settings page in stage 2** has two sections: This machine, and You (ruling 7). The other sections of 7.3 arrive with their stages. Nothing is shown greyed out for a later stage (R31).
- **This machine.** Read only. It shows the system, the graphics card and its memory, and one sentence in plain words. The card is found by asking the tool that comes with the NVIDIA driver, with no heavy library (5.1). A Mac, a machine with no NVIDIA card, and a card that could not be read are each said plainly, and none of them stops the app. Suitable means one card whose memory rounds to 24 GB or more (6.4; 15.7, ruling 1); with several cards, the largest one counts. The lines for local models and for the microphone arrive with stages 3, 5 and 6.
- **The sentence on This machine.** A draft, yours to correct when you see it on screen. With a suitable card: This computer can run OpenConsult's models itself. Nothing spoken needs to leave it. With a smaller card: This card has 8 GB. Running everything on this computer needs 24 GB, so OpenConsult will start on cloud models. With none: No suitable NVIDIA graphics card was found. OpenConsult will use cloud models on this computer.
- **The pages.** Plain pages. Stage 2 has no page script. From the first one, scripts live in their own files (5.1; 15.7, ruling 1). The look is v1's (ruling 8). No page loads anything from the internet. Every refusal shows on the control that was pressed, through one shared helper (R15; V1_LESSONS 5.1). After login the user lands on a home page. It carries the standing statement, and says in one line what this version can do so far.
- **Every sentence shown to the user lives in one file,** openconsult/words.py (15.7, ruling 1). You correct wording there. No test keeps its own copy of a sentence.
- **The port.** 8001 when run from source on mlrig (14.1). If the port is taken, the app says so in plain words and stops. It does not move to another port silently (V1_LESSONS 7.6). Choosing a free port by itself belongs to the installer stage.
- **The GitHub check (D12).** On every push to v2, on GitHub's own Linux, Windows and macOS machines: install from the lock file, run the suite, then start the app, check that it answers, and stop it. A test skipped by accident fails the check (5.2). The check uses no secret, has read-only rights, and pins each outside step it uses to an exact version. It is free for a public repo on GitHub's standard machines; Cowork checked GitHub's own pages on 4 Oct 2026. It is the first check this repo has had.
- **Tests.** Each names the rule or the incident it pins (5.2), and Claude Code lists them in its plan before writing any. Expected here: R15, R18 and its guard, R23, D20, D26, rulings 4 to 7, and V1_LESSONS 7.6, 8.5, 8.6, 10.1 and 10.2.
- **Documents.** CLAUDE.md gains its Running it section and the corrected line about the root (ruling 1). The holding README stops saying that the app does not run. HANDOVER gains an entry. The stage prompt is copied into stage-prompts.
- **v1 keeps running.** Stage 2 loads no model, so the v1 service is not stopped while v2 is tried on port 8001.

**Done when you see:**

1. On mlrig, at port 8001: the statement, then This machine describing mlrig correctly, then your title, name and password, and you log in.
2. In the You section you change your name and change it back. The log page shows what you did.
3. You push. The GitHub check is green on Linux, Windows and macOS.

### 15.7 Stage 3: the language model door

The brainstorm for stage 3 was on 4 Oct 2026. These are your rulings, in the order you gave them.

1. **The leftovers of stage 2 are folded in.** 4 Oct 2026. Owed from stage 2. Two lines of 15.6 were not yet true, and each now says when it becomes true: a settings change is audited from the first setting a page can change, and page scripts live in their own files from the first script. Six choices made in the plan review of stage 2 are now written in 15.6: the wait after a wrong password, a wrong current password in the You section, how a reset ends the logins of the running app, how an unused screen locks itself, what counts as a suitable card, and the one file that holds every sentence shown to the user. One point is carried to stage 6: typing must count as use.
2. **The app opens the browser by itself.** 4 Oct 2026. You asked for this for users who are not at ease with computers. When the app is up, it opens the system's default browser at its own address. It does so only once the app really answers. One switch starts the app without a browser: the tests and the GitHub check use it. It is the first small item of stage 3. Section 6.4 already promises this for the installed app; this ruling brings it forward to the app run from source. For stage 15: a second start while the app is already running opens the browser at the running app, and does not show a port error the user may never see.
3. **What the same marks means.** 4 Oct 2026. Stage 3 is done when the v2 bench on Gemma 4 QAT gives the same marks as v1 (15.4). The cases are those of v1.1 Tasks 5 and 5b: the ectopic pregnancy consultation (495), the two travel cases and the 13 scripts, each with the patient line, 13 runs each. The pass marks you set for those two tasks stand, unchanged. v1's prompts for the assessment and the alarm have not changed since, so those marks are v1 today. Same means every hard mark is met, not every number identical, because two runs of the same model differ by chance (V1_LESSONS 9.1). The soft marks and the time marks are reported by the same rules as then. One check runs with no model: v2 sends the model exactly the same words as v1 did, call for call. That is the firm proof that the rewrite lost nothing, and the marks then confirm it.
4. **Stage 3 covers Gemma 4 QAT only.** 4 Oct 2026. The door is built so that Claude and Qwen fit in later without rework. Claude comes with the connect screens in stage 9, after its own bench. That bench is thousands of paid calls, so it gets its own brainstorm. Qwen comes once its answer order is fixed, after its own bench (10.1). Nothing of either is built in stage 3 (R31). The check owed under 15.6, ruling 9, was made on 4 Oct 2026, on Anthropic's own pages. The pricing page says new users receive a small amount of free credits to test the API. It gives no amount and does not say whether a card is needed, and two help pages say to buy credits before using the API. So a free credit is stated, and a free trial with no card is not confirmed. The same pages say the words sent to the API are not used for training and are deleted within 30 days. Cowork checks all of this again before stage 9.
5. **The engine bench: llama.cpp and vLLM against Ollama, as a report only.** 4 Oct 2026. This settles 15.6, ruling 10, for now. Once Cowork has checked the Ollama proof of ruling 3, the same cases run on llama.cpp and on vLLM. It is a second Claude Code run: a sub-stage, with its own short brainstorm. The marks, in this order: the clinical marks first, then the seconds for each pass, then how much of the graphics card each engine takes. The bench is built so that it can be pointed at any engine. No setting to choose an engine is built until you have read the report. Until then 3.4 stands, and v2.0 uses Ollama. What Cowork found on the makers' own pages on 4 Oct 2026, which the report must say plainly: llama.cpp and Ollama can both load one and the same file, Google's own, so that arm tests the engine alone, and llama.cpp runs on Windows, macOS and Linux. Whether that file is the very one behind Ollama's own tag is not confirmed. If it is not, the Ollama arm of the engine bench runs again on Google's file, so that the two engines are compared on one file. vLLM runs on Linux only and cannot use that file. vLLM's own page for Gemma 4 says that the 26B model is not among the 4-bit versions made for vLLM, because its small expert parts lose too much quality at 4 bits. Those are the words of vLLM's page, not Google's. This spec first said that Google had said it. That was Cowork's mistake of 4 Oct, corrected on 6 Oct 2026 by your ruling: a Hugging Face user with no Google badge had repeated the sentence, and Cowork took it for Google's. The 8-bit route that the same page names comes to about 25 GB by Cowork's arithmetic, just over the card. So the vLLM arm uses a version of the model made by an individual, and it measures the engine and that version together. You chose to run it knowing this. Cowork checks that version on its own page before the run, and brings it to the short brainstorm.

**The details, settled by Cowork.** They are here for Claude Code. You do not need to read them.

- **Stage 3 in one line.** Every call to the language model goes through one door, is limited, and is recorded. The bench proves that the door sends v1's words and reaches v1's marks. No consultation, no patient list and no sound yet.
- **Two runs.** Stage 3 itself is one Claude Code session: the browser, the door, the prompts, the record, the bench and the Ollama proof. The engine bench of ruling 5 is stage 3b, a second session, after Cowork has checked the first.
- **The browser (ruling 2).** The command opens the system's default browser once the app answers on its address, and it still prints the address. The switch is --no-browser. A machine with no browser or no screen is not an error: the app runs and the address is printed. No test ever opens a real browser. Claude Code's own runs and the GitHub check use the switch.
- **The folders made now.** llm, prompts, consult and bench. A folder is made by the stage that first fills it (15.6).
- **The door (llm).** One module is the only code that talks to a language model (5.1). It holds one table of jobs (V1_LESSONS 3.11). Each job names its prompt file, its answer form, its limit on length, its limit on time, and what happens when it fails. Stage 3 fills two jobs: the assessment and the alarm. The other jobs of 10.2 arrive with their stages (R31).
- **One result, and never an error thrown into the consultation (R30).** A call gives back an answer, or a failure with its reason: too slow, too long, the model cannot be reached, or an answer that does not fit its form. A reply cut off at its length limit is a failure, never an answer.
- **The limits.** The assessment: 1,500 tokens and 60 seconds, as v1 set them after consultation 486. The alarm: 1,000 tokens, as v1, and 60 seconds. v1 left the alarm's time at a default of 180 seconds that nobody chose. The 60 is a design choice, not a measurement.
- **The model's profile (V1_LESSONS 3.8).** One place holds what a model needs: its tag, thinking switched off for Gemma 4 QAT, temperature 0 and seed 42 (10.4), and one context size of 16,384 for every call (R19). The model's name is typed in that one place and nowhere else.
- **No silent cut of what the model reads (V1_LESSONS 3.3).** A call whose input did not fit the context size is a failure and is marked so in its record. Claude Code says in its plan how this is detected on Ollama.
- **The engine behind the door.** The door speaks to an engine through one small joint. Stage 3 builds the Ollama engine only (R31). A second engine, or the cloud, is added at that joint with no change to the jobs (ruling 4; ruling 5).
- **Never a silent fallback (10.4).** If Ollama or the model is absent, the call fails and says so. Nothing else is tried.
- **What the plan review of stage 3 settled (15.8, ruling 4).** What crosses the joint is the parts of a call and nothing of any one engine: the model's tag, the system text, the user text, the answer form, the temperature, the seed, the context size, the length limit, the thinking switch and the time limit. Each engine builds its own request from those parts. The engine gives back one plain reply: the answer text, how it ended, the tokens, the times, and the request and the raw reply exactly as they went, for the record. The Ollama engine sends truncate false, so an input that does not fit is refused and never cut. The record's prompt hash is the sha256 of the system text as it was sent. The two Ollama lines on This machine show only on a machine with a suitable card; on any other machine Ollama is not asked and nothing about it is shown. The soft marks are the numbers fixed on 2 Oct, from the arm they were written against. The alarm of a pass has three states: judged with one or more actions, judged with none, and not judged because the call failed, with the reason. In the bench, a pass whose alarm was not judged has no urgent action for scoring and is listed in the report, and a script chain in which any call failed is a failed chain.
- **Prompts are files (5.1).** One prompt in one file, in the prompts folder. Stage 3 brings two, word for word from v1 at commit b2e61d0: the assessment and the alarm. The fixed words placed around the transcript live in that folder too. So no sentence the model reads is typed in the code, except the patient line, which code builds from the age and the sex. No prompt is changed in stage 3: a change is a bench of its own (V1_LESSONS 3.7). R13 and R21 are checked over every prompt file.
- **The pass (consult).** One pass is two calls: the alarm first, then the assessment (R30). Both read the transcript afresh (R9, R12). Both open with the patient line (R11). The assessment is also given its earlier differentials, as names only, as a stale list (R12). Code does the bookkeeping, as in v1: once the urgent step is arranged, it stays arranged. If one call fails, the other still gives its result. A reply that says time-critical and names no action is kept as such in the result, for the screen of stage 6 (V1_LESSONS 3.14). The message builders, the patient line and the bookkeeping are ported from v1 as plain functions (6.1). The affect call and the end-of-turn call are not built now (R31). Neither took part in any mark.
- **The record of every model call (6.5; V1_LESSONS 3.12, 3.13).** One table, written by the door itself, so that no call can skip it. Each row holds: when, the job, the engine and its version, the model's tag and digest, the hash of the prompt file, exactly what was sent, the raw reply, the tokens read and written, the times, and how the call ended. This is the stamp of R20. The record holds what the patient said. So it lives in the data folder only: never in the repo, and never in the audit log. Stage 6 ties each row to its consultation, and a deleted consultation takes its rows with it (D44).
- **This machine gains two lines.** Whether Ollama is running, with its version. Whether Gemma 4 QAT is present. Read only. The offer to download is stage 9.
- **The bench kit (6.5; V1_LESSONS 9).** One shared kit in the bench folder: the replay, the scoring, and a writer that cannot write over an existing result. It runs 13 chains: 3 at temperature 0 with seed 42, and 10 at temperature 0.5 with seeds 1 to 10 (V1_LESSONS 9.1). It goes through the same door as the app, and it can be pointed at any engine (ruling 5). It never writes to the app's data: its results and its own record of calls go to the private log folder. The engine bench also has a public form (15.8, ruling 2). Every result carries the model's tag and digest, the engine's version and the prompt hashes (V1_LESSONS 9.6).
- **The cases stay outside the repo for now.** The 495 transcript is the record of an acted consultation. The two travel cases and the 13 scripts are scripted. Stage 3 copies all of them to the private log folder, with a list and checksums. The scripts enter the repo with the teaching bank (stage 10), by your ruling then. What the engine bench publishes is the one exception (15.8, ruling 2).
- **The word check (ruling 3).** It needs no model. For every assessment and alarm call that v1 recorded in Tasks 5 and 5b with the patient line, v2 builds its own request from the same case, the same point in it and the same earlier answer. The two must match in the prompt, the message, the answer form, the model, the thinking switch and the options. The result is a count: so many of so many.
- **The marks, fixed before the run (V1_LESSONS 9.2).** Claude Code writes them in its plan, as numbers, from the logs of Tasks 5 and 5b. Cowork checks them before you approve the plan. Task 5 marked the scripts on one run each and Task 5b marked them on 13, so for the scripts the marks of Task 5b stand. The hard marks: on 495, ectopic pregnancy is on the list at some pass, 13 of 13; on 495, the alarm names a pregnancy test or hCG, 13 of 13; on the first travel case, dengue is on the list by turn 20, 13 of 13; on the second, malaria is on the list by turn 16 and the alarm has fired by turn 16, 13 of 13 each; each of the seven emergency scripts fires, 13 of 13; and in the male cases no differential and no urgent action names pregnancy, ectopic, ovarian or hCG.
- **A missed hard mark.** Claude Code stops and reports. It does not run again to get a pass. You and Cowork then decide.
- **The same model.** Before the run, the digest of Gemma 4 QAT in Ollama is checked against the one recorded in Tasks 5 and 5b. If it differs, Claude Code stops and reports.
- **Tests.** Each names what it pins (5.2), and Claude Code lists them in its plan. The suite still needs no graphics card and no Ollama: a made-up engine stands behind the door. Expected here: R9, R11, R12, R13, R19, R20, R21, R30, 10.4, ruling 2, and V1_LESSONS 3.3, 3.10, 3.12, 3.13 and 9.4. What the model says is never asserted in a test (5.2).
- **Documents.** CLAUDE.md gains the new commands under Running it. The README says what this version can now do. HANDOVER gains an entry. NOTICE gains each library added. The stage prompt is copied into stage-prompts.
- **v1 keeps running.** The bench uses the same model as v1, through the same Ollama. You do not run a v1 consultation while the bench runs.

**Done when you see:**

1. On mlrig you start the app, and the browser opens by itself at the login page.
2. In Settings, This machine says that Ollama is running and that Gemma 4 QAT is present.
3. The bench report: the word check is complete, and every hard mark is met. Cowork checks it from the raw files before you read it.
4. You push. The GitHub check is green on Linux, Windows and macOS.

Then stage 3b, the engine bench (ruling 5), after its own short brainstorm.

### 15.8 Stage 3b: the engine bench

The brainstorm for stage 3b was on 6 Oct 2026. These are your rulings, in the order you gave them. The first four were parked on 4 Oct, because Claude Code was building stage 3 against this spec's checksum and the spec could not be touched. You said yes to each that day. They are written here on 6 Oct.

1. **Every prompt a model reads is discussed with you before it is built.** 6 Oct 2026. Your rule of 4 Oct. You want to work on each prompt together with Cowork, and to spend quality time thinking about it. Each prompt is put to you in full, word for word, one prompt at a time, at the brainstorm of the stage that adds or changes it. That covers the prompt files, the fixed words placed around the transcript, and the patient line. A summary never stands in for the words. Your approved wording is kept as the prompt file itself, and this spec records the date. Claude Code never writes or changes a word a model reads: the prompt for a stage gives the exact text, or says that no prompt changes. Then the bench, before a change is kept (V1_LESSONS 3.7). Stage 3 did not break this rule: it carried v1's two prompts across word for word, and you shaped those for v1 on 30 Sep. The first prompts that will need it: the note (stage 6), the letters and the guideline summary (stage 8), the teaching prompts (stage 10), the area call and the question call (stage 12), and the end of turn and affect calls (stages 12 and 13). Sections 15.2 and 15.3 now carry the rule.
2. **The engine bench is published.** 6 Oct 2026. Your ruling of 4 Oct. A few people asked you to use vLLM for OpenConsult, and one raised it as issue 1 on the repo. You want to answer with proof, so the data goes where people can look at it. The engine bench has a public form: a report and its figures in a folder of the repo, not at the root (5.3). For all three engines it gives the clinical marks, the seconds for each pass, the card memory, the version of each engine, and which version of the model each engine ran. The 495 transcript and the model's replies are published with it. Cowork checked on 4 Oct that this is safe: the transcript is what the speech model wrote down when you acted script 18, which is already public in v1. It follows the script and holds nothing personal. This is an exception, not a new rule. Every other plan, log and report stays private (15.5), and the cases of stage 3 stay outside the repo as 15.7 says, apart from what this bench publishes. The private word check runs on everything published. The report says plainly what the vLLM arm measures: the engine and a version of the model made by an individual, together (15.7, ruling 5).
3. **The v1 service is off.** 6 Oct 2026. You stopped the v1 service on mlrig on 4 Oct and removed its start at boot. You did this yourself. Its files, its database and its recordings are kept, and it can be switched back on. Ollama and the v1 database server run as before. Section 14.1 said that v1 keeps running as the service, and that you stop it before running v2. Items 3 and 5 there now say what is true: with v1 off, v2 has the graphics card to itself, and if v1 is ever switched back on, it is stopped again before v2 runs. The lines in 15.6 and 15.7 that say v1 keeps running were true when those stages were built. They are left as the record of those stages.
4. **What the plan review of stage 3 settled is written in.** 6 Oct 2026. Six points, now in the details of 15.7. One: the door hands an engine the plain parts of a call, not Ollama's own format, so a second engine fits without rework. Two: the two Ollama lines on This machine show only on a computer with a suitable card. On any other computer a line saying Ollama is not running would read as a fault. Three: the soft marks keep the numbers fixed on 2 Oct. Four: a failed alarm call never reads as no alarm. The result says plainly that this pass's alarm was not judged. Five: Claude Code found that Ollama, by default, cut a long input to about half the context size and answered as if nothing had happened. v2 refuses such a call instead. v1 ran with that default. This matters to the patient: the model could have been reading only part of a long consultation, with no sign of it. Six: the record keeps the hash of the prompt exactly as it was sent.
5. **An empty list keeps the earlier list.** 6 Oct 2026. Your ruling, on the one soft miss of stage 3 (script 15: the reasoning named cauda equina, and the list of differentials came back empty). When the model returns an empty list, for example the list of differentials, the earlier list stays as the list until the next pass. That is the stale list that went in with the call. The patient's differentials never vanish from the screen because of one empty reply, and the next pass is given the same list again. If the next pass is empty too, the list stays again. This is bookkeeping by code, as the latch on the urgent step is. It changes no word a model reads, so ruling 1 is not touched. Two things Cowork adds, so that nothing is hidden: the result of the pass says plainly that the list was kept from the earlier pass, and the record still holds the model's own empty reply. At the first pass there is no earlier list, so an empty list is shown as empty.
6. **Showing the app somewhere else.** 6 Oct 2026. You may need to demonstrate the app running on mlrig from another place, through Tailscale Funnel. There is no date yet. The need is recorded now, and how it is built is settled at the brainstorm of stage 6, when there is a consultation to show. Until then a demonstration uses v1, switched back on for the occasion; v1 already works through Funnel. What Cowork brings to that brainstorm: v2 refuses any outside address on purpose (15.6, ruling 6, and the guards in its details), so this needs a switch that you turn on for a demonstration and off again after, off by default, with every change written to the audit log. Funnel is the open internet. With it on, only the password stands between a stranger and the app. The app holds acted consultations only, so the harm is small, but the risk is real and the switch must say so. Setting up the user stays possible only from the computer itself (D20). Nothing is built for this in stage 3b (R31).
7. **The vLLM arm runs the repack by xbill9.** 6 Oct 2026. Three versions of Gemma 4 26B that vLLM can read and that fit a 24 GB card were on Hugging Face on 6 Oct, each made by an individual. You chose xbill9/gemma-4-26B-A4B-it-qat-q4_0-w4a16-ct. Its own page says: it holds Google's own trained weights, the same ones as in Google's file, repacked into the form vLLM loads, with no new shrinking of the model; the maker publishes a check of the weights against Google's, and what it shows is this: every weight sits on Google's grid of levels; the 748 tensors that were not shrunk are identical, byte for byte; of the shrunk values, 89.7 to 92.6 % are bit-identical, and the rest differ by at most 1.1e-2 relative, about 1 %; its maker tested it on vLLM 0.30.0 on one NVIDIA L4 card of 24 GB, at a context of 2,048, text only, where this bench runs it on another card at 16,384 (these words were made exact on 6 Oct 2026 by your ruling, after the run: the spec first said a check of every weight, which read as if every weight were identical); it is 15.29 GiB. So this arm comes as close as vLLM allows to the same model on all three engines. Its weakness, which the report says plainly: one person made it, it was published on 27 Sep 2026, and few people have used it. Claude Code checks that it loads and answers before the run. The two not chosen: cyankiwi's is widely used but is made from the ordinary Gemma 4 by a different method, so it would test a different model as well as a different engine; NeoChen1024's is made from Google's file but was last tested on a much older vLLM. What Cowork found the same day: the file behind Ollama's own tag is not Google's file. Their fingerprints differ (Ollama's begins 4c856523d61d; Google's is 3eca3b8f6d7b...). So, as 15.7, ruling 5 already says, the Ollama arm of this bench runs again on Google's file, and llama.cpp runs on that same file. Claude Code confirms the two fingerprints on mlrig before the run.
8. **The calls of a pass are also sent together.** 6 Oct 2026. Issue 1 says vLLM is much faster. vLLM's strength is doing several jobs at the same moment. OpenConsult has one user, but a pass has two calls, the alarm and the assessment, and auto mode will add a third, Alba's question. Today they go one after another. So each engine gets one extra arm: the calls of a pass sent at the same moment. It is the fair test of the claim, and it bears on the patient: if it works, the alarm and Alba's question arrive sooner. The arm sends the two calls that exist today. Nothing is built for Alba's question (R31). It is a measurement only: the app still sends its calls one after another until you have read the report.
9. **Does an engine give the same answer twice?** 6 Oct 2026. At temperature 0 with seed 42 the model should give the same answer to the same words every time. In v1's bench it did, on 13 of 13 scripts. In stage 3 the three chains at temperature 0 agreed on only 2 of 16 cases, although the words sent were identical. So the cause is inside the engine, most likely in what Ollama keeps in memory between calls. Each engine gets one small test: the same call sent several times, and a count of how often the replies match. It matters because a bench can be trusted only if a second run gives the same result, and because a doctor who looks back at a consultation should be able to get the answer the model gave then. The report gives the count for each engine, and says what was tried to make an engine repeat itself.
10. **What counts as faster, fixed before the run.** 6 Oct 2026. Two parts. First, the clinical marks decide who is a candidate: an engine that misses any hard mark of 15.7 is not a candidate, however fast it is. This follows from your order of 4 Oct, clinical marks first. Second, the seconds: the report calls an engine faster in a way that matters to the patient only if its typical pass, the alarm and the assessment one after another, is at least 1 second shorter than Ollama's in this same bench, on the same file where the engine can read it. Typical means the median. On Ollama in stage 3 that pass took 4.63 seconds, and 7.01 seconds at worst. A smaller difference is reported as a figure and is not called a win. The arm with the calls sent together (ruling 8) is held to the same 1 second, against Ollama sending its calls one after another, which is what the app does today. The slowest pass and the card memory are reported beside it. No engine setting is built on this report alone: you read it first (15.7, ruling 5).
11. **Every case the engine bench reads is published.** 6 Oct 2026. This widens ruling 2. The 495 transcript is covered by ruling 2. The 13 scripts are already public in v1. The two travel cases, the returned travellers with dengue and with malaria, had never been public. They are scripted and hold nothing personal, and you ruled that they are published with the bench. So every case the bench reads, and every reply the models gave, is in the public folder, and anyone can run the whole bench again and check the figures. That is the strongest answer to issue 1. The private word check runs on every published file. This ruling is for the engine bench only: how the scripts enter the teaching bank is still your ruling at stage 10 (15.7).
12. **The words in the terminal at the start.** 6 Oct 2026. The second line still told the user to open the address by hand, although the browser now opens by itself (15.7, ruling 2). Your wording for it, from Cowork's draft: Your browser will open by itself. If it does not, open that address in a browser on this computer. Press Ctrl+C to stop. The old line stays for a start without a browser on purpose. It is one line in the file that holds every sentence shown to the user (15.6).
13. **The together arm on Ollama ran on a second Ollama process.** 6 Oct 2026. Your ruling at the plan review, made while this spec was locked for the run and written here after it. Ollama as installed on mlrig takes one call at a time: two calls sent at the same moment came back after 1.02 and 2.04 seconds, the second waiting for the first. So the arm of ruling 8 could not run on the service as it is. You ruled that it runs on a second, private Ollama process: the same program and the same version, started by hand for that arm only, with its own model folder inside the bench's folder, its own port (11500), and Ollama's own setting for two calls at once (OLLAMA_NUM_PARALLEL=2). Your Ollama service and your models were not touched, and the process was stopped and seen gone after its arm. It is the one exception to the rule that nothing is set up beside the Ollama service. The public report says how the arm was run.
14. **Ollama runs llama.cpp inside it.** 6 Oct 2026. A fact found during the run, written here with your yes. Ollama 0.33.3 on mlrig serves this model through llama.cpp's own server, one call at a time. With the model loaded, the service was seen running that server, and Ollama's source at that version names the llama.cpp build it carries (b10760, from early September 2026). Since a change merged on 29 May 2026, Ollama uses llama.cpp's server for every model file of this kind. Ollama's own code writes the prompt around the words. The template inside the model file is not used. So the llama.cpp arm of this bench did not test a different engine from the Ollama arm. It tested the newest llama.cpp (build b11429, of 5 Oct 2026), spoken to directly, with the template inside Google's file, against the older llama.cpp inside Ollama, with Ollama's own prompt writing and Ollama's settings. Both read the same number of tokens on the same calls. A difference between those two arms is a difference between two builds and two ways of wrapping the words. The public report says so near its top. It also fits what ruling 9's test found: the two behave alike when the same call is sent twice.
15. **The two travel cases are published unchanged, with a note.** 6 Oct 2026. Your ruling at the publishing gate. The headers of the two travel cases hold three working notes written before the run: that the file is not part of the repo, a proposal by Cowork about the alarm, and that the pass marks were still to be set. The bench sends only the lines a speaker says, so the model never saw a header. You ruled that the two files are published byte for byte as the bench read them, and that the public report says in one paragraph what the notes are. Nothing in a case file is edited for publishing.
16. **The push is held, and vLLM gets a second arm.** 6 Oct 2026. Your ruling after the local publish. You want to give vLLM a fair chance as a candidate, so nothing is pushed until a new vLLM arm has run. Why: Cowork read the 14 failed replies and found one cause, and it is on every engine. The model sometimes writes a plain double quote inside its reasoning, to quote a word. Nearly always it is in the sentence that says there are no red flags. Inside the answer form a plain double quote ends the text. After that the model can only write blank space or go on to the next part. llama.cpp allows very little blank space there, and Ollama runs llama.cpp (item 14). So on those two the reply survives, with its reasoning cut mid-sentence, and is counted as fine: 24 replies on Ollama and 34 on llama.cpp, of 3,796 each. vLLM allows blank space without limit by default, so the reply runs on in blank space until its length limit. Those are the 14 failures. So the failures are one default of vLLM meeting a habit of the model. They are not the repack's weights and not vLLM's speed. vLLM has its own switch for this, which makes the answer compact, with no blank space between its parts (disable_any_whitespace, off by default). The new arm is the first vLLM arm with that one switch on and nothing else changed: the same repack, the same vLLM 0.31.0, the same cases, the same 13 chains, the same marks and the same two rules of ruling 10. It is a new arm with one named change, declared before it runs. It is not a second try at the same arm, so the rule that no arm is run again to get a pass stands. Both vLLM arms are published side by side. Whatever the new arm shows, there is no third. The arm with the two calls sent together is run again on the same start. The repeat test is not. You ruled that the arm runs the same night, 6 Oct, with no Ollama run beside it. Its seconds are held against Ollama's 5.00 s of that morning, and the report says that the machine was quieter at night: the browser closed, the monitor off, nobody at the desk. For the run the desktop's idle behaviour is switched off, as it was through the arms of the day, so that the screensaver cannot start; it is switched back on when the run ends. So that the arm can run the same night there is no separate plan gate: Cowork's file of steps is the plan, you start it by giving Claude Code the prompt, and Claude Code stops if anything does not match. The second gate stands: nothing more is published until Cowork has recomputed the new arm from its raw files. The same stray quote explains two more things on Ollama. Every empty list of differentials that ruling 5 was built for, 11 of 11 over both days, is in a reply cut by it. And after a cut the alarm often answers that something is time critical and names no action. The quote itself is a matter of the words the model reads and of the answer form, so it goes to the session on the two carried prompts (ruling 1), owed before stage 6.
17. **Faster means half a second, in every round.** 7 Oct 2026. Your ruling, before the full bench is run again. It replaces the second part of ruling 10. You judged the line of 1 second too high: half a second, many times in a consultation, matters. It matters most in auto mode, where the patient waits for each of Alba's questions. The report calls an engine faster in a way that matters to the patient only if its typical pass is at least 0.5 seconds shorter than Ollama's. The three engines take turns three times through the day, and each turn is a round. The line must be met in each of the three rounds, the engine against Ollama in the same round, so that one slow hour cannot make or break the result. A smaller difference, or one that holds in only some rounds, is reported as a figure and is not called a win. The first part of ruling 10 stands: the clinical marks decide who is a candidate.
18. **Temperature 0 decides who is a candidate.** 7 Oct 2026. Your ruling. It changes the first part of ruling 10. Cowork checked the app first: in a live consultation v2 sends temperature 0 with seed 42 and never anything else, and v1 did the same. The bench has 13 chains for every case: three at temperature 0 and ten at 0.5. The patient only ever meets temperature 0. So an engine is a candidate if every hard mark of 15.7 is met on its three chains at temperature 0 and none of those chains fails. The typical pass of ruling 17 is taken from the same chains: the median of the passes of consultation 495 at temperature 0. The ten chains at 0.5 still run, as a stress test, and are reported apart. They show a weakness early: all 14 failures of the first vLLM arm were at 0.5, and they led to the stray quote. A failure or a missed mark at 0.5 is named plainly in the report, but by itself it does not bar an engine. You had thought of dropping the higher temperature, to be patient focused; you chose to keep it beside the deciding figures.
19. **The full bench is run again, on 7 Oct.** 7 Oct 2026. Your ruling, agreed on the evening of 6 Oct and settled this morning. The first bench is tainted in its seconds: the arms ran at different hours of one day, the machine wrote about 10 % slower than on 4 Oct, a screensaver slowed the start, and Cowork's own early look slowed part of the vLLM arm. Its clinical marks are sound. So all three engines run again in one sitting, on a quiet machine, in a day when nobody is at the desk: about ten hours, with the monitor off. Each engine runs two arms, as on 6 Oct: all 16 cases and all 13 chains with the two calls of a pass one after another, and then the together arm of ruling 8. The repeat test of ruling 9 is not run again: it does not depend on the hour, and its result of 6 Oct stands. By the times of 6 Oct this takes about 8.5 hours. The run uses the words the models read today. The stray quote is not touched: it goes to the session on the two carried prompts, which then gets its own bench on the chosen engine. Nothing is published and nothing is pushed by this run. Cowork runs no command on the machine while an arm is being timed.
20. **The together arms run the three chains at temperature 0.** 7 Oct 2026. Your ruling. These are the chains that decide (ruling 18), and they are the app's own temperature. All 13 chains sent together on three engines would add more than five hours, over twelve in all, and the day has ten. So the stress test at 0.5 stays in the arms with the calls one after another, and the together arms stay as ruling 8 and the details below have them.
21. **Three rounds, and the order rotates.** 7 Oct 2026. Your ruling, so that the time of day cannot favour an engine. The work of each engine is cut into three parts, and the day into three rounds. In each round every engine runs one part, and the order rotates: Ollama, llama.cpp, vLLM in the first round; llama.cpp, vLLM, Ollama in the second; vLLM, Ollama, llama.cpp in the third. So each engine goes first once, second once and last once. Each round holds one of the three chains at temperature 0, run both ways, one after another and together, and a share of the ten chains at 0.5. So the seconds that decide are measured three times through the day on every engine, and an engine is held against Ollama in the same round (ruling 17). The bench also measures its own noise: if Ollama's own typical pass differs between its three rounds by more than 0.25 seconds, the report says that the day was too unsteady, and it calls no engine faster. You want Ollama's own gain from sending the calls together kept in view, and not only vLLM's. So the report shows every engine both ways, and holds each together arm against two figures: Ollama with its calls one after another, which is what the app does today, and Ollama with its calls together, which is like for like.
22. **vLLM runs with the switch, and only so.** 7 Oct 2026. Your ruling. Cowork recounted the second vLLM arm of 6 Oct from its raw files: with the switch no chain failed, of 208, every hard mark and every soft mark was met, and no list came back empty. So vLLM is a candidate, and in this bench it runs as that arm ran: the backend named as xgrammar and disable_any_whitespace on. Without the switch it is known to fail chains, and running that again would cost two hours and show nothing new. This is a new bench, so the line of ruling 16 that there is no third arm is not broken: that line was about the first bench. Two things the report must say plainly. First, the switch cured the failures and not the stray quote: 22 replies of that arm were still cut mid-sentence, all at 0.5, against 24 on Ollama and 34 on llama.cpp; the reply now survives the cut, as on the other two. Second, the switch makes the answers shorter, about a fifth fewer tokens, and most of vLLM's gain of that night came from there and not from a faster engine. Ollama has no such switch, and whether llama.cpp can be given the same compact form was not tested. So the report gives two figures for each engine: the wait of the patient, and the time for each token written, which shows the engine's own speed. A compact form for the other engines goes to the brainstorm on the engine choice.
23. **The first bench waits for the result of the second.** 7 Oct 2026. Your ruling. The first bench was published locally in two commits, the engine bench (8a6961d) and the documents (23198ab), and neither is pushed. You have not yet ruled whether the first bench is ever public. If it is not, those two commits come out of the local history before any push. You decide when you have seen the result of the bench of 7 Oct. Until then the two commits stay as they are, the folder engine-bench is not touched, and nothing is pushed. The run of 7 Oct writes its results to the private log folder only.

**The details, settled by Cowork.** They are here for Claude Code. You do not need to read them.

- **Stage 3b in one line.** The same cases go through three engines, are scored by the same rules and timed by the same clock, and the result is published. Two small items come first (rulings 5 and 12). No engine setting, no page and no consultation is built.
- **The two small items.** Ruling 5 is built in the pass. When the assessment returns an empty list of differentials and an earlier list exists, the earlier list stays as the list and is handed to the next pass, and the result of the pass says that the list was kept. The record keeps the model's own reply. At this one point v2 now differs from v1 on purpose: v1 handed on an empty list. The word check of stage 3 is not touched and must still give 1,898 of 1,898 for each call, because it rebuilds v1's requests from v1's own earlier answers. Ruling 12 is one line in words.py.
- **The arms.** Three full arms are run, each with all 16 cases and 13 chains, as in stage 3: Ollama on Google's file, llama.cpp on Google's file, and vLLM on the repack of ruling 7. One arm is carried over and not run again: stage 3's own run of 4 Oct, on Ollama's own tag. It is the reference. It was made before ruling 5, and the report says so. Then, on each of the three engines, the together arm (ruling 8) and the repeat test (ruling 9).
- **One file for two engines.** Google's file is gemma-4-26B_q4_0-it.gguf in google/gemma-4-26B-A4B-it-qat-q4_0-gguf on Hugging Face, at revision d1c082be9cf3c8a514acf63b8761f4b41935842e. Its page gave its sha256 on 6 Oct 2026 as 3eca3b8f6d7baf218a7dd6bba5fb59a56ee25fe2d567b6f5f589b4f697eca51d. Claude Code checks the sha256 of the file it downloads. llama.cpp loads that file. Ollama is given the same file as a new model with a name of its own, with the template, the parameters and everything else copied from Ollama's own tag, so that the file is the only thing that changed. Ollama's own tag is never changed and never deleted. If Ollama cannot serve Google's file the way it serves its own tag, Claude Code stops and reports before any arm runs.
- **The repack for vLLM.** xbill9/gemma-4-26B-A4B-it-qat-q4_0-w4a16-ct at revision 2096d38dad51a19b8e982b44241c47102a8bbb00. Neither download asked for a sign-in on 6 Oct 2026.
- **Each engine's version is written down.** Ollama stays at the version installed on mlrig, the one stage 3 was proven on (0.33.3 on 4 Oct). The report says which version was the newest on the day. llama.cpp and vLLM are taken at their newest release on the day of the run, unless the plan gives a reason for another. The repack was tested by its maker on vLLM 0.30.0. Every version, every build option and every start-up option goes into the report, so that anyone can repeat the bench.
- **Where the engines and the files live.** Outside the repo and outside the private log folder, in one folder that Claude Code proposes in its plan, on the drive where Ollama keeps its models, with the free space checked first. Nothing is installed for the whole system, and Claude Code never uses sudo. If an engine cannot be installed without it, the plan gives you one block to run yourself and says why. The Ollama service is not changed.
- **One engine holds the card at a time.** Before an arm starts, the other engines are stopped or their model is unloaded, and the card's memory is checked to be free.
- **The same call on every engine.** The door, the pass, the prompts, the patient line, the answer form, the limits, the temperature and the seed are the same for every arm. The two new engines are modules of the bench. They speak through the joint of 15.7. The app cannot reach them, and nothing in the app changes for them (R31; 15.7, ruling 5). Each engine has its own way to switch thinking off, to hold an answer to its form, to set the context to 16,384, and to refuse an input that does not fit. Claude Code proves all four on each engine before the run: no thinking text in a reply, a reply that fits its form, a call at the full context accepted, and an oversize input refused and not cut.
- **Every setting that shapes an answer is the same, or is named.** An engine fills in some sampling settings by itself. Where the engine allows, they are set to the values of Ollama's own tag. The full list for each engine is in the plan and in the report.
- **Did the model read the same words?** For the same calls, the number of tokens each engine says it read is compared. A difference means the engines wrap the words differently. It is found and explained before the run, not after.
- **The clock.** Seconds are measured by the door, with the same clock for every engine, for each call and for each pass. Each arm starts with the model loaded and one call that is not measured. The time from starting an engine to its first answer is reported on its own, because a doctor feels it at the start of a clinic.
- **The card.** The sampler of stage 3 runs through every arm. vLLM takes a fixed share of the card whatever it needs. The report says what share was set and what the model itself needed, so that the figure is not misread.
- **The together arm (ruling 8).** On each of the three engines: the three chains at temperature 0, all 16 cases, with the alarm and the assessment of each pass sent at the same moment. The time of the pass runs from sending until both are back. Each engine is set up as its own documents advise for two calls at once, and the report says how. If Ollama as installed takes one call at a time, the plan says so and proposes a fair setting that does not touch the service. The replies are scored as well, so the report can say whether sending together changed any mark.
- **The repeat test (ruling 9).** On each of the three engines: one alarm call and one assessment call from each of three cases, 495 at its last pass, the malaria case at turn 16 and script 15 at its last update. Each call is sent 10 times at temperature 0 with seed 42, first with nothing in between, then with a different call in between each time. The count is how many of the 10 replies are the same as the first, character for character. Then one thing that the engine's own documents offer to make it repeat itself is tried, if there is one, and reported.
- **The marks, fixed before the run.** The hard, soft and time marks of stage 3 stand as numbers, unchanged (15.7). Ruling 10 adds the two rules of the report: who is a candidate, and what counts as faster. All of it is written into the log, with the time, before the first arm starts. A missed hard mark does not stop the bench: the arm is scored as it is and reported as not a candidate, and the other arms go on. No arm is run again to get a pass. Scoring uses the list the pass gives, with a kept list marked (ruling 5), and the report also counts the empty replies each engine gave.
- **What is published (rulings 2 and 11).** One folder at the repo root, called engine-bench. It holds: the report; the cases, with their list and checksums; for each arm, every reply with its case, chain, point, job, how it ended, the tokens and the seconds, as compressed text; the marks and the times as data; a summary of the card's memory; and the exact versions, options and commands. The reference arm is published in the same form. The requests are not stored: anyone can rebuild them from the cases, the prompts and the code. The folder stays under 30 MB. One care with the 495 transcript: the private file that holds it also holds the transcript of another acted consultation, which is not part of the bench. Only the rows of consultation 495 are published. The other rows never enter the repo.
- **The public report** is written for a reader who has never seen OpenConsult. Its first lines answer the two questions behind issue 1 in plain words: do the clinical marks hold on each engine, and is either engine faster in a way that matters to the patient. Then the figures. It says plainly what the bench is: one machine, one card, one model, one user, and a vLLM arm that ran a version of the model made by an individual. It says what was not tested. It makes no case: the figures do the work. It names no person, except the makers of the model versions by their public account names.
- **Two gates.** The plan gate, as before. Then a second gate before anything is published. Claude Code writes the public folder into the private log folder first, and stops. Cowork recomputes the marks and the times from the raw files, and reads every line the private word check prints on the cases and the replies. Those are data: a common phrase said by a made-up patient can match the list. Such a match is judged by Cowork and never edited away. Only then do you tell Claude Code to publish. It copies the folder into the repo and commits it. For every other commit the private word check must print nothing, as before.
- **Tests.** Each names what it pins (5.2). Expected here: ruling 5 (a kept list is marked; an empty first list stays empty; the kept list is handed on; two empty replies in a row), ruling 12, the two bench engines against a made-up server (what each sends for thinking, the form, the context and the limits, and how each ending is read: complete, cut, did not fit, error), and the together sender (both calls are recorded, and one failing does not lose the other). The suite still needs no graphics card and no engine, and passes on GitHub's three systems. What the model says is never asserted in a test (5.2).
- **Documents.** CLAUDE.md gains the bench commands for a second engine. HANDOVER gains an entry with the measurements. The README gains one line that points to the engine bench. NOTICE gains each library added; none is expected, because the engines are spoken to with Python's own library, and the engines themselves are not part of the app and are not shipped. The stage prompt is copied into stage-prompts.
- **Not built (R31).** No setting to choose an engine, no second engine in the app, nothing on a page, no cloud, and nothing for ruling 6.
- **Left on the machine.** The engines and the model files stay where the plan put them until you have read the report. The report gives their sizes and the one command that removes them.
- **What the plan review of stage 3b settled (6 Oct 2026).** The kept list of ruling 5 holds the earlier entries whole. The typical pass of ruling 10 is the median of the 143 passes of consultation 495. A together arm is held against the same three chains of the Ollama arm sent one after another. llama.cpp now has ready-made Linux builds for NVIDIA cards, so nothing was built from source and no sudo was needed. vLLM ran at 0.31.0, the newest on the day, and the repack loaded and answered on it. Ollama as installed takes one call at a time (ruling 13). Nothing that is published names a path, a user or a host of the machine.
- **The bench of 7 Oct, settled by Cowork (rulings 17 to 23).** Six arms, in a new folder of the private log folder, so that nothing of 6 Oct is written over: for each engine the arm with the calls one after another (16 cases, 13 chains) and the together arm (16 cases, the three chains at temperature 0). The engines, the files, the versions and the starts are those of 6 Oct, word for word: Ollama 0.33.3 on Google's file, as the service for the calls one after another and as the second process of ruling 13 for the together arm; llama.cpp b11429 on the same file, with one place for a call and with two; vLLM 0.31.0 on the repack, with the start of the second vLLM arm of 6 Oct. The proofs of 6 Oct are made again on each start before the first round. The rounds: round 1 holds chain A1 and chains B1 to B3; round 2 holds A2 and B4 to B6; round 3 holds A3 and B7 to B10. A turn is one engine in one round: its chain at temperature 0 one after another, its chains at 0.5, then its chain at 0 sent together. The typical pass of a round is the median of the 11 passes of consultation 495 in that round's chain at temperature 0. The median over all 16 cases is reported beside it. Faster (ruling 17) is judged four times: llama.cpp and vLLM, each one after another against Ollama one after another, and each together against Ollama together. Each together arm, Ollama's own included, is also held against Ollama one after another, which is the app today. The marks at temperature 0 are the hard marks of 15.7 counted over three chains: 3 of 3 where the mark says 13 of 13, and none where it says none. The soft marks, and every mark over all 13 chains, are reported beside them as on 6 Oct. The report also gives for each engine: the chains that failed at each temperature, the replies cut mid-sentence, the passes that say time critical and name no action, the pass at which the alarm first shows in each case, the tokens written, and the time for each token in each round. The driver runs with nobody at the desk. A step that fails ends that engine's turn and not the day. No turn starts after 16:45, and what did not run is reported as not run. No code of the repo changes for this run. The scoring by temperature and by round is done by private scripts, and enters the bench's own scorer only when you have ruled what is published (ruling 23).

**Done when you see:**

1. On mlrig you start the app, and the second line in the terminal reads as you ruled.
2. The engine bench report, checked by Cowork from the raw files. For each engine: the hard marks met or not, the typical pass in seconds beside Ollama's, the together arm, the repeat count, and the card's memory.
3. You tell Claude Code to publish, and you push. The folder engine-bench is on GitHub, and the GitHub check is green on Linux, Windows and macOS.
4. If you wish, you answer issue 1 with a link, in your own words.

**Owed after stage 3b.** A session of its own, before stage 6, in which you and Cowork read the two carried prompts together, word for word, as the baseline (ruling 1). You chose this on 6 Oct 2026.

**For the brainstorm of stage 6.** Ruling 5 covers an empty list only. Whether the screen also keeps the earlier list when the assessment call fails is not settled. Today a failed call leaves things as they were built in stage 3. It is put to you at the brainstorm of stage 6, and Claude Code has left a note in HANDOVER. Two findings of the bench go to the same brainstorm. First, sending the two calls of a pass together shortens the pass by about a second on every engine, but the alarm itself comes back about 0.3 seconds later (1.45 s against 1.14 s on Ollama), and on Ollama it needs the setting for two calls at once, which takes about 0.8 GB more of the card. Second, a screensaver that draws on the same card slows every answer by about 40 %: it did so in the first two minutes of 6 Oct, and the reference arm of 4 Oct shows the same figure in four blocks of about seven minutes. That also belongs in the install advice of stage 12.

## 16. Decisions for Wajira

All 54 are decided, as of 4 Oct 2026. In the decisions session of 4 Oct you ruled on six: D2, D5, D17, D25, D32 and D35. The other 32 that were open took their defaults. You can open any of them again in the brainstorm of the stage it belongs to.

| # | Decision | Default |
|---|---|---|
| D1 | DECIDED 4 Oct, default taken. The small parts in 3.3 are left out of v2.0. | Yes, all left out. |
| D2 | DECIDED 4 Oct, your ruling: yes. The second-opinion call and the management plan wait for v2.1. | Yes, v2.1. |
| D3 | DECIDED 4 Oct, default taken. The note call gets the patient line only after a bench passes. Until then it goes without, as today. | Yes. |
| D4 | DECIDED 4 Oct, default taken. v1 consultations are not moved into the v2 database. They stay in Postgres as a research record. | Not moved. |
| D5 | DECIDED 4 Oct, your ruling: yes, for now. Teaching feedback gives no grade and no pass or fail. | No grade, for now. |
| D6 | DECIDED 4 Oct, default taken. No face in teaching mode in v2.0. | No face. |
| D7 | DECIDED 4 Oct, default taken. The first five scripts to record are 15, 14, 01, 03 and 18. | Those five. |
| D8 | DECIDED 4 Oct: v1.1 development stops. main takes no new work. Report-only benches may still run on v1 code until v2 has its own. | Decided. |
| D9 | DECIDED 4 Oct, default taken. Typed teaching is built before Alba's voice and auto mode. | Yes. |
| D10 | DECIDED 4 Oct, default taken. In step 4 of teaching, the learner gets findings only for what they asked to examine. A button then shows the rest. | Yes. |
| D11 | DECIDED 4 Oct, default taken. The targets in section 5 and in 7.3: 600 lines a file, 80 a function, tests no larger than the app, about 30 settings. | As written. |
| D12 | DECIDED 4 Oct, default taken. A free GitHub check runs the tests that need no graphics card on every push to v2, on Windows, macOS and Linux. | Yes. |
| D13 | DECIDED 4 Oct: v2 is built only on Fable 5.1 at high effort, or Fable 5.5 when it comes out. Cowork and Claude Code. | Decided. |
| D14 | DECIDED 4 Oct, default taken. SQLite replaces Postgres. One engine only, on mlrig too. | Yes, SQLite. |
| D15 | DECIDED 4 Oct, default taken. The installed app opens in the browser. It has no desktop window of its own in v2.0. ComfyUI's desktop app has one, built with a second toolkit (Electron). That would be a second codebase to maintain. | Browser. |
| D16 | DECIDED 4 Oct, default taken. Signing the installers. Option A: ship unsigned and document the extra clicks, at no cost. Option B: pay for Apple signing (US$99 a year). Option C: also pay for a Windows certificate (about $150 to $300 a year). | A for v2.0. |
| D17 | DECIDED 4 Oct, your ruling: yes, you have a Mac, a MacBook Air M1. You test the Mac installer on it before the release. It has an Apple chip, so that is the kind of Mac the test covers (6.4). | Tested on your MacBook Air M1. |
| D18 | DECIDED 4 Oct, default taken. The settings page may download a local model or a speech pack when the user clicks, with the size shown first. In v1 the app never downloaded a model; the operator did. | Yes, on a click. |
| D19 | DECIDED 4 Oct, default taken. A Mac uses cloud models only in v2.0. Local models on Apple chips wait for a later version. | Cloud only. |
| D20 | DECIDED 4 Oct, default taken. The first-run screen sets up the one user, and only from the computer the app is installed on. | Yes. |
| D21 | DECIDED 4 Oct, default taken. The Patients page replaces the Today tab and the walk-in queue. | Yes, replaced. |
| D22 | DECIDED 4 Oct, default taken. A patient has a date of birth, not just an age. The app works out the age on the day. | Date of birth. |
| D23 | DECIDED 4 Oct, default taken. The earlier context is the last three approved notes, cut to a fixed length. No summary written by a model. | As written. |
| D24 | DECIDED 4 Oct, default taken. The earlier notes go to the assessment call, the alarm call and Alba's area and question calls. Not to the note, and not to the letters. | As written. |
| D25 | DECIDED 4 Oct, your ruling: yes. For a patient seen before, the switch is on at Start, and the user can turn it off for that consultation. | On, with the switch. |
| D26 | DECIDED 4 Oct, default taken. A forgotten password is reset by a command run on the computer itself. Patients and consultations are kept. | Yes. |
| D27 | DECIDED 4 Oct, default taken. You write or approve at least two follow-up cases for the bench of 8.6, and set the marks before the run. | Two cases. |
| D28 | DECIDED 4 Oct, default taken. Each question call is a fresh request carrying every question and answer so far. A kept conversation is tried in the bench only if you ask for it. | Fresh. |
| D29 | DECIDED 4 Oct, default taken. In auto mode, the assessment and alarm calls are also given the questions beside the answers. | Yes. |
| D30 | DECIDED 4 Oct, default taken. In auto mode, the note call is given each question beside its answer, marked as asked by the system. Claims still cite only what the patient said. It goes in only after a bench passes. | Yes, after a bench. |
| D31 | DECIDED 4 Oct, default taken. Signposting (9.7) is built in v2.0: the area call, one area at a time, the spoken signpost, no handover until every area is opened, unless the time is used. It brings the history scaffold of Task 8 into v2.0 in this form. | Yes. |
| D32 | DECIDED 4 Oct, your ruling: yes. The target: Alba starts speaking within 3 s of the patient's last word. Alba may say one short acknowledgement while the question is made, and no more than one. | 3 s, one acknowledgement allowed. |
| D33 | DECIDED 4 Oct, default taken. The case-card patient from teaching mode plays the patient in the auto-mode bench. | Yes. |
| D34 | DECIDED 4 Oct, default taken. R7 is widened by one thing: Alba may speak a signpost that code builds from the fixed list. The model never writes it. | Yes. |
| D35 | DECIDED 4 Oct, your ruling: yes. The list of areas in 9.7 and the spoken wording for each stand as drafted. They stay yours to correct at any time. | The draft stands. |
| D36 | DECIDED 4 Oct, default taken. Teaching feedback also says whether the learner signposted. | Yes. |
| D37 | DECIDED 4 Oct, default taken. On the live page the doctor can add an area or take one off with one tap. | Yes. |
| D38 | DECIDED 4 Oct, default taken. The intended time is picked on the Start screen, for each consultation, not with the patient's details. The list is 15, 30, 45 and 60 minutes. It opens on the time used last. | As written. |
| D39 | Alba's share of the intended time for the history. DECIDED 4 Oct: 75 %, for now. It is a value on the settings page. | 75 %. |
| D40 | DECIDED 4 Oct, default taken. The live page shows a quiet clock in every consultation: time used, against the time intended. | Yes. |
| D41 | DECIDED 4 Oct, default taken. When Alba's time is used and nothing justifies more, she hands over, and the doctor is shown the areas not reached. The list is kept with the consultation. | Yes. |
| D42 | DECIDED 4 Oct: the time is a guide. Alba may run over for a patient who needs the time, or for high priority questions. The upper limit is the whole intended time; Alba then hands over. The doctor can take over at any point. | Decided. |
| D43 | AGREED 4 Oct. The face. v1 spent five sessions and a rewrite on it in four days, and it once smiled through a chest pain history. After the rewrite, the borrowed engine underneath was no longer doing the work. So: keep the look of the face, and drive it from a plain table of feeling to expression. | Agreed. |
| D44 | AGREED 4 Oct. Deleting, for one user. v1 has void, unvoid and purge, built for an admin. So: one delete, which really removes the audio, the transcript and the note, and leaves a line in the audit log. | Agreed. |
| D45 | AGREED 4 Oct. At Stop, the final transcript is set against the live one, and any passage missing from the final is shown to the doctor. | Agreed. |
| D46 | AGREED 4 Oct. A first-run self-test: the app transcribes a short clip that comes with it and checks the words. | Agreed. |
| D47 | AGREED 4 Oct. The stand-in patient is built (13.5), as a test tool outside the app. It can also play both parts, so a whole consultation runs with no person. | Agreed. |
| D48 | AGREED 4 Oct. A human actor is still used for two things: the recordings that choose the speech model, and one consultation at the end of each stage that changes the consultation. The stand-in covers everything in between, including runs while you are away. | Agreed. |
| D49 | DECIDED 4 Oct: both virtual actors speak through the monitor's speaker. | Decided. |
| D50 | DECIDED 4 Oct: the computer may speak out loud in the empty room while you are away. Tests run through the speaker, to best copy the room. | Decided. |
| D51 | AGREED 4 Oct. On the player for a past consultation (8.8): pressing a line of the transcript plays the sound from that line, and a strip shows how loud the recording is along its length. | Agreed. |
| D52 | AGREED 4 Oct. One last v1 release on GitHub, tagged from today's main, with a short note to users that v1.0.0 drops speech and this release fixes it. | Agreed. |
| D53 | AGREED 4 Oct. The doctor's voice is learnt once at first run, and each line is marked doctor or not doctor. It is benched in stage 5 before it is relied on. | Agreed. |
| D54 | AGREED 4 Oct. The app refuses to write over an existing recording (R18). | Agreed. |

## 17. Sources

Project:

- The repo at commit b4cd9b9 (github.com/IndyWH/OpenConsult): CLAUDE.md, HANDOVER.md, PHASE_7_SPEC.md, .env.example, app/, tests/, mock_consultations/.
- In /home/indy/Work/openconsult-review: V1_LESSONS.md, CODE_REVIEW_2026-10-01.md, REFACTOR_DRAFT.md, V1_1_PLAN.md, and the task reports in v1.1-logs (3F, 3I, 3L, 13 to 17). Tasks 18 and 19 are cited from their summaries in V1_1_PLAN.md.
- LESSONS_FOR_V2.md at the top of the v1 repo, commit b2e61d0.

Outside:

- RCGP, how the curriculum is structured: https://www.rcgp.org.uk/mrcgp-exams/gp-curriculum/how-the-curriculum-is-structured
- RCGP, marking and results for the SCA: https://www.rcgp.org.uk/mrcgp-exams/simulated-consultation-assessment/Marking-and-results
- The Calgary-Cambridge guide to the medical interview (internal summarising and signposting): https://www.mygpnotes.com/clinical/guide-to-the-medical-interview-calgary-cambridge-guide
- Speechmatics pricing and models: https://www.speechmatics.com/pricing
- AssemblyAI, real-time speech recognition compared: https://www.assemblyai.com/blog/best-api-models-for-real-time-speech-recognition-and-transcription
- NVIDIA Nemotron Speech Streaming model card: https://huggingface.co/nvidia/nemotron-speech-streaming-en-0.6b
- Comfy Desktop, how it installs: https://github.com/Comfy-Org/Comfy-Desktop
- Microsoft, code signing options for Windows app developers: https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options
