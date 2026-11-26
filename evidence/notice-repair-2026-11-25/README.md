# Notice retrieval repair evidence

From the repository root, run:

    python -B -m unittest check_notice_evidence check_koigen_notice check_notice_evaluation -q
    python -B evidence/notice-repair-2026-11-25/koigen-replay-request-options.py

The replay uses saved responses without calling Ollama. For a new local run,
use koigen-heldout-evaluation.py with the included confirmed labels and a new
output directory. Use --no-thinking-9b for the reasoning-disabled comparison.

The historical results came from the earlier revision identified in the JSON.
The first completed held-out run made zero model requests. The repair checks
reuse the diagnosed notices. The historical reasoning-off request was recorded
in the run notes. The updated runner records the option in new results.
