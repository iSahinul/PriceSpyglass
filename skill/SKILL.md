---
name: pricespyglass
description: Use when working with PriceSpyglass — adding products to the watchlist, choosing a fetch path, running the tracker or digest, or interpreting deal scores. Enforces the core rule: a price that cannot be read is never recorded, guessed or carried over.
---

# PriceSpyglass

A store-agnostic price tracker: `products.json` watchlist → `tracker.py`
(JSON-LD or Shopify .js fetch) → `prices.sqlite` history → `digest.py`
(drops, 30-day lows, deal scores). Python standard library only.

## The one rule

**Unknown means absent.** If a fetch fails or a page has no readable price,
record nothing for that product. Never guess a price, never copy yesterday's
price into today, never fill a gap. A hole in the history is honest; a
plausible number is a lie.

## Adding a product

Add an entry to `products.json`:

```json
{"key": "short-unique-slug", "name": "Human name", "store": "store-domain",
 "url": "https://store/products/page", "via": "jsonld"}
```

Pick `via` like this:

- The store is Shopify (page URL has `/products/`, or the shop runs on
  Shopify) → `"shopify"` — the tracker appends `.js` to the URL and reads
  the first variant. This path also gives the compare-at (list) price,
  which feeds the deal score's discount-depth component.
- Anything else → `"jsonld"` — the tracker reads the schema.org JSON-LD
  Product block. If a test run prints "no price found", the page ships no
  usable JSON-LD; do not invent another path silently — tell the user this
  store is not readable yet.

After adding, run `python3 tracker.py --dry-run` and confirm the new
product's price prints before doing a real run.

## Running it

```bash
python3 tracker.py            # fetch + store (idempotent per minute)
python3 tracker.py --dry-run  # fetch + print only
python3 digest.py             # writes digests/YYYY-MM-DD.md
```

Config comes from environment variables only: `PT_PRODUCTS`, `PT_DB`,
`PT_DELAY` (seconds between fetches — do not lower it below 1; politeness
is a feature), `PT_CURRENCY` (symbol shown in the digest).

## Reading a deal score (0–100)

- Discount depth: 40 points — vs the list/compare-at price, capped.
- Vs 30-day low: 40 points — at the month's lowest = full marks.
- Vs 30-day average: 20 points — below the usual price.

Interpretation: a big "percent off" with a mediocre score means the
product has been cheaper — the score trusts history over the banner.
Scores need history: a product tracked for two days has a thin score.
Say so instead of presenting it as settled.

## House rules

- Keep the watchlist in `products.json`; never hardcode products into code.
- The database is one file (`prices.sqlite`). Backing it up backs up
  everything; deleting rows rewrites history — don't.
- Fetch failures are reported as failures. "No price found" is a result,
  not an error to paper over.
