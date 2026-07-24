# RAG grounding evaluation — guideline retrieval, citation, refusal

**Date:** 2026-07-07
**Component:** RAG service (`app/rag.py`) — pgvector store over the starter
guideline corpus (v2026-07-07.2, 7 sources, 250 chunks), embeddinggemma
embeddings, MedGemma 27B summarisation (temperature 0, seed 42), structured
JSON output.
**Harness:** `scripts/evaluate_rag.py`. Raw data: `evals/rag_results.json`.

## Question under test

Does the guideline layer (a) retrieve the right guideline for queries built
from the CDS layer's identified conditions, (b) produce summaries whose
every claim carries a valid citation to a provided passage, and (c) refuse
gracefully when the corpus does not cover the topic, rather than answering
from model memory?

**Success criteria:** covered, correctly-sourced, cited answers for the
five in-corpus condition sets (one per original mock consultation); refusal
with zero citations for all four out-of-corpus queries.

## Design

**Chunking** (`app/chunking.py`): a chunk is a *section*, not a token
window — guideline advice lives under headings, and windows cut
recommendations in half. Every chunk carries its heading trail
("NG28 › Complications › 1.39 Painful diabetic neuropathy"), which is
embedded with the text and displayed in citations. List items stay with
their introducing stem ("Offer aspirin if:" + bullets is one clinical
unit). Oversized sections split at paragraph then sentence boundaries —
never mid-sentence; undersized ones merge into the next sibling.

**Two refusal layers:** a retrieval-similarity floor in code
(RAG_MIN_SIMILARITY = 0.45 — queries far from every chunk never reach the
LLM) and the model's own covered=false verdict (retrieval found something,
but it doesn't answer the question). A "covered" answer with zero valid
citations is demoted to a refusal in code.

**Threshold calibration** (single-condition queries, top-1 similarity):
in-corpus queries scored 0.56–0.70; out-of-corpus 0.16–0.35, except
TIA at ~0.47–0.52, which retrieves the *cardiac chest pain* guideline —
semantically adjacent, clinically wrong. The floor at 0.45 catches the
clear misses; the adjacent-topic case is exactly what the model-verdict
layer is for (and it worked: MedGemma refused, naming what the corpus
lacks).

**Queries come from the CDS layer:** `answer_for_conditions()` takes the
differential's condition names, retrieves per condition (k=12 candidates),
merges, and caps passages per source (2) before summarising — see design
note 3 below for why.

## Results

**9/9 cases meet expectations.**

| Case | Kind | Covered | Top sim | Citations | Top cited source / refusal layer | Verdict |
|---|---|---|---|---|---|---|
| chest pain (script 01) | in-corpus | yes | 0.596 | 2 | NICE CG95 chest pain | PASS |
| dyspepsia (script 05) | in-corpus | yes | 0.608 | 2 | NICE CG184 dyspepsia | PASS |
| dengue child (script 02) | in-corpus | yes | 0.652 | 4 | WHO dengue fact sheet | PASS |
| asthma (script 04) | in-corpus | yes | 0.691 | 2 | NICE NG245 asthma | PASS |
| diabetes (script 03) | in-corpus | yes | 0.560 | 3 | NICE NG28 type 2 diabetes | PASS |
| TIA (script 06) | out-of-corpus | no | 0.353 | 0 | retrieval floor | PASS |
| torsion (script 10) | out-of-corpus | no | 0.213 | 0 | retrieval floor | PASS |
| postpartum haemorrhage | out-of-corpus | no | 0.314 | 0 | retrieval floor | PASS |
| non-medical (cricket) | out-of-corpus | no | 0.167 | 0 | retrieval floor | PASS |

Note: with per-condition queries the TIA case is refused at the retrieval
floor (0.353); under the earlier concatenated-sentence query it scored
0.474 and was refused by the model verdict instead. Both layers have been
observed doing their job.

## Design notes: three findings from building this

**1. A guideline URL is not a stable contract.** NICE restructured NG28:
its `/chapter/Recommendations` URL now holds only *research*
recommendations. First ingestion produced 8 junk chunks and an in-corpus
diabetes query scored 0.41 — the corpus was silently hollow. Fixed by
ingesting NG28's five topical clinical chapters (manifest supports a URL
list per source). Lesson: validate ingested content against expected
queries, not just chunk counts.

**2. Refusal telemetry is the corpus-growth loop.** The first evaluation
run failed the diabetes case *correctly*: retrieval found NG28's "Painful
diabetic neuropathy" section, but that section is a one-line
cross-reference ("see NICE's guideline on neuropathic pain") — so the
model refused rather than improvise, exactly as designed. The fix was not
prompt engineering but corpus maintenance: ingest the guideline the stub
points to (CG173), recorded in the manifest as v2026-07-07.2. A refusal
on an expected-covered topic is a curation signal.

**3. Concatenated queries let one guideline's vocabulary monopolise
retrieval.** With the query "…Diabetic Peripheral Neuropathy; Poorly
Controlled Diabetes Mellitus", every retrieved chunk was NG28 — its title
appears in every chunk's embedded heading trail, swamping CG173 (whose
title says "neuropathic pain", not "diabetes"). CG173's best chunk ranked
8th. Fix: retrieve per CDS condition separately, merge, and cap passages
per source. This also *sharpened refusals* — condition-name queries are
crisper than sentence queries, dropping TIA's top similarity from 0.47 to
0.35.

## Clinical fidelity spot-check (project owner, 2026-07-07)

A doctor's spot-check of the system's outputs, ahead of the formal
fidelity evaluation:

- **Chest-pain summary vs cited passages:** claims verified against the
  passages they cite. One fidelity drift found — the aspirin qualifier.
  CG95 1.2.3 reads "a single loading dose of 300 mg aspirin … **unless
  there is clear evidence that they are allergic to it**"; the summary
  rendered this "**unless contraindicated**". A broadening paraphrase:
  clinically conservative in direction (contraindication ⊇ allergy), but
  not faithful to the passage — and qualifier paraphrase is precisely the
  class of drift a fidelity evaluation must catch, since a *narrowing*
  paraphrase of the same kind would be dangerous.
- **Refusal behaviour, live:** on the TIA mock consultation the guidelines
  panel declined with the provenance line shown, while the urgency alarm
  fired independently — correct separation of the two layers (urgency is
  judged from the transcript; guideline summaries refuse when the corpus
  lacks coverage; neither blocks the other).

**Decision:** formal claim-by-claim fidelity evaluation deferred to the
end-of-project review, alongside the script-02 dengue boundary case from
the urgency evaluation.

## Limitations

- Corpus coverage is deliberately narrow (the five test-case topics);
  breadth of the refusal boundary is sampled at only four points.
- Summaries are checked for citation validity, not clinical fidelity to
  the cited passages. A spot-check (see above) found one qualifier
  paraphrase; the formal claim-by-claim audit is deferred to the
  end-of-project review.
- Single embedding model, no reranker; the NG28-vs-CG173 finding suggests
  a reranking stage would help as the corpus grows.
- n=1 per case, deterministic (temperature 0, seed 42).
- NICE/WHO content is UK/global guidance; Sri Lankan national guidelines
  are the intended corpus for the real use case (roadmap).

## Reproduce

```bash
ollama serve &
ollama pull embeddinggemma
uv run python scripts/ingest_guidelines.py
uv run python scripts/evaluate_rag.py
```

## Addendum 2026-07-24 — corpus expanded for public demo; eval re-run

The corpus grew from 7 sources / ~250 chunks (five mock-script topics) to
**38 sources / 1301 chunks** (corpus v2026-07-24.1) covering the
presentations external demo users are likely to record — common UK
primary-care topics plus dengue. See `corpus/manifest.yaml` for the full
list and the new validation convention: every source now carries
`expect_title` (checked at fetch time; a redirect to a different page is
a fetch failure) and 2–3 `expected_queries` that must retrieve a chunk
from their own source within the global top 8 at similarity ≥ 0.45, or
ingestion exits non-zero. All 82 expected queries passed (almost all at
global rank 1, sims 0.57–0.79) — no NG28-vs-CG173-class crowding.

Verified-at-fetch findings (the NG28 lesson recurring): NG51 (sepsis) is
replaced by NG253/NG254/NG255 — NG253+NG254 ingested; NG138 (CAP) is
replaced by NG250 — NG250 ingested; both guidelines' /Recommendations
URLs silently redirect to research-only chapters, so clinical chapters
are listed explicitly. The BSR giant cell arteritis full text
(academic.oup.com) blocks automated fetch (403, also via the BSR site);
the NICE CKS GCA topic — written from that BSR guideline — is ingested
as its retrievable equivalent. No NICE guideline exists for
iron-deficiency anaemia or adult eczema management; CKS topics fill both.

Eval changes with the expanded corpus (both are corrections of
expectations that only held while the corpus was tiny, not regressions):

- **TIA (script 06) moved from OUT_OF_CORPUS to IN_CORPUS** — NG128
  (stroke/TIA) and NG196 (AF) are now in corpus, so a covered answer is
  correct. It passes: top-cited NG128, 4 valid citations.
- **Chest pain (script 01) now accepts CG126 or CG95 as top-cited** —
  the case queries conditions "Stable Angina" + "ACS"; with a dedicated
  stable-angina guideline (CG126) in corpus it correctly tops the
  citations, and CG95 (assessment) is still cited alongside (2+2
  passages — the per-source cap keeping the set diverse).

**Result: 9/9** (6 in-corpus covered with valid citations and the right
top source; 3 out-of-corpus refused, all at the retrieval floor).
Raw per-case JSON: `rag_results.json` (regenerated).

End-to-end spot-checks of three new topics via the live chain
(transcript → CDS conditions → guideline panel): script 13 migraine
(CG150, incl. medication-overuse criteria), script 14 GCA (CKS/BSR
source for GCA suspicion features + ultrasound/biopsy, CG150/CG173
cross-cited for the rest of the differential), manual hypertension query
(NG136 targets/white-coat + NG203 CKD blood-pressure crossover). All
claims cited; no uncited assertions observed.
