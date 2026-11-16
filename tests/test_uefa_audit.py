"""Offline regression tests for the read-only UEFA reconciliation."""
import pathlib
import sys
import unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from audit_uefa_fixtures import extract,audit,norm

class UefaAuditTests(unittest.TestCase):
    def test_normalization(self):
        self.assertEqual(norm("Bayern München"),norm("Bayern Munich"))
        self.assertEqual(norm("Atlético de Madrid"),norm("Atletico Madrid"))
    def test_extract_results_and_fixtures(self):
        rows=[]
        for i in range(1,19):
            rows.append(f"<p>Tuesday {i} November 2026</p><p>Club A {i}-0 Club B</p><p>Club C vs Club D (18:45)</p>")
        html="<article>"+"".join(rows)+"</article>"
        matches=extract(html,"UCL")
        self.assertEqual(len(matches),36)
        self.assertEqual(matches[0]["status"],"finished")
        self.assertEqual(matches[1]["status"],"scheduled")
    def test_conflicts_are_reported_not_applied(self):
        original=[dict(date="2026-11-03",home="Bayern Munich",away="Roma",hg=2,ag=1,status="finished")]
        source=[dict(date="2026-11-03",home="Bayern München",away="Roma",hg=2,ag=0,status="finished")]
        report=audit(original,source)
        self.assertEqual(report["verified"],0)
        self.assertEqual(len(report["conflicts"]),1)
        self.assertEqual(original[0]["ag"],1)
    def test_exact_match(self):
        original=[dict(date="2026-11-03",home="Bayern Munich",away="Roma",hg=2,ag=1,status="finished")]
        source=[dict(date="2026-11-03",home="Bayern München",away="Roma",hg=2,ag=1,status="finished")]
        self.assertEqual(audit(original,source)["verified"],1)
if __name__=="__main__":unittest.main()
