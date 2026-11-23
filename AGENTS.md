# AGENTS.md — PriceSpyglass

A store-agnostic price tracker (Python, standard library only).
`products.json` watchlist → `tracker.py` → `prices.sqlite` → `digest.py`.

## Working in this repo
- Run tests: `python3 -m unittest discover -s tests`
- Fetch: `python3 tracker.py [--dry-run]` · Digest: `python3 digest.py`
- The user-facing skill for this project lives in `skill/SKILL.md` —
  read it before changing fetch or scoring behaviour.

## House rules
- **Unknown means absent:** a price that cannot be read is never recorded,
  guessed or carried over.
- No third-party dependencies. Standard library only.
- Never hardcode products into code; the watchlist is `products.json`.
- Fetch politely: sequential requests, `PT_DELAY` (default 2s) between them.
