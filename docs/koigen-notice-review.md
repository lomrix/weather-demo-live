# Koigen notice-to-map review

## Launch

From the repository root:

```text
python hamar_workspace.py --open
```

Select **Load Koigen demo**. Select **Draft from notice** for the optional local
Ollama step, review the cited sentence and corrections, then explicitly confirm
OSM way `112510399` as a modeled candidate before selecting **Assess projects**.
The notice is the saved file
[`fixtures/notices/hamar-koigen-footpath.json`](../fixtures/notices/hamar-koigen-footpath.json).
The extraction and sentence-ID approach is adapted, with attribution, from
Kai's draft PR #20 at commit
`408db94022cbf0a58d163921618fdddcf51dbc8c`.

## Actual local Ollama comparison

One browser action was run on 2026-11-18 with the installed local
`qwen2.5:3b` model. It made one request to `127.0.0.1:11434/api/generate`, with
a 90-second timeout and a 16 KiB response limit. This is a local model result,
not a mocked result.

The model cited sentences 9, 10, 11, 12, 13 and 14. Only sentence 10 directly
describes the focused footpath closure:

> Mens byggingen av nytt ledningsnett fra avløpspumpestasjon og ut i Mjøsa
> pågår, vil gangstien langs Mjøsa bli stengt, og omlegging av gangstien skal
> være skiltet.

Hand-checked comparison:

- **Correct fields:** No field matched the complete reference exactly. The
  model did include walking and cited the correct closure sentence.
- **Omissions:** the location was too narrow (`pumpestasjon`), and walking was
  not the only travel mode. The restriction was paraphrased instead of using a
  source quote.
- **Unsupported claims:** cycling; project, road, and parking sentences cited
  outside the focused consequence; and the parking period
  `oktober-november 2026 til sommeren 2027` presented as a footpath closure
  date.
- **Corrections:** use walking only, cite sentence 10 only, quote the closure
  and signed-diversion clause, describe the location with the sentence's
  pumping-station-to-Mjøsa wording, and leave exact footpath dates unknown.

Python verifies that displayed sentence IDs exist in the saved notice and
applies the focused-scope correction. The notice still does not establish the
exact closure endpoints or dates. The OSM section used for the route comparison
remains a modeled candidate, not a verified closure boundary.

## Verification

Passed:

- Focused checks for unsupported evidence, parking-date confusion, invalid
  citation IDs, explicit confirmation before assessment, one bounded request,
  and Ollama-unavailable behavior.
- Existing workspace checks including the 323 m baseline, 593 m modeled detour
  and +270 m change.
- Browser flow: load Koigen, draft from the saved notice, inspect the reviewed
  fields and sentence, confirm the modeled section, and assess to 323 m/593 m.

Incomplete by design:

- Exact footpath closure dates and endpoints are unknown.
- The 593 m route is not a reconstruction of the signed diversion.
- On-site accessibility, slope, surface, steps, legal access and physical
  feasibility are not checked.
- A successful draft remains a model result requiring human review.
