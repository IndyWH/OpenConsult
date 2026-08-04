# Where the guidelines come from — a corpus you build, not download

*Part of the Consultation AI help series. True as of corpus version
2026-07-24.1 — the manifest in the repository is always the current
record.*

The guidelines panel does something deliberately narrow: it summarises
only from real guideline text it has retrieved, cites every claim, and
declines when the corpus doesn't cover a topic. This page answers the
question that design raises: where does that guideline text come from,
and why isn't it in the repository?

## Why the repository ships a recipe, not the documents

Two reasons, and both would be enough alone.

**Licence.** The corpus is third-party copyrighted content — NICE
guidelines, NICE Clinical Knowledge Summaries, WHO and CDC guidance.
Fetching a copy to your own machine for local research and educational
use is one thing; a public repository redistributing those documents
would be quite another. So the documents are never committed, and an
image or archive containing them would be redistribution too.

**Staleness.** Guidance changes, and serving last year's guidance is
itself a clinical risk. During one corpus expansion, two NICE guidelines
were found to have been replaced entirely (NG51 by NG253/NG254, NG138 by
NG250) — and the retired pages didn't disappear; they silently redirected
to overview stubs. A bundled corpus would have carried the dead versions
without anyone noticing. A corpus each installation fetches for itself,
dated and versioned, cannot quietly rot in the repository.

What IS committed is `corpus/manifest.yaml`: the recipe and the receipt.
For every source it records the publisher, the exact URL, a licence
note, the ingestion date — and two validation fields described below.
The corpus becomes a property of an installation, declared rather than
bundled: your instance knows exactly what it holds and when it was
fetched.

## Building yours: one command

With the embedding model pulled (`ollama pull embeddinggemma`, one-time):

    uv run python scripts/ingest_guidelines.py

The script walks the manifest: fetches each source, chunks it along the
document's own structure, embeds the chunks, and stores them in
PostgreSQL. Then it validates what it fetched — and this is the part
worth understanding, because a failure here is the script protecting
you, not breaking.

```mermaid
flowchart LR
    M["manifest.yaml\n(the recipe)"] --> F["Fetch each source"]
    F --> T{"Title matches\nexpect_title?"}
    T -->|no, or redirected| X["LOUD FAILURE\nnames the source"]
    T -->|yes| C["Chunk + embed\ninto pgvector"]
    C --> Q{"expected_queries\nretrieve their source?"}
    Q -->|no| X
    Q -->|yes| R["Corpus ready,\nversioned and dated"]
```

Two gates, each earned by a real incident:

- **`expect_title`** — a substring that must appear in every fetched
  page's title. This catches replaced guidelines and wrong codes at
  fetch time, and a redirect to a different page counts as a failure,
  because that is exactly how retired NICE pages fail: they redirect
  instead of returning an error.
- **`expected_queries`** — two or three realistic retrieval queries per
  source. After ingestion, each must actually retrieve a chunk from its
  own source at a similarity above the refusal floor. A document that
  downloads but cannot be found again has not really been ingested —
  chunk counts alone prove nothing about retrievability.

A source that fails either gate fails the run loudly, by name, and a
partially ingested corpus never presents itself as ready. If a guideline
website has moved things around, expect the script to say so — that is
the design working.

## Making it your own

This is where the corpus stops being plumbing and becomes a research
instrument. The manifest defines what your instance will and will not
discuss: ask the panel about something outside it and you get a polite
refusal, not an improvisation. Which means an investigator can shape the
system's knowledge deliberately — a different specialty, a different
country's guidance, a deliberately restricted set for a study condition.

To add a source: give it a slug, title, publisher, URL, an
`expect_title` substring, two or three `expected_queries`, and a licence
note, then re-run the ingestion command. Then one standing rule, learned
the evaluation-first way: **after any corpus change, re-run the
retrieval-composition harness** (`scripts/evaluate_retrieval_composition.py`)
so the retrieval behaviour is measured again rather than assumed. The
harness writes a dated results file beside the baseline, so the
comparison is explicit.

One honest limit: not everything can be ingested. Some publishers block
automated fetching entirely — the full text of one rheumatology
guideline lives behind such a block, so the corpus carries the NICE CKS
topic written from it instead. The manifest records that kind of
substitution rather than hiding it.

---

## Where to go next

- **The install map →** [Installing and running it](03-installing-and-running.md)
  — the corpus is stage 6 of seven.
- **Where retrieval sits →** [The architecture](04-the-architecture.md)
  — how the guidelines panel relates to the rest.
- **Back to the start →** [the introduction](00-introduction.md) — the
  whole tour, and the router by reader type.

*The manifest itself, with every source and its validation queries, is
[`corpus/manifest.yaml`](../corpus/manifest.yaml) in the repository.*
