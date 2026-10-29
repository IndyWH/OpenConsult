# HANDOVER

The record for OpenConsult v2: decisions and measurements, newest first.
It stays under 500 lines. Older entries move to HANDOVER_ARCHIVE.md.
The spec is V2_SPEC.md. The record for v1 is the HANDOVER.md on the main branch.

## 2026-10-28. Stage 8b: the guideline corpus, its search and its bench; the panel held

Built in one session on 28 and 29 Oct 2026, under the plan review of
Cowork (five points; all are in; the owner's ruling on the stop was A: a
third fetch, the reranker's, by name). The unattended bench ran the
guideline queries on vLLM and the Gemma 4 bench of stage 3 on two
Ollamas (ruling 12); the panel's marks did not all hold, so the panel
and its record are held in the private log folder as a patch, as 7b and
8a held theirs, and nothing of the reranker is wired either (rule 5 of
the stage). The report is STAGE8B_REPORT.md in the private log folder.
The room run is the owner's, still to come: the Guidelines section is
his to try now; the panel waits on his ruling on the figures.

The spec, committed once, not a character changed: eee605d
(sha256 d913903c..., 8a marked done and rulings 18 to 23 of 28 Oct).

The rulings it builds, one line each (spec 15.12):
- 5: the corpus ships empty; the Guidelines section of Settings takes a
  file from this computer (HTML, PDF or plain text) with its title, its
  publisher and the one statement, splits it, embeds it and lists it
  with Remove; every add and remove audited; the app fetches nothing.
- 6: the panel (held): called after a pass whose top two differentials
  differ from the last search's pair, one at a time, never during Stop;
  the summary with [n] marks each a press to the passage with its
  source's title and publisher, or the one line that the loaded
  guidelines do not cover the names; a failed call touches nothing of
  the pass or the alarm; with no document loaded, no call.
- 7: openconsult/prompts/guideline.prompt.txt sha256 7e07e017..., the
  approved block byte for byte with one line break, proven by hash and
  by cmp against Cowork's copy. The frame is fixed words in
  guideline.frame.txt (QUERY: {query}, a blank line, PASSAGES: and
  {passages}) and guideline.passage.txt ([{n}] {source} and the text
  under it), the form v1's three fields; the patient line opens the
  message (R11); the background block never reaches it (D24).
- 9: the reranker benched as an arm, in the worker's own environment and
  process, on its own device; its three marks held; not wired, because
  the panel's did not (the plan's rule, accepted by the review).
- 10, 19: the bench, below. 11: guideline_answer keeps the names, the
  query and the passages sent with their sources and similarities, the
  named parts; the model_call row the request as sent.
- 12, 21, 23: the two Ollama arms, below; vLLM stopped and started by
  the owner's script for this run alone; the service never touched.
- 18: the loader command, every file through the same code as the page.
- Ruling 25 of 15.9: every passage records the model and revision that
  built it; an index built with another model is never searched.

The record (6.5): schema version 8 brings a version 7 folder forward with
every row kept: guideline_source (title, publisher, file name, kind,
hash, size, date added, by the page or the command, the statement
accepted, the passage count, the model, the date removed),
guideline_passage (the trail, the text, the words, the vector as 768
float32 at unit length, the model) and guideline_answer (the pass, the
names, the query, the passages sent with sources and similarities, the
candidates, the top similarity, the floor, whether the reranker ran, the
outcome, the call, covered, the summary, the numbers cited, the invalid
marks, the failure, the search and the whole in milliseconds, shown).
Delete takes the answers with the consultation (D44).

The loader (guidelines/passages.py): HTML by its headings with the
standard library's parser, one passage per leaf section with its trail,
a stem and its bullets one unit, nav and the like dropped, as v1's
chunker did; PDF by pypdf's text in page order at blank lines; plain
text at blank lines; MAX_WORDS 350 and MIN_WORDS 40 (v1), a small
section joining the next under the same parent, a last small subsection
joining its parent section, a long one split at paragraph ends and a
long paragraph at sentence ends, never inside a sentence; a file with no
passage of 40 words is refused. The corpus of the bench: 47 files, 1,143
passages, 75 outside 40 to 350 words, 4.7 s to cut and embed on the
card, 3 to 106 passages a file.

The search (guidelines/search.py; 6.3): the names' vectors from the
worker in one request, the dot product over every loaded passage from an
index in memory read again after a change, the nearest 12 a name, merged
by passage at the higher similarity, at most 2 from one source, 6 in
all; GUIDELINE_FLOOR = 0.45 (v1's) under which nothing is sent; the
reranker's reordering before the floor and the cut when a search asks
for it (the bench alone). 29 to 53 ms a search without the reranker on
1,143 passages, 53 to 76 with it on the card, 1.6 to 4.6 s with it on
the processor.

The summary call (guidelines/summary.py): the message from the frame,
the call through the door (job guideline, 1,000 tokens, 60 s), the
outcome by code: covered false is a refusal with the model's one
sentence; a covered reply citing no number it was given is a refusal
(no_citation); a covered reply's marks are checked against the numbers
sent, the invalid ones counted and left as plain text.

The worker (guidelines/embedding2, moved from the bench kit with its
lock file; guidelines/embedder.py, environment.py): started at app
start where the room check put it, the load not waited for, the first
use waiting once; a death a failure with its reason and no restart by
itself; openconsult install-guidelines builds the environment from the
lock file and fetches EmbeddingGemma 2 at its pinned revision with no
token, and with --reranker the reranker at the revision its page named
at the fetch (953dc6f6..., pinned with the weights' hash beside it);
a model whose weights are there and match is never fetched again
(the review, point 4). The worker loads in about 7 s on the card and
held 1,004 MiB with the embedding alone through its arm and 2,324 to
2,438 with the reranker through its, about 1,430 more (the report).
One finding for the room: at the load of the 47 files the worker's
process peaked at 4,892 MiB (the card 23,131 of 24,564 beside vLLM),
the working room of embedding sixteen passages at a time, which the
room check's 1,010 does not count; an Add beside vLLM and a speech
worker could run the card out, the worker would die and the Add be
refused on the control until the next start. The fix proposed in the
report, not made after the bench: embed one passage at a time at a
load, or count the load's peak in the room check.

The bench (rulings 10 and 19; bench/guideline.py, guideline_marks.py,
guideline_load.py): fifteen approved queries (twelve real, from the
documents' headings; three made), each once through the app's search
and 13 chains through its call, once without the reranker and once with
it, on vLLM 0.31.0 with the model of 3c, the patient line 50 and F for
every query; 390 summary calls, none failed, about 1.2 s each, 8 minutes
for both arms. The marks, fixed before the run as numbers:

| mark | what | without the reranker | with it |
|---|---|---|---|
| G1 | cites only passage numbers it was given, 13 of 13, each real query | held, 12 of 12 queries | held, 12 of 12 |
| G2 | under 150 words, 13 of 13, each real query | missed on Q07 (1 of 13) and Q12 (11 of 13); held on 10 | missed on Q05 (12), Q07 (3), Q09 (12), Q12 (10); held on 8 |
| G3 | each made query refused 13 of 13 | held, 3 of 3 | held, 3 of 3 |
| R1 | the right passage first in more queries with than without | 11 of 12 without | 12 of 12 with: held |
| R2 | none first without lost from the top three with | | held, 0 lost |
| R3 | every search with the reranker under 1 s on this card | | held, slowest 76 ms |

The over-length summaries run 150 to 178 words; the three made queries
were refused by the model in 78 of 78 chains, not by the floor: their
top similarities (0.66 to 0.68) are above 0.45, and the lowest real
query's is 0.72, so the floor is the owner's to set again (rule 5). The
first scoring's matching of the right passage read the trail's last
heading alone and missed six numbered sections' subsections (R1 then 6
against 5); commit 2bd8308 matches any heading of the trail, its
section number left out, and the scorer matches the stored searches
again from the corpus; both scorings are in the report.

The two Ollama arms (ruling 12), the stage 3 command on its 16 cases,
13 chains, the hard marks of 15.7, report only, no verdict (the owner's):


| | the service, 0.40.7 | the private release, 0.40.12 |
|---|---|---|
| every hard mark of 15.7 (H1 to H7) | met, 13 of 13 each | met, 13 of 13 each |
| soft marks | 8 of 9 (S12: script 05's alarm in 7 chains against 4) | 8 of 9, the same |
| 495: median pass, slowest pass (6.0, 8.0 s) | 4.76, 6.28 | 4.71, 6.26 |
| chains, failed; the arm's time | 208, none; 2 h 26 min | 208, none; 2 h 27 min |

The same model blob (digest 2dd70431...) in both; the two gave the same
differential names at every pass in all 208 chains. The private release
was installed by the run (ruling 21): v0.40.12 of 27 Oct, its Linux
amd64 archive checked against the release's own sha256 file, extracted
under the engine folder as ollama-0.40.12 with its own home, the model
pulled once into ollama-0.40.12-models beside it, started on port 11500
and stopped after its arm; the service, its unit, its port and its store
untouched; vLLM stopped and started by the owner's script, the card read
before and after each; the service let its model go by itself (1,630 s)
with no request sent to it. The first driver stumbled three times in its
own steps (a raw count before the schema came forward, a cold first call
over the 60 s, the asset's ./ name); the second driver reran every step
but the checks; the report says it plainly.

The proof on this machine (stage8b_proof.py on stage8b-data with the
patch applied for the proof alone, against vLLM and the real worker on
the card; stage8b-proof.log and -part2.log; counts only): the folder came
forward with every row kept; the section listed the 47 sources, Remove
took one out with its 23 passages and Add put it back through the page
in 0.13 s, both audited; a headache story's two searches gave two
covered summaries (0.79 and 0.84 top similarity, 2 passages each, 46 ms
a search, 1.2 s a call), the row's parts by name rebuilding the request
byte for byte (2,174 bytes), the patient line first, no background, the
marks opening passages with title and publisher; a nasal polyp story's
three searches gave the refusal line (the model's covered false at 0.68
to 0.73, over the floor); nothing of the panel in the alarm, assessment,
label check, note, list or letter calls nor on the review page; a timed
out summary call left the pass and the alarm as judged; the corpus
emptied gave no_corpus and no call.

What was built, by file: guidelines/{sources,passages,texts,loading,
embedder,environment,search,summary}.py and embedding2/ (worker.py with
the rerank request, fetch.py with the reranker's fetch); web/guidelines.py
and the section in settings.html; bench/guideline.py, guideline_marks.py,
guideline_load.py; the prompt, the two frames and the form; the job;
schema 8; the multipart reader in web/pages.py; MadeUpEmbedder in the
fakes. Held in the patch: guidelines/panel.py, static/guidelines.js, the
pane in live.html, the hook in consult/live.py, the state, the words.
The constants: GUIDELINE_FLOOR 0.45, NEAREST_PER_NAME 12, PER_SOURCE 2,
SENT 6 (v1 app/rag.py); MAX_WORDS 350, MIN_WORDS 40 (v1 app/chunking.py);
UPLOAD_LIMIT_BYTES 50,000,000 and BATCH 16 (the plan); WORKER_READY_S 300
and WORKER_REQUEST_S 120 (the speech workers'); the job's 1,000 tokens and
60 s (the plan, until this bench: the longest reply 1.8 s, under 300
tokens). Every sentence shown to the user is in words.py, drafts for the
owner. pypdf 6.21.4 (BSD-3) is the one library added (NOTICE).

Sizes (5.4): no function over 80 lines; no file over 600 but words.py at
792, accepted under 5.4 as 7a's and 8a's reviews did. The suite: 748 tests (585 before 8b; 5 more in the patch), green three times before the last commit, none skipped
Nothing pushed. The private word check printed nothing before every
commit. R21: no file in the repo names the publisher; the private check
holds its name; one test of stage 3, that no prompt holds a guideline
word, now passes over the summary prompt's own approved words.

What this stage has made untrue: README's so far and CLAUDE.md's lines,
fixed in this commit; 7a's and 7b's entries, moved to the archive; the
spec's 15.12 Done when you see, which waits on the owner's ruling and his
room run (Cowork's); the plan's items 5 and 9 where they said the panel
would be wired and the room run would show it; the 8a report's line that
the panel lives on the live page, true of the patch alone. For the view
run of ruling 11: guideline_answer.names, .query and .passages (each
with passage_id, source_id, title, publisher, trail, text, similarity,
rerank_score, cited) are the named parts; model_call.request the request
as sent, tied by call_id; summary.message(query, passages, patient)
rebuilds the request from the row's parts byte for byte.

## 2026-10-28. Stage 8a: the referral letters, benched four times, then wired

Built in five sessions on 28 Oct 2026. The plan was reviewed by Cowork the
same day (three points; all are in). The bench of the two new prompts ran
first and stopped at its figures four times; the owner ruled after each
run (spec 15.12, rulings 14 to 17), three sentences of the letter prompt
changed after the first, four after the second, one after the third, and
five rules of the check were made finer; the fourth ruling let the figures
stand and wired the page from the patch held since the first run. The
report is STAGE8A_REPORT.md in the private log folder. The room run is the
owner's, still to come: the steps are in the report, and his reading of
the letters is the judge of them (V1_LESSONS, the twelve, point 1).

The spec, committed five times, not a character changed: 6e46f3d
(sha256 c5833101..., the brainstorm of 28 Oct), 731aa30 (5d5a374a...,
ruling 14), be3e933 (67d60a1c..., ruling 15), a7ade2d (1d8529a7...,
ruling 16), 8cecb12 (56e9dd5f..., ruling 17).

The rulings it builds, one line each (spec 15.12):
- 1: one letter per specialty, any number per consultation; code writes
  the salutation (Dear Consultant and the item's title), the Re line
  (name, date of birth and sex as the consultation ran with them) and
  the sign-off (Yours faithfully, the one user's title and name); the
  model writes the body only.
- 2: after Approve the review page shows the referral items: the ones
  the note states, then, under a line that they are the model's
  suggestions and not advice, the ones it suggests; the list call runs
  once per approved note, at the first opening after Approve; code sorts
  the items by the cited Plan line and the specialty's words
  (referrals.sort_items), never the model.
- 3 and 8: openconsult/prompts/letter.prompt.txt sha256 220d61f0...
  (as ruling 16 left it; b2e5e816..., d10ccaa4... and 49c1f652... were
  the three earlier texts of the day) and referrals.prompt.txt
  5eab5bb5..., each the approved block byte for byte with one line
  break, proven by hash and by cmp against Cowork's copies. The two
  frames are fixed words in letter.frame.txt (SPECIALTY: {specialty}, a
  blank line, APPROVED CONSULTATION NOTE: and {note}) and
  referrals.frame.txt (APPROVED CONSULTATION NOTE: and {note}); the
  letter call sees each Assessment entry's words replaced by
  letter.withheld.txt ([assessment withheld from referral letters]), the
  numbers unchanged. The patient line opens both messages (R11); the
  background block reaches neither (D24).
- 4: the check in code (consult/letter_check.py), per sentence against
  the lines its paragraph cites: a heading and an Assessment line are
  never citable; a number must be in the cited lines (the age excepted;
  a figure inside a word counts); a result verb over a line that only
  plans the test is an upgrade; the model's placeholder anywhere fails
  the sentence; an expectation sentence stands only on a line holding
  Patient's expectations and a colon, else dropped; an allergy sentence
  stands only on a cited line holding the word, else dropped and
  counted; a failed sentence becomes the placeholder, one for a run; the
  letter is refused under half grounded, LETTER_GROUNDED_HALF = 0.5
  beside CITATION_HALF.
- 8: name a specialty, two fields and one control, a named item and its
  letter with no list call.
- 10: the bench, below. 11: the note lines sent are a named part of the
  record, in referral_list.note_lines and letter.note_lines.
- 14 to 17: the four benches and the rulings on them, below.

The record (6.5): schema version 7 brings a version 6 folder forward with
every row kept: referral_list (the approved note it was made from, the
call, the note lines sent, the failure), referral_item (kind stated,
suggested or named; specialty, title, reason, urgency, the lines cited,
position), letter (its item and number, the call, engine, version, tag
and digest, the prompt's hash, the note lines sent as masked, both
bodies, the check's detail, the four counts, refused, the failure, the
seconds, the doctor's refusal), letter_edit (before and after),
letter_approval (one per letter, the text). Delete takes them with the
consultation, counted in the audit line.

The bench (ruling 10; bench/letters.py and letter_marks.py): four
approved notes (A, B by reference to 7b's cases; C dysphagia and D polyp
with psoriasis, made for 8a), 13 chains each (A1 to A3 at temperature 0,
B1 to B10 at 0.5), one list call a chain and one letter call per
specialty, through the door with the app's own numbering, frames and
check; vLLM 0.31.0 at the local port, the model of 3c (digest
2096d38d...), thinking off in every request and none in any reply; about
three minutes a run; 260 letter calls over the four runs, one failed
(a loop of bracketed line numbers to the 2,500-token limit, 13.8 s,
stored as too_long). The five marks, fixed before the first run and
never loosened: M1 no letter refused and no failed call, 13 of 13; M2
the placeholder absent in at least 12 of 13; M3 no Assessment citation
and no number outside the cited lines, 13 of 13; M4 no expectation
sentence for the one note without the line, 13 of 13; M5 the stated
list as the note states it, 13 of 13. The four runs side by side, chains
holding the mark of 13 (run 1 the morning prompt and the first check;
run 2 after ruling 14; run 3 after ruling 15, the finer check; run 4
after ruling 16, the allergy rule):

| mark | A 1 | A 2 | A 3 | A 4 | B 1 | B 2 | B 3 | B 4 | C 1 | C 2 | C 3 | C 4 | D 1 | D 2 | D 3 | D 4 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M1 | 13 | 13 | 13 | 12 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 |
| M2 (12 needed) | 12 | 8 | 0 | 9 | 13 | 13 | 10 | 13 | 13 | 2 | 13 | 13 | 11 | 9 | 10 | 13 |
| M3 numbers | 12 | 8 | 1 | 9 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 12 | 10 | 10 | 13 |
| M3 Assessment | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 |
| M4 (A only) | 13 | 13 | 13 | 13 | | | | | | | | | | | | |
| M5 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 12 | 12 | 12 | 12 | 13 | 13 | 13 | 13 |

Marks held: 13, 11, 11, 13 of 17. The fourth run, as numbers: held, M1 on
B, C and D, M2 on B, C and D, M3 on B, C and D, M4 on A, M5 on A, B and
D; missed, M1 on A (12 of 13, the one failed call), M2 on A (9 of 13),
M3 on A (9 of 13 without a number outside the lines), M5 on C (12 of 13,
the list call's empty answer on seed 5, the fourth time). Every mark held
in every chain at temperature 0, the app's own sampling (10.4). The
longest finished letter reply was 505 tokens in 2.88 s against the
letter job's 2,500 tokens and 120 s; the longest list reply under 300
tokens in 1.5 s against 1,500 and 60 s.

The owner's four rulings of the day, in plain words:
- 14, after the first run (13 held): nothing invented reached a letter,
  but C's letter never said the suspected-cancer referral was urgent,
  and A's letter gave the medicines as they were before the Plan changed
  them. Three sentences of the letter prompt changed (the urgency
  said; the medicines as the Plan leaves them); no rule of the check
  changed; run again.
- 15, after the second run (11 held): the two things were now written,
  but every C letter wrote the haemoglobin with a unit the note does not
  give, the upgrade rule replaced C's true results sentence in 11 of
  13, and the model's own placeholder inside a sentence went uncaught.
  Four sentences of the prompt changed (no unit the note does not give,
  no reckoning; a started medicine with its dose; citations in
  note_lines only; the placeholder as a sentence of its own) and four
  rules of the check (the upgrade per sentence; the placeholder
  anywhere; a figure inside a word; a unit's figure); run a third time.
- 16, after the third run (11 held): C clean and A's medicines right,
  but six letters carried an allergy status the note does not hold,
  which no rule read; the invention R4 exists to stop. One sentence of
  the prompt changed (allergy status only where a note line records it,
  no placeholder for a missing one) and one rule of the check (an
  allergy sentence stands only on a cited allergy line, else dropped and
  counted); run a fourth time, and the ruling on wiring made on what
  reaches the page, not on M2 and M3 alone.
- 17, after the fourth run (13 held): nothing invented reached a letter;
  of 65 letters 34 state an allergy status and every one rests on a
  cited note line that records it, the one written for a note without
  an allergy line dropped by the new rule; no unit the note does not
  give, no bracketed fragment, no old dose, no stopped medicine given as
  taken, no Assessment line cited, no letter refused. The misses are
  four chains of A at temperature 0.5, each a placeholder the doctor
  sees beside its line before Approve, one failed call said plainly, and
  C's one empty list. The figures stand, no fifth run; M2 and M3 on A at
  0.5 are the record of how well this model cites; the page is wired.

Left for the brainstorm of 8b as prompt matters with their own bench,
what the check cannot read:
- the letter prompt: C's urgent suspected-cancer referral unnamed in
  2 of 13 chains (0 of 13 in the third run) when the concerns line is
  cited instead of the Plan line;
- the letter prompt: D's dermatology letter opening with the nose, the
  other letter's problem, in 12 of 13;
- the letter prompt: a medicine the Plan starts named in 1 letter of 39,
  the sentence that asks for it not reaching the model;
- the referrals prompt, unchanged all day: an empty list on C's seed 5
  in all four runs; and the expectation pattern's pronoun form.

The proof on this machine (stage8a_proof.py on a copy of 7b's data
folder, through the app's own pages; stage8a-proof.log; counts only): the
folder came from version 6 to 7 with every row kept; vLLM chosen. A final
consultation with no approved note shows no section and makes no list
call. The owner's consultation of 20 Oct (30 numbered lines, 25 citable):
one list call at the first opening and none at the second, 1.0 s, the
stored note lines the list text byte for byte, the request the patient
line and the frame with no block; 1 stated and 2 suggested items. The
letter drafted against vLLM in 2.1 s: engine, version, tag, digest and
the prompt file's hash stored, the note lines sent the masked text byte
for byte, the request the letter message byte for byte; 14 sentences, 14
grounded, the body as the check left it equal to the check run again on
the stored model body. An edit kept what stood before; Approve wrote the
assembled text, the copy text is that text alone, every post after is
refused on its control. Name a specialty: no second list call, one letter
call, the typed title in the salutation. On a made consultation whose
made note holds a planned line, a made letter got each thing the check
gives it: the paragraph citing Assessment alone became the placeholder,
a number not in its line the placeholder beside its kept sentences, a
planned test written as a result the placeholder with the planning
sentence kept, an allergy sentence with no allergy line dropped and
counted (9 sentences, 5 grounded, 3 placeholders, 1 dropped, shown in
the counts sentence); a made letter 0 of 3 grounded was refused with the
reason on the page, no body, Approve refused.

What was built, by file: consult/letter_rows.py (the rows), referral_note.py
(the numbering, the masking, the two messages), referrals.py (the list
call, the sorting by code, the named item), letter_check.py and letter.py
(the check, the draft, assemble); web/letters.py, templates/_letters.html
and letter.html, static/letters.js; bench/letters.py and letter_marks.py;
Door.engine_name. The constants: LETTER_GROUNDED_HALF = 0.5 (ruling 4;
v1's shape); the jobs' limits, referrals 1,500 tokens and 60 s, letter
2,500 tokens and 120 s (the plan); CHAINS = 13 and MARK_PLACEHOLDER_ABSENT
= 12 (ruling 10). Every sentence shown to the user is in words.py, the
section's, the letter's (LETTER_COUNTS now with the allergy count) and
ten audit events, drafts for the owner to correct on screen; the
placeholder in the prompt and the one the check writes are one string,
pinned by a test.

Sizes (5.4): no function over 80 lines; no file over 600 but words.py at
721, accepted under 5.4 as 7a's review did. The suite: 711 before commit
16, 723 from commit 17 (ten page tests, the no-block case in
test_background, one on the allergy count shown), green three times
before the last commit. Nothing pushed.

What this stage has made untrue: README's so far and CLAUDE.md's running
and bench lines, fixed in this commit; 6b's entry, moved to the archive;
stage-prompts/STAGE_08A.md, whose rule 4 gives the letter prompt's first
hash and whose rule 5 says a missed mark stops the stage, both
superseded by rulings 14 to 17, kept as the record of the prompt as
given; the plan's items 4, 5, 8 and 9, as the report lists. The spec's
15.12 says Done when you see: not yet, and the 15.4 row's done-when
sentence waits on the owner's room run; both are Cowork's.

What 8b should know: the review page is the draft note, then the
Referral letters section, then the controls, the warnings and alarms, the
transcript with the player, the model line, Delete; the letter's own page
is /consultations/{cid}/letters/{lid}; the guideline panel lives on the
live page. The stored parts by name (ruling 11): referral_list.note_lines
and letter.note_lines hold the numbered note as each call read it,
model_call.request the request as sent, tied by call_id;
letter.model_body the paragraphs with their note_lines;
letter.check_detail each sentence's verdict and reason and
allergies_dropped. The embedding worker of the bench kit sits in
openconsult/bench/shared/embedding2 with its own pyproject and lock,
started by bench/shared/commands.py; 8b brings it into the app as a
worker of its own, started where the room check put it (15.8, ruling
32). The check cannot read a sentence with no number that the note does
not support, an omission, or which problem a letter is about: those are
the doctor's eye, or a prompt matter. The model can loop; the token
limit stopped it, the clock did not have to.
