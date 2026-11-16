"""Offline regression tests for the read-only UEFA reconciliation."""
import pathlib
import sys
import unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from audit_uefa_fixtures import extract,audit,norm,SOURCES

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
    def test_three_official_competitions_configured(self):
        self.assertEqual(set(SOURCES), {"UCL", "UEL", "UECL"})
        for url in SOURCES.values():
            self.assertTrue(url.startswith("https://www.uefa.com/"))
    def test_conference_article_by_team_section_is_not_double_counted(self):
        rows=[]
        for i in range(1,19):
            rows.append(f"<p>Thursday {i} October 2026</p><p>Club A {i}-0 Club B</p><p>Club C vs Club D</p>")
        html="<article>"+"".join(rows)+"<h2>League phase fixtures by team</h2>"+"".join(rows)+"</article>"
        self.assertEqual(len(extract(html,"UECL")),36)
    def test_missing_source_games_are_not_auto_published(self):
        original=[]
        source=[dict(date="2026-11-05",home="Ajax",away="Roma",hg=2,ag=0,status="finished")]
        result=audit(original,source)
        self.assertEqual(len(result["not_in_archive"]),1)
        self.assertEqual(original,[])
    def test_conflicts_are_reported_not_applied(self):
        original=[dict(date="2026-11-03",home="Bayern Munich",away="Roma",hg=2,ag=1,status="finished")]
        source=[dict(date="2026-11-03",home="Bayern München",away="Roma",hg=2,ag=0,status="finished")]
        report=audit(original,source)
        self.assertEqual(report["verified"],0)
        self.assertEqual(len(report["conflicts"]),1)
        self.assertEqual(original[0]["ag"],1)
    def test_scheduled_match_with_official_result_is_pending_not_conflict(self):
        original=[dict(date="2026-11-24",home="Ajax",away="Roma",hg=None,ag=None,status="scheduled")]
        source=[dict(date="2026-11-24",home="Ajax",away="Roma",hg=2,ag=1,status="finished")]
        result=audit(original,source)
        self.assertEqual(len(result["pending_results"]),1)
        self.assertEqual(result["conflicts"],[])
        self.assertEqual(original[0]["status"],"scheduled")
    def test_archive_only_matches_are_reported(self):
        original=[dict(date="2026-11-24",home="Ajax",away="Roma",hg=None,ag=None,status="scheduled")]
        result=audit(original,[])
        self.assertEqual(len(result["not_in_source"]),1)
        self.assertEqual(result["source_count"],0)
    def test_unrealistic_score_is_rejected(self):
        rows=[]
        for i in range(1,19):
            rows.append(f"<p>Tuesday {i} November 2026</p><p>Club A 31-0 Club B</p><p>Club C vs Club D</p>")
        with self.assertRaises(ValueError):
            extract("<article>"+"".join(rows)+"</article>","UCL")
    def test_duplicate_archive_is_rejected(self):
        game=dict(date="2026-11-24",home="Ajax",away="Roma",hg=None,ag=None,status="scheduled")
        with self.assertRaisesRegex(ValueError,"duplicate archive"):
            audit([game,dict(game)],[])
    def test_duplicate_source_is_rejected(self):
        game=dict(date="2026-11-24",home="Ajax",away="Roma",hg=2,ag=1,status="finished")
        with self.assertRaisesRegex(ValueError,"duplicate source"):
            audit([],[game,dict(game)])
    def test_malformed_calendar_date_does_not_crash_parser(self):
        rows=["<p>Tuesday 31 February 2026</p><p>Wrong 1-0 Date</p>"]
        for i in range(1,19):
            rows.append(f"<p>Tuesday {i} November 2026</p><p>Club A 1-0 Club B</p><p>Club C vs Club D</p>")
        self.assertEqual(len(extract("<article>"+"".join(rows)+"</article>","UCL")),36)
    def test_large_score_cannot_be_truncated(self):
        rows=[]
        for i in range(1,19):
            rows.append(f"<p>Tuesday {i} November 2026</p><p>Club A 100-0 Club B</p><p>Club C vs Club D</p>")
        with self.assertRaises(ValueError):
            extract("<article>"+"".join(rows)+"</article>","UCL")
    def test_exact_match(self):
        original=[dict(date="2026-11-03",home="Bayern Munich",away="Roma",hg=2,ag=1,status="finished")]
        source=[dict(date="2026-11-03",home="Bayern München",away="Roma",hg=2,ag=1,status="finished")]
        self.assertEqual(audit(original,source)["verified"],1)
if __name__=="__main__":unittest.main()
