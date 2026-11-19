# Evidence-linked notice review — 19 November 2026

The workspace now reviews one source consequence at a time. It no longer fills
the displayed draft from Koigen's prepared reference answer. The model remains
`qwen2.5:3b`; routing, simulation dates, map confirmation and alerts are unchanged.

## How the current path works

1. Python uses the requested transport subject and simple source-word/status
   patterns to retrieve candidate sentences. Location words in the focus rank
   candidates. Obvious answer instructions are excluded. This is lexical
   retrieval, not geographic matching or general document understanding.
2. One bounded local request asks the model for one selected consequence,
   quoted location/restriction/dates, mode evidence and open/closed status.
   Source IDs, mode choices and status choices are constrained using the
   candidate set. These constraints are Python's contribution.
3. Python checks each field against that same source sentence. Casing and
   whitespace may be restored to the source form; paraphrases are withheld.
   A supplied date needs a literal quote containing a digit. Dates from a
   different sentence remain unknown, even when a person could link them.
4. If a model supplies `walking` as its evidence quote rather than the actual
   source word `gangstien`, a narrow source-word rule may support that mode.
   This is explicitly labelled **Source rule — review**, and the original
   model answer is retained. It is not counted as a successful model quotation.
5. The browser shows the fields, open/closed/unknown status, source sentence,
   expandable field evidence and raw-model diagnostics. Unsupported fields
   stay unknown. Human review and modeled-map-section confirmation remain required.

No prepared reference, `focus_quote` or reference sentence ID enters retrieval,
the prompt or the field checks. Source and focus are the inputs. The old prompt
and raw extractor remain available for reproducing the original comparison.

## What the experiments showed

We preserved two further live runs, eight requests each, and one offline recheck:

- **Sentence-bound v2:** asking the small models to list several consequences
  and choose one was not useful enough. Qwen still selected parking in some
  cases; Llama returned three abstentions and one invalid/duplicate-ID answer.
  The checks withheld inconsistent fields. This is retained as a failed revision.
- **Focused-source v3:** all eight requests produced selected, schema-valid
  answers. Qwen kept Koigen's footpath dates unknown; both models selected the
  actual path sentence and preserved the synthetic open-path status. Both
  avoided selecting the planted instruction. These results depend on source
  filtering and schema constraints, not on improved model reasoning alone.
- **Offline quote recheck:** the same eight v3 responses were rechecked after
  allowing source-case restoration and explicitly labelled source-word mode
  rules. No additional model requests were made. Qwen's Koigen closure statement
  remained available for review. Llama's Koigen restriction was incomplete and
  its non-calendar `pågår` date claim was withheld; access status remained unknown.

Four-field exact matches on the known real notice were 0/4 originally versus
2/4 revised raw for Qwen, and 0/4 versus 1/4 for Llama. Valid alternative
source quotes still lose matches, so these are contract scores, not semantic
accuracy percentages. The non-AI keyword reader using the **same retrieval**
scored 3/4 on Koigen and 4/4 on each synthetic case. AI superiority and review
time savings remain unproven on this small set.

The data contains one known municipal notice and three invented diagnostic
texts. They are reported separately; independent teammate reference review,
new real notices and repeated runs are still needed. The work strengthens the
source-to-scenario component of the wider walking, driving and bus-access
platform; it does not establish a general notice reader or a commercial product.

## Run and inspect

```text
python -B -m unittest check_notice_evidence check_koigen_notice check_notice_evaluation -v
python hamar_workspace.py --open
```

In the browser: **Load Koigen demo → Draft from notice → Field evidence and
review notes**. Inspect unknowns and the source, confirm the modeled section,
then select **Assess projects**. The modeled route remains **323 m → 593 m**.
Without Ollama, manual source review and confirmed simulation remain available.
The running Python server must be restarted after this Python-code change.

An explicit new eight-request experiment (Ollama running, models installed):

```text
python -B -m harness.notice_improvement --mode live --models qwen2.5:3b llama3.2:3b --output out/notice-revision-new-run
```

The limit is eight sequential requests, no retries, 90 seconds per request,
16 KiB response size and a 700-token generation setting. No candidate means no
model request. This is a client timeout and output setting, not a token-price
or guaranteed wall-clock budget. Existing output directories are preserved.

To recheck a saved revised `results.json` offline:

```text
python -B -m harness.notice_improvement --replay out/notice-revision-new-run/results.json --output out/notice-revision-recheck
```

The [preserved development experiment bundle](../fixtures/notice-evaluation/runs/evidence-development-2026-11-19.json)
contains both live runs, actual prompts/schemas, source snapshots, model digests
and the zero-request recheck. Its phases are `sentence_bound_v2`,
`focused_source_v3` and `offline_quote_recheck`. The original eight-request
experiment remains unchanged in `runs/2026-11-19/`.

## Remaining limits

Quote presence does not prove semantic support. Same-sentence text can still
contain several subjects or restrictions. Lexical retrieval can miss notices,
choose the wrong place, or fail on negation and unfamiliar wording. It reviews
one consequence and does not measure recall of every consequence. Simple
instruction patterns do not provide a general prompt-injection defence.
Calendar meaning, exact extent, current conditions and physical accessibility
require further verification. No model output creates a verified map closure,
reopening notice or navigation instruction automatically.
