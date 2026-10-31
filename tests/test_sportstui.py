#!/usr/bin/env python3
"""Tests for sportstui."""

import datetime as dt
import sys
import unittest
from pathlib import Path

# Add parent directory to path so we can import sportstui
REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

import importlib.machinery

loader = importlib.machinery.SourceFileLoader("sportstui", str(REPO_DIR / "sportstui.py"))
sportstui = loader.load_module()


class TestSportstui(unittest.TestCase):
    def test_aliases(self):
        self.assertEqual(sportstui.ALIASES.get("cfbtui"), "cfb")
        self.assertEqual(sportstui.ALIASES.get("cbbtui"), "cbb")
        self.assertEqual(sportstui.ALIASES.get("ncaabtui"), "cbb")
        self.assertEqual(sportstui.ALIASES.get("nbatui"), "nba")
        self.assertEqual(sportstui.ALIASES.get("nhltui"), "nhl")
        self.assertEqual(sportstui.ALIASES.get("mlbtui"), "mlb")
        self.assertEqual(sportstui.ALIASES.get("nfltui"), "nfl")

    def test_color_conversions(self):
        # Test basic hex colors
        self.assertEqual(sportstui.hex_rgb("#ffffff"), (255, 255, 255))
        self.assertEqual(sportstui.hex_rgb("000000"), (0, 0, 0))
        self.assertEqual(sportstui.hex_rgb("18453B"), (24, 69, 59))  # MSU Green

        # Xterm palette mapping
        code = sportstui.hex_to_xterm("18453B")
        self.assertIsInstance(code, int)
        self.assertTrue(16 <= code <= 255)

        # Basic fallback
        basic = sportstui.hex_to_basic("18453B")
        self.assertIsInstance(basic, int)

    def test_spread_text(self):
        # Empty odds
        self.assertEqual(sportstui.spread_text(None), "")
        self.assertEqual(sportstui.spread_text({}), "")

        # Odds with explicit details
        self.assertEqual(sportstui.spread_text({"details": "DET -3.5"}), "DET -3.5")

        # Away favorite
        away_fav = {
            "spread": "-7.5",
            "awayTeamOdds": {"favorite": True},
        }
        self.assertEqual(sportstui.spread_text(away_fav), "AWAY -7.5")

        # Home favorite
        home_fav = {
            "spread": "-10.0",
            "homeTeamOdds": {"favorite": True},
        }
        self.assertEqual(sportstui.spread_text(home_fav), "HOME -10")

    def test_parse_side(self):
        comp = {
            "team": {
                "abbreviation": "MSU",
                "shortDisplayName": "Spartans",
                "displayName": "Michigan State Spartans",
                "color": "18453B",
            },
            "records": [{"type": "total", "summary": "7-1"}],
            "curatedRank": {"current": 12},
            "score": "24",
            "winner": True,
        }
        side = sportstui.parse_side(comp)
        self.assertEqual(side["abbr"], "MSU")
        self.assertEqual(side["name"], "Spartans")
        self.assertEqual(side["record"], "7-1")
        self.assertEqual(side["rank"], 12)
        self.assertEqual(side["score"], "24")
        self.assertTrue(side["winner"])
        self.assertEqual(side["color"], "18453B")

    def test_parse_game(self):
        lg = sportstui.BY_KEY["cfb"]
        ev = {
            "id": "401628540",
            "date": "2026-10-31T19:30:00Z",
            "week": {"number": 9},
            "status": {
                "type": {
                    "state": "post",
                    "detail": "Final",
                    "shortDetail": "Final",
                },
                "period": 4,
            },
            "competitions": [
                {
                    "competitors": [
                        {
                            "homeAway": "home",
                            "team": {"abbreviation": "MICH", "shortDisplayName": "Wolverines"},
                            "records": [{"summary": "5-3"}],
                            "score": "17",
                        },
                        {
                            "homeAway": "away",
                            "team": {"abbreviation": "MSU", "shortDisplayName": "Spartans"},
                            "records": [{"summary": "6-2"}],
                            "score": "24",
                            "winner": True,
                        },
                    ],
                    "odds": [{"details": "MICH -3.5"}],
                    "venue": {"fullName": "Michigan Stadium"},
                }
            ],
        }
        game = sportstui.parse_game(ev, lg)
        self.assertIsNotNone(game)
        self.assertEqual(game["id"], "401628540")
        self.assertEqual(game["league"], "cfb")
        self.assertEqual(game["state"], "post")
        self.assertEqual(game["week"], 9)
        self.assertEqual(game["away"]["abbr"], "MSU")
        self.assertEqual(game["home"]["abbr"], "MICH")
        self.assertEqual(game["away"]["score"], "24")
        self.assertEqual(game["home"]["score"], "17")
        self.assertEqual(game["venue"], "Michigan Stadium")

    def test_scoreboard_url(self):
        lg = sportstui.BY_KEY["cfb"]
        d = dt.date(2026, 10, 31)
        url_date = sportstui.scoreboard_url(lg, d)
        self.assertIn("dates=20261031", url_date)

        url_week = sportstui.scoreboard_url(lg, d, week=9)
        self.assertIn("week=9", url_week)


if __name__ == "__main__":
    unittest.main()
