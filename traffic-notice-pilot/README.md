# Traffic notice pilot

Run from this directory with Python 3.

- Offline demo: python traffic_demo.py --archive-example
- Live demo: python traffic_demo.py --live --export-koigen --archive-example
- AI review: python traffic_ai.py out/koigen-live-input.txt --sentence-ids --focus "Stenging av gangstien ved Koigen pumpestasjon" --review-html out/koigen-ai-review.html

Open out/traffic-archive-test.html for Norwegian, English and Ukrainian. The AI command uses local Ollama and qwen2.5-coder:7b by default. For a saved input, use ai-cases/koigen.txt instead of out/koigen-live-input.txt.

The live pilot checks the municipal traffic listing and reads up to five notices. The CC Hamar bus card and Basar underpass example were reviewed manually. AI output requires human review and does not change routes.

The team needs to confirm the Koigen path segment before connecting its card to a simulation. The card ID is koigen-sjoledning and map_segment is null until verified.

See ai-cases/ for fixture expectations and recorded results. Four of four responses passed the sentence-ID check on rewritten fixtures. Human review found omissions and incorrect field assignments. The focused run on the Koigen web text excluded the parking dates but left the affected-user field empty.
