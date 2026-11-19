# Measuring the notice-reading AI

The question is whether a local model can draft the **correct facts with useful
citations**, rather than whether Python can display a prewritten reference.
The existing Koigen UI corrects the draft with its hand-checked reference.
That corrected result is useful for review but cannot count as model accuracy.
This evaluator scores raw extraction first. It does not change routing,
confirmation requirements, alerts or the browser's selected model.

## Reproduce

From the repository root, with Python 3.12 or later:

```text
python -B -m unittest check_notice_evaluation check_koigen_notice -v
python -B -m harness.notice_evaluation --mode baseline --output out/notice-baseline
```

Baseline mode is offline and makes zero model requests. It uses a deliberately
simple fixed rule: select the first sentence mentioning `gangsti`, extract its
first `vil`/`er` clause, and look for an explicit `fra … til …` date range in
that sentence. It never receives reference answers. This is a narrow Norwegian
walking-notice baseline, not a general document reader.

With Ollama already running and both models already installed, explicitly run:

```text
python -B -m harness.notice_evaluation --mode live --models qwen2.5:3b llama3.2:3b --output out/notice-model-comparison
```

This makes at most **eight sequential model requests**, one per model per case,
with no retries, a 90-second timeout per request, 16 KiB response limit and 400
generated-token setting. It uses the existing workspace extraction prompt and
JSON schema. It does not download models or contact a paid model service. A
timeout or malformed answer is a recorded failure; a failed run exits nonzero
but still saves its results. Existing output directories are never overwritten.

For just the known real notice (two model requests):

```text
python -B -m harness.notice_evaluation --mode live --models qwen2.5:3b llama3.2:3b --case hamar-koigen-footpath --output out/notice-koigen-comparison
```

Each new output directory contains `report.md` and `results.json`. JSON retains
source/prompt/code hashes, references, raw model replies, individual field
scores, citation precision/recall, failures, timings and model-reported token
counts when supplied. Timing includes local model loading; it is not a claim
about a cloud service or user time saved. Model tags may change; archive the
installed model digests separately with any experiment used in the final report.

## Dataset and interpretation

`fixtures/notice-evaluation/cases.json` fixes the cases before execution:

| Evidence | Cases | Purpose |
| --- | ---: | --- |
| Existing saved municipal Koigen notice | 1 | Known development case with unrelated parking dates |
| Invented diagnostic notices | 3 | Explicit path dates, path open beside closed parking, planted source instruction |

Synthetic locations, restrictions and dates are fictional. They must not
become actual project records or route alerts. The real notice retains its
municipal attribution and saved provenance; no new collection is performed.
References were prepared by the developer from the supplied text. They are
**not independently validated yet**, and Koigen is not a held-out test case.

Four fields are scored separately: location, travel modes, restriction and
stated dates. Sentence IDs are evaluated separately using precision/recall;
an exact case requires all four fields and the reference citation set. An
unknown date correctly returned as null counts as a match; it does not prove
successful date extraction. Inspect the per-field results as well as totals.
Whitespace is normalised and mode lists are compared as sets. Every extraction
attempt remains in the field-score denominator, including failed requests.

A reference mismatch is **not automatically a hallucination**. Alternative
valid wording can lose an exact match. Quote presence alone does not prove a
claim is supported; a quote can describe the wrong restriction. An unexpected
date for a reference with no stated dates is separately flagged for review.
Neither the model nor this evaluation proves map geometry or physical access.

The unchanged production prompt explicitly asks for a closure and signed
diversion. The open-path case deliberately tests that wording's possible bias.
Record the results before changing the prompt; compare any revised prompt in
a new run, retaining both versions and avoiding claims of held-out improvement.

## Teammate review and stronger exam evidence

1. Independently read each saved source before seeing the model's answer.
2. Check the location, modes, restriction, applicable dates and citation IDs;
   record disagreements and resolve them before freezing a test set.
3. Add independently sourced notices covering other locations and transport
   consequences in a later corpus extension. Keep development and held-out
   notices separate; the current prompt/baseline are limited to footpaths.
4. Repeat model runs and compare review time with manual review and the baseline.
5. Record two consequential failure cases, how review prevents a bad scenario,
   and whether the AI provides any measured benefit. Report negative results.

This is evidence infrastructure for the lecturer's LLM feedback. It does not
establish commercial demand, human-review time savings or general AI superiority.
