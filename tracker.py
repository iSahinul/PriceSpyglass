#!/usr/bin/env python3
"""Fetch current prices for every product in products.json.

Two fetch paths, chosen per product with "via":

  jsonld   - fetch the product page and read the JSON-LD Product block
             (offers.price). Works on any store that ships schema.org
             markup - most modern e-commerce themes do.
  shopify  - fetch the product's public .js endpoint
             (https://store/products/<handle>.js) and read the first
             variant's price / compare_at_price / available. Works on
             every Shopify store, no API key needed.

Polite by default: sequential requests, a browser user-agent, and a
configurable delay between fetches (PT_DELAY seconds, default 2).
A product whose price cannot be read records NOTHING - prices are
never guessed.

Usage:
  python3 tracker.py            # fetch all, store points
  python3 tracker.py --dry-run  # fetch and print, store nothing
"""
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_db, upsert_product, add_point

BASE = os.path.dirname(os.path.abspath(__file__))
REGISTRY = os.environ.get("PT_PRODUCTS", os.path.join(BASE, "products.json"))
DELAY = float(os.environ.get("PT_DELAY", "2"))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "replace")


def _products_from_jsonld(data):
    """Yield every Product node in a parsed JSON-LD blob."""
    if isinstance(data, dict):
        if data.get("@type") == "Product":
            yield data
        for node in data.get("@graph", []) or []:
            yield from _products_from_jsonld(node)
        for value in data.values():
            if isinstance(value, (dict, list)):
                yield from _products_from_jsonld(value)
    elif isinstance(data, list):
        for item in data:
            yield from _products_from_jsonld(item)


def parse_jsonld_price(html):
    """Return (price, currency) from the first JSON-LD Product offer."""
    blocks = re.findall(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        html, re.S | re.I)
    for block in blocks:
        try:
            data = json.loads(block.strip())
        except (ValueError, TypeError):
            continue
        for product in _products_from_jsonld(data):
            offers = product.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            price = offers.get("price")
            if price is None:
                spec = offers.get("priceSpecification") or {}
                price = spec.get("price")
            if price is not None:
                try:
                    return float(price), offers.get("priceCurrency")
                except (TypeError, ValueError):
                    continue
    return None, None


def parse_shopify_js(text):
    """Return (price, compare_at_price, available) from a .js payload.
    Shopify reports money in the smallest currency unit (paise/cents)."""
    data = json.loads(text)
    variants = data.get("variants") or []
    if not variants:
        return None, None, None
    v = variants[0]
    def money(x):
        return x / 100.0 if isinstance(x, (int, float)) else None
    return money(v.get("price")), money(v.get("compare_at_price")), v.get("available")


def main():
    dry = "--dry-run" in sys.argv
    products = json.load(open(REGISTRY))
    if isinstance(products, dict):
        products = products.get("products", [])
    conn = None if dry else get_db()
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
    stored = 0
    for i, p in enumerate(products):
        if i:
            time.sleep(DELAY)
        key, name = p["key"], p.get("name", p["key"])
        store, url = p.get("store", ""), p["url"]
        via = p.get("via", "jsonld")
        price = mrp = None
        try:
            if via == "shopify":
                price, mrp, _avail = parse_shopify_js(fetch(url.rstrip("/") + ".js"))
                source = "shopify-js"
            else:
                price, _cur = parse_jsonld_price(fetch(url))
                source = "jsonld"
        except Exception as e:
            print("%s: FETCH FAILED (%s)" % (key, e))
            continue
        if price is None:
            print("%s: no price found - nothing recorded" % key)
            continue
        print("%s: %s (mrp %s) via %s" % (key, price, mrp, source))
        if not dry:
            upsert_product(conn, key, name, store, url)
            stored += add_point(conn, key, name, store, stamp, price, mrp, source)
    if conn is not None:
        conn.commit()
        conn.close()
    print("done: %d new points stored" % stored if not dry else "dry run - nothing stored")


if __name__ == "__main__":
    main()
