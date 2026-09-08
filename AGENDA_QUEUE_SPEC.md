# Standing question queue — spec for owner approval (7 Sept 2026)

Owner's proposal, 7 Sept: keep MedGemma's questions-to-ask as a dynamic
list that Alba draws from; each new CDS pass adds new questions and
removes redundant ones; an asked question is deleted; and a small
MedGemma call between full passes re-sorts and prunes the list against
what has unfolded.

What it fixes (486 baseline): 27.7 s mean from turn end to Alba
speaking, 74 % of it the full CDS pass; a question asked twice; two
re-asks in substance from the topic cone. Target: under 8 s, with zero
re-asks of an answered question — by construction, not by prompt.

## 1. What changes
Today the agenda is replaced wholesale by every pass, and in strict mode
Alba cannot ask until the replacement lands. New: one persistent queue
per session. Passes merge into it; Alba consumes from its head; a tiny
re-ranker keeps it current between passes. The urgency check, the
transcript-exclusion guarantee, the pause banner and the note pipeline
are untouched.

## 2. The queue
Each item: id, text, normalised key (the E3 normaliser), topic
(normalised, slice 3), first_version (the pass that proposed it),
last_seen_version, rank, status — pending / asked / answered / dropped —
and timestamps.

Operations:
- merge(pass_version, questions): a new-pass question that matches a
  PENDING item refreshes it; one that matches an ASKED or ANSWERED
  item is discarded — an asked question can never re-enter, whatever
  the pass says; one that matches nothing is appended. Pending items
  the pass did not mention are NOT deleted on that evidence alone
  (decision D-A). **Matching is exact equality of normalised token sets
  (the E3 normaliser; the slice-3 F4 rule) — not a 0.6 similarity, as
  this spec first proposed.** Built that way, and kept, because two
  questions on one topic are legitimately different questions: at 0.6
  "Have you ever had chest pain like this before?" and a question about
  the pain's character would be one item, and the never-re-enter
  guarantee would silence a question the patient has not been asked. A
  looser bound is the owner's to set; the actions and topics keep their
  0.6 for their own reasons.
- consume(item_id): the PLANNED item becomes asked — by id, not
  whatever is head at issue time, because the prepared audio is for its
  words; when the patient's turn ends with speech (F5 rule) it becomes
  answered. A doctor tap on a queue item consumes that item (D-E); a
  tapped question the queue never held is recorded asked
  (add_asked) so it can never re-enter. A politeness-aborted ask goes
  back to pending at its rank (requeue) — it was never put to the
  patient — and the prepared plan is kept for the re-issue.
- rerank(order, drops): applied only to pending items; drops are
  audited with the re-ranker's one-word reason.
- cap: at most Q_MAX pending (D-D); lowest-ranked excess dropped, audited.

Baseline order without a re-rank: the latest pass's own order for the
items it listed, then the unlisted pending items in their previous order.

## 3. The re-ranker
A stateless call in the affect/topic-call shape. Input: the pending
texts (ids attached) and the transcript since the last full pass,
bounded (D-B). Instruction: return the ids still worth asking, in the
best order for this moment; drop any the patient has already addressed
in the excerpt — a question counts as answered when its subject was
addressed, even if not every example in it was named (the parenthetical
lesson); never write a new question. Output: ordered ids + drop list.
Timeout AUTO_RERANK_TIMEOUT_S (2 s), fail-soft to the current order,
audited auto.rerank_failed. Guarantee, code-enforced: any output that is
not a known pending id is ignored — the re-ranker cannot invent.

When: after each answered turn, unless a full pass is in flight (D-F).

## 4. Cadence (D-C)
(a) Full pass on every answer as now; the queue makes asking
    non-blocking. GPU load unchanged; latency solved; cleanest
    measurement of the queue's own effect. RECOMMENDED first. BUILT
    (slice 2): this is `AUTO_STRICT_REVISE=true`, whose meaning is now
    "a full pass is requested on every answer" — not "asking waits for
    it", which nothing does any more. `false` requests no pass on every
    answer (one is still requested when the queue has nothing pending)
    and is the comparison posture for the mock-patient round; a test
    counts exactly one pass per answer under (a).
(b) Full pass every second answer, re-rank every answer — behind a
    flag for later (slice 5). Halves the heavy load.
Guarantee under either: the urgency check runs on its own memory-less
call at every answered turn, whatever the full-pass cadence — pinned by
a test.

## 5. Asking from the queue (BUILT, slice 2)
At an answered turn end: if the queue has a pending item → topic call
for a new topic (D3 cone, unchanged) else verbatim → pre-synthesis →
issue at the next quiet. A running pass never blocks the ask; when it
completes, merge may change the head before the next ask, which is
fine. If the queue is empty and a pass is running → one bridge "go on"
and wait, as today (the bridge fires only with nothing to ask — never
a second before a question in preparation). If the queue is empty and
no pass is running → the existing rule: request a pass; an empty queue
after the merge of a fresh post-answer revision → the handover
sequence (§6 as amended).
As built, two more turn ends go the same way: the golden exit and a
hand-back (the first ask), and a turn end with nothing asked and
nothing queued (the span after a pass landed mid-speech). A pass that
lands while the patient is mid-turn plans nothing; that turn's end
plans from the head — the slot where §3's re-rank will run. The manner
rule from the pilot fixes stays: not the same words twice in a row when
there is another to ask. A queue with nothing pending at RESUME AUTO
hands over, as an empty agenda did.

## 6. The doctor's panel
The questions-to-ask panel shows the queue: pending in order, asked
struck through, dropped hidden (expandable). A tap consumes that item
and Alba continues from the new head. The preparing state now covers
re-rank plus synthesis — seconds, not tens of seconds.
Slice 2 built the tap's half (D-E): a tapped question whose normalised
text equals a pending item consumes it (by=tap) and the machine
continues from the new head; one the queue never held is recorded
asked. The panel itself still shows the assessment's list, not the
queue (slice 4); until then the panel and the queue can differ — a
question the doctor sees may already be asked or dropped in the queue.
The tap guard and the tapped examination handover are unchanged.

## 7. Audit and the number to beat
auto.queue_merged (added / refreshed / discarded, version),
auto.queue_reranked (order, drops, ms), auto.queue_consumed (item, by
auto or tap), auto.rerank_failed, auto.queue_capped. Built (slice 2)
with the rest the module reports: auto.queue_dropped_absent,
auto.queue_answered, auto.queue_requeued, auto.queue_dropped,
auto.queue_asked_externally — each with the module's flat details, the
session and the audio time. The metric: turn end → Alba speaking, per
question — now on the record for every auto question:
`turn_end_to_issue_ms` on the question's row and its speech.requested
audit, and `auto.question_latency` at the client's speak_started with
`turn_end_to_speech_ms` and `issue_to_speech_ms`. 486 baseline mean
27.7 s (report table). Prereg untouched; spec §5, §6, §9 truth-ups;
help/ flagged for the owner's wording where the panel's behaviour
changes.

## 7a. GPU discipline (owner's principle, 7 Sept)
The RTX 4090 is the slow element in the chain. During a live
consultation it must never load or unload a model, and it must never be
idle when there is useful work — but "useful" is ordered, because
Ollama serves one request at a time and every model call is a queue.
486 showed the failure: one runaway assessment held the slot for three
minutes while five officer verdicts died behind it. Three mechanisms:

1. Resident live set, as an invariant. The models a live consultation
   needs (MedGemma, the live transcriber, the embedder; Piper is CPU)
   are loaded before the first consultation and stay loaded until the
   session ends; the finalisation swap (MedGemma out, WhisperX and
   pyannote in, MedGemma back for the note) happens only after Stop, as
   today. Any model load or unload observed during a live session is
   audited as model.load_during_live and is a defect. Ollama keep-alive
   is set so the live set cannot age out mid-consultation.
2. Priority order for model calls, with teeth. Urgency check first,
   always; then the short conversational calls — end-of-turn officer,
   topic call, re-ranker — then the full CDS pass; then speculative
   work. The app's call scheduler enforces it: a long pass is not
   launched when a short critical call is due within its expected run
   time, and a runaway (slice 3's cap) is cut rather than waited for.
   Alternative for measurement: a second Ollama slot
   (OLLAMA_NUM_PARALLEL=2) so a short call can overlap a long one — at a
   VRAM cost per slot's context cache that must be measured on the 24
   GB card before it is adopted.
3. Speculation while the patient speaks. While the patient is
   answering, the card would otherwise wait. The next full pass runs on
   the transcript so far, so that at the turn end the agenda is nearly
   current; the queue merges it when it lands (§2) and nothing waits on
   it. A speculative pass yields to any higher-priority call.

Every model call is audited as model.call with kind, queued_ms, run_ms,
tokens and outcome, so utilisation and waiting become numbers per run
rather than impressions.

## 8. Decisions for the owner
- D-A  Unmentioned pending items: (rec) kept until the re-ranker drops
       them or they are absent from THREE consecutive passes, then
       dropped and audited. Absence from one pass is weak evidence.
- D-B  Re-ranker context: (rec) the last six transcript turns since the
       previous full pass, capped by characters.
- D-C  Cadence: (rec) (a) now, (b) as a flag.
- D-D  Queue cap: (rec) 8 pending.
- D-E  A doctor tap consumes the tapped item and the flow continues:
       (rec) yes.
- D-F  Re-rank skipped while a full pass is in flight: (rec) yes — the
       merge supersedes it.
- D-G  GPU discipline (§7a): (rec) adopt all three mechanisms; build
       the resident-set invariant and the priority scheduler in this
       round, speculation as the last slice once the queue is measured;
       the second Ollama slot stays a measurement experiment, not a
       default.

## 9. Build order (after approval)
1. Pure AgendaQueue module + tests (merge, consume, rerank apply, cap,
   normaliser reuse, the never-re-enter guarantee).
2. Wiring: pass completion → merge; ask-from-queue; empty rules;
   slice 3's asked-memory becomes the queue's asked status. BUILT
   2026-09-08 (six commits; HANDOVER entry of that date), with the
   tap's half of D-E, the per-question latency numbers and the D-C (a)
   cadence pin pulled forward from slices 4 and 5.
3. Re-ranker call, fail-soft, no-invention guard, audit.
4. Panel and taps.
5. Cadence flag, urgency-cadence pin, HANDOVER, spec truth-ups, help/
   flags.
6. GPU discipline: model.call audit, resident-set invariant with its
   audit, the priority scheduler.
7. Speculative pass during the patient's answer, behind a flag, once
   the queue's own effect has been measured against the 486 baseline.
