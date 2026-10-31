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
    def test_league_order(self):
        expected_order = ["cfb", "nfl", "nhl", "nba", "cbb", "mlb"]
        actual_order = [lg["key"] for lg in sportstui.LEAGUES]
        self.assertEqual(actual_order, expected_order)

    def test_glyph_sets(self):
        for name in ("nerd", "unicode", "emoji", "ascii"):
            self.assertIn(name, sportstui.GLYPHS)
            g = sportstui.GLYPHS[name]
            for key in ("live", "final", "pregame", "star", "upset", "red_zone", "fresh"):
                self.assertIn(key, g)
        # Check emoji specific values
        em = sportstui.GLYPHS["emoji"]
        self.assertEqual(em["live"], "🔴")
        self.assertEqual(em["final"], "🏁")
        self.assertEqual(em["star"], "⭐")
        self.assertEqual(em["red_zone"], "🔥")

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

    def test_wcag_luminance(self):
        self.assertAlmostEqual(sportstui.wcag_luminance("#ffffff"), 1.0, places=3)
        self.assertAlmostEqual(sportstui.wcag_luminance("000000"), 0.0, places=3)
        # Bright maize/yellow should have high brightness (>0.5)
        self.assertGreater(sportstui.hex_brightness("FFCB05"), 0.5)
        # Dark green should have low brightness (<0.5)
        self.assertLess(sportstui.hex_brightness("18453B"), 0.5)

    def test_evaluate_upset(self):
        # Ranked #3 losing to unranked in Final -> confirmed upset
        away = {"abbr": "MSU", "rank": None, "score_int": 28}
        home = {"abbr": "OSU", "rank": 3, "score_int": 24}
        res_final = sportstui.evaluate_upset(away, home, "post")
        self.assertIsNotNone(res_final)
        self.assertTrue(res_final["confirmed"])
        self.assertEqual(res_final["underdog"]["abbr"], "MSU")

        # Live Q2 ranked #5 trailing unranked -> upset watch (confirmed=False)
        res_live = sportstui.evaluate_upset(away, home, "in")
        self.assertIsNotNone(res_live)
        self.assertFalse(res_live["confirmed"])

        # Pro unranked upset via spread >= 7.5
        away_pro = {"abbr": "DET", "rank": None, "score_int": 110}
        home_pro = {"abbr": "BOS", "rank": None, "score_int": 102}
        res_pro = sportstui.evaluate_upset(away_pro, home_pro, "post", odds={"details": "BOS -8.5"})
        self.assertIsNotNone(res_pro)
        self.assertTrue(res_pro["confirmed"])

    def test_parse_rankings_coaches_poll(self):
        from unittest.mock import patch

        mock_data = {
            "latestWeek": {"number": 10},
            "rankings": [
                {
                    "name": "AP Top 25",
                    "type": "ap",
                    "ranks": [
                        {
                            "current": 1,
                            "previous": 2,
                            "points": 1500.0,
                            "recordSummary": "8-0",
                            "trend": "+1",
                            "team": {
                                "location": "Oregon",
                                "name": "Ducks",
                                "abbreviation": "ORE",
                                "color": "154733",
                            },
                        }
                    ],
                },
                {
                    "name": "AFCA Coaches Poll",
                    "type": "usa",
                    "ranks": [
                        {
                            "current": 1,
                            "previous": 1,
                            "points": 1450.0,
                            "recordSummary": "8-0",
                            "trend": "-",
                            "team": {
                                "location": "Oregon",
                                "name": "Ducks",
                                "abbreviation": "ORE",
                                "color": "154733",
                            },
                        }
                    ],
                },
            ],
        }
        with patch.object(sportstui, "fetch_json", return_value=mock_data):
            polls = sportstui.parse_rankings(sportstui.BY_KEY["cfb"])
        self.assertEqual(len(polls), 2)
        self.assertEqual(polls[0]["name"], "AP Top 25")
        self.assertEqual(polls[1]["name"], "AFCA Coaches Poll")
        self.assertEqual(polls[0]["ranks"][0]["team"], "Oregon")

    def test_parse_standings_dedup(self):
        from unittest.mock import patch

        # Simulate ESPN CFB standings with duplicate stat names across split categories
        mock_data = {
            "children": [
                {
                    "name": "Big Ten Conference",
                    "standings": {
                        "entries": [
                            {
                                "team": {
                                    "shortDisplayName": "Indiana",
                                    "abbreviation": "IU",
                                    "color": "990000",
                                },
                                "stats": [
                                    {"name": "wins", "displayValue": "8", "value": 8.0},
                                    {"name": "losses", "displayValue": "0", "value": 0.0},
                                    {"name": "overall", "displayValue": "8-0"},
                                    {"name": "vs. Conf.", "displayValue": "5-0"},
                                    {"name": "streak", "displayValue": "W8"},
                                    # Duplicate later split stats that previously overwrote overall wins
                                    {"name": "wins", "type": "vsusarankedteams_wins", "displayValue": "1", "value": 1.0},
                                    {"name": "streak", "type": "vsusarankedteams_streak", "displayValue": "W1"},
                                ],
                            }
                        ]
                    },
                }
            ]
        }
        with patch.object(sportstui, "fetch_json", return_value=mock_data):
            groups = sportstui.parse_standings(sportstui.BY_KEY["cfb"])
        self.assertEqual(len(groups), 1)
        st = groups[0]["rows"][0]["stats"]
        self.assertEqual(st["vs. Conf."], "5-0")
        self.assertEqual(st["overall"], "8-0")
        self.assertEqual(st["wins"], "8")
        self.assertEqual(st["streak"], "W8")

    def test_parse_detail_football_scoring_plays(self):
        from unittest.mock import patch

        mock_summary = {
            "header": {
                "competitions": [
                    {
                        "competitors": [
                            {
                                "homeAway": "away",
                                "linescores": [{"displayValue": "7"}, {"displayValue": "7"}, {"displayValue": "3"}, {"displayValue": "7"}],
                            },
                            {
                                "homeAway": "home",
                                "linescores": [{"displayValue": "7"}, {"displayValue": "3"}, {"displayValue": "0"}, {"displayValue": "7"}],
                            },
                        ]
                    }
                ]
            },
            "scoringPlays": [
                {
                    "period": {"number": 1},
                    "clock": {"displayValue": "8:42"},
                    "team": {"abbreviation": "MSU"},
                    "scoringType": {"name": "touchdown"},
                    "text": "Nate Carter 5 yd run (Jonathan Kim kick)",
                    "awayScore": 7,
                    "homeScore": 0,
                }
            ],
            "winprobability": [{"homeWinPercentage": 0.45}, {"homeWinPercentage": 0.20}],
        }
        with patch.object(sportstui, "fetch_json", return_value=mock_summary):
            det = sportstui.parse_detail(sportstui.BY_KEY["cfb"], "401628540")
        self.assertEqual(len(det["plays"]), 1)
        self.assertEqual(det["plays"][0]["team"], "MSU")
        self.assertEqual(det["plays"][0]["away_score"], 7)
        self.assertEqual(det["linescores"]["away"], ["7", "7", "3", "7"])
        self.assertEqual(det["wp_series"], [0.45, 0.20])


if __name__ == "__main__":
    unittest.main()
