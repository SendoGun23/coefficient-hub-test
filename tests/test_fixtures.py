"""Regression tests for the documented partial match archive."""
import collections
import datetime
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
FILE = ROOT / "v2" / "data" / "fixtures.json"

def validate(payload):
    if payload.get("status") != "partial_unverified":
        raise ValueError("Fixture provenance must remain explicitly unverified")
    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) != payload.get("count") or not rows:
        raise ValueError("Fixture count mismatch")
    seen = set()
    for row in rows:
        if row.get("competition") not in {"UCL", "UEL", "UECL"}:
            raise ValueError("Unknown competition")
        if row.get("season") not in {"2025/26", "2026/27"}:
            raise ValueError("Unexpected season")
        date = datetime.date.fromisoformat(row["date"])
        if not row["home"] or not row["away"] or row["home"] == row["away"]:
            raise ValueError("Invalid teams")
        key = (row["season"], row["competition"], date, row["home"], row["away"])
        if key in seen:
            raise ValueError("Duplicate fixture")
        seen.add(key)
        if row["status"] == "finished":
            if any(type(row[k]) is not int or not 0 <= row[k] <= 30 for k in ("hg", "ag")):
                raise ValueError("Invalid final score")
        elif row["status"] == "scheduled":
            if row["hg"] is not None or row["ag"] is not None:
                raise ValueError("Scheduled game has a score")
        else:
            raise ValueError("Unknown fixture status")
    return rows

class FixtureTests(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads(FILE.read_text(encoding="utf-8"))

    def test_archive_integrity(self):
        rows = validate(self.payload)
        self.assertEqual(len(rows), 288)
        self.assertEqual(sum(x["status"] == "finished" for x in rows), 216)
        self.assertEqual(sum(x["status"] == "scheduled" for x in rows), 72)

    def test_duplicate_rejected(self):
        self.payload["rows"][-1] = dict(self.payload["rows"][0])
        with self.assertRaises(ValueError):
            validate(self.payload)

    def test_scheduled_score_rejected(self):
        scheduled = next(x for x in self.payload["rows"] if x["status"] == "scheduled")
        scheduled["hg"] = 1
        with self.assertRaises(ValueError):
            validate(self.payload)

    def test_completed_score_rejected(self):
        played = next(x for x in self.payload["rows"] if x["status"] == "finished")
        played["hg"] = None
        with self.assertRaises(ValueError):
            validate(self.payload)

if __name__ == "__main__":
    unittest.main()
