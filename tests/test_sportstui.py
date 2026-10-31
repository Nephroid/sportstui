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
    def test_league_groups_and_filtering(self):
        # All 6 leagues have configured group/conference pickers
        for lg in ("cfb", "nfl", "nhl", "nba", "cbb", "mlb"):
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
        expected_order = ["all", "cfb", "nfl", "nhl", "nba", "cbb", "mlb"]
        actual_order = [lg["key"] for lg in sportstui.LEAGUES]
        self.assertEqual(actual_order, expected_order)

        # 1 is ALL sports together, rest shift to 2: CFB, 3: NFL, 4: NHL, 5: NBA, 6: CBB, 7: MLB
        self.assertEqual(sportstui.LEAGUES[0]["key"], "all")
        self.assertEqual([lg["key"] for lg in sportstui.SPORT_LEAGUES], ["cfb", "nfl", "nhl", "nba", "cbb", "mlb"])

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
        """Test column calculation matching cfbtui: 5 cols widescreen, 2 cols half-page on CM34."""
        opts = sportstui.parse_args([])
        app = sportstui.App(None, opts)

        # Widescreen on CM34 Flip (Hyprland fullscreen foot ~180-206 cols)
        self.assertEqual(app.grid_cols(206), 5)
        self.assertEqual(app.grid_cols(180), 5)

        # Half-page on CM34 Flip (Hyprland 50/50 split ~100-104 cols)
        self.assertEqual(app.grid_cols(100), 2)
        self.assertEqual(app.grid_cols(104), 2)

        # Intermediate widths
        self.assertEqual(app.grid_cols(132), 3)
        self.assertEqual(app.grid_cols(144), 4)
        self.assertEqual(app.grid_cols(70), 1)
        self.assertEqual(app.grid_cols(36), 1)

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
                self.assertGreaterEqual(w_i, 34, f"Card width {w_i} < 34 at terminal width {w}")
                if i > 0:
                    prev_x, prev_w = layout[i - 1]
                    self.assertEqual(x_i, prev_x + prev_w + 1, f"Gutter mismatch between cols {i-1} and {i} at width {w}")

            last_x, last_w = layout[-1]
            end_x = last_x + last_w
            self.assertLessEqual(end_x, w, f"Card layout overflows width {w}: ends at {end_x}")

    def test_all_sports_mode_and_league_shifting(self):
        """Test that 1 is ALL sports together, and leagues shift to 2-7."""
        # 1: ALL, 2: CFB, 3: NFL, 4: NHL, 5: NBA, 6: CBB, 7: MLB
        keys = [lg["key"] for lg in sportstui.LEAGUES]
        self.assertEqual(keys, ["all", "cfb", "nfl", "nhl", "nba", "cbb", "mlb"])

        names = [lg["name"] for lg in sportstui.LEAGUES]
        self.assertEqual(names, ["ALL", "CFB", "NFL", "NHL", "NBA", "CBB", "MLB"])

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


if __name__ == "__main__":
    unittest.main()
