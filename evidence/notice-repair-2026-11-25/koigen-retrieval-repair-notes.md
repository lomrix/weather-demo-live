# Notice retrieval repair and model comparison

The original held-out run on the two user-confirmed references made zero model requests because neither notice had a candidate. A general driving vocabulary repair added the literal word `biltrafikk`. The focused regression suite passed 41 tests. The subsequent runs are repair checks on known inputs.

On Grevelokka, the keyword baseline abstained. Qwen 2.5 3B selected the correct sentence but returned a classification in place of the literal restriction quote. Validation withheld the restriction and access status. It matched two of four exact fields.

Qwen 3.5 9B in default reasoning mode used the 700-token allowance without an answer. A separate run explicitly set think=false on the 9B request only, keeping the input, prompt, schema and generation ceiling unchanged. It returned an answer in 127 generated tokens and about 2.6 seconds. All four fields were semantically consistent with the approved reference, and the checked status was closed. The strict scorer gave 3/4 because it extracted the street name as part of the restriction quote. Closure dates stayed unknown.

Both models still made zero requests on Skappelsgate. The notice describes an intention to keep the walking link available and the possibility of changes. The explicit-status filter defers this case. No model switch or publication is supported by this single repair case.

Raw artifacts: koigen-heldout-run-2026-11-25-retry/, koigen-repair-biltrafikk/, koigen-repair-biltrafikk-no-thinking/.

## Run provenance

The first held-out attempt created its output directory and then stopped at the Ollama model-list preflight with WinError 10061 (connection refused). No generation was attempted. The retry directory contains the completed held-out record.

The historical 9B reasoning-off run used a temporary request wrapper and did not record the option in its results JSON. The later --no-thinking-9b flag records the setting explicitly. Run python -B out/koigen-replay-request-options.py to reproduce the request-body check and checked scores from saved raw responses without a model call. See koigen-replay-request-options.log. The 12 November heading was checked on the official Grevelokka page and was outside the frozen evaluation excerpts.
