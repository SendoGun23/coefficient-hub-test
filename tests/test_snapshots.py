"""Offline integrity checks for published coefficient snapshots."""
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
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

if __name__ == "__main__":
    unittest.main()
