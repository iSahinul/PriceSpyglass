import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["PT_DB"] = os.path.join(tempfile.mkdtemp(), "test.sqlite")

import db
import tracker
import digest


class JsonLdTests(unittest.TestCase):
    def test_simple_product(self):
        html = ('<script type="application/ld+json">'
                '{"@type":"Product","offers":{"price":"1299","priceCurrency":"INR"}}'
                '</script>')
        price, cur = tracker.parse_jsonld_price(html)
        self.assertEqual(price, 1299.0)
        self.assertEqual(cur, "INR")

    def test_graph_and_list_offers(self):
        html = ('<script type="application/ld+json">'
                '{"@graph":[{"@type":"Product","offers":[{"price":499.5}]}]}'
                '</script>')
        price, _ = tracker.parse_jsonld_price(html)
        self.assertEqual(price, 499.5)

    def test_no_product(self):
        price, _ = tracker.parse_jsonld_price("<html>no markup</html>")
        self.assertIsNone(price)

    def test_bad_json_skipped(self):
        html = ('<script type="application/ld+json">{not json</script>'
                '<script type="application/ld+json">'
                '{"@type":"Product","offers":{"price":10}}</script>')
        price, _ = tracker.parse_jsonld_price(html)
        self.assertEqual(price, 10.0)


class ShopifyTests(unittest.TestCase):
    def test_first_variant_smallest_unit(self):
        payload = json.dumps({"variants": [
            {"price": 249900, "compare_at_price": 299900, "available": True}]})
        price, mrp, avail = tracker.parse_shopify_js(payload)
        self.assertEqual(price, 2499.0)
        self.assertEqual(mrp, 2999.0)
        self.assertTrue(avail)


class DbTests(unittest.TestCase):
    def test_idempotent_points(self):
        conn = db.get_db()
        db.upsert_product(conn, "k1", "Widget", "store", "https://x")
        self.assertEqual(db.add_point(conn, "k1", "Widget", "store",
                                      "2026-01-01 10:00", 100.0, 120.0, "jsonld"), 1)
        self.assertEqual(db.add_point(conn, "k1", "Widget", "store",
                                      "2026-01-01 10:00", 100.0, 120.0, "jsonld"), 0)
        conn.commit()
        conn.close()


class ScoreTests(unittest.TestCase):
    def test_at_low_full_marks_low_component(self):
        # price == 30d low, no mrp, price == avg -> low 40 only
        self.assertEqual(digest.deal_score(100.0, None, 100.0, 100.0), 40)

    def test_deep_discount_scores_high(self):
        s = digest.deal_score(400.0, 1000.0, 400.0, 500.0)
        self.assertGreaterEqual(s, 80)

    def test_no_data_zero(self):
        self.assertEqual(digest.deal_score(None, None, None, None), 0)


if __name__ == "__main__":
    unittest.main()
