"""Replay saved Grevelokka responses and record the outgoing request options."""
import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import importlib.util

out = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("heldout", out / "koigen-heldout-evaluation.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
case = next(c for c in runner.load_json(runner.INPUTS) if c["id"] == "grevelokka-driving")
case.update(runner.load_json(out / "koigen-heldout-labels-confirmed.json")[case["id"]])
case["input"] = {"focus": case["focus"], "sentences": runner.article_sentences(case["text"])}
saved = out / "koigen-repair-biltrafikk-no-thinking"
for model, disable, expected in zip(runner.MODELS, (False, True), (2, 3), strict=True):
    raw = saved / f"{case['id']}-{model.replace(':', '-')}-raw.json"
    requests = []

    def replay(request, **kwargs):
        requests.append(json.loads(request.data))
        return io.BytesIO(raw.read_bytes())

    with patch.object(runner, "urlopen", replay), tempfile.TemporaryDirectory(dir=out) as temp:
        result = runner.model_run(case, model, Path(temp), "offline-replay", disable)
    assert len(requests) == 1 and requests[0]["model"] == model
    assert ("think" in requests[0]) == disable
    if disable:
        assert requests[0]["think"] is False
    assert result["request_options"] == ({"think": False} if disable else {})
    score = result["checked_score"]["matched_fields"]
    assert score == expected
    print(f"{model}: think={requests[0].get('think', 'omitted')}; checked={score}/4; {raw.name}")
print("Offline replay passed. No requests were sent to Ollama.")
