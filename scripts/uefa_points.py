"""UEFA 2026/27 association match points (partial calculation only).

Annex D.3: qualifying/play-offs 1/0.5; league and knockouts 2/1.
No invented country memberships, bonuses, divisors or verified results.
"""
from decimal import Decimal, ROUND_DOWN

def match_points(game):
    if game.get("status") != "finished":
        return None
    if game.get("competition") not in {"UCL","UEL","UECL"}:
        raise ValueError("unknown competition")
    home,away=game.get("hg"),game.get("ag")
    if type(home) is not int or type(away) is not int or min(home,away)<0:
        raise ValueError("invalid final score")
    stage=game.get("stage")
    if stage in {"QUALIFYING","QUALIFICATION","Q1","Q2","Q3","PLAYOFF","PLAY-OFF","QUALIFYING_PLAYOFF"}:
        win,draw=Decimal("1"),Decimal("0.5")
    elif stage in {"LEAGUE","ROUND_OF_16","R16","QUARTER_FINAL","SEMI_FINAL","FINAL","KNOCKOUT","KNOCKOUT_PLAYOFF"}:
        win,draw=Decimal("2"),Decimal("1")
    else:
        raise ValueError("unknown stage; cannot award UEFA points")
    if home>away: return win,Decimal("0")
    if away>home: return Decimal("0"),win
    return draw,draw

def association_coefficient(points, entrants):
    if not isinstance(entrants,int) or isinstance(entrants,bool) or entrants<=0:
        raise ValueError("positive official entrant count required")
    total=sum((Decimal(str(p)) for p in points),Decimal("0"))
    return (total/Decimal(entrants)).quantize(Decimal("0.001"),rounding=ROUND_DOWN)
