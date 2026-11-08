#!/usr/bin/env python3
"""Tests for sportstui."""

import datetime as dt
import sys
import time
import unittest
from pathlib import Path

# Add parent directory to path so we can import sportstui
REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

import importlib.machinery

loader = importlib.machinery.SourceFileLoader("sportstui", str(REPO_DIR / "sportstui.py"))
sportstui = loader.load_module()


class TestSportstui(unittest.TestCase):
    def test_league_groups_and_filtering(self):
        # All 8 sports leagues have configured group/conference/weight pickers
        for lg in ("cfb", "nfl", "nhl", "nba", "cbb", "mlb", "ufc", "box"):
            self.assertIn(lg, sportstui.LEAGUE_GROUPS)
            self.assertGreater(len(sportstui.LEAGUE_GROUPS[lg]), 0)

        # Pro leagues have team mappings
        for lg in ("nfl", "nhl", "nba", "mlb"):
            self.assertIn(lg, sportstui.PRO_TEAM_GROUPS)
            self.assertIn("DET", sportstui.PRO_TEAM_GROUPS[lg])

        # Test scoreboard URL includes master groups for CFB and CBB
        cfb_url = sportstui.scoreboard_url(sportstui.BY_KEY["cfb"], dt.date(2026, 10, 31))
        self.assertIn("groups=80", cfb_url)
        cbb_url = sportstui.scoreboard_url(sportstui.BY_KEY["cbb"], dt.date(2026, 10, 31))
        self.assertIn("groups=50", cbb_url)

        # Test App group filtering in memory
        opts = sportstui.parse_args([])
        app = sportstui.App(None, opts)
        app.league_key = "cfb"
        group_opts = app.get_group_options()
        self.assertEqual(group_opts[0], ("all", "All conferences"))
        self.assertEqual(group_opts[1], ("5", "Big Ten"))

        games = [
            {"id": "1", "state": "post", "start": None, "away": {"abbr": "MSU", "conf_id": "5", "rank": None}, "home": {"abbr": "MICH", "conf_id": "5", "rank": None}},
            {"id": "2", "state": "post", "start": None, "away": {"abbr": "BAMA", "conf_id": "8", "rank": None}, "home": {"abbr": "LSU", "conf_id": "8", "rank": None}},
        ]
        app.group_filter = "5"
        filtered = app.visible(games)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["id"], "1")

        # Test NFL pro division filtering
        nfl_app = sportstui.App(None, opts)
        nfl_app.league_key = "nfl"
        nfl_opts = nfl_app.get_group_options()
        self.assertEqual(nfl_opts[0], ("all", "All divisions / conferences"))
        nfl_games = [
            {"id": "10", "state": "post", "start": None, "away": {"abbr": "DET", "rank": None}, "home": {"abbr": "GB", "rank": None}},
            {"id": "20", "state": "post", "start": None, "away": {"abbr": "KC", "rank": None}, "home": {"abbr": "DEN", "rank": None}},
        ]
        nfl_app.group_filter = "nfc_north"
        nfl_filtered = nfl_app.visible(nfl_games)
        self.assertEqual(len(nfl_filtered), 1)
        self.assertEqual(nfl_filtered[0]["id"], "10")

    def test_league_order(self):
        expected_order = ["all", "cfb", "nfl", "nhl", "nba", "cbb", "mlb", "ufc", "box"]
        actual_order = [lg["key"] for lg in sportstui.LEAGUES]
        self.assertEqual(actual_order, expected_order)

        # 1 is ALL sports together, rest shift to 2: CFB, 3: NFL, 4: NHL, 5: NBA, 6: CBB, 7: MLB, 8: UFC, 9: BOX
        self.assertEqual(sportstui.LEAGUES[0]["key"], "all")
        self.assertEqual([lg["key"] for lg in sportstui.SPORT_LEAGUES], ["cfb", "nfl", "nhl", "nba", "cbb", "mlb", "ufc", "box"])

    def test_glyph_sets(self):
        for name in ("nerd", "unicode", "emoji", "ascii"):
            self.assertIn(name, sportstui.GLYPHS)
            g = sportstui.GLYPHS[name]
            for key in ("live", "final", "pregame", "star", "upset", "red_zone", "rivalry", "fresh"):
                self.assertIn(key, g)
        # Check emoji specific values
        em = sportstui.GLYPHS["emoji"]
        self.assertEqual(em["live"], "🔴")
        self.assertEqual(em["final"], "🏁")
        self.assertEqual(em["star"], "⭐")
        self.assertEqual(em["red_zone"], "🔥")
        self.assertEqual(em["rivalry"], "🔥")

    def test_aliases(self):
        self.assertEqual(sportstui.ALIASES.get("cfbtui"), "cfb")
        self.assertEqual(sportstui.ALIASES.get("cbbtui"), "cbb")
        self.assertEqual(sportstui.ALIASES.get("ncaabtui"), "cbb")
        self.assertEqual(sportstui.ALIASES.get("nbatui"), "nba")
        self.assertEqual(sportstui.ALIASES.get("nhltui"), "nhl")
        self.assertEqual(sportstui.ALIASES.get("mlbtui"), "mlb")
        self.assertEqual(sportstui.ALIASES.get("nfltui"), "nfl")
        self.assertEqual(sportstui.ALIASES.get("ufctui"), "ufc")
        self.assertEqual(sportstui.ALIASES.get("mmalui"), "ufc")
        self.assertEqual(sportstui.ALIASES.get("mmatui"), "ufc")
        self.assertEqual(sportstui.ALIASES.get("boxtui"), "box")

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

    def test_width_utilities(self):
        # ASCII characters return width 1
        for ch in ("A", "z", "0", "9", " ", "#", "-", "&"):
            self.assertEqual(sportstui.char_width(ch), 1)
            self.assertEqual(sportstui.str_width(ch), 1)
        self.assertEqual(sportstui.str_width("Hello World"), 11)

        # Single-width unicode characters return width 1
        for ch in ("▸", "★", "·", "│", "─", "┏", "┓"):
            self.assertEqual(sportstui.char_width(ch), 1, f"Expected width 1 for single-width unicode {ch}")
            self.assertEqual(sportstui.str_width(ch), 1)

        # Double-width emojis return width 2
        for em in ("🔴", "👉", "👀", "⭐", "🔥", "⚡", "✅", "🏈"):
            self.assertEqual(sportstui.char_width(em), 2, f"Expected width 2 for {em}")
            self.assertEqual(sportstui.str_width(em), 2, f"Expected width 2 for {em}")
        self.assertEqual(sportstui.str_width("🔴 Q1 10:00"), 11)
        self.assertEqual(sportstui.str_width("🔴 Q1 13:42"), 11)
        self.assertEqual(sportstui.str_width("👀 UPSET WATCH"), 14)

        # Combining characters
        combining = "\u0300"  # grave accent
        self.assertEqual(sportstui.char_width(combining), 0)

        # clip_to_width
        self.assertEqual(sportstui.clip_to_width("abc", 2), "ab")
        self.assertEqual(sportstui.clip_to_width("🔴abc", 2), "🔴")
        self.assertEqual(sportstui.clip_to_width("🔴abc", 3), "🔴a")
        # Should not cut double-width character in half
        self.assertEqual(sportstui.clip_to_width("a🔴", 2), "a")
        self.assertEqual(sportstui.clip_to_width("a🔴", 3), "a🔴")
        self.assertEqual(sportstui.clip_to_width("🔴 Q1 10:00", 1), "")
        self.assertEqual(sportstui.clip_to_width("🔴 Q1 10:00", 2), "🔴")
        self.assertEqual(sportstui.clip_to_width("🔴 Q1 10:00", 12), "🔴 Q1 10:00")

    def test_team_row_prefix_visual_width(self):
        cases = [
            ("", "", None),
            ("", "", 12),
            ("", "", 3),
            ("👉", "", None),
            ("👉", "", 12),
            ("", "⭐", None),
            ("", "⭐", 12),
            ("👉", "⭐", 12),
            ("▶", "★", 12),
            ("", "★", 12),
            (">", "*", 12),
        ]
        for lead, star, rank in cases:
            prefix = sportstui.team_row_prefix(lead, star, rank)
            w = sportstui.str_width(prefix)
            self.assertEqual(w, 8, f"Prefix {prefix!r} for ({lead!r}, {star!r}, {rank!r}) has width {w} != 8")
            self.assertTrue(prefix.endswith(" "), f"Prefix {prefix!r} must end with space before abbreviation")

    def test_team_cell_text_alignment(self):
        opts = sportstui.parse_args(["--glyphs", "emoji"])
        app = sportstui.App(None, opts)
        app.league_key = "cfb"
        app.favs.add("cfb:MICH")

        # 1. Unranked, no icon (BC)
        g_bc = {
            "state": "in",
            "situation": {},
            "home": {
                "id": "103",
                "abbr": "BC",
                "record": "4-3",
                "rank": None,
                "score": "0",
                "score_int": 0,
                "color": "8B0000",
            },
        }
        bc_row = app._team_cell_text(g_bc, g_bc["home"], False, 40)
        self.assertEqual(sportstui.str_width(bc_row), 40)
        bc_prefix = bc_row[:bc_row.find("BC")]
        self.assertEqual(sportstui.str_width(bc_prefix), 8, f"BC prefix width was {sportstui.str_width(bc_prefix)}, expected 8")
        self.assertEqual(bc_prefix, "        ")

        # 2. Unranked with emoji possession (👉 DUKE)
        g_duke = {
            "state": "in",
            "situation": {"possession": "150"},
            "home": {
                "id": "150",
                "abbr": "DUKE",
                "record": "5-2",
                "rank": None,
                "score": "0",
                "score_int": 0,
                "color": "00539B",
            },
        }
        duke_row = app._team_cell_text(g_duke, g_duke["home"], False, 40)
        self.assertEqual(sportstui.str_width(duke_row), 40)
        duke_prefix = duke_row[:duke_row.find("DUKE")]
        self.assertEqual(sportstui.str_width(duke_prefix), 8, f"DUKE prefix width was {sportstui.str_width(duke_prefix)}, expected 8")
        self.assertTrue(duke_prefix.startswith(" 👉"))

        # 3. Ranked with double-digit rank (#19 SMU)
        g_smu = {
            "state": "in",
            "situation": {},
            "away": {
                "id": "2567",
                "abbr": "SMU",
                "record": "6-1",
                "rank": 19,
                "score": "0",
                "score_int": 0,
                "color": "CC0000",
            },
        }
        smu_row = app._team_cell_text(g_smu, g_smu["away"], True, 40)
        self.assertEqual(sportstui.str_width(smu_row), 40)
        smu_prefix = smu_row[:smu_row.find("SMU")]
        self.assertEqual(sportstui.str_width(smu_prefix), 8, f"SMU prefix width was {sportstui.str_width(smu_prefix)}, expected 8")
        self.assertEqual(smu_prefix, "    #19 ")

        # 4. Ranked with single-digit rank (#6 IU)
        g_iu = {
            "state": "in",
            "situation": {},
            "home": {
                "id": "84",
                "abbr": "IU",
                "record": "7-0",
                "rank": 6,
                "score": "31",
                "score_int": 31,
                "color": "990000",
            },
        }
        iu_row = app._team_cell_text(g_iu, g_iu["home"], False, 40)
        self.assertEqual(sportstui.str_width(iu_row), 40)
        iu_prefix = iu_row[:iu_row.find("IU")]
        self.assertEqual(sportstui.str_width(iu_prefix), 8, f"IU prefix width was {sportstui.str_width(iu_prefix)}, expected 8")
        self.assertEqual(iu_prefix, "     #6 ")

        # 5. Favorite with star (⭐ MICH)
        g_mich = {
            "state": "in",
            "situation": {},
            "away": {
                "id": "130",
                "abbr": "MICH",
                "record": "5-2",
                "rank": None,
                "score": "17",
                "score_int": 17,
                "color": "00274C",
            },
        }
        mich_row = app._team_cell_text(g_mich, g_mich["away"], True, 40)
        self.assertEqual(sportstui.str_width(mich_row), 40)
        mich_prefix = mich_row[:mich_row.find("MICH")]
        self.assertEqual(sportstui.str_width(mich_prefix), 8, f"MICH prefix width was {sportstui.str_width(mich_prefix)}, expected 8")
        self.assertTrue("⭐" in mich_prefix)

    def test_draw_box_title_width(self):
        opts = sportstui.parse_args(["--glyphs", "emoji"])
        app = sportstui.App(None, opts)

        # Mock put to inspect top_bar width
        captured = []
        def mock_put(y, x, text, attr=0, width=None, reverse=False):
            captured.append(text)

        app.put = mock_put
        app.draw_box(0, 0, 5, 42, 0, title="👀 UPSET WATCH")

        top_bar = captured[0]
        # Top bar must have EXACT visual width 42 (does not push right border)
        self.assertEqual(sportstui.str_width(top_bar), 42, f"top_bar width: {sportstui.str_width(top_bar)}")
        self.assertTrue(top_bar.endswith("┓") or top_bar.endswith("╮") or top_bar.endswith("+") or top_bar.endswith("#"))

    def test_draw_card_status_line_clock_intact(self):
        opts = sportstui.parse_args(["--glyphs", "emoji"])
        app = sportstui.App(None, opts)

        # Case A: Live 🔴 Q1 10:00 (Card 1)
        game1 = {
            "id": "1",
            "league": "cfb",
            "state": "in",
            "period": 1,
            "clock": "10:00",
            "short": "Q1 10:00",
            "detail": "Q1 10:00",
            "broadcast": "",
            "odds": {},
            "away": {
                "id": "2567",
                "abbr": "SMU",
                "name": "Mustangs",
                "record": "6-1",
                "rank": 19,
                "score": "0",
                "score_int": 0,
                "color": "CC0000",
            },
            "home": {
                "id": "183",
                "abbr": "SYR",
                "name": "Orange",
                "record": "3-4",
                "rank": None,
                "score": "7",
                "score_int": 7,
                "color": "D44500",
            },
        }

        row3_card1 = []
        def mock_put_card1(y, x, text, attr=0, width=None, reverse=False):
            if y == 3:
                row3_card1.append((x, text))

        app.put = mock_put_card1
        app.draw_card(game1, 0, 0, 42, False)

        # Check that the clock text contains full "10:00" and never truncates to "10:0"
        clock_seg1 = [txt for _, txt in row3_card1 if "10:00" in txt]
        self.assertEqual(len(clock_seg1), 1)
        self.assertIn("🔴 Q1 10:00", clock_seg1[0])
        self.assertNotIn("10:0 ", clock_seg1[0])

        # Padding starts at x=13 (x_orig=1 + str_width(' 🔴 Q1 10:00')=12 -> 13)
        pad_x1 = [x for x, txt in row3_card1 if x > 1 and txt.startswith(" ")][0]
        self.assertEqual(pad_x1, 13, f"Pad segment x is {pad_x1}, expected 13")

        # Case B: Live 🔴 Q1 13:42 with situation "4th & 4 at DUKE 31" (Card 2)
        game2 = {
            "id": "2",
            "league": "cfb",
            "state": "in",
            "period": 1,
            "clock": "13:42",
            "short": "Q1 13:42",
            "detail": "Q1 13:42",
            "broadcast": "",
            "odds": {},
            "situation": {
                "possession": "150",
                "down_dist": "4th & 4 at DUKE 31",
            },
            "away": {
                "id": "103",
                "abbr": "BC",
                "name": "Eagles",
                "record": "4-3",
                "rank": None,
                "score": "0",
                "score_int": 0,
                "color": "8B0000",
            },
            "home": {
                "id": "150",
                "abbr": "DUKE",
                "name": "Blue Devils",
                "record": "5-2",
                "rank": None,
                "score": "0",
                "score_int": 0,
                "color": "00539B",
            },
        }

        row3_card2 = []
        def mock_put_card2(y, x, text, attr=0, width=None, reverse=False):
            if y == 3:
                row3_card2.append((x, text))

        app.put = mock_put_card2
        app.draw_card(game2, 0, 0, 42, False)

        # Check that the clock text contains full "13:42" and never truncates to "13:4"
        clock_seg2 = [txt for _, txt in row3_card2 if "13:42" in txt]
        self.assertEqual(len(clock_seg2), 1)
        self.assertIn("🔴 Q1 13:42", clock_seg2[0])
        self.assertNotIn("13:4 ", clock_seg2[0])

        # Padding starts at x=13
        pad_x2 = [x for x, txt in row3_card2 if x > 1 and txt.startswith(" ")][0]
        self.assertEqual(pad_x2, 13, f"Pad segment x is {pad_x2}, expected 13")

        # Verify extra text was also printed
        extra_seg = [txt for _, txt in row3_card2 if "4th & 4 at DUKE 31" in txt]
        self.assertEqual(len(extra_seg), 1)

    def test_grid_cols_widescreen_and_half_page(self):
        """Test column calculation: 6 cols widescreen (W >= 200), 5 cols (170-199), 2 cols half-page on CM34."""
        opts = sportstui.parse_args([])
        app = sportstui.App(None, opts)

        # Widescreen on CM34 Flip (Hyprland fullscreen foot ~200-206 cols)
        self.assertEqual(app.grid_cols(206), 6)
        self.assertEqual(app.grid_cols(200), 6)

        # Widescreen / Wide terminal
        self.assertEqual(app.grid_cols(199), 5)
        self.assertEqual(app.grid_cols(180), 5)
        self.assertEqual(app.grid_cols(170), 5)

        # Intermediate widths
        self.assertEqual(app.grid_cols(169), 4)
        self.assertEqual(app.grid_cols(144), 4)
        self.assertEqual(app.grid_cols(136), 4)
        self.assertEqual(app.grid_cols(135), 3)
        self.assertEqual(app.grid_cols(132), 3)
        self.assertEqual(app.grid_cols(105), 3)

        # Half-page on CM34 Flip (Hyprland 50/50 split ~100-104 cols)
        self.assertEqual(app.grid_cols(104), 2)
        self.assertEqual(app.grid_cols(100), 2)
        self.assertEqual(app.grid_cols(70), 2)

        # Compact widths
        self.assertEqual(app.grid_cols(69), 1)
        self.assertEqual(app.grid_cols(36), 1)

    def test_grid_cols_forced_flag_and_config(self):
        """Test that --cols CLI flag and config override dynamic reflow."""
        opts = sportstui.parse_args(["--cols", "6"])
        self.assertEqual(opts.cols, 6)
        app = sportstui.App(None, opts)
        self.assertEqual(app.grid_cols(100), 6)
        self.assertEqual(app.grid_cols(80), 6)

        opts_c = sportstui.parse_args(["-c", "4"])
        self.assertEqual(opts_c.cols, 4)
        app_c = sportstui.App(None, opts_c)
        self.assertEqual(app_c.grid_cols(206), 4)

    def test_card_layout_fits_terminal(self):
        """Test card layout distributes width evenly with 1-char gutter and fits within terminal."""
        opts = sportstui.parse_args([])
        app = sportstui.App(None, opts)

        for w in (72, 80, 100, 104, 132, 144, 180, 206):
            cols = app.grid_cols(w)
            layout = app.card_layout(w, cols)
            self.assertEqual(len(layout), cols)
            self.assertEqual(layout[0][0], 1)  # Starts at x=1 (1-char left margin)

            for i in range(len(layout)):
                x_i, w_i = layout[i]
                self.assertGreaterEqual(w_i, 32, f"Card width {w_i} < 32 at terminal width {w}")
                if i > 0:
                    prev_x, prev_w = layout[i - 1]
                    self.assertEqual(x_i, prev_x + prev_w + 1, f"Gutter mismatch between cols {i-1} and {i} at width {w}")

            last_x, last_w = layout[-1]
            end_x = last_x + last_w
            self.assertLessEqual(end_x, w, f"Card layout overflows width {w}: ends at {end_x}")

    def test_all_sports_mode_and_league_shifting(self):
        """Test that 1 is ALL sports together, and leagues shift to 2-9."""
        # 1: ALL, 2: CFB, 3: NFL, 4: NHL, 5: NBA, 6: CBB, 7: MLB, 8: UFC, 9: BOX
        keys = [lg["key"] for lg in sportstui.LEAGUES]
        self.assertEqual(keys, ["all", "cfb", "nfl", "nhl", "nba", "cbb", "mlb", "ufc", "box"])

        names = [lg["name"] for lg in sportstui.LEAGUES]
        self.assertEqual(names, ["ALL", "CFB", "NFL", "NHL", "NBA", "CBB", "MLB", "UFC", "BOX"])

        opts = sportstui.parse_args([])
        app = sportstui.App(None, opts)
        app.switch_league("all")
        self.assertEqual(app.league_key, "all")
        self.assertEqual(app.board_key(), f"board:all:{app.date.isoformat()}")

        # Verify card title in ALL mode includes league badge
        game = {
            "id": "1",
            "league": "cfb",
            "state": "in",
            "period": 1,
            "clock": "12:00",
            "short": "Q1 12:00",
            "detail": "Q1 12:00",
            "status_name": "STATUS_IN_PROGRESS",
            "start": None,
            "situation": {},
            "odds": {},
            "upset": None,
            "away": {"id": "1", "abbr": "AW", "name": "Away", "score": "7", "score_int": 7, "color": "000000", "rank": None, "record": "1-0"},
            "home": {"id": "2", "abbr": "HM", "name": "Home", "score": "3", "score_int": 3, "color": "FFFFFF", "rank": None, "record": "0-1"},
        }
        drawn_titles = []
        def mock_draw_box(y, x, h, w, attr, title="", heavy=False):
            drawn_titles.append(title)

        app.put = lambda *args, **kwargs: None
        app.fill_line = lambda *args, **kwargs: None
        app.segment = lambda *args, **kwargs: None
        app.draw_box = mock_draw_box
        app.draw_card(game, 0, 0, 42, False)
        self.assertIn("CFB", drawn_titles[0])

    def test_timeouts_str_and_card_rendering(self):
        """Test timeouts dot generation across glyph sets and exact card alignment."""
        # 1. Test timeouts_str across glyph sets
        for g_name in ("nerd", "unicode", "emoji", "ascii"):
            g = sportstui.GLYPHS[g_name]
            self.assertEqual(sportstui.timeouts_str(g, None), "")
            self.assertEqual(sportstui.timeouts_str(g, "bad"), "")

            t3 = sportstui.timeouts_str(g, 3)
            t2 = sportstui.timeouts_str(g, 2)
            t1 = sportstui.timeouts_str(g, 1)
            t0 = sportstui.timeouts_str(g, 0)

            # Check counts
            self.assertEqual(t3.count(g["timeout"]), 3)
            self.assertEqual(t2.count(g["timeout"]), 2)
            self.assertEqual(t2.count(g["timeout_used"]), 1)
            self.assertEqual(t1.count(g["timeout"]), 1)
            self.assertEqual(t1.count(g["timeout_used"]), 2)
            self.assertEqual(t0.count(g["timeout_used"]), 3)

        # 2. Test row formatting in card with timeouts
        opts = sportstui.parse_args(["--glyphs", "unicode"])
        app = sportstui.App(None, opts)
        live_game = {
            "id": "1",
            "league": "cfb",
            "state": "in",
            "situation": {"away_timeouts": 2, "home_timeouts": 0},
            "away": {"id": "1", "abbr": "ND", "record": "6-1", "rank": 5, "score": "20", "score_int": 20, "color": "0C2340"},
            "home": {"id": "2", "abbr": "NAVY", "record": "2-5", "rank": None, "score": "13", "score_int": 13, "color": "00205B"},
        }
        away_row = app._team_cell_text(live_game, live_game["away"], True, 40)
        self.assertEqual(sportstui.str_width(away_row), 40)
        self.assertTrue(away_row.endswith("●●○  20"), f"Expected row to end with '●●○  20', got {away_row!r}")

        home_row = app._team_cell_text(live_game, live_game["home"], False, 40)
        self.assertEqual(sportstui.str_width(home_row), 40)
        self.assertTrue(home_row.endswith("○○○  13"), f"Expected row to end with '○○○  13', got {home_row!r}")

    def test_possession_arrow_glyphs_and_fallback(self):
        """Test possession arrow glyphs across sets and fallback parsing."""
        self.assertEqual(sportstui.GLYPHS["nerd"]["poss"], "\uf0da")
        self.assertEqual(sportstui.GLYPHS["unicode"]["poss"], "▶")
        self.assertEqual(sportstui.GLYPHS["emoji"]["poss"], "👉")
        self.assertEqual(sportstui.GLYPHS["ascii"]["poss"], ">")

        # Situation fallback when possession is None but active down has lastPlay team
        raw_sit = {
            "down": 1,
            "distance": 10,
            "possession": None,
            "lastPlay": {"team": {"id": "275"}},
        }
        sit = sportstui.parse_situation(raw_sit)
        self.assertEqual(sit["possession"], "275")

        # Test possession arrow placement in card team cell text
        for g_name, exp_arrow in [("unicode", "▶"), ("nerd", "\uf0da"), ("emoji", "👉"), ("ascii", ">")]:
            opts = sportstui.parse_args(["--glyphs", g_name])
            app = sportstui.App(None, opts)
            game = {
                "id": "1",
                "league": "cfb",
                "state": "in",
                "situation": {"possession": "103"},
                "away": {"id": "103", "abbr": "BC", "record": "4-3", "rank": None, "score": "7", "score_int": 7, "color": "8B0000"},
                "home": {"id": "150", "abbr": "DUKE", "record": "5-2", "rank": None, "score": "0", "score_int": 0, "color": "00539B"},
            }
            bc_row = app._team_cell_text(game, game["away"], True, 40)
            duke_row = app._team_cell_text(game, game["home"], False, 40)
            self.assertEqual(sportstui.str_width(bc_row), 40)
            self.assertEqual(sportstui.str_width(duke_row), 40)
            self.assertIn(exp_arrow, bc_row)
            self.assertNotIn(exp_arrow, duke_row)

    def test_ufc_and_box_league_definitions(self):
        """Verify UFC and Boxing league definitions and combat period labels."""
        ufc = sportstui.BY_KEY["ufc"]
        self.assertTrue(ufc.get("combat"))
        self.assertTrue(ufc.get("poll"))
        self.assertEqual(ufc.get("period_prefix"), "R")
        self.assertEqual(ufc.get("reg_periods"), 3)

        box = sportstui.BY_KEY["box"]
        self.assertTrue(box.get("combat"))
        self.assertFalse(box.get("poll"))
        self.assertEqual(box.get("period_prefix"), "R")
        self.assertEqual(box.get("reg_periods"), 12)

        self.assertEqual(sportstui.period_label("ufc", 2), "R2")
        self.assertEqual(sportstui.period_label("box", 10), "R10")

    def test_parse_ufc_bouts(self):
        """Verify unpacking of UFC event card into individual bouts."""
        mock_events = [{
            "id": "60001",
            "name": "UFC 300: Pereira vs. Hill",
            "date": "2026-11-07T22:00Z",
            "venues": [{"fullName": "T-Mobile Arena"}],
            "competitions": [
                {
                    "id": "40101",
                    "type": {"abbreviation": "Light Heavyweight"},
                    "types": [{"text": "UFC Light Heavyweight Title"}],
                    "status": {
                        "period": 1,
                        "displayClock": "3:14",
                        "type": {"state": "post", "shortDetail": "Final (KO/TKO)"}
                    },
                    "competitors": [
                        {
                            "order": 1,
                            "winner": True,
                            "athlete": {"displayName": "Alex Pereira", "shortName": "A. Pereira", "flag": {"href": "https://flag.png"}},
                            "records": [{"summary": "10-2-0"}]
                        },
                        {
                            "order": 2,
                            "winner": False,
                            "athlete": {"displayName": "Jamahal Hill", "shortName": "J. Hill", "flag": {"href": "https://flag2.png"}},
                            "records": [{"summary": "12-2-0"}]
                        }
                    ]
                }
            ]
        }]
        bouts = sportstui._unpack_ufc_events(mock_events)
        self.assertEqual(len(bouts), 1)
        b = bouts[0]
        self.assertEqual(b["league"], "ufc")
        self.assertTrue(b["is_combat"])
        self.assertEqual(b["weight_class"], "Light Heavyweight")
        self.assertTrue(b["is_title"])
        self.assertEqual(b["home"]["name"], "A. Pereira")
        self.assertEqual(b["home"]["color"], "CC0000")  # Red corner
        self.assertTrue(b["home"]["winner"])
        self.assertEqual(b["home"]["score"], "✔")
        self.assertEqual(b["away"]["name"], "J. Hill")
        self.assertEqual(b["away"]["color"], "0047AB")  # Blue corner
        self.assertFalse(b["away"]["winner"])

    def test_parse_ufc_rankings(self):
        """Verify parsing of UFC P4P and divisional rankings."""
        mock_rankings_payload = {
            "rankings": [
                {
                    "name": "Men's Pound for Pound Rankings",
                    "ranks": [
                        {
                            "current": 1,
                            "hasAccolade": True,
                            "defenses": 3,
                            "recordSummary": "17-1-0",
                            "athlete": {"displayName": "Ilia Topuria", "shortname": "Topuria", "color": "#FFCC00"}
                        },
                        {
                            "current": 2,
                            "hasAccolade": False,
                            "defenses": 0,
                            "recordSummary": "31-3-0",
                            "athlete": {"displayName": "Max Holloway", "shortname": "Holloway", "color": "#000000"}
                        }
                    ]
                }
            ]
        }
        orig_fetch = sportstui.fetch_json
        try:
            sportstui.fetch_json = lambda url: mock_rankings_payload
            polls = sportstui.parse_rankings(sportstui.BY_KEY["ufc"])
            self.assertEqual(len(polls), 1)
            poll = polls[0]
            self.assertEqual(poll["name"], "Men's Pound for Pound Rankings")
            self.assertEqual(len(poll["ranks"]), 2)
            self.assertEqual(poll["ranks"][0]["team"], "Ilia Topuria (C)")
            self.assertEqual(poll["ranks"][0]["rank"], 1)
            self.assertEqual(poll["ranks"][0]["first"], 1)
            self.assertEqual(poll["ranks"][1]["team"], "Max Holloway")
            self.assertEqual(poll["ranks"][1]["rank"], 2)
        finally:
            sportstui.fetch_json = orig_fetch

    def test_combat_card_rendering_and_alignment(self):
        """Test combat sports card cell text width and card title headers."""
        opts = sportstui.parse_args(["--league", "ufc"])
        app = sportstui.App(None, opts)
        game = {
            "id": "600:400",
            "league": "ufc",
            "is_combat": True,
            "weight_class": "Featherweight",
            "is_title": True,
            "state": "post",
            "method": "KO/TKO",
            "period": 3,
            "clock": "1:34",
            "short": "Final (KO/TKO)",
            "detail": "Final (KO/TKO)",
            "start": None,
            "situation": {},
            "odds": {},
            "upset": None,
            "away": {"id": "1", "abbr": "Holloway", "name": "Max Holloway", "full": "Max Holloway", "color": "0047AB", "rank": 2, "record": "28-9-0", "winner": False, "score": "-", "score_int": 0},
            "home": {"id": "2", "abbr": "Topuria", "name": "Ilia Topuria", "full": "Ilia Topuria", "color": "CC0000", "rank": 1, "record": "17-1-0", "winner": True, "score": "✔", "score_int": 1},
        }

        # Card cell text maintains exact width
        row_away = app._team_cell_text(game, game["away"], True, 36)
        row_home = app._team_cell_text(game, game["home"], False, 36)
        self.assertEqual(sportstui.str_width(row_away), 36)
        self.assertEqual(sportstui.str_width(row_home), 36)
        self.assertIn("WIN", row_home)

        # Card status text shows finish method and round
        st_txt = app.status_text(game)
        self.assertIn("KO/TKO", st_txt)
        self.assertIn("R3 1:34", st_txt)

        # Test draw_box captures weight class and title badge
        captured_titles = []
        def mock_box(y, x, h, w, attr, title="", heavy=False):
            captured_titles.append(title)
        app.put = lambda *args, **kwargs: None
        app.fill_line = lambda *args, **kwargs: None
        app.segment = lambda *args, **kwargs: None
        app.draw_box = mock_box
        app.draw_card(game, 0, 0, 38, False)
        self.assertTrue(any("FEATHERWEIGHT" in t and "🏆 TITLE" in t for t in captured_titles))

    def test_ordinal_and_shorten_group(self):
        # Ordinal numbers
        self.assertEqual(sportstui.ordinal(1), "1st")
        self.assertEqual(sportstui.ordinal(2), "2nd")
        self.assertEqual(sportstui.ordinal(3), "3rd")
        self.assertEqual(sportstui.ordinal(4), "4th")
        self.assertEqual(sportstui.ordinal(11), "11th")
        self.assertEqual(sportstui.ordinal(12), "12th")
        self.assertEqual(sportstui.ordinal(13), "13th")
        self.assertEqual(sportstui.ordinal(21), "21st")
        self.assertEqual(sportstui.ordinal(22), "22nd")
        self.assertEqual(sportstui.ordinal(23), "23rd")
        self.assertEqual(sportstui.ordinal(30), "30th")
        self.assertEqual(sportstui.ordinal(101), "101st")
        self.assertEqual(sportstui.ordinal(111), "111th")

        # Group name shortening
        self.assertEqual(sportstui.shorten_group("Eastern Conference"), "East")
        self.assertEqual(sportstui.shorten_group("Western Conference"), "West")
        self.assertEqual(sportstui.shorten_group("American Football Conference"), "AFC")
        self.assertEqual(sportstui.shorten_group("National Football Conference"), "NFC")
        self.assertEqual(sportstui.shorten_group("Big Ten Conference"), "Big Ten")
        self.assertEqual(sportstui.shorten_group("Southeastern Conference"), "SEC")
        self.assertEqual(sportstui.shorten_group("Atlantic Coast Conference"), "ACC")
        self.assertEqual(sportstui.shorten_group("Big 12 Conference"), "Big 12")
        self.assertEqual(sportstui.shorten_group("AL East Division"), "AL East")

    def test_get_team_standing(self):
        # Mock NBA standings groups
        nba_groups = [
            {
                "name": "Eastern Conference",
                "rows": [
                    {
                        "id": "20",
                        "team": "76ers",
                        "full": "Philadelphia 76ers",
                        "abbr": "PHI",
                        "color": "006BB6",
                        "stats": {"overall": "8-2", "gamesBehind": "-", "streak": "W2", "playoffSeed": "1"},
                    },
                    {
                        "id": "2",
                        "team": "Celtics",
                        "full": "Boston Celtics",
                        "abbr": "BOS",
                        "color": "007A33",
                        "stats": {"overall": "7-2", "gamesBehind": "0.5", "streak": "W3", "playoffSeed": "2"},
                    },
                ],
            }
        ]

        # Match by abbr
        st_phi = sportstui.get_team_standing(nba_groups, {"id": "20", "abbr": "PHI", "name": "76ers", "full": "Philadelphia 76ers"}, "nba")
        self.assertIsNotNone(st_phi)
        self.assertEqual(st_phi["rank"], 1)
        self.assertEqual(st_phi["group_short"], "East")
        self.assertEqual(st_phi["badge"], "1st East (- GB)")
        self.assertEqual(st_phi["summary"], "1st in East (8-2, - GB)")
        self.assertEqual(st_phi["streak"], "W2")
        self.assertEqual(st_phi["seed"], "1")

        # Match by ID with GB
        st_bos = sportstui.get_team_standing(nba_groups, {"id": "2", "abbr": "BOS", "name": "Celtics", "full": "Boston Celtics"}, "nba")
        self.assertIsNotNone(st_bos)
        self.assertEqual(st_bos["rank"], 2)
        self.assertEqual(st_bos["badge"], "2nd East (0.5 GB)")
        self.assertEqual(st_bos["summary"], "2nd in East (7-2, 0.5 GB)")

        # Mock CFB standings
        cfb_groups = [
            {
                "name": "Big Ten Conference",
                "rows": [
                    {
                        "id": "127",
                        "team": "Spartans",
                        "full": "Michigan State Spartans",
                        "abbr": "MSU",
                        "color": "18453B",
                        "stats": {"overall": "8-1", "vs. Conf.": "5-1", "streak": "W4"},
                    }
                ],
            }
        ]
        st_msu = sportstui.get_team_standing(cfb_groups, {"id": "127", "abbr": "MSU", "name": "Michigan State", "full": "Michigan State Spartans"}, "cfb")
        self.assertIsNotNone(st_msu)
        self.assertEqual(st_msu["rank"], 1)
        self.assertEqual(st_msu["badge"], "1st Big Ten (5-1)")
        self.assertEqual(st_msu["summary"], "1st in Big Ten (5-1 Conf, 8-1 Ovr)")

        # Test collision handling: ensure Michigan State does not match Michigan
        cfb_collision_groups = [
            {
                "name": "Big Ten Conference",
                "rows": [
                    {
                        "id": "130",
                        "team": "Michigan",
                        "full": "Michigan Wolverines",
                        "abbr": "MICH",
                        "color": "00274C",
                        "stats": {"overall": "5-3", "vs. Conf.": "2-3", "streak": "W1"},
                    },
                    {
                        "id": "127",
                        "team": "Michigan St",
                        "full": "Michigan State Spartans",
                        "abbr": "MSU",
                        "color": "173F35",
                        "stats": {"overall": "2-6", "vs. Conf.": "0-5", "streak": "L5"},
                    },
                ],
            }
        ]
        msu_side = {"id": "127", "abbr": "MSU", "name": "Michigan St", "full": "Michigan State Spartans", "record": "2-6"}
        mich_side = {"id": "130", "abbr": "MICH", "name": "Michigan", "full": "Michigan Wolverines", "record": "5-3"}
        st_msu_res = sportstui.get_team_standing(cfb_collision_groups, msu_side, "cfb")
        st_mich_res = sportstui.get_team_standing(cfb_collision_groups, mich_side, "cfb")
        self.assertEqual(st_msu_res["rank"], 2)
        self.assertEqual(st_msu_res["summary"], "2nd in Big Ten (0-5 Conf, 2-6 Ovr)")
        self.assertEqual(st_mich_res["rank"], 1)
        self.assertEqual(st_mich_res["summary"], "1st in Big Ten (2-3 Conf, 5-3 Ovr)")

        # Non-matching returns None
        st_none = sportstui.get_team_standing(cfb_groups, {"id": "999", "abbr": "XYZ", "name": "Unknown"}, "cfb")
        self.assertIsNone(st_none)
        self.assertIsNone(sportstui.get_team_standing([], {"id": "127"}, "cfb"))

    def test_draw_detail_standings(self):
        opts = sportstui.parse_args([])
        app = sportstui.App(None, opts)
        app.league_key = "nba"
        game = {
            "id": "100",
            "league": "nba",
            "state": "post",
            "score": "100-98",
            "status_name": "STATUS_FINAL",
            "detail": "Final",
            "short": "Final",
            "start": None,
            "situation": {},
            "odds": {},
            "venue": "TD Garden",
            "tv": "ESPN",
            "upset": None,
            "away": {"id": "20", "abbr": "PHI", "name": "76ers", "full": "Philadelphia 76ers", "color": "006BB6", "rank": None, "record": "8-2", "score": "98", "score_int": 98, "winner": False},
            "home": {"id": "2", "abbr": "BOS", "name": "Celtics", "full": "Boston Celtics", "color": "007A33", "rank": None, "record": "7-2", "score": "100", "score_int": 100, "winner": True},
        }
        app.detail_game = game

        # Inject cached standings and detail data
        nba_groups = [
            {
                "name": "Eastern Conference",
                "rows": [
                    {"id": "20", "team": "76ers", "full": "Philadelphia 76ers", "abbr": "PHI", "color": "006BB6", "stats": {"overall": "8-2", "gamesBehind": "-", "streak": "W2", "playoffSeed": "1"}},
                    {"id": "2", "team": "Celtics", "full": "Boston Celtics", "abbr": "BOS", "color": "007A33", "stats": {"overall": "7-2", "gamesBehind": "0.5", "streak": "W3", "playoffSeed": "2"}},
                ],
            }
        ]
        app.cache["stand:nba"] = (time.time(), nba_groups, None)
        app.cache["detail:nba:100"] = (time.time(), {
            "location": "Boston, MA",
            "linescores": {"away": [24, 25, 24, 25], "home": [25, 25, 25, 25]},
            "leaders": [],
            "plays": [],
            "winprob": None,
        }, None)

        captured_puts = []
        captured_segments = []
        app.put = lambda y, x, text, *args, **kwargs: captured_puts.append((y, x, text))
        app.segment = lambda y, x, segs, *args, **kwargs: captured_segments.append((y, x, segs))

        app.draw_detail(0, 40, 100)

        # Team banners should include the standings badges
        banner_texts = [text for y, x, text in captured_puts if "Philadelphia 76ers" in text or "Boston Celtics" in text]
        self.assertTrue(any("1st East (- GB)" in t for t in banner_texts))
        self.assertTrue(any("2nd East (0.5 GB)" in t for t in banner_texts))

        # Body virtual lines should include League Standings section with full team names
        all_seg_texts = ["".join(s[0] for s in segs) for _, _, segs in captured_segments]
        self.assertTrue(any("League Standings" in t for t in all_seg_texts))
        self.assertTrue(any("Philadelphia 76ers" in t for t in all_seg_texts))
        self.assertTrue(any("Boston Celtics" in t for t in all_seg_texts))
        self.assertTrue(any("1st in East (8-2, - GB)" in t for t in all_seg_texts))
        self.assertTrue(any("2nd in East (7-2, 0.5 GB)" in t for t in all_seg_texts))

        # Body should also include full conference standings table with both teams highlighted
        self.assertTrue(any("Eastern Conference Standings" in t for t in all_seg_texts))
        self.assertTrue(any("▸PHI" in t for t in all_seg_texts))
        self.assertTrue(any("▸BOS" in t for t in all_seg_texts))

        # Test T key in detail opens extra standings focused on game's group
        app.handle_detail(ord("T"))
        self.assertEqual(app.view, "extra")
        self.assertEqual(app.extra_kind, "stand")
        self.assertEqual(app.extra_group, 0)

    def test_smart_team_name_resolution(self):
        # Teams where shortDisplayName is an abbreviation or missing (FAU, UTSA, etc.)
        mock_raw_fau = {
            "standings": {
                "entries": [
                    {
                        "team": {
                            "id": "2226",
                            "abbreviation": "FAU",
                            "shortDisplayName": "FAU",
                            "location": "Florida Atlantic",
                            "name": "Owls",
                            "displayName": "Florida Atlantic Owls",
                            "color": "003366",
                        },
                        "stats": [{"name": "overall", "displayValue": "6-2"}],
                    },
                    {
                        "team": {
                            "id": "127",
                            "abbreviation": "MSU",
                            "shortDisplayName": "Michigan St",
                            "location": "Michigan State",
                            "name": "Spartans",
                            "displayName": "Michigan State Spartans",
                            "color": "18453B",
                        },
                        "stats": [{"name": "overall", "displayValue": "5-3"}],
                    },
                ]
            },
            "name": "American Athletic Conference",
        }
        with unittest.mock.patch("sportstui.fetch_json", return_value=mock_raw_fau):
            groups = sportstui.parse_standings(sportstui.BY_KEY["cfb"])
            self.assertEqual(len(groups), 1)
            row_fau = groups[0]["rows"][0]
            # FAU short name should resolve to location "Florida Atlantic" rather than raw "FAU"
            self.assertEqual(row_fau["team"], "Florida Atlantic")
            self.assertEqual(row_fau["full"], "Florida Atlantic Owls")

            # In parse_side as well
            side_fau = sportstui.parse_side({"team": mock_raw_fau["standings"]["entries"][0]["team"], "score": "24"})
            self.assertEqual(side_fau["name"], "Florida Atlantic")
            self.assertEqual(side_fau["full"], "Florida Atlantic Owls")

    def test_get_cutoff_lines(self):
        # NHL: Division (top 3) vs Conference (top 8)
        self.assertEqual(sportstui.get_cutoff_lines("nhl", "Atlantic Division", 8), {3: "Playoff Cutoff (Top 3)"})
        self.assertEqual(sportstui.get_cutoff_lines("nhl", "Eastern Conference", 16), {8: "Playoff Cutoff (Top 8)"})

        # NBA: Conference (top 6 playoff, top 10 play-in)
        self.assertEqual(sportstui.get_cutoff_lines("nba", "Eastern Conference", 15), {6: "Playoff Cutoff (Top 6)", 10: "Play-In Cutoff (Top 10)"})

        # NFL: Conference (top 7) vs Division (top 1)
        self.assertEqual(sportstui.get_cutoff_lines("nfl", "American Football Conference", 16), {7: "Playoff Cutoff (Top 7)"})
        self.assertEqual(sportstui.get_cutoff_lines("nfl", "AFC East", 4), {1: "Division Winner"})

        # MLB: League (top 6) vs Division (top 1)
        self.assertEqual(sportstui.get_cutoff_lines("mlb", "American League", 15), {6: "Playoff Cutoff (Top 6)"})
        self.assertEqual(sportstui.get_cutoff_lines("mlb", "AL East", 5), {1: "Division Winner"})

        # MLS: Conference (top 7 and top 9)
        self.assertEqual(sportstui.get_cutoff_lines("mls", "Eastern Conference", 14), {7: "Playoff Cutoff (Top 7)", 9: "Wild Card Cutoff (Top 9)"})

        # CFB / CBB: No fixed rank cutoff
        self.assertEqual(sportstui.get_cutoff_lines("cfb", "Big Ten", 18), {})
        self.assertEqual(sportstui.get_cutoff_lines("cbb", "ACC", 18), {})

    def test_playoff_cutoff_rendering_in_detail_and_standings(self):
        opts = sportstui.parse_args([])
        app = sportstui.App(None, opts)
        app.league_key = "nhl"

        # Mock NHL game with Atlantic Division standings
        game = {
            "id": "500",
            "league": "nhl",
            "state": "post",
            "score": "4-2",
            "status_name": "STATUS_FINAL",
            "detail": "Final",
            "short": "Final",
            "start": None,
            "situation": {},
            "odds": {},
            "venue": "Amerant Bank Arena",
            "tv": "ESPN+",
            "upset": None,
            "away": {"id": "10", "abbr": "TOR", "name": "Maple Leafs", "full": "Toronto Maple Leafs", "color": "00205B", "rank": None, "record": "10-5-1", "score": "2", "score_int": 2, "winner": False},
            "home": {"id": "13", "abbr": "FLA", "name": "Panthers", "full": "Florida Panthers", "color": "041E42", "rank": None, "record": "11-4-1", "score": "4", "score_int": 4, "winner": True},
        }
        app.detail_game = game

        nhl_groups = [
            {
                "name": "Atlantic Division",
                "rows": [
                    {"id": "13", "team": "Panthers", "full": "Florida Panthers", "abbr": "FLA", "color": "041E42", "stats": {"points": "23", "overall": "11-4-1"}},
                    {"id": "10", "team": "Maple Leafs", "full": "Toronto Maple Leafs", "abbr": "TOR", "color": "00205B", "stats": {"points": "21", "overall": "10-5-1"}},
                    {"id": "14", "team": "Lightning", "full": "Tampa Bay Lightning", "abbr": "TBL", "color": "002868", "stats": {"points": "20", "overall": "9-5-2"}},
                    {"id": "6", "team": "Bruins", "full": "Boston Bruins", "abbr": "BOS", "color": "FFB81C", "stats": {"points": "18", "overall": "8-6-2"}},
                    {"id": "17", "team": "Red Wings", "full": "Detroit Red Wings", "abbr": "DET", "color": "CE1126", "stats": {"points": "16", "overall": "7-7-2"}},
                ],
            }
        ]
        app.cache["stand:nhl"] = (time.time(), nhl_groups, None)
        app.cache["detail:nhl:500"] = (time.time(), {
            "location": "Sunrise, FL",
            "linescores": {"away": [1, 0, 1], "home": [2, 1, 1]},
            "leaders": [],
            "plays": [],
            "winprob": None,
        }, None)

        captured_segments = []
        captured_puts = []
        app.put = lambda y, x, text, *args, **kwargs: captured_puts.append((y, x, text))
        app.segment = lambda y, x, segs, *args, **kwargs: captured_segments.append((y, x, segs))

        # 1. Test Game Detail has cutoff line after Rank 3
        app.draw_detail(0, 40, 100)
        all_seg_texts = ["".join(s[0] for s in segs) for _, _, segs in captured_segments]
        self.assertTrue(any("Playoff Cutoff (Top 3)" in t for t in all_seg_texts))

        # 2. Test draw_standings has cutoff line rendered
        captured_puts.clear()
        captured_segments.clear()
        app.draw_standings(nhl_groups, 0, 30, 80)
        self.assertTrue(any("Playoff Cutoff (Top 3)" in text for y, x, text in captured_puts))

    def test_rivalry_detection_and_rendering(self):
        # 1. Detection via curated dictionary
        mock_ev_msu = {
            "id": "1001",
            "competitions": [
                {
                    "competitors": [
                        {"homeAway": "away", "team": {"abbreviation": "MSU", "shortDisplayName": "Michigan St"}, "score": "0"},
                        {"homeAway": "home", "team": {"abbreviation": "MICH", "shortDisplayName": "Michigan"}, "score": "0"},
                    ],
                    "notes": [],
                    "status": {"type": {"state": "pre", "name": "STATUS_SCHEDULED"}},
                }
            ]
        }
        game_msu = sportstui.parse_game(mock_ev_msu, sportstui.BY_KEY["cfb"])
        self.assertIsNotNone(game_msu["rivalry"])
        self.assertEqual(game_msu["rivalry"], "Paul Bunyan Trophy")

        # Holy War detection
        mock_ev_byu = {
            "id": "1002",
            "competitions": [
                {
                    "competitors": [
                        {"homeAway": "away", "team": {"abbreviation": "BYU", "shortDisplayName": "BYU"}, "score": "0"},
                        {"homeAway": "home", "team": {"abbreviation": "UTAH", "shortDisplayName": "Utah"}, "score": "0"},
                    ],
                    "notes": [],
                    "status": {"type": {"state": "pre", "name": "STATUS_SCHEDULED"}},
                }
            ]
        }
        game_byu = sportstui.parse_game(mock_ev_byu, sportstui.BY_KEY["cfb"])
        self.assertEqual(game_byu["rivalry"], "Holy War")

        # Bears vs Packers detection
        mock_ev_nfl = {
            "id": "1003",
            "competitions": [
                {
                    "competitors": [
                        {"homeAway": "away", "team": {"abbreviation": "CHI", "shortDisplayName": "Bears"}, "score": "0"},
                        {"homeAway": "home", "team": {"abbreviation": "GB", "shortDisplayName": "Packers"}, "score": "0"},
                    ],
                    "notes": [],
                    "status": {"type": {"state": "pre", "name": "STATUS_SCHEDULED"}},
                }
            ]
        }
        game_nfl = sportstui.parse_game(mock_ev_nfl, sportstui.BY_KEY["nfl"])
        self.assertEqual(game_nfl["rivalry"], "Bears–Packers Rivalry")

        # 2. Card rendering with fire badge
        opts = sportstui.parse_args([])
        app = sportstui.App(None, opts)
        app.glyphs = "emoji"
        captured_boxes = []
        app.draw_box = lambda y, x, h, w, attr, title="", heavy=False: captured_boxes.append((title, heavy))
        app.put = lambda *a, **kw: None
        app.fill_line = lambda *a, **kw: None
        app.segment = lambda *a, **kw: None

        app.draw_card(game_msu, 0, 0, 42, False)
        self.assertTrue(any("🔥" in title and "PAUL BUNYAN TROPHY" in title for title, _ in captured_boxes))
        self.assertTrue(any(heavy for _, heavy in captured_boxes))

        # 3. Game Detail rendering with rivalry banner
        captured_detail_puts = []
        app.put = lambda y, x, text, *a, **kw: captured_detail_puts.append((y, x, text))
        app.detail_game = game_msu
        app.cache["stand:cfb"] = (time.time(), [], None)
        app.cache["detail:cfb:1001"] = (time.time(), {
            "location": "Ann Arbor, MI",
            "linescores": {"away": [], "home": []},
            "leaders": [],
            "plays": [],
            "winprob": None
        }, None)

        app.draw_detail(0, 40, 100)
        self.assertTrue(any("🔥 Rivalry Game" in text and "Paul Bunyan Trophy" in text for _, _, text in captured_detail_puts))

    def test_completed_games_filter(self):
        opts = sportstui.parse_args([])
        app = sportstui.App(None, opts)
        app.league_key = "cfb"

        games = [
            {"id": "1", "state": "pre", "start": None, "away": {"abbr": "MSU", "rank": None}, "home": {"abbr": "MICH", "rank": None}},
            {"id": "2", "state": "in", "start": None, "away": {"abbr": "OSU", "rank": None}, "home": {"abbr": "PSU", "rank": None}},
            {"id": "3", "state": "post", "start": None, "away": {"abbr": "TEX", "rank": None}, "home": {"abbr": "OU", "rank": None}},
            {"id": "4", "state": "post", "start": None, "away": {"abbr": "BAMA", "rank": None}, "home": {"abbr": "LSU", "rank": None}},
        ]

        # 1. Filter = 'final'
        app.filter = "final"
        filtered_final = app.visible(games)
        self.assertEqual(len(filtered_final), 2)
        self.assertEqual({g["id"] for g in filtered_final}, {"3", "4"})

        # 2. Filter = 'completed' alias
        app.filter = "completed"
        filtered_completed = app.visible(games)
        self.assertEqual(len(filtered_completed), 2)
        self.assertEqual({g["id"] for g in filtered_completed}, {"3", "4"})

        # 3. Filter options rotation in CFB (with poll: top25 present)
        app.league_key = "cfb"
        cfb_options = ["all", "live", "final", "fav", "upsets"] + (["top25"] if app.lg()["poll"] else [])
        self.assertIn("final", cfb_options)
        self.assertEqual(cfb_options, ["all", "live", "final", "fav", "upsets", "top25"])

        # 4. Filter options rotation in NFL (without poll)
        app.league_key = "nfl"
        nfl_options = ["all", "live", "final", "fav", "upsets"] + (["top25"] if app.lg()["poll"] else [])
        self.assertIn("final", nfl_options)
        self.assertEqual(nfl_options, ["all", "live", "final", "fav", "upsets"])

    def test_news_all_league_aggregation(self):
        from unittest.mock import patch

        mock_art_cfb = {
            "articles": [{
                "id": "101",
                "headline": "CFB Big Game",
                "description": "Preview of match",
                "published": "2026-11-07T14:00:00Z",
                "links": {"web": {"href": "https://espn.com/cfb1"}},
                "categories": [{"type": "team", "description": "MSU"}],
            }]
        }
        mock_art_nfl = {
            "articles": [{
                "id": "102",
                "headline": "NFL Big Game",
                "description": "NFL summary",
                "published": "2026-11-07T15:00:00Z",
                "links": {"web": {"href": "https://espn.com/nfl1"}},
                "categories": [{"type": "team", "description": "DET"}],
            }]
        }

        def mock_fetch(url, *args, **kwargs):
            if "college-football" in url:
                return mock_art_cfb
            elif "nfl" in url:
                return mock_art_nfl
            return {"articles": []}

        with patch.object(sportstui, "fetch_json", side_effect=mock_fetch):
            items = sportstui.parse_news(sportstui.BY_KEY["all"])
            self.assertGreaterEqual(len(items), 2)
            # Latest first
            self.assertEqual(items[0]["id"], "102")
            self.assertEqual(items[0]["league"], "NFL")
            self.assertEqual(items[1]["id"], "101")
            self.assertEqual(items[1]["league"], "CFB")

    def test_copy_news_article(self):
        from unittest.mock import patch
        opts = sportstui.parse_args([])
        app = sportstui.App(None, opts)

        # 1. Copy from open reader (news_story)
        app.news_story = ("Headline Here", "Story paragraph text", "https://espn.com/story1")
        with patch.object(sportstui, "copy_to_clipboard", return_value=True) as mock_clip:
            app.copy_news_article()
            mock_clip.assert_called_once()
            copied_text = mock_clip.call_args[0][0]
            self.assertIn("Headline Here", copied_text)
            self.assertIn("https://espn.com/story1", copied_text)
            self.assertIn("Story paragraph text", copied_text)
            self.assertEqual(app.notice[0], "Copied article to clipboard")

        # 2. Copy from article dict with story_url fetching full body
        app.news_story = None
        mock_art = {
            "headline": "Trade Alert",
            "description": "Short preview",
            "web_url": "https://espn.com/trade",
            "story_url": "https://site.api.espn.com/story",
        }
        mock_story_json = {
            "headlines": [{"story": "<p>Full details of the blockbuster trade.</p>"}]
        }
        with patch.object(sportstui, "fetch_json", return_value=mock_story_json), \
             patch.object(sportstui, "copy_to_clipboard", return_value=True) as mock_clip:
            app.copy_news_article(mock_art)
            mock_clip.assert_called_once()
            copied_text = mock_clip.call_args[0][0]
            self.assertIn("Trade Alert", copied_text)
            self.assertIn("https://espn.com/trade", copied_text)
            self.assertIn("Full details of the blockbuster trade.", copied_text)

        # 3. Handle news input key 'c' while in reader and list
        import time
        app.cache["news:cfb"] = (time.time(), [mock_art])
        app.league_key = "cfb"
        app.news_sel = 0
        app.news_story = None
        with patch.object(app, "copy_news_article") as mock_copy:
            app.handle_news(ord("c"))
            mock_copy.assert_called_once_with(mock_art)

        app.news_story = ("Headline", "Body", "https://url")
        with patch.object(app, "copy_news_article") as mock_copy:
            app.handle_news(ord("c"))
            mock_copy.assert_called_once_with()

    def test_breathing_attr_and_animated_borders(self):
        """Test breathing animation attribute generation and card integration."""
        opts = sportstui.parse_args([])
        app = sportstui.App(None, opts)

        # 1. Breathing attributes return valid integers
        a_rz = app.breathing_attr("red_zone")
        a_up = app.breathing_attr("upset")
        self.assertIsInstance(a_rz, int)
        self.assertIsInstance(a_up, int)

        # 2. Card border in red zone uses strobe in strobe mode (Option #3)
        game_rz = {
            "id": "1", "state": "in", "short": "Q4 02:15", "league": "nfl",
            "away": {"id": "1", "name": "Packers", "abbr": "GB", "color": "203731", "score": "20", "score_int": 20},
            "home": {"id": "2", "name": "Lions", "abbr": "DET", "color": "0076B6", "score": "24", "score_int": 24},
            "situation": {"red_zone": True, "down_dist": "1st & Goal at DET 4"},
        }
        captured_boxes = []
        app.draw_box = lambda y, x, h, w, attr, title="", heavy=False, marquee=None, alert=None: captured_boxes.append((attr, title, heavy, marquee, alert))
        app.put = lambda *a, **kw: None
        app.fill_line = lambda *a, **kw: None
        app.segment = lambda *a, **kw: None

        app.anim_mode = "strobe"
        app.draw_card(game_rz, 0, 0, 42, False)
        self.assertEqual(len(captured_boxes), 1)
        attr, title, heavy, marquee, alert = captured_boxes[0]
        self.assertTrue(heavy)
        self.assertIsNotNone(alert)
        self.assertEqual(alert["kind"], "red_zone")
        self.assertEqual(alert["sitrep"], "1ST & GOAL")

        # 3. Card border in breathing mode passes alert=None and marquee=None
        captured_boxes.clear()
        app.anim_mode = "breathing"
        app.draw_card(game_rz, 0, 0, 42, False)
        self.assertEqual(len(captured_boxes), 1)
        attr, title, heavy, marquee, alert = captured_boxes[0]
        self.assertTrue(heavy)
        self.assertIsNone(alert)
        self.assertIsNone(marquee)

        # 4. Off mode returns static attribute without crashing
        app.anim_mode = "off"
        attr_off = app.breathing_attr("red_zone")
        self.assertIsInstance(attr_off, int)

        # 5. Hotkey 'm' cycles modes: hybrid -> strobe -> breathing -> off -> hybrid
        app.anim_mode = "hybrid"
        app.handle(ord("m"))
        self.assertEqual(app.anim_mode, "strobe")
        app.handle(ord("m"))
        self.assertEqual(app.anim_mode, "breathing")
        app.handle(ord("m"))
        self.assertEqual(app.anim_mode, "off")
        app.handle(ord("m"))
        self.assertEqual(app.anim_mode, "hybrid")

        # 6. Real draw_box with strobe renders tactical corner brackets and flashing sitrep badges
        real_app = sportstui.App(None, opts)
        real_app.anim_mode = "strobe"
        segments_drawn = []
        puts_drawn = []
        real_app.segment = lambda y, x, segs, w: segments_drawn.append((y, x, segs, w))
        real_app.put = lambda y, x, ch, attr=0, **kw: puts_drawn.append((y, x, ch, attr))
        real_app.draw_box(0, 0, 5, 42, 0, title="⚑ RED ZONE", heavy=True, alert={"kind": "red_zone", "sitrep": "1ST & GOAL"})
        self.assertEqual(len(segments_drawn), 2)  # top and bottom bars
        self.assertEqual(len(puts_drawn), 6)      # 3 left + 3 right edge cells
        top_segs = segments_drawn[0][2]
        self.assertTrue(top_segs[0][0].startswith("┏"))  # top-left bracket starts with ┏
        self.assertTrue(any("1ST & GOAL" in txt or "RED ZONE" in txt for txt, _ in top_segs))

    def test_two_phase_strobe_phases_and_sitrep(self):
        """Test exact rendering and sitrep extraction for Phase 0 and Phase 1 of Two-Phase Strobe."""
        import time as py_time
        opts = sportstui.parse_args([])
        app = sportstui.App(None, opts)
        app.anim_mode = "strobe"

        # Phase 0 test: Solid Heavy Alert Frame + Inverted Alert Badge Block
        orig_time = py_time.time
        try:
            py_time.time = lambda: 0.0  # int(0.0 * 2.5) % 2 == 0
            segs_p0, puts_p0 = [], []
            app.segment = lambda y, x, segs, w: segs_p0.append((y, x, segs, w))
            app.put = lambda y, x, ch, attr=0, **kw: puts_p0.append((y, x, ch, attr))
            app.draw_box(0, 0, 5, 42, 0, heavy=True, alert={"kind": "red_zone", "sitrep": "1ST & GOAL", "base_label": "RED ZONE"})

            self.assertEqual(len(segs_p0), 2)  # top bar and bottom bar are segments
            self.assertEqual(len(puts_p0), 6)  # 3 left + 3 right
            top0 = segs_p0[0][2]
            self.assertEqual(top0[0][0], "┏━")
            self.assertTrue(any("RED ZONE" in txt for txt, _ in top0))

            # Phase 1 test: Tactical Corner Brackets + Flashing Sitrep Badge
            py_time.time = lambda: 0.4  # int(0.4 * 2.5) % 2 == 1
            segs_p1, puts_p1 = [], []
            app.segment = lambda y, x, segs, w: segs_p1.append((y, x, segs, w))
            app.put = lambda y, x, ch, attr=0, **kw: puts_p1.append((y, x, ch, attr))
            app.draw_box(0, 0, 5, 42, 0, heavy=True, alert={"kind": "red_zone", "sitrep": "1ST & GOAL", "base_label": "RED ZONE"})

            self.assertEqual(len(segs_p1), 2)  # top bar and bottom bar are segments
            self.assertEqual(len(puts_p1), 6)  # 3 left + 3 right
            top1 = segs_p1[0][2]
            self.assertEqual(top1[0][0], "┏━━")
            self.assertTrue(any("1ST & GOAL" in txt for txt, _ in top1))

            # Bottom bar in Phase 1 has 3 bracket segments: left bracket, thin bridge, right bracket
            bot1 = segs_p1[1][2]
            self.assertEqual(bot1[0][0], "┗━━")
            self.assertTrue(bot1[1][0].startswith("─"))
            self.assertEqual(bot1[2][0], "━━┛")

            # Middle side edge in Phase 1 is dim thin vertical line │
            side_chars = [ch for _, _, ch, _ in puts_p1]
            self.assertIn("│", side_chars)
            self.assertIn("┃", side_chars)
        finally:
            py_time.time = orig_time

    def test_dynamic_leverage_escalation_option_b(self):
        """Test Option B Dynamic Leverage Escalation across time, score, and situation."""
        opts = sportstui.parse_args([])
        app = sportstui.App(None, opts)
        app.anim_mode = "hybrid"

        # 1. Red Zone: Q1 1st & 10 at 18 (build-up) -> breathing, alert=None
        game_rz_buildup = {
            "id": "1", "state": "in", "league": "nfl", "period": 1, "clock": "11:20",
            "away": {"id": "1", "abbr": "DET", "name": "Lions", "color": "0076B6", "score": "0", "score_int": 0},
            "home": {"id": "2", "abbr": "GB", "name": "Packers", "color": "203731", "score": "0", "score_int": 0},
            "situation": {"red_zone": True, "down": 1, "down_dist": "1st & 10 at GB 18", "yard_line": 82},
        }
        captured = []
        app.draw_box = lambda y, x, h, w, attr, title="", heavy=False, alert=None, **kw: captured.append((heavy, alert))
        app.put = lambda *a, **kw: None
        app.fill_line = lambda *a, **kw: None
        app.segment = lambda *a, **kw: None

        app.draw_card(game_rz_buildup, 0, 0, 42, False)
        self.assertEqual(len(captured), 1)
        heavy, alert = captured[0]
        self.assertTrue(heavy)
        self.assertIsNone(alert)  # Breathing pulse (alert is None)

        # 2. Red Zone: Q1 1st & Goal at 3 (inside 5) -> escalates to Strobe
        game_rz_goal = dict(game_rz_buildup)
        game_rz_goal["situation"] = {"red_zone": True, "down": 1, "down_dist": "1st & Goal at GB 3", "yard_line": 97}
        captured.clear()
        app.draw_card(game_rz_goal, 0, 0, 42, False)
        self.assertEqual(len(captured), 1)
        heavy, alert = captured[0]
        self.assertTrue(heavy)
        self.assertIsNotNone(alert)
        self.assertEqual(alert["sitrep"], "1ST & GOAL")

        # 3. Red Zone: Q4 01:45, 21-24, 2nd & 6 at GB 14 (Late & Close 1-possession) -> escalates to Strobe
        game_rz_clutch = dict(game_rz_buildup)
        game_rz_clutch["period"] = 4
        game_rz_clutch["clock"] = "01:45"
        game_rz_clutch["away"] = {"id": "1", "abbr": "DET", "name": "Lions", "color": "0076B6", "score": "21", "score_int": 21}
        game_rz_clutch["home"] = {"id": "2", "abbr": "GB", "name": "Packers", "color": "203731", "score": "24", "score_int": 24}
        game_rz_clutch["situation"] = {"red_zone": True, "down": 2, "down_dist": "2nd & 6 at GB 14", "yard_line": 86}
        captured.clear()
        app.draw_card(game_rz_clutch, 0, 0, 42, False)
        self.assertEqual(len(captured), 1)
        heavy, alert = captured[0]
        self.assertTrue(heavy)
        self.assertIsNotNone(alert)

        # 4. Red Zone: Q3 07:15, 7-35 blowout -> breathes (alert is None)
        game_rz_blowout = dict(game_rz_buildup)
        game_rz_blowout["period"] = 3
        game_rz_blowout["clock"] = "07:15"
        game_rz_blowout["away"] = {"id": "1", "abbr": "DET", "name": "Lions", "color": "0076B6", "score": "7", "score_int": 7}
        game_rz_blowout["home"] = {"id": "2", "abbr": "GB", "name": "Packers", "color": "203731", "score": "35", "score_int": 35}
        game_rz_blowout["situation"] = {"red_zone": True, "down": 2, "down_dist": "2nd & 4 at GB 11", "yard_line": 89}
        captured.clear()
        app.draw_card(game_rz_blowout, 0, 0, 42, False)
        self.assertEqual(len(captured), 1)
        heavy, alert = captured[0]
        self.assertTrue(heavy)
        self.assertIsNone(alert)  # Breathing pulse

        # 5. Upset: Q1 early lead -> breathes (alert is None)
        game_up_early = {
            "id": "10", "state": "in", "league": "cfb", "period": 1, "clock": "08:30",
            "away": {"id": "1", "abbr": "VAN", "name": "Vanderbilt", "color": "000000", "score": "7", "score_int": 7},
            "home": {"id": "2", "abbr": "ALA", "name": "Alabama", "color": "9E1B32", "score": "0", "score_int": 0},
            "upset": {"underdog": {"abbr": "VAN"}, "favorite": {"abbr": "ALA"}, "confirmed": False},
        }
        captured.clear()
        app.draw_card(game_up_early, 0, 0, 42, False)
        self.assertEqual(len(captured), 1)
        heavy, alert = captured[0]
        self.assertTrue(heavy)
        self.assertIsNone(alert)  # Early upset breathes

        # 6. Upset: Q4 late lead -> escalates to Strobe
        game_up_late = dict(game_up_early)
        game_up_late["period"] = 4
        game_up_late["clock"] = "03:15"
        game_up_late["away"] = {"id": "1", "abbr": "VAN", "name": "Vanderbilt", "color": "000000", "score": "33", "score_int": 33}
        game_up_late["home"] = {"id": "2", "abbr": "ALA", "name": "Alabama", "color": "9E1B32", "score": "28", "score_int": 28}
        captured.clear()
        app.draw_card(game_up_late, 0, 0, 42, False)
        self.assertEqual(len(captured), 1)
        heavy, alert = captured[0]
        self.assertTrue(heavy)
        self.assertIsNotNone(alert)  # Late upset strobes
        self.assertEqual(alert["sitrep"], "VAN LEADS ALA")

    def test_excitement_engine_and_filter(self):
        opts = sportstui.parse_args(["--glyphs", "unicode"])
        app = sportstui.App(None, opts)
        app.league_key = "cfb"
        app.favs.clear()

        # 1. Routine unranked pre-game (should NOT qualify)
        g_routine_pre = {
            "id": "1", "league": "cfb", "state": "pre", "period": 0, "clock": "", "start": None,
            "away": {"id": "10", "abbr": "MAC1", "name": "Team A", "rank": None, "score_int": 0, "color": "333333"},
            "home": {"id": "11", "abbr": "MAC2", "name": "Team B", "rank": None, "score_int": 0, "color": "444444"},
            "odds": {"details": "MAC1 -14.5"},
        }
        exc_pre = sportstui.evaluate_excitement(g_routine_pre)
        self.assertFalse(exc_pre["qualifies"])
        self.assertLess(exc_pre["score"], sportstui.EXCITEMENT_THRESHOLD)

        # 2. Live Q3 Blowout (should NOT qualify)
        g_blowout = {
            "id": "2", "league": "cfb", "state": "in", "period": 3, "clock": "05:00", "start": None,
            "away": {"id": "12", "abbr": "UGA", "name": "Georgia", "rank": 2, "score_int": 42, "color": "BA0C2F"},
            "home": {"id": "13", "abbr": "MSST", "name": "Miss St", "rank": None, "score_int": 3, "color": "660000"},
        }
        exc_blowout = sportstui.evaluate_excitement(g_blowout)
        self.assertFalse(exc_blowout["qualifies"])

        # 3. Pre-game Rivalry (qualifies, ~42)
        g_rivalry = {
            "id": "3", "league": "cfb", "state": "pre", "period": 0, "clock": "", "start": None,
            "rivalry": "Paul Bunyan's Axe",
            "away": {"id": "14", "abbr": "MINN", "name": "Minnesota", "rank": None, "score_int": 0, "color": "7A0019"},
            "home": {"id": "15", "abbr": "WIS", "name": "Wisconsin", "rank": None, "score_int": 0, "color": "C5050C"},
        }
        exc_riv = sportstui.evaluate_excitement(g_rivalry)
        self.assertTrue(exc_riv["qualifies"])
        self.assertEqual(exc_riv["badge"], "RIVALRY")

        # 4. Pre-game Top-10 Ranked Clash (qualifies, ~50)
        g_top10 = {
            "id": "4", "league": "cfb", "state": "pre", "period": 0, "clock": "", "start": None,
            "away": {"id": "16", "abbr": "OSU", "name": "Ohio State", "rank": 3, "score_int": 0, "color": "BB0000"},
            "home": {"id": "17", "abbr": "ORE", "name": "Oregon", "rank": 6, "score_int": 0, "color": "154733"},
        }
        exc_top10 = sportstui.evaluate_excitement(g_top10)
        self.assertTrue(exc_top10["qualifies"])
        self.assertEqual(exc_top10["badge"], "TOP-10 CLASH")

        # 5. Live Q4 01:20 1-score Clutch + Red Zone Goal-to-Go (qualifies, 99)
        g_clutch_rz = {
            "id": "5", "league": "cfb", "state": "in", "period": 4, "clock": "01:20", "start": None,
            "away": {"id": "18", "abbr": "ALA", "name": "Alabama", "rank": 7, "score_int": 24, "color": "9E1B32"},
            "home": {"id": "19", "abbr": "TENN", "name": "Tennessee", "rank": 11, "score_int": 27, "color": "FF8200"},
            "situation": {"red_zone": True, "down": 4, "down_dist": "4th & Goal at TENN 2", "yard_line": 98},
        }
        exc_clutch = sportstui.evaluate_excitement(g_clutch_rz)
        self.assertTrue(exc_clutch["qualifies"])
        self.assertEqual(exc_clutch["score"], 99)
        self.assertEqual(exc_clutch["badge"], "CLUTCH")

        # 6. Verify visible() with 'exciting' filter filters & sorts highest score first
        all_games = [g_routine_pre, g_blowout, g_rivalry, g_top10, g_clutch_rz]
        app.filter = "exciting"
        vis = app.visible(all_games)
        self.assertEqual([g["id"] for g in vis], ["5", "4", "3"])

        # 7. Verify visible() with 'live-exciting' filter isolates strictly live thrillers
        app.filter = "live-exciting"
        vis_live_exc = app.visible(all_games)
        self.assertEqual([g["id"] for g in vis_live_exc], ["5"])

    def test_hate_watch_tri_state_and_schadenfreude(self):
        opts = sportstui.parse_args(["--glyphs", "emoji"])
        app = sportstui.App(None, opts)
        app.league_key = "cfb"
        app.favs.clear()
        app.hated.clear()

        # 1. Test team_row_prefix visual width with skull glyph across sets
        skull_cases = [
            ("💀", None),
            ("💀", 24),
            ("☠", None),
            ("☠", 7),
            ("", 12),
            ("X", None),
        ]
        for skull, rk in skull_cases:
            pfx = sportstui.team_row_prefix("", skull, rk)
            w = sportstui.str_width(pfx)
            self.assertEqual(w, 8, f"Prefix {pfx!r} for ({skull!r}, {rk!r}) has width {w} != 8")
            self.assertTrue(pfx.endswith(" "))

        # 2. Test tri-state watchlist cycle on toggle_fav
        side_smu = {"id": "2567", "abbr": "SMU", "name": "Mustangs"}
        side_nd = {"id": "87", "abbr": "ND", "name": "Notre Dame"}
        gm = {"league": "cfb", "away": side_smu, "home": side_nd, "state": "in"}

        # State 1 (Normal) -> State 2 (Favorite ★)
        app.toggle_fav(side_smu, gm)
        self.assertTrue(app.is_fav(side_smu, gm))
        self.assertFalse(app.is_hated(side_smu, gm))
        self.assertTrue(app.game_watched(gm))

        # State 2 (Favorite ★) -> State 3 (Hate-Watch 💀)
        app.toggle_fav(side_smu, gm)
        self.assertFalse(app.is_fav(side_smu, gm))
        self.assertTrue(app.is_hated(side_smu, gm))
        self.assertTrue(app.game_watched(gm))

        # State 3 (Hate-Watch 💀) -> State 1 (Normal / Clear)
        app.toggle_fav(side_smu, gm)
        self.assertFalse(app.is_fav(side_smu, gm))
        self.assertFalse(app.is_hated(side_smu, gm))
        self.assertFalse(app.game_watched(gm))

        # 3. Test Schadenfreude Excitement Boost when Hated Team is Trailing
        app.hated.add("cfb:SMU")
        # SMU trailing 14-28 in Q3
        gm_smu_trailing = {
            "id": "100", "league": "cfb", "state": "in", "period": 3, "clock": "06:00", "start": None,
            "away": {"id": "2567", "abbr": "SMU", "score_int": 14, "color": "CC0000"},
            "home": {"id": "183", "abbr": "SYR", "score_int": 28, "color": "D44500"},
        }
        exc_smu = sportstui.evaluate_excitement(gm_smu_trailing, app.hated)
        self.assertTrue(exc_smu["qualifies"])
        self.assertGreaterEqual(exc_smu["score"], 40)
        self.assertEqual(exc_smu["badge"], "HATE WATCH")

        # 4. Scoreboard pinning: SMU game is pinned under watchlist
        unrelated_gm = {
            "id": "101", "league": "cfb", "state": "in", "period": 3, "clock": "06:00", "start": None,
            "away": {"id": "1", "abbr": "TEM", "score_int": 10, "color": "990000"},
            "home": {"id": "2", "abbr": "USF", "score_int": 14, "color": "006747"},
        }
        app.filter = "all"
        vis = app.visible([unrelated_gm, gm_smu_trailing])
        self.assertEqual(vis[0]["id"], "100")  # Pinned to the top!


if __name__ == "__main__":
    unittest.main()
