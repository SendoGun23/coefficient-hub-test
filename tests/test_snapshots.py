"""Offline integrity checks for published coefficient snapshots."""
import json
import pathlib
import sys
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import refresh_coefficients as importer
from refresh_coefficients import validate_snapshot

class SnapshotTests(unittest.TestCase):
    def read(self, kind):
        return json.loads((ROOT / "v2" / "data" / (kind + ".json")).read_text(encoding="utf-8"))

    def test_country_snapshot(self):
        payload = self.read("countries")
        self.assertEqual(payload["count"], 55)
        self.assertFalse(payload["verified_by_uefa"])
        self.assertTrue(validate_snapshot("countries", payload["rows"]))

    def test_club_snapshot(self):
        payload = self.read("clubs")
        self.assertEqual(payload["count"], len(payload["rows"]))
        self.assertFalse(payload["verified_by_uefa"])
        self.assertTrue(validate_snapshot("clubs", payload["rows"]))

    def test_country_corruption_rejected(self):
        rows = self.read("countries")["rows"]
        rows[0]["seasons"][0] += 5
        with self.assertRaises(ValueError):
            validate_snapshot("countries", rows)

    def test_club_duplicate_rejected(self):
        rows = self.read("clubs")["rows"]
        rows[-1]["name"] = rows[0]["name"]
        with self.assertRaises(ValueError):
            validate_snapshot("clubs", rows)

class ImportSafetyTests(unittest.TestCase):
    def test_partial_import_never_publishes(self):
        with patch.object(importer, "get", side_effect=["<html></html>", "<html></html>"]), \
             patch.object(importer, "extract_countries", side_effect=ValueError("missing countries")), \
             patch.object(importer, "extract_clubs", return_value=[{"rank": i + 1, "name": f"Club {i}", "score": 150 - i / 10} for i in range(100)]), \
             patch.object(importer, "publish") as publish, \
             patch.object(sys, "argv", ["refresh_coefficients.py"]):
            self.assertEqual(importer.main(), 1)
            publish.assert_not_called()

    def test_valid_import_publishes_both(self):
        countries = self.read("countries")["rows"]
        clubs = self.read("clubs")["rows"]
        with patch.object(importer, "get", return_value="<html></html>"), \
             patch.object(importer, "extract_countries", return_value=countries), \
             patch.object(importer, "extract_clubs", return_value=clubs), \
             patch.object(importer, "publish") as publish, \
             patch.object(sys, "argv", ["refresh_coefficients.py", "--dry-run"]):
            self.assertEqual(importer.main(), 0)
            self.assertEqual(publish.call_count, 2)

if __name__ == "__main__":
    unittest.main()
