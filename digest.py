#!/usr/bin/env python3
"""Daily digest over the price history: what actually got cheaper?

Reads prices.sqlite and writes digests/YYYY-MM-DD.md with:
  - Top 5 price drops (last 7 days)
  - Products sitting at their 30-day low
  - Average discount by store
  - Deal scores (top 10)

Deal score (0-100) = discount depth vs list price (40)
                   + how close the price is to its 30-day low (40)
                   + how far it sits below its 30-day average (20).
A high score means "genuinely cheap right now", not just "big MRP".

Usage: python3 digest.py
"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_db

BASE = os.path.dirname(os.path.abspath(__file__))
DIGEST_DIR = os.path.join(BASE, "digests")
SYMBOL = os.environ.get("PT_CURRENCY", "")


def fmt(n):
    return "%s%s" % (SYMBOL, f"{n:,.0f}") if n is not None else "-"


def parse_ts(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M").replace(
        tzinfo=datetime.now().astimezone().tzinfo)


def deal_score(price, mrp, low30, avg30):
    depth = 0.0
    if mrp and mrp > 0 and price is not None:
        depth = min(max((mrp - price) / mrp * 100, 0), 60) / 60 * 40
    low = 0.0
    if price is not None and low30:
        low = min(low30 / price, 1.0) * 40 if price > 0 else 0.0
    avg = 0.0
    if price is not None and avg30:
        avg = min(max((avg30 - price) / avg30, 0), 0.30) / 0.30 * 20
    return round(min(depth + low + avg, 100))


def main():
    conn = get_db()
    now = datetime.now().astimezone().replace(tzinfo=None)
    win7, win30 = now - timedelta(days=7), now - timedelta(days=30)
    products = conn.execute(
        "SELECT product_key, name, store FROM products ORDER BY name").fetchall()
    rows = []
    for key, name, store in products:
        pts = conn.execute(
            "SELECT checked_at, price, mrp FROM price_history"
            " WHERE product_key=? AND price IS NOT NULL ORDER BY checked_at",
            (key,)).fetchall()
        if not pts:
            continue
        latest_ts, latest_price = pts[-1][0], pts[-1][1]
        mrp = pts[-1][2] or next((p[2] for p in reversed(pts) if p[2]), None)
        old = next((p for p in pts if parse_ts(p[0]).replace(tzinfo=None) <= win7), None) or pts[0]
        w30 = [p[1] for p in pts if parse_ts(p[0]).replace(tzinfo=None) >= win30]
        low30 = min(w30) if w30 else None
        avg30 = sum(w30) / len(w30) if w30 else None
        disc = round((mrp - latest_price) / mrp * 100) if mrp and mrp > latest_price else 0
        drop_pct = round((old[1] - latest_price) / old[1] * 100, 1) if old[1] else 0
        rows.append({
            "key": key, "name": name, "store": store or "-",
            "price": latest_price, "mrp": mrp, "disc": disc,
            "old_price": old[1], "drop_pct": drop_pct, "low30": low30,
            "at_low": bool(low30 and latest_price <= low30 and len(w30) >= 2),
            "score": deal_score(latest_price, mrp, low30, avg30),
        })
    conn.close()

    drops = sorted([r for r in rows if r["drop_pct"] > 0], key=lambda r: -r["drop_pct"])[:5]
    at_lows = [r for r in rows if r["at_low"]]
    by_store = {}
    for r in rows:
        by_store.setdefault(r["store"], []).append(r["disc"])
    avg_disc = {s: round(sum(v) / len(v), 1) for s, v in sorted(by_store.items())}
    top_scores = sorted(rows, key=lambda r: -r["score"])[:10]
    date_s = now.strftime("%Y-%m-%d")

    lines = ["# Price digest - %s" % date_s, "",
             "_%d products tracked._" % len(rows), "",
             "## Top 5 price drops (7d)"]
    if drops:
        for r in drops:
            lines.append("- **%s** (%s): %s -> %s (**-%s%%**) - score %d" % (
                r["name"], r["store"], fmt(r["old_price"]), fmt(r["price"]),
                r["drop_pct"], r["score"]))
    else:
        lines.append("- No drops in the window.")
    lines += ["", "## At 30-day low"]
    if at_lows:
        for r in at_lows:
            lines.append("- **%s** (%s): %s - score %d" % (
                r["name"], r["store"], fmt(r["price"]), r["score"]))
    else:
        lines.append("- None right now.")
    lines += ["", "## Average discount by store"]
    for s, d in avg_disc.items():
        lines.append("- %s: %s%%" % (s, d))
    lines += ["", "## Deal scores (top 10)"]
    for r in top_scores:
        lines.append("- %d/100 - **%s** (%s): %s (list %s, %d%% off)" % (
            r["score"], r["name"], r["store"], fmt(r["price"]),
            fmt(r["mrp"]), r["disc"]))
    lines += ["", "_Deal score = discount depth 40 + vs 30-day low 40 + vs 30-day average 20._"]
    md = "\n".join(lines) + "\n"

    os.makedirs(DIGEST_DIR, exist_ok=True)
    out = os.path.join(DIGEST_DIR, "%s.md" % date_s)
    open(out, "w").write(md)
    print("digest written: %s" % out)


if __name__ == "__main__":
    main()
