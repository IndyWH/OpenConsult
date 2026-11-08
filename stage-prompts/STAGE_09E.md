OpenConsult v2.0, run 9e: the frequency rule of the letter check, and the README section on the cloud model. No call to any service.

WHAT THIS IS
Run 9d2 (commits 739b45a to 7474c1a, not all pushed) benched Claude Haiku 5.5 under the rules of rulings 19 and 20, and the owner ruled on 8 Nov 2026 that the figures stand and the model is offered (15.13, ruling 24). Two small things are left from it. First, the letter check marked a true sentence in 13 of 13 letters of one case because the model wrote four times a day where the note wrote qds: the check reads the frequency abbreviations of a prescription and their number words as one figure from now on. Second, the owner asked that the repo show clearly why the cloud model is Claude Haiku (ruling 21): Cowork has drafted the section and it goes into the README as it stands. Nothing is offered on any page beyond this (R31). No call to any service. Done when the owner sees the two commits and Cowork has checked them.
The spec is V2_SPEC.md. Read 15.13 rulings 21, 23 and 24 and the details headed for run 9e; then 15.12 ruling 4 and 15.13 ruling 20. Then, in this repo, stage-prompts/STAGE_09D2.md: EVERY RULE AND FOLDER OF THAT PROMPT AND THE PROMPTS IT STANDS ON HOLDS IN THIS RUN except where this prompt changes it. Where this prompt and the spec differ, the spec wins: stop and report.
OpenConsult is a research and education prototype. Never real patients. Every consultation is acted.

MODEL
This runs on Fable 5.1 at high effort. Say in your first line which model you are. If you are not Fable 5.1, stop there.

WHAT CHANGES
1. Names. Every file you make in LOGS begins stage9e- or STAGE9E_. Earlier files and folders in LOGS are read only. Files of Cowork's whose names begin cowork-spec- or stage9e-readme- are not yours to change.
2. The spec. Check it with sha256sum before anything else. It must be:
   4e45032a105812e373be79c2f916f1bb674e47e6b5f4ddd9633977353b959249  V2_SPEC.md
   HEAD holds 292ec7cb; the disk holds rulings 23 and 24 of 15.13, the details for run 9e, and four small dated changes in 7.3 (the Alba row), 9.6, 15.13 ruling 13 and the row of D32. The branch is v2 and HEAD is 7474c1a. git status --porcelain must print only V2_SPEC.md as modified. Otherwise stop and report.
3. No key is read, no address outside this machine is reached but uv to the package index, no bench is run. The KEY folder is not opened, listed or named.

PART 1. TWO COMMITS, THEN THE SHORT PLAN, THEN STOP
Commit 1. Subject: Run 9e: the spec with rulings 23 and 24 of stage 9
   V2_SPEC.md alone, as it stands on disk, checksum proven.
Commit 2. Subject: Run 9e: the run prompt
   Copy this file to V2/stage-prompts/STAGE_09E.md. Prove with cmp that it is identical.
Then write LOGS/STAGE9E_PLAN.md, a page at most:
1. The frequency rule: where it goes in letter_check (the reading of figures of a sentence and of its cited lines), the table (od, om, on, mane, nocte, once as 1; bd, twice as 2; tds as 3; qds as 4), whole words only, both ways; the tests, each with what it pins (the stop sentence of case A against its note line kept with no mark; a figure the lines do not hold still marked; a word that merely contains the letters not read as one; every existing test of the check still green); and the recount of M3 on case A from the stored replies of run 9d2 (LOGS/stage9d2-bench-letters), by letter_marks with the rule in place, as a count for HANDOVER, no call made.
2. The README: the section of LOGS/stage9e-readme-section.md inserted as it stands, byte for byte, after the list and before the line that OpenConsult is a research and education prototype; proven by code that the inserted text equals the file; the private word check on the staged README.
3. The two commits and the HANDOVER line.
Then stop. Wait for the owner. He will type: Approved. Go.

PART 2. BUILD
Commit 3. Subject: Run 9e: the letter check reads prescription frequencies as figures
   letter_check and its tests; the suite green; then the recount of M3 on case A from run 9d2's stored replies, written to LOGS/stage9e-recount.out, counts only.
Commit 4. Subject: Run 9e: the README says how the cloud model was chosen
   README.md with the section; HANDOVER.md gains one entry (the rule, the recount's figure, the README section, under 500 lines).
Before each commit: the suite green, the private word check on the staged files printing nothing, no home path, no machine name, no publisher name.

FINAL MESSAGE
Five lines at most: the spec's checksum as given and committed; the recount of M3 on case A with the rule (n of 13, beside 0 of 13 in run 9d2); the suite's count; the number of commits and the last hash; then this line for the owner: Tell Cowork: Run 9e built. Do not push yet.
