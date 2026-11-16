"""Offline unit tests for UEFA 2026/27 association match points."""
import pathlib,sys,unittest
from decimal import Decimal
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"scripts"))
from uefa_points import match_points,association_coefficient

class AssociationPointsTests(unittest.TestCase):
    def game(self,stage,hg,ag,status="finished"):
        return {"competition":"UCL","stage":stage,"hg":hg,"ag":ag,"status":status}
    def test_league_win(self):
        self.assertEqual(match_points(self.game("LEAGUE",2,0)),(Decimal("2"),Decimal("0")))
    def test_league_draw(self):
        self.assertEqual(match_points(self.game("LEAGUE",1,1)),(Decimal("1"),Decimal("1")))
    def test_qualifying_win(self):
        self.assertEqual(match_points(self.game("QUALIFYING",1,0)),(Decimal("1"),Decimal("0")))
    def test_qualifying_draw(self):
        self.assertEqual(match_points(self.game("Q2",0,0)),(Decimal("0.5"),Decimal("0.5")))
    def test_scheduled_not_scored(self):
        self.assertIsNone(match_points(self.game("LEAGUE",None,None,"scheduled")))
    def test_unknown_stage_rejected(self):
        with self.assertRaises(ValueError):match_points(self.game("UNKNOWN",1,0))
    def test_truncation_not_rounding(self):
        self.assertEqual(association_coefficient([2,2,1],3),Decimal("1.666"))
    def test_divisor_required(self):
        with self.assertRaises(ValueError):association_coefficient([2],0)
if __name__=="__main__":unittest.main()
