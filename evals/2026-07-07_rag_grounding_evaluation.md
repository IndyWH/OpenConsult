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

## Limitations

- Corpus coverage is deliberately narrow (the five test-case topics);
  breadth of the refusal boundary is sampled at only four points.
- Summaries are checked for citation validity, not clinical fidelity to
  the cited passages — that audit needs the doctor (project owner) and is
  the natural next evaluation.
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
