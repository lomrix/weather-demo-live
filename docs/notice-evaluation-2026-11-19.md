# Local AI comparison — 19 November 2026

We ran the existing raw notice-extraction prompt against the two already
installed local models, `qwen2.5:3b` and `llama3.2:3b`. Each received the same
four cases, without reference answers. Eight model requests were made, with
no retries or prompt changes between them. All eight returned parseable,
schema-valid answers; that does **not** mean their claims were correct.

The comparison does not change the browser's model, routing, human-confirmation
gate or saved-journey alerts. It measures one component of the wider platform:
turning source text into facts someone can review before modeling an impact.

## Known real notice

The saved Koigen source is already a development example. It is not an unseen
test of generalisation. Scores below measure exact agreement with the saved
reference, not a human judgment of the overall usefulness of each answer.

| Method | Exact fields out of 4 | Citation precision / recall | Footpath date falsely supplied | Time |
| --- | ---: | --- | --- | ---: |
| Fixed keyword reader | 3/4 | 1.00 / 1.00 | No | 0.001 s |
| Qwen 2.5 3B | 0/4 | 0.17 / 1.00 | Yes | 5.310 s |
| Llama 3.2 3B | 0/4 | 1.00 / 1.00 | Yes | 53.830 s |

Both models transferred the parking period, `oktober-november 2026 til sommeren
2027`, to the footpath. Both added unsupported modes to the focused footpath
consequence. Llama cited the correct sentence, showing that a correct citation
ID alone does not establish support for every field. The fixed reader found
the right restriction and kept dates unknown, but its location quotation was
broader than the reference and lost an exact match.

Model timing includes loading and local runtime conditions. The two timings
are not a controlled speed comparison. Token counts and loading durations are
retained in the raw record; these local runs make no monetary cost claim.

## Synthetic diagnostic cases

These three texts, locations and dates were invented. Their results are
reported separately from the municipal notice.

- **Explicit footpath dates beside parking dates:** Qwen selected the right
  sentence and gave a source-supported location, restriction and date range,
  but shorter/longer quotes lost exact matches. Its 1/4 exact field score is
  not a fair description of that answer's semantic accuracy. Llama identified
  the path and dates, but added all four transport modes and paraphrased the
  restriction instead of quoting it.
- **Footpath explicitly open, nearby parking closed:** both models described
  a footpath closure and borrowed the parking period. This is a consequential
  source-scope failure, not just a wording mismatch. The production prompt's
  closure-focused wording may contribute; this run does not isolate its cause.
- **Instruction planted in the source text:** Qwen cited the instruction's
  sentence instead of the actual closure sentence. Llama included the planted
  year `2030`. The fixed reader also selected the wrong first sentence, so it
  is not a safe replacement for human review.

The aggregate exact-field scores on synthetic text were 10/12 for the fixed
reader, 2/12 for Qwen and 3/12 for Llama. These totals are diagnostic only:
the examples are small and author-created, the baseline is deliberately narrow,
and acceptable quote variants can lose matches. Do not present the totals as
real-world model accuracy or as proof that rules generally outperform models.

## What we can say in the exam report

We implemented a reproducible comparison of raw model extraction against a
non-AI baseline. The evaluation uncovered cross-restriction date errors,
unsupported travel modes and source-instruction/citation failures. The existing
review gate prevents these drafts from automatically becoming verified map
closures. The current UI uses a prewritten reference to correct Koigen facts;
that correction is not general automated fact verification. Human review and
unknown closure geometry/dates remain explicit.

We have **not yet demonstrated** that either model saves review time or beats
the baseline on independently annotated, unseen notices. The next experiment
should freeze teammate-reviewed references, include further real notices,
allow supported wording variants in manual assessment, and repeat runs. Compare
the current prompt with a revised one only after retaining this original run.

## Saved evidence

- [Complete raw answers, scores, source/prompt/code hashes and usage](../fixtures/notice-evaluation/runs/2026-11-19/results.json)
- [Installed model digests and metadata](../fixtures/notice-evaluation/runs/2026-11-19/installed-models.json)
- [Fixed cases and annotation status](../fixtures/notice-evaluation/cases.json)
- [Commands, scoring rules and review checklist](notice-ai-evaluation.md)

The installed-model snapshot was collected immediately after this comparison;
no model downloads or updates were performed. Saved results are an actual
local-model experiment. Unit tests replaying them remain offline checks and
are not additional live experiments.
