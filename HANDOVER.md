# HANDOVER

The record for OpenConsult v2: decisions and measurements, newest first.
It stays under 500 lines. Older entries move to HANDOVER_ARCHIVE.md.
The spec is V2_SPEC.md. The record for v1 is the HANDOVER.md on the main branch.

## 2026-10-29. Stage 8b: the guideline corpus, its search, its bench, and the panel wired on the owner's rulings

Built in two sessions, 28 to 29 Oct 2026, under the plan review of
Cowork (five points; all are in; the owner's ruling on the stop was A: a
third fetch, the reranker's, by name). The first session built the
corpus, the loader, the search, the worker and the bench, ran the
unattended bench (the guideline queries on vLLM, the Gemma 4 bench of
stage 3 on two Ollamas) and held the panel as a patch because one of its
marks missed. The owner ruled on the figures (spec 15.12, rulings 24 to
27, committed as 2344cfb, not a character changed); the second session
wired the panel from the patch without the reranker, made the load embed
one passage at a time, and proved the whole on this machine. The report
is STAGE8B_REPORT.md in the private log folder. The room run is the
owner's, still to come, with the panel in it.

The spec, committed twice, not a character changed: eee605d (8a marked
done and rulings 18 to 23 of 28 Oct) and 2344cfb (rulings 24 to 27 of
29 Oct, sha256 9dbc55ec...).

The owner's four rulings, in plain words:
- 24. The bench's figures stand: nothing invented reached a panel, the
  model refused every made topic, and it ran over 150 words on two of
  twelve queries. No second run, no change to the prompt; the panel and
  its record are wired from the held patch, and the length is recorded
  as the measure of how closely this model keeps a word limit.
- 25. The reranker is not wired: its marks held on the card, but beside
  vLLM, Nemotron and the embedding the room check's sums leave no room
  for its 1,430 MiB, so in the room it would sit on the processor at
  about four seconds a search, for one query in twelve. No setting, no
  constant, no row of This machine, no sentence shown; the worker's
  rerank request, the fetch with --reranker and the bench's arm stay in
  the code for a later run.
- 26. GUIDELINE_FLOOR stays 0.45 (v1's). The model, not the floor,
  refused every made query: their nearest passages scored 0.66 to 0.68
  and the lowest real query's 0.72, a gap of 0.034 too narrow to set a
  floor in without refusing a real topic worded differently.
- 27. Ollama 0.40.7 stays: the latest release gave the same marks. The
  load embeds one passage at a time. A review of every component's
  version, and GitHub's security findings on main, are for the end of
  the build (14.3).

The rulings of 28 Oct it builds, one line each (spec 15.12):
- 5: the corpus ships empty; the Guidelines section of Settings takes a
  file from this computer (HTML, PDF or plain text) with its title, its
  publisher and the one statement, splits it, embeds it and lists it
  with Remove; every add and remove audited; the app fetches nothing.
- 6: the panel: called after a pass whose top two differentials differ
  from the last search's pair, one at a time, never during Stop; the
  summary with [n] marks each a press to the passage with its source's
  title and publisher, the cited sources and the provenance counts under
  it, or the one line that the loaded guidelines do not cover the names,
  with the model's one sentence under it when it gave one; a failed call
  touches nothing of the pass or the alarm (R30); with no document
  loaded, no call (R3); a result landing after Stop recorded, not shown.
- 7: openconsult/prompts/guideline.prompt.txt sha256 7e07e017..., the
  approved block byte for byte with one line break, proven by hash and
  by cmp against Cowork's copy. The frame is fixed words in
  guideline.frame.txt (QUERY: {query}, a blank line, PASSAGES: and
  {passages}) and guideline.passage.txt ([{n}] {source} and the text
  under it), the form v1's three fields; the patient line opens the
  message (R11); the background block never reaches it (D24).
- 9: the reranker benched as an arm, in the worker's own environment and
  process, on its own device; its three marks held; not wired (25).
- 10, 19: the bench, below. 11: guideline_answer keeps the names, the
  query and the passages sent with their sources and similarities, the
  named parts; the model_call row the request as sent.
- 12, 21, 23: the two Ollama arms, below; vLLM stopped and started by
  the owner's script for the bench run alone; the service never touched.
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
candidates, the top similarity, the floor, reranker_ran (always 0 in
the app, ruling 25), the outcome, the call, covered, the summary, the
numbers cited, the invalid marks, the failure, the search and the whole
in milliseconds, shown). Delete takes the answers with the consultation
(D44).

The loader (guidelines/passages.py, loading.py): HTML by its headings
with the standard library's parser, one passage per leaf section with
its trail, a stem and its bullets one unit, nav and the like dropped, as
v1's chunker did; PDF by pypdf's text in page order at blank lines;
plain text at blank lines; MAX_WORDS 350 and MIN_WORDS 40 (v1), a small
section joining the next under the same parent, a last small subsection
joining its parent section, a long one split at paragraph ends and a
long paragraph at sentence ends, never inside a sentence; a file with no
passage of 40 words is refused. The passages go to the worker one at a
time (ruling 27): sixteen at a time, the worker's process peaked at
4,892 MiB on the card at the bench's load (the card 23,131 of 24,564
beside vLLM), the working room of a batch, which the room check's
1,010 does not count, so an Add beside vLLM and a speech worker could
have run the card out and left the worker dead until the next start;
one at a time, its peak at a load of 106 passages was 1,162 MiB (the
card sampled every 0.2 s), the vectors the same to within bfloat16's
noise (against the bench's sixteen-at-a-time vectors: the largest
component difference 0.0044, the lowest cosine 0.99979; a one-at-a-time
load against itself exact), 1.5 s for 106 passages through the page.
The corpus of the bench: 47 files, 1,143 passages, 75 outside 40 to
350 words, 3 to 106 passages a file. The room check's constants are
unchanged.

The search (guidelines/search.py; 6.3): the names' vectors from the
worker in one request, the dot product over every loaded passage from an
index in memory read again after a change, the nearest 12 a name, merged
by passage at the higher similarity, at most 2 from one source, 6 in
all; GUIDELINE_FLOOR = 0.45 under which nothing is sent; the reranker's
reordering before the floor and the cut only when a search asks for it,
which the app never does. 29 to 53 ms a search on 1,143 passages.

The summary call (guidelines/summary.py): the message from the frame,
the call through the door (job guideline, 1,000 tokens, 60 s), the
outcome by code: covered false is a refusal with the model's one
sentence; a covered reply citing no number it was given is a refusal
(no_citation); a covered reply's marks are checked against the numbers
sent, the invalid ones counted and left as plain text.

The panel (guidelines/panel.py; static/guidelines.js; the pane in
live.html after the assessment): the service holds the corpus's rows
and index, the worker, the door and the floor; PanelState, one a
consultation, is asked under the consultation's lock after a pass is
stored and shown, keeps the pair last searched, runs one search at a
time on a thread of its own and holds the next pair for after it; the
page draws the row's state (no corpus, not installed, the worker
failed, waiting, searching, the result) and the earlier summary stays
marked while a new search runs. Each search that reached the floor or
the call is a row with the audit line of counts (guideline.summary,
guideline.not_covered, guideline.failed). Nothing of it reaches the
note, the list or the letter call (R4, R5), and the review page has no
panel.

The worker (guidelines/embedding2, moved from the bench kit with its
lock file; guidelines/embedder.py, environment.py): started at app
start where the room check put it, without the reranker, the load not
waited for, the first use waiting once; a death a failure with its
reason and no restart by itself; openconsult install-guidelines builds
the environment from the lock file and fetches EmbeddingGemma 2 at its
pinned revision with no token, a model whose weights are there and
match never fetched again (the review, point 4); with --reranker, for
the bench alone, the reranker at the revision its page named at the
fetch (953dc6f6..., pinned with the weights' hash beside it). The worker
loads in about 7 s on the card and holds 1,004 MiB with the embedding
alone; 2,324 to 2,438 with the reranker through the bench's arm.

The bench (rulings 10 and 19; bench/guideline.py, guideline_marks.py,
guideline_load.py): fifteen approved queries (twelve real, from the
documents' headings; three made), each once through the app's search
and 13 chains through its call, once without the reranker and once with
it, on vLLM 0.31.0 with the model of 3c, the patient line 50 and F for
every query; 390 summary calls, none failed, about 1.2 s each, 8 minutes
for both arms. Per query, the chains of 13 holding each mark, without
the reranker and with it (the right rank by the rule of 2bd8308):

| query | real | top sim. | sent | covered | cites only given (G1) | under 150 (G2) | refused (G3) | right rank | words, largest |
|---|---|---|---|---|---|---|---|---|---|
| Q01 | yes | 0.836 | 2 | 13, 13 | 13, 13 | 13, 13 | 0, 0 | 1, 1 | 142, 144 |
| Q02 | yes | 0.798 | 4 | 9, 11 | 13, 13 | 13, 13 | 4, 2 | 1, 1 | 87, 70 |
| Q03 | yes | 0.804 | 2 | 13, 13 | 13, 13 | 13, 13 | 0, 0 | 1, 1 | 135, 133 |
| Q04 | yes | 0.867 | 6 | 13, 13 | 13, 13 | 13, 13 | 0, 0 | 1, 1 | 143, 130 |
| Q05 | yes | 0.803 | 6 | 13, 13 | 13, 13 | 13, 12 | 0, 0 | 1, 1 | 146, 152 |
| Q06 | yes | 0.794 | 6 | 13, 13 | 13, 13 | 13, 13 | 0, 0 | 1, 1 | 113, 120 |
| Q07 | yes | 0.812 | 6 | 13, 13 | 13, 13 | 1, 3 | 0, 0 | 1, 1 | 178, 159 |
| Q08 | yes | 0.866 | 2 | 13, 13 | 13, 13 | 13, 13 | 0, 0 | 1, 1 | 130, 128 |
| Q09 | yes | 0.796 | 4 | 13, 13 | 13, 13 | 13, 12 | 0, 0 | 1, 1 | 137, 153 |
| Q10 | yes | 0.806 | 5 | 13, 13 | 13, 13 | 13, 13 | 0, 0 | 1, 1 | 89, 148 |
| Q11 | yes | 0.718 | 6 | 13, 13 | 13, 13 | 13, 13 | 0, 0 | 2, 1 | 93, 139 |
| Q12 | yes | 0.834 | 2 | 13, 13 | 13, 13 | 11, 10 | 0, 0 | 1, 1 | 159, 159 |
| M01 | made | 0.684 | 6 | 0, 0 | 13, 13 | 13, 13 | 13, 13 | - | 0, 0 |
| M02 | made | 0.660 | 6 | 0, 0 | 13, 13 | 13, 13 | 13, 13 | - | 0, 0 |
| M03 | made | 0.671 | 6 | 0, 0 | 13, 13 | 13, 13 | 13, 13 | - | 0, 0 |

The marks as numbers: G1 held, 12 of 12 queries, 156 of 156 chains an
arm; G2 missed without the reranker on 2 of 12 queries (Q07 1 of 13,
Q12 11 of 13; the over-length summaries 150 to 178 words) and with it
on 4 (Q05, Q07, Q09, Q12); G3 held, 3 of 3, 78 of 78 chains an arm,
the model's covered false every time, the floor refusing nothing; R1
held, the right passage first in 12 of 12 with the reranker against 11
of 12 without (the first scoring, matching the trail's last heading
alone, read 6 against 5; 2bd8308 matches any heading of the trail with
its section number left out); R2 held, 0 lost from the top three; R3
held, every search with the reranker under 1 s on the card, slowest
76 ms (1.6 to 4.6 s with it on the processor, report only). Q02's
refused chains are the model's own covered false on passages that pass
the floor, the right passage first in both arms.

The two Ollama arms (ruling 12), the stage 3 command on its 16 cases,
13 chains, the hard marks of 15.7, report only; the owner's ruling
(27): keep 0.40.7.

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
pulled once into a store of its own beside it, started on port 11500
and stopped after its arm, left there for a later run; the service, its
unit, its port and its store untouched; vLLM stopped and started by the
owner's script, the card read before and after each; the service let
its model go by itself (1,630 s) with no request sent to it. The first
driver stumbled three times in its own steps (a raw count before the
schema came forward, a cold first call over the 60 s, the asset's ./
name); the second driver reran every step but the checks.

The proof on this machine, on the committed tree (stage8b_proof.py on
stage8b-data against vLLM 0.31.0 and the real worker on the card;
stage8b-proof-final.log; counts only): the folder came forward with
every row kept; the section listed the 47 sources, Remove took one out
with its 18 passages and Add put it back through the page in 0.26 s,
both audited; a headache story's three passes each changed the pair, so
three searches and three covered summaries (top similarity 0.79, 0.81
and 0.84; 2 passages sent each; 122, 26 and 139 words; 45 to 51 ms a
search, 0.4 to 1.2 s a call), the row's parts by name rebuilding the
request byte for byte (2,174 bytes), the patient line first and once,
no background block, the marks opening passages with title and
publisher, the provenance 47 documents and 1,143 passages; a nasal
polyp story's three searches gave the refusal line (the model's covered
false at 0.68 to 0.73, over the floor, six passages sent each time);
nothing of the panel in the alarm, assessment, label check, note, list
or letter calls nor on the review page; on a scratch copy with a made
engine, a timed-out summary call left the pass stored and shown and the
alarm as judged, the panel saying failed; the corpus emptied gave
no_corpus, no search, no call and no row.

What was built, by file: guidelines/{sources,passages,texts,loading,
embedder,environment,search,summary,panel}.py and embedding2/
(worker.py with the rerank request, fetch.py with the reranker's
fetch); web/guidelines.py and the section in settings.html; the pane in
live.html, static/guidelines.js and the hook in consult/live.py;
bench/guideline.py, guideline_marks.py, guideline_load.py,
guideline_commands.py; the prompt, the two frames and the form; the
job; schema 8; the multipart reader in web/pages.py; MadeUpEmbedder in
the fakes. The constants: GUIDELINE_FLOOR 0.45, NEAREST_PER_NAME 12,
PER_SOURCE 2, SENT 6 (v1 app/rag.py); MAX_WORDS 350, MIN_WORDS 40 (v1
app/chunking.py); UPLOAD_LIMIT_BYTES 50,000,000 (the plan);
WORKER_READY_S 300 and WORKER_REQUEST_S 120 (the speech workers'); the
job's 1,000 tokens and 60 s (the plan, until this bench: the longest
reply 1.8 s, under 300 tokens); TOP 2 (ruling 6). Every sentence shown
to the user is in words.py, drafts for the owner. pypdf 6.21.4 (BSD-3)
is the one library added (NOTICE); the reranker's weights are the
bench's, not the app's, and are not in NOTICE.

Sizes (5.4): no function over 80 lines (build_app came to 81 with the
panel's service and was folded to 76); no file over 600 but words.py at
795, accepted under 5.4 as 7a's and 8a's reviews did. The suite: 755
tests (585 before 8b), green three times before the last commit, none
skipped. Nothing pushed. The private word check printed nothing before
every commit. R21: no file in the repo names the publisher; one test of
stage 3, that no prompt holds a guideline word, passes over the summary
prompt's own approved words. The commits: eee605d, 05278c9, e7491a4,
247ba02, 383d0d3, 16c332a, ab50019, 57263bb, 2bd8308, 5d9672a, 1f100f4,
00a0343 (the first session), 2344cfb, a6e9f80, 9133d42 and this one.

What this stage has made untrue: README's so far and CLAUDE.md's lines,
fixed in this commit (the panel in, the reranker not); 7a's and 7b's
entries and now 8a's, moved to the archive; the spec's 15.12 Done when you see,
which waits on the owner's room run with the panel (Cowork marks it);
the stage prompt's rule 5 as it read before ruling 24 (the panel held
while a mark missed) and its rule 3 on the fetches (a third allowed by
the review); the plan's item 5 where it read that the reranker's
switch and sentence would be wired if its marks held (they held; ruling
25 left it out); the 8a report's line that the panel lives on the live
page, now true. For the view run of ruling 11: guideline_answer.names,
.query and .passages (each with passage_id, source_id, title,
publisher, trail, text, similarity, rerank_score, cited) are the named
parts; model_call.request the request as sent, tied by call_id;
summary.message(query, passages, patient) rebuilds the request from
the row's parts byte for byte; the passages' text, title and publisher
stay in the row after a source is removed; no row is written with no
document loaded or no worker, so the view reads the start-time decision
(decision.guideline_search in the audit) rather than look for a row.

