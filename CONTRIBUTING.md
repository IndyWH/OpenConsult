# Contributing

Thank you for looking.

OpenConsult is a research and education prototype, built by one GP mostly in his own time. It is not a medical device, it has had no regulatory assessment, and it must never be used with real patients or real patient data.

## What I am asking for

Findings, not pull requests.

I am not taking code contributions at the moment. That is not standoffishness, it is how the project is actually built: I write the specifications, an AI assistant writes most of the code, and I referee. Dropping outside patches into that loop would break the record this project keeps of why each change was made. If you do want to write code against it, say so in a discussion first and we will work out how.

What is genuinely useful is being told where it is wrong. The README names the three things I would most like to hear about: where it breaks in a real clinic, the mostly AI-written code, and what the security audit missed. Blunt is welcome.

## Where to put things

Open a discussion for questions, ideas, and anything open-ended.

Open an issue for a defect you can describe, or a concrete proposal.

Do not open an issue for a security problem. SECURITY.md has the private route.

## Decisions that are mine

Every clinical and product judgement in this project belongs to me: what the system says to a patient, what a threshold should be, what the face expresses, whether a safety rule can be relaxed. If you think one of them is wrong, argue it. A well-made argument is the whole job, and I would rather have it than a patch.

## Things that are load-bearing

Each of these exists because something went wrong once.

Tests pin properties, not snapshots. A test is never weakened or deleted to make the suite green.

The help/ series is reader-facing prose and the wording is mine. If something makes an article untrue, say which article and what is now untrue in it.

The vendor/ directory holds pinned upstream code with its own licence. It is not edited here. If the vendored behaviour is wrong for this project, our own layer is what changes.

The urgency alarm is not wired to the face, and must not be. An alarmed face would tell the patient something the doctor has not decided yet. A test guards it.

Every AI output is a draft. Nothing enters the record until the doctor reviews and approves it.

Refusal is a feature. The guideline layer refuses when the corpus does not cover a topic, and the finalisation gate refuses to draft from an untrustworthy transcript. Neither is softened to make a demonstration run smoothly.

## Running it yourself

The README has the full setup on a fresh machine, start to finish. Heavy tests skip themselves when Ollama, PostgreSQL or the guideline corpus are absent, and the suite runs against a disposable database, never a live one.

## Licence

This project's own code is AGPL-3.0-or-later. See LICENSE, and NOTICE for the full third-party picture.
