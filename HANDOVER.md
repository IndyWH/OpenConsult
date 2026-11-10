# HANDOVER

The record for OpenConsult v2: decisions and measurements, newest first.
It stays under 500 lines. Older entries move to HANDOVER_ARCHIVE.md.
The spec is V2_SPEC.md. The record for v1 is the HANDOVER.md on the main branch.

## 2026-11-10. Stage 5e: the speech bench on three new recordings, both passes of the two cloud services

Built and run in one session on 10 Nov 2026 under the owner's approval of
the plan. THE FIGURES COUNT: three recordings of 21 Oct 2026, real voices
(545, 355 and 387 s). Nothing of 5e is built into the app but the opening
commit (R31). The tables are stage5e-tables3 in the private log folder;
the private report is STAGE5E_REPORT.md beside them.

The spec, committed once, not a character changed: 233ec9b (sha256
66469965...). The stage prompt is e56af10 (stage-prompts/STAGE_05E.md).

The opening commit (9e8cfc1): the live page asks the browser for sound at
48,000 samples a second and says so when it is not given; no fallback.

The bench (4147c6f to d4efa9e): a key folder apart from the workers' data
folder; each service's upload arm with the delete and its proof; the wait
to first shown defined again; the line for Alba; the doctor's voice cut
from a recording's own page and never used on that recording; the label
check as the app sends it beside the bench's own; the tables of 5e.

The run. 18 live results and 6 uploads, none failed; every upload deleted
and proven gone, and asked for again afterwards with the two gate clips
(Speechmatics 5 jobs, AssemblyAI 4): nothing held. The driver's first pass
gave speech-calls no --data-folder, so its seven steps ended at once with
no call made; a second pass made the 126 calls on vLLM. The engine was
found down and left down. Scored twice, the same byte for byte.

For the patient, over the three recordings: no kind of page had a passage
missing with no sign or a word where nobody spoke. AssemblyAI live wrote
one drug as another real drug three times, and both notes held it; no
other kind did. Drug names caught of 61 spoken: WhisperX 50, Nemotron 18,
the tied pair 8, Speechmatics live 58 and whole 60, AssemblyAI live 56
and whole 61. Words under the wrong speaker by the choice itself:
WhisperX 47, Nemotron 2, the tied pair 3, Speechmatics live 5 and whole
11, AssemblyAI live 257 and whole 0. The label check left more words under the wrong speaker than the choice
alone on every kind but AssemblyAI live, and as the app sends it today it failed on all three Speechmatics live pages (613 to 785
lines; the reply would need 8,000 to 10,000 tokens of a limit of 3,000).
The line for Alba: no live arm serves; almost every patient speech was
final only after the doctor's reply began.

Read by hand, the line for Alba was wrong three ways and was fixed
(32c32dd, d4efa9e): a pause inside a short reply taken for the patient's;
words matching no speech between the line and the reply; a sound going on
after the line was final. Both script notes of script 14 lack facts 14-03
and 14-16: the notes lack them, the rule is not wrong.

Flags. The suite is 881 tests in 73 s, over the target of one minute.
Speechmatics' reply does not itself prove the medical domain was applied;
the job's own record holds it. AssemblyAI names a host for the uploaded
file that is not EU by name. Nemotron's largest gap inside a word was
1.92 s, close to the 2.0 s figure. speech-calls without --data-folder
refuses its own results folder. The private check found one run of six
common dosing words of a script in V2_SPEC.md and in a test of 8 Nov,
neither written by this run.

Made untrue: CLAUDE.md's speech commands and the README's line of the
live page, both corrected in this commit. No help page names the sample
rate; none is made untrue.

## 2026-11-08. Run 9e: the letter check reads prescription frequencies as figures; the README says how the cloud model was chosen

Built in one session on 8 Nov 2026 under the owner's approval of the
plan. Run 9e is 15.13 rulings 21 and 24; no call to any service, no
bench run, nothing offered on any page (R31). The plan and the recount
are STAGE9E_PLAN.md and stage9e-recount.out in the private log folder.

The spec, committed once, not a character changed: 36354c4 (sha256
4e45032a...). The run prompt is 492be72 (stage-prompts/STAGE_09E.md).

The frequency rule (c42875f). letter_check.numbers_in, the one reader of
a text's figures for a sentence and for its cited lines, reads the
frequencies of a prescription as figures both ways: od, om, mane, nocte
and once as 1; bd and twice as 2; tds as 3; qds as 4; whole words only
(abdomen holds no bd). One choice the spec did not spell out, put in the
plan and approved: on (omni nocte) is also the English preposition, and
read everywhere it marked 38 true sentences in the 65 stored letters of
run 9d2 (1 of A, 6 of B, 6 of C, 25 of D) and took M3 of D from 13 to 0
of 13; so on is a frequency only after a dose, a figure then a unit (mg,
g, mcg, ml, units, iu, tablet, puff, drop), the unit within three tokens
(20 mg up to on). A frequency the lines do not give is still a figure
outside them, marked as ruling 20 says. 3 tests; the suite 828.

The recount, run 9d2's 65 stored letters through the check at c42875f,
no call made: M3 of A 13 and 11 of 13 (run 9d2 13 and 0 of 13); letters
marked on A 2 (run 9d2 13), the two the sentence that gives the
unchanged doses (metformin 1 g, amlodipine 5 mg, atorvastatin 20 mg,
omeprazole 20 mg) cited to the Plan line that names those medicines
without their doses, which the check is right to point at; B, C and D
unchanged (C's one marked letter stands, D's M3 13 of 13). Every other
figure of the table as run 9d2 left it.

The README (this commit): Cowork's section on how the cloud model was
chosen (ruling 21), 84 lines, inserted byte for byte after the list and
before the prototype line, proven by code (the bytes found once, the
file without them equal to the committed one); the private word check
printed nothing. HANDOVER's run 8d entry moved to the archive to stay
under 500 lines.

Made untrue: the 9d2 entry's last line (the README section came with
this run); the figure 13 of 13 marked on A in STAGE9D2_REPORT.md,
STAGE9D2_LETTERS.md and ruling 24 stands as run 9d2's record, with the
recount beside it. Carried, unchanged: for 9b the line Why this model on
the connect screen (ruling 21); for 9c the control's disabled reason
(ruling 23); for 5e the live-or-not of each cloud transcription service.
Open for the owner: the rule on model-specific prompt lines (ruling 22)
waits for a real complaint; Alba in cloud mode is ruled (ruling 23).

## 2026-11-08. Run 9d2: the door accepts any list length, the letter check marks instead of removing, the effort tested, Claude Haiku 5.5 benched again; stage 3 and 7b passed, the letters and the summaries missed, no call failed

Built and run in one session on 8 Nov 2026 under Cowork's plan review
(one point: the effort test in four rounds). Run 9d2 is 15.13 rulings
19 to 22. The plan, the effort file, the report and the letters are
STAGE9D2_PLAN.md, STAGE9D2_EFFORT.md, STAGE9D2_REPORT.md and
STAGE9D2_LETTERS.md in the private log folder.

The spec, committed once, not a character changed: 739b45a (sha256
292ec7cb...). The run prompt is e050afc (stage-prompts/STAGE_09D2.md).

The two rules (4e64e09, ea4634d). The door checks the shape and the
fields of a reply and never refuses for the count of a list's items:
forms.misfit dropped its maxItems judgement, minItems stands, and the
alarm form lost its one line, maxItems 3 on urgent_actions, the only
change in the prompts folder since 15898f5; the other forms keep their
numbers as targets and the Claude kind's wire copy still takes them off.
The letter check's number rule marks instead of removing: a sentence
whose only failure is a figure the cited lines do not give stays as
written in a fourth state, marked, not grounded, shown again under its
paragraph with the words figure not in the note, please check, in no
text that leaves the page (the copy, the approval, an edit's
text_before); the counts, check_detail and the audit line gain the
figures to check; the bench's M3 reads a marked sentence's number as the
model's and the table counts letters with one. The effort setting
(c3747cf): --effort on the bench command, the Claude kind's alone, sent
in output_config when named; engine_version holds it on every call
("anthropic-version 2026-10-21, effort default"). 5 tests added, one
rewritten; the suite 825.

The effort test (four rounds of case 01, 244 calls, 0.12 dollars):
pooled, a pass 4,404 ms at the default and 4,376 at low, the two default
rounds 96 ms apart; 2.1 per cent fewer tokens written at low; the form
held in all, no thinking, no failed call, H6 and H7 held in every
round; the one field proven over every request. The owner chose the
default.

The benches 09:22 to 12:21 UTC, no stop, no wait for the rate, the
proof of the words 0 parts differing on each, the form as sent equal to
the wire copy of the files as they stand:
- Stage 3: passed on every hard, soft and time mark (T17 5.13 s, T18
  7.61 s; S12 0 on every routine case). 0 failed calls, 0 failed chains
  (run 9d 72 and 55). 119 of 1,898 alarm replies listed four or five
  urgent actions, largest 5, all accepted; the assessment's lists never
  crossed their targets.
- 7b: passed, the same four lines as this computer, the host and 9d; 0
  failed calls (9d 24 refused).
- 8a: missed on M3 of A (13 of 13 letters marked: the paracetamol
  frequency written as words where the note's line writes qds, 2 also
  the unchanged doses cited to lines lacking them) and C (one opening
  sentence's duration) and on M5 of D (one list of 13 named one
  referral of two). M1 and M2 held on every case (9d missed M1 on three
  and M2 on two); 0 failed calls, 0 refused, 1 placeholder in 65
  letters (the model's own), 16 letters of five or six paragraphs
  accepted. On A every page now says ibuprofen was stopped and names
  the new doses with the change (13 of 13; 9d 9 stale, 2 wrong); the
  mark stands beside the stop sentence in 13 letters.
- 8b: the searches matched 9a2's 15 of 15. G1 and G3 held; G2 missed on
  four queries (Q04 5, Q05 4, Q07 9, Q12 2 of 13; 9d five; this computer
  two).

The wait and the cost: a pass 4.5 s median over stage 3 (this computer
2.8, the host 6.5, 9d 4.6), 12.8 s slowest, 1 of 1,898 over 10 s; the
alarm call 2.2 s. The benches 2.27 dollars by the tokens (4,685 calls,
9.04 million read, 2.73 million written), the whole run 2.39; a
15-minute consultation about 9 cents by stage 3's fuller ratios (9d
8.2); the owner reads the service's own figure on his usage page.
Thinking in 0 of 4,929 replies; the three A chains the same in 0 of 16
cases. Sizes: no function over 80 (cli.main 78 after the cloud options
moved to a helper); words.py 872 lines, over 600 as before this run.

Made untrue: STAGE9D2_PLAN's sizes and its two-arm effort test; CLAUDE.md's
bench line (edited here). Open for the owner: Alba in cloud mode
(ruling 13) and the rule on model-specific lines (ruling 22), the
candidates the summaries' length on four queries, the fifth paragraph
in 16 of 65 letters, and the number-word figure the check marks on A.
Cowork's README section (ruling 21) comes with the next run.

## 2026-11-07. Run 9d: Claude Haiku 5.5 through the door on all four benches; 7b passed, stage 3, the letters and the summaries missed, every failed call a list limit

Built and run in one session on 7 Nov 2026 under Cowork's plan review
(four points; all are in). Run 9d is 15.13 rulings 14 to 17: Claude
Haiku 5.5 benched on every job after one gate call of its own, report
only, nothing on any page (R31). The gate, the plan, the trial and the
report are STAGE9D_GATE.md, STAGE9D_PLAN.md, STAGE9D_TRIAL.md and
STAGE9D_REPORT.md in the private log folder.

The spec, committed once, not a character changed: 3567994 (sha256
6a622d74...). The run prompt is 0aeb21c (stage-prompts/STAGE_09D.md).

The gate (four calls, the last passed): the service demands every
object marked as taking no other property, does not hold maxItems, and
refuses the temperature field on its API version 2026-10-21 (its words:
temperature: Extra inputs are not permitted); thinking off by its own
field was taken. The form and the service's own instruction add 391
tokens to the alarm call; Claude adds an instruction of its own whose
words are not published (ruling 16). The owner's word at the plan: no
temperature is sent, so all thirteen chains sample at the service's
default; the list limits are held by the door alone.

The kinds (bd28624, cab1088): what the two cloud kinds share is in
bench/cloud.py (the address rule, the stop, the registry's shape).
bench/claude.py is a class of its own on the door's joint in the
Messages API shape: the system message in the system field, the user
message in messages, the form in output_config.format as a copy with
every object marked and maxItems off (the door checks the whole form),
thinking disabled, the job's max_tokens; no temperature, no seed, none
of the local arm's sampling values; the key in the x-api-key header
alone, read from the key folder's .env by the one module; the record
holds engine claude, engine_version "anthropic-version 2026-10-21", the
tag and the line "no digest given by the service" (a later run cannot
be proven the same build); the rate kept by the service's reply headers
with no second send, a 429 a failed call and three in a row a stop;
401, 403 or a credit message stop the run with the chain written
apart. 15 tests, each named for its rule; the suite 820.

The trial met its three conditions (61 of 61 ok, 2.23 dollars
estimated, thinking off). The benches 20:17 to 23:06 UTC, no stop, no
wait for the rate, the proof of the words 0 parts differing on each:
- Stage 3: missed by the scorer on H6, H7 and T18; held on the words.
  72 alarm replies of 1,743 listed 4 or 5 urgent actions where the form
  allows 3 and the door refused them; in the emergency cases that fails
  the chain, so 55 chains of 208 failed. In every one the alarm had
  fired on an accepted reply or on the refused one (all 72 said time
  critical); no male case named a female term on any accepted reply. The
  495 case 5.27 s median (mark 6.0, held) and 8.61 slowest (8.0,
  missed). S12 0 on every routine case (the local 9 on one).
- 7b: passed, the same four lines as the local and the host; 24 refused
  alarm replies failed no chain.
- 8a: missed on M1 of A, C and D (15 letters of 65 refused for 5 or
  more paragraphs against the form's 4), M2 and M3 of A, M3 of B, M2
  and M3 of D (13 placeholders in 12 letters, the check's number rule).
  No unit the note does not give, no line number, no citation into
  Assessment. On case A the check replaced the one sentence that said
  ibuprofen was stopped in 9 letters of 13, so the page reads her as
  still on it (the local 0, the host 4), and in 2 of those the sentence
  held every change of the plan, so the page gives the old doses of
  gliclazide and losartan as current. Nothing reached the page that the
  local's list did not hold; 4 marked lines against 49 and 31.
- 8b: the searches matched 9a2's 15 of 15 before any summary call. G1
  and G3 held in every chain; G2 missed on five queries (Q03 12, Q04 7,
  Q05 6, Q07 8, Q12 1 of 13; the local missed Q07 1 and Q12 11).

The wait and the cost: a pass sent together 4.6 s median over stage 3
(the local 2.8, the host 6.5), 8.6 s slowest, 0 of 1,742 over 10 s (the
host 241); a summary call 1.9 s. The whole run 2.13 dollars by the
tokens (4,438 calls, 8.46 million read, 2.57 million written); a
15-minute consultation about 8 cents (Cowork's estimate 4.6, the host
3.2); the owner reads the service's own figure on his usage page.
Thinking in 0 of 4,438 replies; 0 cut replies; the three A chains gave
the same reply in 0 of 16 cases, as the local and the host.

Every failed call of the run (108 in the benches) is a list limit the
forms carry and the service does not hold; the prompt names no number.
The owner said in chat that the check should accept more than three and
that a brainstorm with Cowork follows; nothing was changed in this run.

Untrue now: nothing in the repo but CLAUDE.md's bench line, fixed with
this entry. For the owner's three rulings (the default cloud model, the
letters, Alba in cloud mode) and the brainstorm on the list limits, the
report's last section.



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
