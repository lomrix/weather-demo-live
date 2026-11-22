# Baseline before passing a JSON schema to Ollama

Model: qwen2.5-coder:7b. Source: Kai's PowerShell runs against the four
manually rewritten fixtures. One output per case, using the revised
verbatim prompt and generic JSON mode.

| Case | Quote check | Observation |
| --- | --- | --- |
| Koigen | Passed | Work period correct. Measure omitted the signposted diversion. |
| Gåsbuvegen | Rejected | Location combined words separated in the source. |
| Basar | Rejected | The model returned the string "null" for affected users. |
| CC Hamar | Rejected | The affected-user excerpt changed capitalization. |

The 3B comparison on Koigen was rejected for a paraphrased measure.
Acceptance measures quote matching, not correct field meaning.
