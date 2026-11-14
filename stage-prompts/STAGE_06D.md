OpenConsult v2.0, step 6d: the place to correct a doubted drug name, and the bench of Claude Sonnet

WHAT THIS IS
Step 6c built the marks on drug names the language model doubts. The owner ran it in the room on 14 Nov 2026. The mark did what it is for: the speech choice wrote three plain words for one medicine, the note wrote a different real medicine, and the mark led him to it. But the page led his hand to the wrong place twice: first to the note, where the sign does not answer, then to a highlighted copy of the words that cannot be typed in. And the note was crowded with signs, on 16 of its 17 entries. A mark a doctor cannot act on does not protect a patient. From the patient's side this run does one thing: the warning of a doubted drug name becomes the one place where the doctor hears the line, types the right name over the wrong one, and ticks it as settled; then one press drafts the note again from the corrected lines. The signs come off the note, and a pressed line stops at its end. Beside the build there is one small bench: Claude Haiku raised too many false alarms on drug names to be offered in cloud mode, so the next model up, Claude Sonnet 5.5, is benched on that one call.
The spec is V2_SPEC.md. Read in 15.10 rulings 6, 11, 20, 23 and 25 to 31, and THE DETAILS OF STEP 6D, which follow the details of the second run of step 6c: they are the design of this run and you build them as written. Read the details of step 6c and of its second run for what stands. Then, in this repo, stage-prompts/STAGE_06C.md and STAGE_06C2.md. EVERY RULE OF STAGE_06C.md HOLDS IN THIS RUN except where this prompt changes it. Then, in LOGS: STAGE6C2_REPORT.md, and STAGE6C_PLAN.md with STAGE6C_PLAN_REVIEW.md for how the bench of Claude Haiku was run. Where this prompt and the spec differ, the spec wins: stop and report.
OpenConsult is a research and education prototype. Never real patients. Every consultation is acted.

MODEL
This runs on Fable 5.2 at high effort. Say in your first line which model you are. If you are not Fable 5.2, stop there.

THE FOLDERS
V2, LOGS and KEY as STAGE_06C.md gives them, with one change: every file and folder you make in LOGS has a name that begins stage6d- or STAGE6D_. Everything else in LOGS is read only, the files and folders of 5e, 6c and 6c2 included: copy what you reuse under a stage6d- name. Files whose names begin cowork- are not yours to change.
No engine is started in this run and no call goes to the local model. The card is not needed.

BEFORE YOU START
1. Read V2/CLAUDE.md and the newest entry of V2/HANDOVER.md.
2. Check the spec with sha256sum. It must be:
   f8a75a3b8dce0a9c7ff66fc28c6a1cce3355ad67dcbd0912e97deeaeafde04bb  V2_SPEC.md
   HEAD holds 6ace90ba; the disk holds rulings 25 to 31 of 15.10 and the details of step 6d. If it differs, stop and report.
3. The branch is v2 and HEAD is 3be609f23506a9d96f5e4a48910b1c9b40ba577a. git status --porcelain prints one line only: V2_SPEC.md modified. Otherwise stop and report.
4. Make an empty file LOGS/stage6d-start.marker. Start the record of connections now, before any other command, and keep it for the whole run.
5. Look, read only, and write what you find in your log: whether anything answers on 127.0.0.1 at ports 8000, 8001 and 8172. Change nothing. If the start check later finds its port taken, print exactly: Waiting for the app on port 8001 to be closed. Then stop; the owner will type: Closed. Go.
6. The stored pages and readings are LOGS/stage5e-run and LOGS/stage5e-tables3; the local model's and Claude Haiku's marks on the drug names are in LOGS/stage6c2-marks, LOGS/stage6c2-haiku and LOGS/stage6c2-haiku-marks. All read only. No sound is read in this run.

WHAT CHANGES FROM STAGE_06C.md
1. WHAT LEAVES THE MACHINE. Nothing, until Part 3. In Part 3, to https://api.anthropic.com and to no other address: the approved drug-name prompt, its form, and the text of the 24 stored pages as the heading and the numbered lines. The label check is not sent in this run.
2. THE CLAUDE SERVICE, as rule 5 of STAGE_06C.md, with one change: the model is claude-sonnet-5-5. Cowork read the service's own page on 14 Nov 2026 (platform.claude.com/docs/en/models/overview): Claude Sonnet 5.5, claude-sonnet-5-5, 2 dollars for a million tokens read and 10 for a million written. Write these into your plan as given. Before the first call, ask the service's own list for the model; if it is not listed, stop and report.
3. NO WORD A MODEL READS IS NEW, and no prompt file, frame or form is touched. The page changes; the call at Stop does not.
4. THE SENTENCES. The drafts are named in the details of step 6d; copy each letter for letter into the file of words. Any other sentence a person would read that you find you need: give it in full in your plan, and add none after the plan without saying so in the report.
5. NOT BUILT. The details name what is not built; build none of it (R31). Above all nothing of ruling 31, no correcting of a drug name in the note, and nothing for cloud mode.
6. Commit subjects begin Stage 6d. The report is LOGS/STAGE6D_REPORT.md, the log LOGS/stage6d-run.log.

PART 1. TWO COMMITS, THEN THE PLAN, THEN STOP
Commit 1. Subject: Stage 6d: the spec with rulings 25 to 31 of stage 6 and the details of the step
   V2_SPEC.md alone, as it stands on disk, checksum proven.
Commit 2. Subject: Stage 6d: the stage prompt
   Copy this file to V2/stage-prompts/STAGE_06D.md. Prove with cmp that it is identical.
Then write LOGS/STAGE6D_PLAN.md. Keep it short. It holds, in this order:
1. THE ROW: how a row of a doubted name is built and where; how the field looks until it is pressed and how it works with no script; how the typed words reach the line; the same words twice; words over two lines, and WHAT A LINE HOLDS AND SHOWS IF TAKING A PIECE OUT WOULD LEAVE IT WITH NO WORDS, which Cowork's review rules on; the play button's stretch; the tick, its two states, and how each is told without colour.
2. SETTLED AND OPENED: what each press writes; the count on Approve; the highlight on the line; the press beside the line's box; the second Draft the note again under the rows; the read-only page.
3. THE SIGNS: every place the sign is taken out of, and each test restated, named one by one.
4. A PRESSED LINE: every press that plays a line, and those that play on as before.
5. THE TABLES of version 10 and how a folder of version 9 comes forward.
6. Every sentence a person would read that is new or changed, in full, each marked as the owner's or as a draft.
7. EVERY TEST you intend, each with the ruling or the rule it pins.
8. THE BENCH OF CLAUDE SONNET: what the bench commands gain to send the drug-name call alone and to count its marks alone; the commands with their exact words and folders; the first call; the two rounds; the number of calls, the minutes and the cost you expect; D1, D2 and D3 as numbers, with the local model's and Claude Haiku's figures beside them, read from the stored results and from no report; how you prove that only the text of a page is sent.
9. Anything in the spec or in this prompt that is wrong, silent or in conflict: do not fix it yourself.
Then print five lines at most, and stop. Wait for the owner. He will type: Approved. Go.
He may first tell you to read a review file in LOGS. If so, read it and follow it. It may change your plan.

PART 2. THE BUILD
Item 1. The suite as it stands: the number of tests, the time, none skipped.
Item 2. As the details give it, in commits of one logical change each. A good order: the tables of version 10; the signs off the note; the row with its field and its play button; the tick, settled and opened; the press beside the line's box and the second Draft the note again; a pressed line stops at its end; the words and the home page's account. What a model writes is never asserted in a test.

PART 3. THE BENCH OF CLAUDE SONNET
Item 1. The suite, green. The private word check on the text to be sent, as a count, which must be 0. The service's list asked for the model. Then the first call: one page through the drug-name call with the app's own form; the cost and the wait measured on it. If it does not come back to the form, stop and report; nothing more is sent.
Item 2. The other 23 pages. Then the second round of the same 24. Into LOGS/stage6d-sonnet. A failed call is kept as failed and never sent again.
Item 3. The count from the stored results alone, twice, byte for byte the same. Then D1, D2 and D3 on the first round against the numbers of your plan, the entries dropped, and how many marks are the same in both rounds.
Item 4. Read your own tables as a doubter would, and by hand on the stored pages: every drug name the local model marked and Sonnet did not, and every Sonnet mark on a word that was written rightly. If the counting is wrong, say so plainly.
Item 5. Whether the marks hold or not: no word of a prompt is changed, nothing is run again, and nothing is built for cloud mode. HANDOVER says that the drug-name marks in cloud mode wait for the owner's ruling. You do not choose for the owner.

PART 4. THE CHECKS AND THE LAST COMMIT
Part 5 of STAGE_06C.md, with these changes. In item 2 the prompt folders are compared with 3be609f and show no change at all. In item 3 no address is named before Part 3. In item 4 the files of 6c and 6c2 count among those that are not yours. In item 5 the README gains what the details ask, the dated paragraph included.

THE REPORT
LOGS/STAGE6D_REPORT.md. It is private. First, for the patient, in plain words: what a doctor now does when a drug name is in doubt, in the order his hands do it, and what he no longer has to do. Then, each under its own heading: the build, commit by commit; every sentence that is new or changed, in full, the owner's and the drafts apart; the tables of version 10; the bench of Claude Sonnet, each mark with the local model's and Claude Haiku's figure beside it, the pages of Speechmatics live apart, the entries dropped, the two rounds, what item 4 of Part 3 found, the calls, the cost and the wait; what left the machine; what in LOGS may now be removed, without removing anything yourself. Then THE ROOM RUN: the steps for the owner, short and in the order his hands do them, for the item Done when you see, for 6d. Last: anything you flagged.

FINAL MESSAGE
Eight lines at most: the spec's checksum as given and committed; the build, with the suite's count; Claude Sonnet on the drug names, each of the three marks held or missed with its figure, and the marks that were the same in both rounds; the calls sent, what they cost, and that nothing went to any other host and no key was read by you; the number of commits and the last hash; anything you flagged; then this line for the owner: Tell Cowork: Step 6d built. Do not push yet.
