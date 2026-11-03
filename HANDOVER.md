# HANDOVER

The record for OpenConsult v2: decisions and measurements, newest first.
It stays under 500 lines. Older entries move to HANDOVER_ARCHIVE.md.
The spec is V2_SPEC.md. The record for v1 is the HANDOVER.md on the main branch.

## 2026-11-03. Run 8d: the letters run, the check rule kept, the four prompt edits held

Built in one session on 3 Nov 2026 under the plan review of Cowork (two
points; both are in). The letters run of 15.12 ruling 34: the four edits
to the two letter prompts of rulings 29 to 32 and the one rule of the
check of ruling 33, benched together once on the four approved notes of
ruling 10 by the letter bench of 8a, kept when no mark fell below the
fourth bench of 8a and nothing new reached the page, else held. The
marks fell on A, C and D, so the four prompt edits are HELD as a patch
in the private log folder for the owner's ruling, the two prompt files
are back at their bytes of 2095421, and the check rule is kept. The
report is STAGE8D_REPORT.md in the private log folder, with the fourth
bench of 8a beside this run and one letter each for C and D for the
owner's reading. No room run: nothing new reaches the app.

The spec, committed once, not a character changed: f3fe466 (8c marked
done on 2 Nov and rulings 29 to 34; sha256 49ffe0f2...). The run prompt
is 359f715 (stage-prompts/STAGE_08D.md).

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
as a stronger test. In this run's bench the check dropped five
expectation sentences and every one was an expectation sentence; the
pronoun form caught no ordinary sentence.

The prompt files: copied byte for byte from the private copies (sha256
075a1213... and 1b8cf5b9..., cmp identical, nothing else under
openconsult/prompts changed) for the bench alone, then returned with
git checkout to 220d61f0... and 5eab5bb5...; git diff 2095421 --
openconsult/prompts prints nothing. APPROVED_BYTES and the hash test
are unchanged. The held bytes are stage8d-held-changes.patch (32 lines)
in the private log folder.

The bench (ruling 10; stage8d-bench.sh, the fourth bench's command with
the run's own copy of 8a's data folder): the same four notes at the same
hashes, 13 chains each, the owner's vLLM 0.31.0 with the model of 3c,
thinking off in every request and none in any reply, 118 calls, no
failed call, three minutes; the two prompt hashes of the record eb20f7aa
(letter) and f44b125a (referrals). Chains holding each mark of 13, the
fourth bench of 8a beside this run (4 -> 8d):

| mark | A 4 | A 8d | B 4 | B 8d | C 4 | C 8d | D 4 | D 8d |
|---|---|---|---|---|---|---|---|---|
| M1 | 12 | 13 | 13 | 13 | 13 | 10 | 13 | 13 |
| M2 (12 needed) | 9 | 1 | 13 | 13 | 13 | 10 | 13 | 5 |
| M3 numbers | 9 | 1 | 13 | 13 | 13 | 10 | 13 | 5 |
| M3 Assessment | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 |
| M4 (A only) | 13 | 13 | | | | | | |
| M5 | 13 | 13 | 13 | 13 | 12 | 13 | 13 | 13 |

Marks held: 10 of 17 (13 in the fourth bench). Under the fourth bench on
seven: M2 and M3 on A, M1, M2 and M3 on C, M2 and M3 on D. Every miss is
the number rule of the check: on A the model wrote the units on the
HbA1c and eGFR in 12 of 13 letters (1 of 13 in the fourth bench), each
replaced by the placeholder; on C and D it wrote its citations into the
text, as bracketed numbers, as line n in brackets, or as note_lines,
in 3 C letters (all three refused, 3 of 13 or 14 sentences grounded)
and in 9 of 26 D letters, each such sentence replaced. Nothing
invented reached the page: of 65 letters 29 carry an allergy status and
every one rests on a cited allergy line, no unit the note does not give
is on the page, no Assessment line was cited, no old dose, no stopped
medicine as taken.

The four matters, the fourth bench -> this run, counted by code from the
stored results (stage8d-things.py): C's urgent suspected-cancer referral
named in paragraph 1, 11 -> 13 of 13 chains, and in its second sentence
0 -> 13; D's dermatology letter opening with the skin 1 -> 13 of 13 and
with the nose 12 -> 0; a medicine the Plan starts named with its dose, A
dapagliflozin 1 -> 13 of 13, B sumatriptan 10 -> 13 (the fourth bench's
stored results name it in 10, not 0 as remembered), D mometasone 0 -> 0
in the ENT letter and betamethasone 0 -> 0 in the dermatology letter;
C's stated list found with line 19, 12 -> 13 of 13, the empty list 1 ->
0. The fifth, the expectation sentence by the new pattern: in the
model's body B 13, C 13, D 24 of 26 letters, A 0 of 13 (M4 held).

What reached the page that the fourth bench's list did not hold, read in
every kept sentence of the 65 letters: the started medicine given among
the current medications on A (Her current medications are ... and
dapagliflozin 10 mg om) in 11 of 13 letters, said as to start in 2; the
note's own labels in the text (the word Plan or Subjective in brackets,
as per the Plan, the Patient's expectations line) in 8 kept sentences of
3 letters (B B5, C B5, C B10); one comment on the record (A B8). The
kinds of the fourth bench's list: the label Patient's expectations: in
9 letters (15); a paragraph 4 opening with a bare medicine 0 (12).

The reading I would put to the owner, not a decision: the two new
sentences that say citing that Plan line (rulings 29 and 31) sit beside
the three the prompt already held, and the model answered by writing
its citations into the letter; a started medicine named in a list of
current medications reads as taken. The matters the edits were for are
all answered in the model's body; what the check turns into placeholders
and refusals is the citing. The owner rules; the run ends here.

Sizes (5.4): letter_check.py 162 lines, no function over 80; the suite
770 tests, green three times before the last commit. HANDOVER's 8b
entry moved to the archive. Nothing pushed; no engine started or
stopped; the recordings folder not opened.

What this run has made untrue: the spec's rulings 3 and 8 give
075a1213... and 1b8cf5b9... as the two prompts' hashes while the files
hold 220d61f0... and 5eab5bb5... (for Cowork to mark on the owner's
ruling); STAGE_08D.md's kept case did not happen; the 8a report's line
that the started medicine's sentence does not reach the model is no
longer the whole story (it reaches the model and is answered in a list
of current medications). The 8c report's note for the letters session
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
