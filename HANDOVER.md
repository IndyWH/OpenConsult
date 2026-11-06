# HANDOVER

The record for OpenConsult v2: decisions and measurements, newest first.
It stays under 500 lines. Older entries move to HANDOVER_ARCHIVE.md.
The spec is V2_SPEC.md. The record for v1 is the HANDOVER.md on the main branch.

## 2026-11-06. Run 9a2: Gemma 4 26B on DeepInfra through the door on all four benches; stage 3, 7b and 8b passed, the letters missed

Built and run in one session on 6 Nov 2026 under Cowork's plan review
(four points; all are in). Run 9a2 is 15.13 ruling 11: the host of the
cloud Gemma 4 is DeepInfra if one gate call passes, benched as rulings 4
and 8 say, report only, nothing on any page (R31). The gate, the plan,
the trial and the report are STAGE9A2_GATE.md, STAGE9A2_PLAN.md,
STAGE9A2_TRIAL.md and STAGE9A2_REPORT.md in the private log folder.

The spec, committed once, not a character changed: adf27e9 (sha256
858a6815...). The run prompt is 6532985 (stage-prompts/STAGE_09A2.md).

The kind (deec370; bench/deepinfra.py, the bench's alone): a subclass of
the app's chat engine, so the request body is the vLLM arm's, the six
sampling fields included (proven on the stored records against the
local vLLM runs: 0 parts differing on every bench run); the host's own
address over https and no other; the key in the Authorization header
alone, read from the key folder's .env by the one module and written
nowhere; the host gives no version and no digest, so the record holds
the two lines that say so with the date and the model field of every
reply. A later run cannot be proven to be the same build. 401, 402, 403
and 429 stop the run with the chain written apart. Ollama cloud's kind
was taken out (7cd68f7; ruling 11). 12 tests, each named for its rule.

The gate passed on try (a), the request as the chat engine sends it: the
form's JSON, no thinking, 723 tokens read as on vLLM. The trial met its
three conditions (61 of 61 ok, 0.80 dollars estimated, thinking off).

The benches, the host beside the local vLLM, the host being the local
model's size at another precision than the local build:
- Stage 3: passed on the model's words. Every hard mark the local held,
  held; the routine scripts fired on 0 chains (the local 9 on one case).
  One failed call of the run's 4,729, a chain of case 10 at 0.5 whose
  assessment got no answer within the app's 60 s; the scorer reads that
  chain as a miss of H6 and H7, the rule of the run does not. The two
  time marks of the 495 case missed: a pass 6.64 s median (the mark 6.0;
  the local 2.94) and 34.38 at the slowest (8.0; 4.07).
- 7b: passed, the same four lines as the local, A2 missed both ways in
  the same manner.
- 8a: missed, on A M2, A M3 and D M3. The model writes the two blood
  results of case A with units the note does not give (12 letters of 13;
  the local 1), the check puts the placeholder in their place, 0 units
  reach the page. One stale fact on the page: the medicine the Plan
  stops given as taken in 3 letters of 13 at 0.5 (the local's fourth
  bench 0, its first 12). No kind reached the page that the local's
  list did not hold; the dermatology letter opens with the skin 13 of
  13 (the local 1). The two letters for the owner's reading are in
  STAGE9A2_LETTERS.md, private.
- 8b: passed. The run first stopped at the searches, as the plan says
  on any difference from 8b's stored run: the searches send the local's
  passages on 14 of 15 queries, and on one made query two of six differ,
  because three documents of the bench's own data folder were removed
  and loaded again on 29 Oct after 8b's bench ran (the same files; new
  ids and vectors); 8b's stored search rows also carry its first
  matcher's right passages, not the re-matched ones. The owner ruled in
  chat that the summaries run on the corpus as it stands, that query
  reported as not like for like. G1 13 of 13 on all twelve real queries
  and G3 13 of 13 on all three made ones, as the local; G2 (under 150
  words) 13 on ten, the two the local missed held in more chains (Q07 9
  against 1, Q12 12 against 11); covered 13 of 13 on every real query.

The wait and the cost: a pass sent together 6.5 s median over stage 3
(the local 2.8), 60 s at the slowest; 36 passes of 1,889 over 20 s, the
host's queue; a summary call 4.5 s median (the local about 1.2). The
whole run 0.80 dollars by the tokens and 0.80 by the host's own
estimated_cost; a 15-minute consultation about 3.2 US cents (ruling 4's
count scaled, beside the estimate of 3 to 5). Thinking in 0 of 4,729
replies. The seed: the same reply at every pass on the
three chains at temperature 0 in 0 of 16 cases, as the local vLLM arm.
No engine stopped or started; the card 18 MiB throughout.

Untrue now: nothing in the repo but CLAUDE.md's bench line, fixed with
this entry. For 9b: 8b's stored search rows and the corpus of
stage8b-data are not what its bench ran with (above); every reply
carries the host's service_tier field, and the owner has said a faster
tier at 1.5 times the price is to be tested after this run. For 5e,
the owner's idea, said on 6 Nov and his to rule on: a local speech model
on a laptop processor for the live stream, the final transcription and
the diarization in the cloud after Stop.


## 2026-11-06. Run 9a: the cloud kind built, the bench of Ollama cloud stopped at its first call

Built in one session on 6 Nov 2026 under the plan review of Cowork
(five points; all are in). Run 9a is the bench of 15.13 rulings 4 and 8:
Gemma 4 31B on Ollama cloud through the door on every bench the local
model has run, report only, nothing offered on any page (R31). The
cloud kind of the bench was built and committed; the one-case trial of
the run prompt's rule 10 failed its first call, so no bench ran, and
the run stops here for the owner's ruling. The plan, the trial's file
and the report are STAGE9A_PLAN.md, STAGE9A_TRIAL.md and
STAGE9A_REPORT.md in the private log folder.

The spec, committed once, not a character changed: bebfcd2 (sha256
3aab9a83...; 15.13 whole and the small dated additions). The run prompt
is 6b8afde (stage-prompts/STAGE_09A.md).

The cloud kind (commit 234ee26; bench/ollama_cloud.py, the bench's
alone, as 3b's bench reached llama.cpp before 3c): a subclass of the
local Ollama engine, so the request body is byte for byte the local
one but the model tag (proven on the stored records: the trial's one
request against the 28 Oct arm's for the same call, equal in every
field but model); the service's own address over https and no other
(an address that is not the expected one is refused before any
connection); the key in the Authorization header alone, read by the one
key module from the folder --key-folder names, inside the process,
never from the command line, never in a log, a stamp, a result or a
row (a test with a made key); the record holds the service's version,
the tag and the digest it gives, or the line no digest given by the
service (R20); after 401, 402, 403 or 429 the engine sends nothing
more, the chain in progress is written apart under stopped so that a
later run redoes it and the whole chains stand, and the command exits
11; a 500 or a timeout is an ordinary failed call (R30; 10.4). The
app's engines and its order of choosing do not know the kind (a test,
and the fresh-Python test of 3b). The door gains one read-only property,
stopped, which the app never reads. The example settings file names
OLLAMA_API_KEY with no value. The run, repeat, letters and guideline
commands take --key-folder. Twenty tests, each named for what it pins.

The service's list, read on 6 Nov 2026 with the key in-process and
nothing of ours sent: gemma4:31b, digest 221b330d11a8 (the service's
twelve-character form), modified 2 Apr 2026; its version page 0.0.0.

The trial (rule 10): case 01, three chains at temperature 0, the two
calls sent together, 09:35 UTC. The engine and the model were reached
and recorded. The bench's one unmeasured first call (the alarm, case
01, first point) came back in 959 ms, HTTP 200, 722 tokens read (the
local count for the same call is 722) and 123 written, no thinking
field and no thinking text; the door judged it bad_form, the reply is
not JSON, and the bench stopped before any chain, as it has since
stage 3 when the first call fails. Read privately from the record: the
content is a JSON object wrapped in a markdown fence, and inside the
fence the urgent actions are plain strings where the form asks for
objects with an action and a reason. So the service did not apply the
request's format schema as a local Ollama does (0 bad_form in the 3,797
calls of the 28 Oct arm with the same requests). The three conditions
for going on: no call failed, not met (1 of 1); the estimate under 10
dollars, about 1.33 on the local benches' token counts, not measured;
thinking off, met. Cost of the run: one call, 0.00015 dollars. Nothing
else was sent to the service.

Not changed, because each is the owner's call and not the bench's: the
door still refuses an answer that does not fit its form (R30), for the
cloud as for every engine; no fence is unwrapped; no request to the
service differs from the local one (rule 4; 15.8 ruling 1). Whether
the service honours the format field at all, only as a hint, or in
another shape is for Cowork to check on the service's own page before
the next run, which the run prompt's rule 3 kept this run from reading.
No bench ran, so no mark was judged, no seed test, no seconds of a
pass, no letter for the owner's reading; the vLLM engine was found down
and left down; the card was not touched.

The suite: 790 tests (770 before), green three times before the last
commit, none skipped. The private word check printed nothing before
every commit. Size targets: no function over 80 lines; no file over 600
but words.py, the standing exception. CLAUDE.md 99 lines. Nothing
pushed. The folders of the run in the private log folder:
stage9a-trial (the one call's record), stage9a-data-letters and
stage9a-data-guideline (copies of 8a's and 8b's data folders, unused),
stage9a-recount-8a (the fourth bench of 8a counted again by today's
code: A M1 12, M2 9, M3 9, M4 13, M5 13; B all 13; C M5 12, the rest
13; D all 13, as the run prompt gives them), and the scripts
stage9a-record-check.py, stage9a-request-compare.py,
stage9a-search-compare.py, stage9a-seed-check.py and
stage9a-trial-figures.py, ready for the next run.

What this run has made untrue: CLAUDE.md's line 7 of How a stage runs
and its bench lines, fixed in this commit (15.13 ruling 1; the kind);
the plan's items 3 to 8 and the run prompt's PART 3 from the trial on,
which did not happen; nothing in README (it names no bench kind and no
language model key). What 9b's brainstorm should know: the kind, the
key folder and the stop rule are in place and tested; the one open
question is the answer form on the service, and until it is settled a
cloud consultation would fail every pass.

## 2026-11-03. Run 8d: the letters run, benched twice, the check rule kept, the prompt edits stopped

Built in one session on 3 Nov 2026 and resumed the same evening after
the owner's ruling on the first bench (15.12 ruling 35), under the plan
review of Cowork (two points; both are in). The letters run of ruling
34: the four edits to the two letter prompts of rulings 29 to 32 and the
one rule of the check of ruling 33, benched together on the four
approved notes of ruling 10 by the letter bench of 8a, kept when no mark
fell below the fourth bench of 8a and nothing new reached the page, else
held. The first bench was held on the marks of A, C and D; the owner
reworded the two added sentences (the words citing that Plan line
dropped from both, the started medicine written as a medicine to start)
and the bench ran once more. The second bench was held too: A's and D's
marks still under the fourth bench, and new kinds on the page. Under
ruling 35 the prompt edits STOP: the two prompt files are at their bytes
of 2095421, the check rule is kept, and the letters run as 8a wired
them. Both benches' bytes are patches in the private log folder. The
report is STAGE8D_REPORT.md there, with the fourth bench of 8a beside
both benches and one letter each for C and D from the second bench for
the owner's reading. No room run: nothing new reaches the app.

The spec, committed twice, not a character changed: f3fe466 (8c marked
done on 2 Nov and rulings 29 to 34; sha256 49ffe0f2...) and cebfdb0
(ruling 35 and the reworded prompt text in ruling 3; sha256 5900da8a...).
The run prompt is 359f715 (stage-prompts/STAGE_08D.md); the resume
prompt stayed in the private log folder.

The check rule (ruling 33; consult/letter_check.py, commit 251599b): the
expectation pattern now also reads he, she, they or the patient followed
by hopes, hoped, wants, wanted, would like, expects, expected, is hoping
or was hoping, as well as the forms it read; the verdict is unchanged
(kept only where a valid cited line holds Patient's expectations and a
colon, else dropped and counted, never replaced). One test pins it; the
bench's two expectation readings go through the same function, so M4 on
A reads the pronoun form. One twin sentence of the ruling 4 test changed
(He expects nothing was its example of a non-match; ruling 33 makes it a
match; the twin is now He is expected in clinic), accepted by the review
as a stronger test. Across the two benches the check dropped 12
expectation sentences and every one was an expectation sentence (the
fourth bench's stored results: 8 of 8); the pronoun form caught no
ordinary sentence.

The prompt files: copied byte for byte from the private copies for each
bench alone (the first bench letter 075a1213... and referrals
1b8cf5b9...; the second bench letter a7cdd113..., exactly two sentences
different from the first, and the same referrals text), each proven by
sha256sum and cmp with nothing else under openconsult/prompts changed,
then returned with git checkout to 220d61f0... and 5eab5bb5...; git diff
2095421 -- openconsult/prompts prints nothing. APPROVED_BYTES and the
hash test are unchanged. The held bytes are stage8d-held-changes.patch
and stage8d-held-changes2.patch (32 lines each) in the private log
folder.

The benches (ruling 10; stage8d-bench.sh and stage8d-bench2.sh, the
fourth bench's command with the run's own copy of 8a's data folder): the
same four notes at the same hashes, 13 chains each, the owner's vLLM
0.31.0 with the model of 3c, thinking off in every request and none in
any reply, 118 calls each, no failed call, three to four minutes each;
the letter text hashes of the record eb20f7aa (first) and 3a3ea335
(second), the referrals f44b125a (both). Chains holding each mark of 13,
the fourth bench of 8a (4), the first bench (1) and the second (2):

| mark | A 4 | A 1 | A 2 | B 4 | B 1 | B 2 | C 4 | C 1 | C 2 | D 4 | D 1 | D 2 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M1 | 12 | 13 | 13 | 13 | 13 | 13 | 13 | 10 | 13 | 13 | 13 | 13 |
| M2 (12 needed) | 9 | 1 | 3 | 13 | 13 | 13 | 13 | 10 | 13 | 13 | 5 | 11 |
| M3 numbers | 9 | 1 | 3 | 13 | 13 | 13 | 13 | 10 | 13 | 13 | 5 | 11 |
| M3 Assessment | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 |
| M4 (A only) | 13 | 13 | 13 | | | | | | | | | |
| M5 | 13 | 13 | 13 | 13 | 13 | 13 | 12 | 13 | 13 | 13 | 13 | 13 |

Marks held: the fourth bench 13 of 17, the first bench 10, the second
13. The second bench is under the fourth on four marks (M2 and M3 on A
and on D) and above it on three (M1 on A, M5 on C, and A's failed call
gone). Every miss in both benches is the number rule of the check. First
bench: on A the model wrote the units on the HbA1c and eGFR in 12 of 13
letters (1 of 13 in the fourth bench), each replaced; on C and D it
wrote its citations into the text in 10 letters (3 C letters refused).
Second bench: no citation in any letter and no letter refused; on A the
units in 10 of 13 letters (13 sentences replaced, 3 of them the nine
years of diabetes cited to a line that does not hold it); on D the nose
history in paragraph 1 of two dermatology letters, cited to the skin
lines (3 sentences). Across both benches, of 65 letters every allergy
status on the page rests on a cited allergy line (29 and 36 letters), no
Assessment line was cited, no stopped medicine was given as taken.

The four matters, the fourth bench -> the first -> the second, counted
by code from the stored results (stage8d-things.py): C's urgent
suspected-cancer referral named in paragraph 1, 11 -> 13 -> 13 of 13
chains, and in its second sentence 0 -> 13 -> 13; D's dermatology
letter opening with the skin 1 -> 13 -> 13 of 13 and with the nose 12 ->
0 -> 0 (the nose in paragraph 4 alone 0 -> 2 -> 5); a medicine the Plan
starts named with its dose, A dapagliflozin 1 -> 13 -> 13 of 13, B
sumatriptan 10 -> 13 -> 13, D mometasone 0 -> 0 -> 0 in the ENT letter
and betamethasone 0 -> 0 -> 1 in the dermatology letter; C's stated
list found with line 19, 12 -> 13 -> 13 of 13, the empty list 1 -> 0 ->
0. The fifth, the expectation sentence by the new pattern in the
model's body: B 13 -> 13 -> 10, C 12 -> 13 -> 13, D 23 -> 24 -> 14 of 26
letters, A 0 in every run (M4 held). The review's point 1 passed in both
benches: none of the four counts worse.

What reached the page that the fourth bench's list did not hold, read in
every kept sentence of the 65 letters of each bench. First bench: the
started medicine given among the current medications on A in 11 of 13
letters; the note's own labels in the text in 8 kept sentences of 3
letters; one comment on the record. Second bench: an invented negative
on A (one sentence of one letter saying no recent weight loss or
polyuria was reported, words the note does not hold; the check cannot
read it, there is no number in it); a unit the note does not give on the
page in 1 A letter (the HbA1c with mmol/mol, kept because the figure is
on the cited line and the unit holds no digit); the note's own words as
per the plan in 3 C letters, 1 sentence each; the prompt's own phrase
echoed (as a medicine to start, as to start) in 5 sentences of 3 B
letters; the old dose of gliclazide beside the new in 1 A letter; two
medicines stopped before given as ones the Plan stops now in 1 A letter.
Gone since the first bench: the started medicine among the current
medications (every A letter now says she is to start it), the comment on
the record, the citations in the text. The kinds of the fourth bench's
list in the second bench: the label Patient's expectations: in 7 letters
(15 in the fourth, 9 in the first), and its words without the colon in 7
more; a paragraph 4 opening with a bare medicine 6 (12, 0), all B's Plan
line copied whole.

The reading I would put to the owner, not a decision: the four matters
the edits were for are answered in the model's body in both benches (the
urgency sentence, the dermatology letter opening with the skin, A's and
B's started medicines with their doses, never an empty list), and the
rewording of ruling 35 removed the citations in the text and the started
medicine listed as current; what remains is A's units, which swung
between 1 and 12 of 13 on every change to paragraph 4 in 8a and did so
again (12, then 10), and D's nose history written into paragraph 1 of
the dermatology letter against the skin's lines. The invented negative
on A is one sentence in 130 letters across the two benches and the
guard against it is the owner's reading, not the check. The edits stop
here as ruling 35 says; a later session may take the four matters up
again with the lesson that paragraph 4 moves A's units.

Sizes (5.4): letter_check.py 162 lines, no function over 80; the suite
770 tests, green before every commit and three times before the last.
HANDOVER's 8b entry moved to the archive in the first session. Nothing
pushed; no engine started or stopped; the recordings folder not opened.

What this run has made untrue: the spec's rulings 3 and 8 give
a7cdd113... and 1b8cf5b9... as the two prompts' hashes while the files
hold 220d61f0... and 5eab5bb5..., and ruling 35's second bench is now
run and held (for Cowork to mark); STAGE_08D.md's kept case did not
happen and its rule 4 names the first bench's letter hash 075a1213...,
superseded by a7cdd113... in the resume; the archive's 8a entry and
STAGE_08A.md rule 4 still give 220d61f0... as the letter prompt's hash,
which is true again; the 8a report's line that the started medicine's
sentence does not reach the model is not the whole story (it reaches
the model and is answered). The 8c report's note for the letters session
stays true: the frames, the withheld line and the rows' named parts are
unchanged.


## 2026-11-02. Stage 8c: the what-the-model-saw view, its timeline, and two small fixes

Built in one session on 2 Nov 2026 under the plan review of Cowork (two
points; both are in). The view run of 15.12 ruling 11, settled by ruling
28: one read-only page per final consultation, reached by one link from
the review page beside the model line and one on each final
consultation's row of the patient's page, listing every model call in
time order, each opened to what went in, marked by source, and what came
back word for word, with a timeline at its head. No bench, no mark: the
view reads the record and writes nothing but its page. No word a model
reads changed: git diff 0d28f63 -- openconsult/prompts prints nothing.
The report is STAGE8C_REPORT.md in the private log folder. The room run
is the owner's, still to come.

The spec, committed once, not a character changed: 96fef56 (8b marked
done on 2 Nov and ruling 28; sha256 87d90be3...).

How every call is found (consult/seen.py): model_call.consultation_id
ties each call since stage 6; the list is ordered by the parsed moment
of model_call.at, then id (the stamps' offset changes twice a year). Each
call is named by the row that references it: cds_pass.alarm_call_id and
assessment_call_id (pass n), note_draft.call_id (draft n, asked at Stop,
by Draft the note or by Draft again), referral_list.call_id (the list),
letter.call_id (letter n, the item's specialty), guideline_answer.call_id
(after pass n, with search_ms). The label check is referenced by no row:
it is found by its job on the consultation and the page says so in
plain words. A referral list whose call failed is dropped when the list
is made again, so its call stands alone the same way. A live or stopping
consultation has no view yet; its address leads back to its page.

How each call is read back. The request's two texts come from the body
as sent in its three shapes (the chat body's two messages; the made
engine's job and user pair; the Call's own parts of a call that never
reached its engine). The system text is hashed against prompt_sha256 and
shown as the prompt's file name and hash only, with one of three words:
the file today has the same hash, differs, or no file of that name
(15.8 ruling 1). The user text is taken apart by the kind's own builder
and the reader proves itself by rebuilding it byte for byte: the patient
line, the first paragraph, must equal patient_line for the details the
consultation ran with on the day of the call or on the day of Start
(R11; 15.11 ruling 2; referral_note.patient_on); the background block
by the fixed words of background.frame.txt, looked for in the two pass
calls only (R25); each frame by its fixed segments around its slots
(assessment.first then assessment.later; letter's specialty and note;
guideline's query and passages); the label check's numbered lines and
the note's turns rebuilt through labels.lines_text and note.turns_text
(D3: no patient line there); the list's and the letter's note lines
equal to the row's named part; the guideline call from the row's names,
query and passages through summary.message. A request the reader cannot
take apart is shown whole with its reason (not JSON; no user text; the
first paragraph not the patient line; the frame's words not found; the
parts not rebuilding the request; an unknown job), and even then with
every prompt's words replaced by a mark; never a guess.

The timeline (consult/timeline.py). The band runs from Start to final
with Stop marked; each call is a bar from its at less its wall to its
at; a call that ended after final by more than final's own precision of
one second (final_at is written to the second, a call's at to the
millisecond) is listed under the band with its lead in plain units. The
typical pass is the median of the stored passes' wall_ms, the whole
pass with both calls, over every pass shown or not: the same figure
stop.figures gives the consultation.final line, so the two agree. A pass
over twice the typical pass is marked long, in the warning colour, and
named under the band; with one pass nothing is long. The seconds per
kind are the mean with the count, the failed count and the slowest,
failed calls counted in their kind. The consultation.final line's own
figures stand beside them. No script: the bars are placed by the
computed fractions and a details element opens each call.

The speaker page (ruling 28; R15): the answer's redirect could land
before the Stop thread moved the stage on, so the question stood on
screen again with no refresh and the owner picked twice on 2 Nov. The
page learns the answer was taken from page_state (answered), asks only
until then, and after it shows its own named state, Your answer is
taken. Checking who spoke each line, with the spinner and the refresh,
the choices gone. A second answer is still refused and the first stands.

The retention test: SLOW_RUNNER_S = 60.0 beside the stop tests' wait
helper, taken by the test's two waits on the conversion step (GitHub's
Windows run of 30 Oct took 31 minutes and the 10 s wait timed out);
nothing else of the test changed.

The proof on this machine (stage8c_proof.py on stage8c-data, the 8b
folder's database alone; stage8c-proof.log; counts only): 11 final
consultations, 116 calls, every one listed in time order and taken
apart, the parts joined by plain code equal to the stored request in
116 of 116; the patient line on the 96 alarm, assessment, referral list,
letter and guideline calls and on no other; the background block on the
two pass calls of the one consultation that ran with the switch on after
7b and on no other (consultation 5 ran with the switch on under 7a,
which sent nothing, and the view shows that honestly); the 11 guideline
calls rebuilt from their rows' named parts; each pass call's transcript
equal to cds_pass.transcript, each note's text to note_draft.transcript,
each list's and letter's lines to its row; the averages, the typical
pass, the long marks and every bar equal to a recount from the rows; the
final line found for every consultation; no prompt's first line on any
page; the record's tables unchanged by every view page (the password
change and the login on the copy are the only writes). Consultation 3,
8a's: 43 calls, 19 passes, typical pass 2.98 s, no long pass, 4 calls
after final (the note drafted again, the list, two letters). Seen in
the browser on the copy: the band, the pass ticks, a call opened to its
parts by source. Two corrections came from the proof: final's precision
in the band, and the order by the moment.

Every sentence shown to the user is in words.py, drafts for the owner;
the link text is What the model saw. words.py is 869 lines, over 600,
accepted under 5.4 as the reviews of 7a, 8a and 8b did; no other file
over 600 and no function over 80. The suite: 764 tests (756 before 8c),
green three times before the last commit, none skipped. Nothing pushed.
The private word check printed nothing before every commit. The commits:
96fef56, 2fc8350, a7b2f90, 31a50ce, 420e1a0, ae8e0a6, fa0c188, 99fc75e,
eae7ff6, 8c1d82e and this one.

What this stage has made untrue: README's so far and CLAUDE.md's line,
fixed in this commit; the 8b entry's and report's words that the view
is still to be built; the spec's 15.12 Done when you see for ruling 28,
which waits on the owner's room run (Cowork marks it). For the letters
session of ruling 20: the view reads letter.note_lines and the item's
specialty as the letter call's named parts, and letter.frame.txt's
fixed words by name; a change to the letter frame or to what the letter
row stores must keep referral_note's fill the builder of the message, or
the reader's rebuild fails and the call is shown whole with its reason.
