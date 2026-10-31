#!/usr/bin/env python3
"""sportstui - six leagues, one scoreboard, zero dependencies.

A terminal scoreboard for CFB, CBB, NHL, NBA, MLB and NFL modeled directly on
the visual design of WPTK/cfbtui:
- Full-bleed team color background bars with WCAG luminance-contrasted text
- Starred Favorites section + Other games section
- Upset / Upset Watch / Red Zone card borders & badges
- Live bottom ticker panel + cfbtui status bar & yellow-key footer
- Rich Game Detail view with Win Probability bar, whole-game sparkline,
  Score by period linescore table, Team Stats comparison bars, Leaders,
  and chronological Scoring Plays with running scores
- Side-by-side bordered Rankings (AP / Coaches / CFP) & Standings tables
  with full-bleed team color bars
- League News feed (N) and Discord clipboard copy (c / C)
"""

import argparse
import concurrent.futures
import curses
import datetime as dt
import html
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import unicodedata
import urllib.error
import urllib.request
import webbrowser
from zoneinfo import ZoneInfo

VERSION = "1.2.0"
UA = "sportstui/1.2 (terminal scoreboard)"
SITE = "https://site.api.espn.com/apis/site/v2/sports"
CORE = "https://site.api.espn.com/apis/v2/sports"
EASTERN = ZoneInfo("America/New_York")
CONFIG_PATH = os.path.expanduser(
    os.environ.get("SPORTSTUI_CONFIG", "~/.config/sportstui/config.json")
)

ALL_LEAGUE = {
    "key": "all",
    "name": "ALL",
    "label": "ALL",
    "path": "",
    "poll": False,
    "period_prefix": "",
    "reg_periods": 4,
}

SPORT_LEAGUES = [
    {"key": "cfb", "name": "CFB", "label": "FBS", "path": "football/college-football", "poll": True, "period_prefix": "Q", "reg_periods": 4},
    {"key": "nfl", "name": "NFL", "label": "NFL", "path": "football/nfl", "poll": False, "period_prefix": "Q", "reg_periods": 4},
    {"key": "nhl", "name": "NHL", "label": "NHL", "path": "hockey/nhl", "poll": False, "period_prefix": "P", "reg_periods": 3},
    {"key": "nba", "name": "NBA", "label": "NBA", "path": "basketball/nba", "poll": False, "period_prefix": "Q", "reg_periods": 4},
    {"key": "cbb", "name": "CBB", "label": "NCAAM", "path": "basketball/mens-college-basketball", "poll": True, "period_prefix": "H", "reg_periods": 2},
    {"key": "mlb", "name": "MLB", "label": "MLB", "path": "baseball/mlb", "poll": False, "period_prefix": "", "reg_periods": 9},
]

LEAGUES = [ALL_LEAGUE] + SPORT_LEAGUES
BY_KEY = {lg["key"]: lg for lg in LEAGUES}

DEFAULT_FAVORITES = [
    "cfb:MSU", "cfb:ND", "cfb:TEX",
    "cbb:MSU",
    "nba:PHI", "nba:DET",
    "nhl:DET",
    "mlb:DET",
    "nfl:DET",
]

LEAGUE_GROUPS = {
    "cfb": [
        ("5", "Big Ten"),
        ("8", "SEC"),
        ("1", "ACC"),
        ("4", "Big 12"),
        ("151", "American"),
        ("15", "MAC"),
        ("17", "Mountain West"),
        ("37", "Sun Belt"),
        ("12", "Conference USA"),
        ("9", "Pac-12"),
        ("18", "FBS Independents"),
    ],
    "cbb": [
        ("7", "Big Ten"),
        ("23", "SEC"),
        ("2", "ACC"),
        ("8", "Big 12"),
        ("4", "Big East"),
        ("62", "American"),
        ("3", "Atlantic 10"),
        ("44", "Mountain West"),
        ("29", "WCC"),
        ("1", "America East"),
        ("46", "ASUN"),
        ("5", "Big Sky"),
        ("6", "Big South"),
        ("9", "Big West"),
        ("10", "CAA"),
        ("11", "Conference USA"),
        ("45", "Horizon"),
        ("12", "Ivy League"),
        ("13", "MAAC"),
        ("14", "MAC"),
        ("16", "MEAC"),
        ("18", "MVC"),
        ("19", "NEC"),
        ("20", "OVC"),
        ("22", "Patriot"),
        ("24", "SoCon"),
        ("25", "Southland"),
        ("26", "SWAC"),
        ("49", "Summit"),
        ("27", "Sun Belt"),
        ("30", "UAC"),
    ],
    "nfl": [
        ("afc", "AFC"),
        ("nfc", "NFC"),
        ("afc_east", "AFC East"),
        ("afc_north", "AFC North"),
        ("afc_south", "AFC South"),
        ("afc_west", "AFC West"),
        ("nfc_east", "NFC East"),
        ("nfc_north", "NFC North"),
        ("nfc_south", "NFC South"),
        ("nfc_west", "NFC West"),
    ],
    "nba": [
        ("east", "Eastern Conference"),
        ("west", "Western Conference"),
        ("atlantic", "Atlantic"),
        ("central", "Central"),
        ("southeast", "Southeast"),
        ("northwest", "Northwest"),
        ("pacific", "Pacific"),
        ("southwest", "Southwest"),
    ],
    "nhl": [
        ("east", "Eastern Conference"),
        ("west", "Western Conference"),
        ("atlantic", "Atlantic"),
        ("metropolitan", "Metropolitan"),
        ("central", "Central"),
        ("pacific", "Pacific"),
    ],
    "mlb": [
        ("al", "American League"),
        ("nl", "National League"),
        ("al_east", "AL East"),
        ("al_central", "AL Central"),
        ("al_west", "AL West"),
        ("nl_east", "NL East"),
        ("nl_central", "NL Central"),
        ("nl_west", "NL West"),
    ],
}

PRO_TEAM_GROUPS = {
    "nfl": {
        "BUF": ("afc", "afc_east"), "MIA": ("afc", "afc_east"), "NE": ("afc", "afc_east"), "NYJ": ("afc", "afc_east"),
        "BAL": ("afc", "afc_north"), "CIN": ("afc", "afc_north"), "CLE": ("afc", "afc_north"), "PIT": ("afc", "afc_north"),
        "HOU": ("afc", "afc_south"), "IND": ("afc", "afc_south"), "JAX": ("afc", "afc_south"), "TEN": ("afc", "afc_south"),
        "DEN": ("afc", "afc_west"), "KC": ("afc", "afc_west"), "LAC": ("afc", "afc_west"), "LV": ("afc", "afc_west"),
        "DAL": ("nfc", "nfc_east"), "NYG": ("nfc", "nfc_east"), "PHI": ("nfc", "nfc_east"), "WSH": ("nfc", "nfc_east"),
        "CHI": ("nfc", "nfc_north"), "DET": ("nfc", "nfc_north"), "GB": ("nfc", "nfc_north"), "MIN": ("nfc", "nfc_north"),
        "ATL": ("nfc", "nfc_south"), "CAR": ("nfc", "nfc_south"), "NO": ("nfc", "nfc_south"), "TB": ("nfc", "nfc_south"),
        "ARI": ("nfc", "nfc_west"), "LAR": ("nfc", "nfc_west"), "SEA": ("nfc", "nfc_west"), "SF": ("nfc", "nfc_west"),
    },
    "nba": {
        "BOS": ("east", "atlantic"), "BKN": ("east", "atlantic"), "NY": ("east", "atlantic"), "PHI": ("east", "atlantic"), "TOR": ("east", "atlantic"),
        "CHI": ("east", "central"), "CLE": ("east", "central"), "DET": ("east", "central"), "IND": ("east", "central"), "MIL": ("east", "central"),
        "ATL": ("east", "southeast"), "CHA": ("east", "southeast"), "MIA": ("east", "southeast"), "ORL": ("east", "southeast"), "WSH": ("east", "southeast"),
        "DEN": ("west", "northwest"), "MIN": ("west", "northwest"), "OKC": ("west", "northwest"), "POR": ("west", "northwest"), "UTAH": ("west", "northwest"),
        "GS": ("west", "pacific"), "LAC": ("west", "pacific"), "LAL": ("west", "pacific"), "PHX": ("west", "pacific"), "SAC": ("west", "pacific"),
        "DAL": ("west", "southwest"), "HOU": ("west", "southwest"), "MEM": ("west", "southwest"), "NO": ("west", "southwest"), "SA": ("west", "southwest"),
    },
    "nhl": {
        "BOS": ("east", "atlantic"), "BUF": ("east", "atlantic"), "DET": ("east", "atlantic"), "FLA": ("east", "atlantic"), "MTL": ("east", "atlantic"), "OTT": ("east", "atlantic"), "TB": ("east", "atlantic"), "TOR": ("east", "atlantic"),
        "CAR": ("east", "metropolitan"), "CBJ": ("east", "metropolitan"), "NJ": ("east", "metropolitan"), "NYI": ("east", "metropolitan"), "NYR": ("east", "metropolitan"), "PHI": ("east", "metropolitan"), "PIT": ("east", "metropolitan"), "WSH": ("east", "metropolitan"),
        "CHI": ("west", "central"), "COL": ("west", "central"), "DAL": ("west", "central"), "MIN": ("west", "central"), "NSH": ("west", "central"), "STL": ("west", "central"), "UTA": ("west", "central"), "WPG": ("west", "central"),
        "ANA": ("west", "pacific"), "CGY": ("west", "pacific"), "EDM": ("west", "pacific"), "LA": ("west", "pacific"), "SEA": ("west", "pacific"), "SJ": ("west", "pacific"), "VAN": ("west", "pacific"), "VGK": ("west", "pacific"),
    },
    "mlb": {
        "BAL": ("al", "al_east"), "BOS": ("al", "al_east"), "NYY": ("al", "al_east"), "TB": ("al", "al_east"), "TOR": ("al", "al_east"),
        "CHW": ("al", "al_central"), "CLE": ("al", "al_central"), "DET": ("al", "al_central"), "KC": ("al", "al_central"), "MIN": ("al", "al_central"),
        "ATH": ("al", "al_west"), "OAK": ("al", "al_west"), "HOU": ("al", "al_west"), "LAA": ("al", "al_west"), "SEA": ("al", "al_west"), "TEX": ("al", "al_west"),
        "ATL": ("nl", "nl_east"), "MIA": ("nl", "nl_east"), "NYM": ("nl", "nl_east"), "PHI": ("nl", "nl_east"), "WSH": ("nl", "nl_east"),
        "CHC": ("nl", "nl_central"), "CIN": ("nl", "nl_central"), "MIL": ("nl", "nl_central"), "PIT": ("nl", "nl_central"), "STL": ("nl", "nl_central"),
        "ARI": ("nl", "nl_west"), "COL": ("nl", "nl_west"), "LAD": ("nl", "nl_west"), "SD": ("nl", "nl_west"), "SF": ("nl", "nl_west"),
    },
}

GLYPHS = {
    "nerd": {
        "tl": "╭", "tr": "╮", "bl": "╰", "br": "┘",
        "tl_round": "╭", "tr_round": "╮", "bl_round": "╰", "br_round": "╯",
        "tl_heavy": "┏", "tr_heavy": "┓", "bl_heavy": "┗", "br_heavy": "┛",
        "h": "─", "v": "│", "h_heavy": "━", "v_heavy": "┃",
        "live": "", "final": "", "pregame": "", "halftime": "",
        "kickoff": "", "period": "",
        "td": "", "fg": "◎", "score": "",
        "red_zone": "", "poss": "",
        "timeout": "", "timeout_used": "",
        "upset": "", "upset_watch": "",
        "fresh": "", "stale": "", "error": "", "loading": "", "refresh": "",
        "star": "★", "dot": "  ·  ", "at": "@", "rank": "#",
        "bar_full": "█", "bar_empty": "░", "spark": "▁▂▃▄▅▆▇█",
    },
    "unicode": {
        "tl": "╭", "tr": "╮", "bl": "╰", "br": "╯",
        "tl_round": "╭", "tr_round": "╮", "bl_round": "╰", "br_round": "╯",
        "tl_heavy": "┏", "tr_heavy": "┓", "bl_heavy": "┗", "br_heavy": "┛",
        "h": "─", "v": "│", "h_heavy": "━", "v_heavy": "┃",
        "live": "●", "final": "■", "pregame": "○", "halftime": "½",
        "kickoff": "⚐", "period": "»",
        "td": "★", "fg": "◆", "score": "•",
        "red_zone": "⚑", "poss": "▶",
        "timeout": "●", "timeout_used": "○",
        "upset": "⚡", "upset_watch": "◉",
        "fresh": "✔", "stale": "⌛", "error": "✖", "loading": "…", "refresh": "↻",
        "star": "★", "dot": "  ·  ", "at": "@", "rank": "#",
        "bar_full": "█", "bar_empty": "░", "spark": "▁▂▃▄▅▆▇█",
    },
    "emoji": {
        "tl": "╭", "tr": "╮", "bl": "╰", "br": "╯",
        "tl_round": "╭", "tr_round": "╮", "bl_round": "╰", "br_round": "╯",
        "tl_heavy": "┏", "tr_heavy": "┓", "bl_heavy": "┗", "br_heavy": "┛",
        "h": "─", "v": "│", "h_heavy": "━", "v_heavy": "┃",
        "live": "🔴", "final": "🏁", "pregame": "🕒", "halftime": "⏸",
        "kickoff": "🚀", "period": "⏭",
        "td": "🏈", "fg": "🎯", "score": "🔔",
        "red_zone": "🔥", "poss": "👉",
        "timeout": "🟢", "timeout_used": "⚪",
        "upset": "⚡", "upset_watch": "👀",
        "fresh": "✅", "stale": "⏳", "error": "❌", "loading": "🔃", "refresh": "🔄",
        "star": "⭐", "dot": "  ·  ", "at": "@", "rank": "#",
        "bar_full": "🟩", "bar_empty": "⬜", "spark": "▁▂▃▄▅▆▇█",
    },
    "ascii": {
        "tl": "+", "tr": "+", "bl": "+", "br": "+",
        "tl_round": "+", "tr_round": "+", "bl_round": "+", "br_round": "+",
        "tl_heavy": "#", "tr_heavy": "#", "bl_heavy": "#", "br_heavy": "#",
        "h": "-", "v": "|", "h_heavy": "=", "v_heavy": "|",
        "live": "*", "final": "F", "pregame": "-", "halftime": "H",
        "kickoff": ">", "period": ">>",
        "td": "#", "fg": "^", "score": "*",
        "red_zone": "!!", "poss": ">",
        "timeout": "o", "timeout_used": ".",
        "upset": "!!!", "upset_watch": "?",
        "fresh": "ok", "stale": "~", "error": "x", "loading": "...", "refresh": "@",
        "star": "*", "dot": "  -  ", "at": "@", "rank": "#",
        "bar_full": "#", "bar_empty": "-", "spark": "_.:-=+*#",
    },
}


# --------------------------------------------------------------------------
# plumbing
# --------------------------------------------------------------------------

def fetch_json(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def dig(obj, *path, default=None):
    cur = obj
    for p in path:
        if isinstance(cur, dict):
            cur = cur.get(p)
        elif isinstance(cur, (list, tuple)) and isinstance(p, int) and -len(cur) <= p < len(cur):
            cur = cur[p]
        else:
            return default
        if cur is None:
            return default
    return cur


def parse_iso(text):
    if not text:
        return None
    try:
        return dt.datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone()
    except ValueError:
        return None


def today():
    return dt.date.today()


def format_age(seconds):
    if seconds is None:
        return "0s"
    s = max(0, int(round(seconds)))
    if s < 60:
        return "%ds" % s
    m, sec = divmod(s, 60)
    return "%dm %ds" % (m, sec) if sec else "%dm" % m


def period_label(lg_key, period):
    if not period:
        return ""
    lg = BY_KEY.get(lg_key, LEAGUES[0])
    reg = lg.get("reg_periods", 4)
    prefix = lg.get("period_prefix", "Q")
    if lg_key == "mlb":
        return "Inn %d" % period
    if period > reg + 1:
        return "%dOT" % (period - reg)
    if period > reg:
        return "OT"
    return "%s%d" % (prefix, period)


def copy_to_clipboard(text):
    for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]):
        if shutil.which(cmd[0]):
            try:
                subprocess.run(cmd, input=text.encode("utf-8"), check=True, timeout=3)
                return True
            except Exception:  # noqa: BLE001
                continue
    return False


# --------------------------------------------------------------------------
# parsers
# --------------------------------------------------------------------------

def scoreboard_url(lg, date, week=None):
    url = "%s/%s/scoreboard?limit=250" % (SITE, lg["path"])
    if lg["key"] == "cfb":
        url += "&groups=80"
    elif lg["key"] == "cbb":
        url += "&groups=50"
    if week is not None and lg["key"] in ("cfb", "nfl"):
        url += "&week=%d" % week
    elif date is not None:
        url += "&dates=" + date.strftime("%Y%m%d")
    return url


def parse_side(comp):
    team = comp.get("team") or {}
    records = comp.get("records") or []
    rec = ""
    for r in records:
        if (r.get("type") or "").lower() in ("total", "overall") or (r.get("name") or "").lower() == "overall":
            rec = r.get("summary") or ""
            break
    if not rec and records:
        rec = records[0].get("summary") or ""
    rank = dig(comp, "curatedRank", "current")
    if rank in (0, 99, None) or (isinstance(rank, int) and rank < 0):
        rank = None
    score_raw = comp.get("score")
    try:
        score_int = int(float(score_raw)) if score_raw is not None and score_raw != "" else 0
    except (TypeError, ValueError):
        score_int = 0
    return {
        "id": str(team.get("id") or ""),
        "abbr": team.get("abbreviation") or team.get("shortDisplayName") or "?",
        "name": team.get("shortDisplayName") or team.get("location") or team.get("name") or "?",
        "full": team.get("displayName") or team.get("shortDisplayName") or "?",
        "color": (team.get("color") or "444444").lstrip("#"),
        "alt_color": (team.get("alternateColor") or "888888").lstrip("#"),
        "score": str(score_int) if score_raw is not None else "0",
        "score_int": score_int,
        "record": rec,
        "rank": rank,
        "winner": bool(comp.get("winner")),
        "logo": dig(team, "logo"),
        "conf_id": str(team.get("conferenceId") or ""),
    }


def spread_text(odds):
    if not odds:
        return ""
    details = (odds.get("details") or "").strip()
    if details:
        return details
    spread = odds.get("spread")
    if spread is None:
        return ""
    side = ""
    fav = odds.get("awayTeamOdds") or {}
    if fav.get("favorite") is True:
        side = "away"
    elif (odds.get("homeTeamOdds") or {}).get("favorite") is True:
        side = "home"
    try:
        num = abs(float(spread))
    except (TypeError, ValueError):
        return ""
    label = ("%.1f" % num).rstrip("0").rstrip(".")
    return ("%s -%s" % (side.upper(), label)) if side else "-" + label


def parse_situation(raw):
    if not isinstance(raw, dict):
        return None
    return {
        "down": raw.get("down"),
        "distance": raw.get("distance"),
        "yard_line": raw.get("yardLine"),
        "red_zone": raw.get("isRedZone") is True,
        "possession": str(raw.get("possession") or "") or None,
        "home_timeouts": raw.get("homeTimeouts"),
        "away_timeouts": raw.get("awayTimeouts"),
        "down_dist": (raw.get("downDistanceText") or "").strip(),
        "poss_text": (raw.get("possessionText") or "").strip(),
        "last_play": (dig(raw, "lastPlay", "text") or "").strip(),
    }


def evaluate_upset(away, home, state, odds=None):
    """Evaluate upset / upset watch using poll ranks first, or heavy spread (>= 7.5)."""
    if state == "pre":
        return None
    sa, sh = away["score_int"], home["score_int"]
    if sa == sh:
        return None
    leader, trailer = (away, home) if sa > sh else (home, away)
    ra, rh = leader.get("rank"), trailer.get("rank")
    confirmed = state == "post"
    # Ranked upset: trailer is ranked and leader is either unranked or worse-ranked
    if rh is not None and (ra is None or ra > rh):
        return {"underdog": leader, "favorite": trailer, "confirmed": confirmed, "margin": abs(sa - sh)}
    # Pro/unranked upset: check if pregame spread had trailer favored by >= 7.5 points
    if odds and rh is None and ra is None:
        details = (odds.get("details") or "").strip().split()
        if len(details) == 2 and details[0] == trailer["abbr"]:
            try:
                pts = abs(float(details[1]))
                if pts >= 7.5:
                    return {"underdog": leader, "favorite": trailer, "confirmed": confirmed, "margin": abs(sa - sh)}
            except ValueError:
                pass
    return None


def parse_game(ev, lg):
    comp = dig(ev, "competitions", 0, default={}) or {}
    status_obj = comp.get("status") or ev.get("status") or {}
    status = status_obj.get("type") or {}
    sides = {}
    for c in comp.get("competitors") or []:
        ha = c.get("homeAway")
        if ha in ("home", "away"):
            sides[ha] = parse_side(c)
    if "home" not in sides or "away" not in sides:
        return None
    odds = (comp.get("odds") or [{}])[0]
    broadcasts = comp.get("broadcasts") or []
    tv = ", ".join(dig(b, "names", 0, default="") for b in broadcasts if dig(b, "names", 0)).strip(", ")
    state = status.get("state") or "pre"
    status_name = status.get("name") or "STATUS_SCHEDULED"
    period = status_obj.get("period") or 0
    clock = status_obj.get("displayClock") or ""
    sit = parse_situation(comp.get("situation"))
    upset = evaluate_upset(sides["away"], sides["home"], state, odds)
    return {
        "id": str(ev.get("id")),
        "league": lg["key"],
        "start": parse_iso(ev.get("date") or comp.get("date")),
        "week": dig(ev, "week", "number"),
        "state": state,
        "status_name": status_name,
        "detail": status.get("detail") or "",
        "short": status.get("shortDetail") or "",
        "clock": clock,
        "period": period,
        "is_halftime": status_name == "STATUS_HALFTIME" or "halftime" in (status.get("shortDetail") or "").lower(),
        "is_overtime": period > lg.get("reg_periods", 4) or "ot" in (status.get("shortDetail") or "").lower(),
        "away": sides["away"],
        "home": sides["home"],
        "odds": odds,
        "situation": sit,
        "upset": upset,
        "venue": dig(comp, "venue", "fullName", default="") or "",
        "tv": tv,
    }


def parse_board(lg, date, week=None):
    data = fetch_json(scoreboard_url(lg, date, week=week))
    games = []
    board_week = dig(data, "week", "number")
    for ev in data.get("events") or []:
        g = parse_game(ev, lg)
        if g:
            if board_week and not g.get("week"):
                g["week"] = board_week
            games.append(g)
    return games


def parse_all_boards(date):
    """Fetch and aggregate scoreboard games from all sports concurrently."""
    all_games = []

    def _fetch(lg):
        try:
            return parse_board(lg, date)
        except Exception:
            return []

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(SPORT_LEAGUES)) as ex:
        for g_list in ex.map(_fetch, SPORT_LEAGUES):
            if g_list:
                all_games.extend(g_list)

    return all_games


def parse_rankings(lg):
    data = fetch_json("%s/%s/rankings" % (SITE, lg["path"]))
    polls = []
    week_num = dig(data, "latestWeek", "number")
    for poll in data.get("rankings") or []:
        ptype = (poll.get("type") or "").lower()
        name = poll.get("name") or ""
        if any(w in name for w in ("FCS", "Division II", "Division III")):
            continue
        if lg["key"] == "cfb":
            if ptype not in ("ap", "usa", "coaches", "cfp") and "coaches" not in name.lower() and "playoff" not in name.lower():
                continue
        elif ptype not in ("ap", "usa", "coaches") and "coaches" not in name.lower():
            continue
        ranks = []
        for r in poll.get("ranks") or []:
            team = r.get("team") or {}
            ranks.append({
                "rank": r.get("current") or 0,
                "prev": r.get("previous") or 0,
                "team": team.get("location") or team.get("shortDisplayName") or team.get("nickname") or "?",
                "abbr": team.get("abbreviation") or "",
                "color": (team.get("color") or "444444").lstrip("#"),
                "record": r.get("recordSummary") or "",
                "points": r.get("points") or 0,
                "first": r.get("firstPlaceVotes") or 0,
                "trend": r.get("trend") or "",
            })
        if ranks:
            pweek = dig(poll, "occurrence", "number") or week_num
            polls.append({"name": name, "type": ptype, "week": pweek, "ranks": ranks})
    return polls


def parse_standings(lg):
    data = fetch_json("%s/%s/standings" % (CORE, lg["path"]))
    groups = []
    seen = set()

    def walk(node):
        if not isinstance(node, dict):
            return
        entries = dig(node, "standings", "entries")
        name = node.get("name") or node.get("abbreviation") or ""
        if entries and name and name not in seen:
            seen.add(name)
            rows = []
            for e in entries:
                team = e.get("team") or {}
                stats = {}
                for s in e.get("stats") or []:
                    nm = s.get("name") or ""
                    tp = s.get("type") or ""
                    val = s.get("displayValue")
                    # Keep the first (unprefixed overall) stat for each name so splits don't overwrite it
                    if nm and nm not in stats:
                        stats[nm] = val
                    if tp and tp not in stats:
                        stats[tp] = val
                rows.append({
                    "team": team.get("shortDisplayName") or team.get("location") or team.get("name") or "?",
                    "abbr": team.get("abbreviation") or "",
                    "color": (team.get("color") or "444444").lstrip("#"),
                    "stats": stats,
                })

            def parse_rec_pct(rec_str):
                if not rec_str or "-" not in str(rec_str):
                    return (-1.0, 0.0)
                parts = str(rec_str).split("-")
                try:
                    w = float(parts[0])
                    l = float(parts[1])
                    return (w / (w + l) if (w + l) > 0 else 0.0, w)
                except ValueError:
                    return (-1.0, 0.0)

            def order(row):
                st = row["stats"]
                if lg["key"] in ("cfb", "cbb"):
                    conf_pct, conf_w = parse_rec_pct(st.get("vs. Conf.") or st.get("vsconf"))
                    ovr_pct, ovr_w = parse_rec_pct(st.get("overall") or st.get("total"))
                    return (-conf_pct, -conf_w, -ovr_pct, -ovr_w, row["team"])
                if lg["key"] == "nhl":
                    try:
                        pts = float(st.get("points") or 0)
                    except (TypeError, ValueError):
                        pts = 0.0
                    try:
                        wins = float(st.get("wins") or 0)
                    except (TypeError, ValueError):
                        wins = 0.0
                    return (-pts, -wins, row["team"])
                try:
                    pct = float(st.get("winPercent") or -1)
                except (TypeError, ValueError):
                    pct = -1.0
                try:
                    wins = float(st.get("wins") or 0)
                except (TypeError, ValueError):
                    wins = 0.0
                return (-pct, -wins, row["team"])

            rows.sort(key=order)
            groups.append({"name": name, "rows": rows})
        for child in node.get("children") or []:
            walk(child)

    if isinstance(data, list):
        for item in data:
            walk(item)
    else:
        walk(data)
    return groups


STANDING_COLS = {
    "nba": [("wins", "W"), ("losses", "L"), ("winPercent", "PCT"), ("gamesBehind", "GB"), ("streak", "STRK")],
    "nhl": [("wins", "W"), ("losses", "L"), ("otLosses", "OTL"), ("points", "PTS"), ("streak", "STRK")],
    "mlb": [("wins", "W"), ("losses", "L"), ("winPercent", "PCT"), ("gamesBehind", "GB"), ("streak", "STRK")],
    "nfl": [("wins", "W"), ("losses", "L"), ("ties", "T"), ("winPercent", "PCT"), ("streak", "STRK")],
    "cfb": [("vs. Conf.", "CONF"), ("overall", "OVR"), ("pointDifferential", "DIFF"), ("streak", "STRK")],
    "cbb": [("vs. Conf.", "CONF"), ("overall", "OVR"), ("pointDifferential", "DIFF"), ("streak", "STRK")],
}


def parse_detail(lg, event_id):
    url = "%s/%s/summary?event=%s" % (SITE, lg["path"], event_id)
    data = fetch_json(url)
    # 1. Scoring plays: check scoringPlays (CFB/NFL) then plays with scoringPlay=True (NBA/NHL/CBB/MLB)
    raw_plays = data.get("scoringPlays") or [p for p in (data.get("plays") or []) if p.get("scoringPlay")]
    plays = []
    for p in raw_plays:
        clock = dig(p, "clock", "displayValue", default="") or ""
        period = dig(p, "period", "number", default=0) or 0
        period_disp = dig(p, "period", "displayValue", default="") or ""
        team = dig(p, "team", "abbreviation", default="") or ""
        stype = (dig(p, "scoringType", "name", default="") or dig(p, "type", "text", default="") or "").lower()
        plays.append({
            "clock": clock,
            "period": period,
            "period_disp": period_disp,
            "team": team,
            "stype": stype,
            "text": (p.get("text") or "").strip(),
            "away_score": p.get("awayScore"),
            "home_score": p.get("homeScore"),
        })

    # 2. Linescores (Score by period)
    header_comp = dig(data, "header", "competitions", 0, default={}) or {}
    linescores = {"away": [], "home": []}
    for c in header_comp.get("competitors") or []:
        ha = c.get("homeAway")
        if ha in ("away", "home"):
            ls = []
            for q in c.get("linescores") or []:
                val = q.get("displayValue")
                if val is not None and val != "":
                    ls.append(str(val))
            linescores[ha] = ls

    # 3. Team Stats comparison
    team_stats = {}
    for tm in dig(data, "boxscore", "teams", default=[]) or []:
        abbr = dig(tm, "team", "abbreviation", default="") or ""
        st_map = {}
        for s in tm.get("statistics") or []:
            nm = s.get("name") or ""
            lbl = s.get("label") or nm
            dv = s.get("displayValue") or ""
            if nm and dv:
                st_map[nm] = (lbl, str(dv))
        if abbr and st_map:
            team_stats[abbr] = st_map

    # 4. Leaders
    leaders = []
    for tm in data.get("leaders") or []:
        abbr = dig(tm, "team", "abbreviation", default="") or ""
        color = (dig(tm, "team", "color", default="444444") or "444444").lstrip("#")
        cats = []
        for cat in tm.get("leaders") or []:
            top = (cat.get("leaders") or [{}])[0]
            who = (dig(top, "athlete", "displayName") or top.get("displayName") or "").strip()
            val = (top.get("displayValue") or "").strip()
            cname = (cat.get("shortDisplayName") or cat.get("displayName") or cat.get("name") or "")[:8]
            if who and val:
                cats.append((cname, who, val))
        if cats:
            leaders.append({"abbr": abbr, "color": color, "cats": cats})

    # 5. Win probability & series for sparkline
    winprob = None
    wp_series = []
    for pt in data.get("winprobability") or []:
        hp = pt.get("homeWinPercentage")
        if hp is not None:
            try:
                wp_series.append(float(hp))
            except (TypeError, ValueError):
                pass
    if wp_series:
        winprob = (1.0 - wp_series[-1], wp_series[-1])

    # 6. Venue & Info
    venue = dig(data, "gameInfo", "venue", "fullName") or ""
    city = dig(data, "gameInfo", "venue", "address", "city") or ""
    state = dig(data, "gameInfo", "venue", "address", "state") or ""
    loc = ", ".join(x for x in (venue, city, state) if x)
    recap = (dig(data, "article", "headline") or "").strip()

    return {
        "plays": plays,
        "linescores": linescores,
        "team_stats": team_stats,
        "leaders": leaders,
        "winprob": winprob,
        "wp_series": wp_series,
        "location": loc,
        "recap": recap,
    }


def parse_news(lg):
    url = "%s/%s/news?limit=25" % (SITE, lg["path"])
    data = fetch_json(url)
    items = []
    for art in data.get("articles") or []:
        if (art.get("type") or "").lower() == "media":
            continue
        headline = (art.get("headline") or "").strip()
        if not headline:
            continue
        desc = (art.get("description") or "").strip()
        pub = parse_iso(art.get("published"))
        web_url = dig(art, "links", "web", "href") or ""
        story_url = dig(art, "links", "api", "news", "href") or dig(art, "links", "api", "self", "href") or ""
        teams = []
        seen_t = set()
        for cat in art.get("categories") or []:
            if cat.get("type") == "team":
                tn = dig(cat, "team", "abbreviation") or dig(cat, "team", "shortDisplayName") or cat.get("description") or ""
                if tn and tn not in seen_t:
                    seen_t.add(tn)
                    teams.append(tn)
        items.append({
            "id": str(art.get("id") or headline),
            "headline": headline,
            "description": desc,
            "published": pub,
            "web_url": web_url,
            "story_url": story_url,
            "teams": teams[:4],
        })
    return items


def strip_html(raw_html):
    text = re.sub(r"<(p|br|div|li|h[1-6])[^>]*>", "\n", raw_html or "", flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    lines = [line.strip() for line in text.splitlines()]
    return "\n\n".join(line for line in lines if line)


# --------------------------------------------------------------------------
# fetching off the UI thread
# --------------------------------------------------------------------------

class Fetcher:
    def __init__(self):
        self.req = queue.Queue()
        self.res = queue.Queue()
        self.inflight = set()
        self.lock = threading.Lock()
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def request(self, key, fn):
        with self.lock:
            if key in self.inflight:
                return
            self.inflight.add(key)
        self.req.put((key, fn))

    def is_busy(self):
        with self.lock:
            return bool(self.inflight)

    def _run(self):
        while True:
            key, fn = self.req.get()
            try:
                value, err = fn(), None
            except Exception as exc:  # noqa: BLE001
                value, err = None, "%s: %s" % (type(exc).__name__, exc)
            self.res.put((key, value, err))

    def poll(self):
        out = []
        while True:
            try:
                out.append(self.res.get_nowait())
            except queue.Empty:
                break
        with self.lock:
            for key, _, _ in out:
                self.inflight.discard(key)
        return out


# --------------------------------------------------------------------------
# colours (cfbtui WCAG luminance + full-bleed team background bars)
# --------------------------------------------------------------------------

def hex_rgb(value):
    value = (value or "").strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        return (68, 68, 68)
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (68, 68, 68)


def wcag_luminance(value):
    r, g, b = hex_rgb(value)

    def chan(v):
        s = v / 255.0
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def hex_brightness(value):
    """Perceived brightness (0..1), matching Textual's Color.brightness split at 0.5."""
    r, g, b = hex_rgb(value)
    return (299 * r + 587 * g + 114 * b) / 255000.0


def hex_to_xterm(value):
    r, g, b = hex_rgb(value)
    if max(r, g, b) - min(r, g, b) < 12:
        if r < 8:
            return 16
        if r > 245:
            return 231
        grey = int(round((r - 8) / 10.0))
        return 232 + max(0, min(23, grey))
    steps = (0, 95, 135, 175, 215, 255)

    def near(v):
        return min(range(6), key=lambda i: abs(steps[i] - v))

    return 16 + 36 * near(r) + 6 * near(g) + near(b)


def xterm_to_rgb(code):
    if code == 16:
        return (0, 0, 0)
    if code == 231:
        return (255, 255, 255)
    if 232 <= code <= 255:
        v = 8 + (code - 232) * 10
        return (v, v, v)
    if 16 <= code <= 231:
        idx = code - 16
        steps = (0, 95, 135, 175, 215, 255)
        return (steps[idx // 36], steps[(idx % 36) // 6], steps[idx % 6])
    return (136, 136, 136)


BASIC = [
    (curses.COLOR_BLACK, (0, 0, 0)), (curses.COLOR_RED, (205, 49, 49)),
    (curses.COLOR_GREEN, (13, 188, 121)), (curses.COLOR_YELLOW, (229, 229, 16)),
    (curses.COLOR_BLUE, (36, 114, 200)), (curses.COLOR_MAGENTA, (188, 63, 188)),
    (curses.COLOR_CYAN, (17, 168, 205)), (curses.COLOR_WHITE, (229, 229, 229)),
]


def hex_to_basic(value):
    r, g, b = hex_rgb(value)
    best, dist = curses.COLOR_BLUE, None
    for code, (br, bg, bb) in BASIC:
        d = (r - br) ** 2 + (g - bg) ** 2 + (b - bb) ** 2
        if dist is None or d < dist:
            best, dist = code, d
    return best


def readable_fg_xterm(value):
    """Readable foreground xterm color on a dark terminal background."""
    r, g, b = hex_rgb(value)
    if (299 * r + 587 * g + 114 * b) / 255000.0 < 0.28:
        r = min(255, r + 95)
        g = min(255, g + 95)
        b = min(255, b + 95)
        return hex_to_xterm("%02x%02x%02x" % (r, g, b))
    return hex_to_xterm(value)


# --------------------------------------------------------------------------
# terminal display width utilities
# --------------------------------------------------------------------------

try:
    import wcwidth
    _wcwidth_func = wcwidth.wcwidth
except ImportError:
    _wcwidth_func = None


def char_width(c):
    """Visual display width of a single character in terminal columns."""
    if not c:
        return 0
    if _wcwidth_func is not None:
        w = _wcwidth_func(c)
        if w >= 0:
            return w
    if ord(c) < 32 or 0x7F <= ord(c) < 0xA0:
        return 0
    if unicodedata.combining(c):
        return 0
    if unicodedata.east_asian_width(c) in ("W", "F"):
        return 2
    return 1


def str_width(s):
    """Visual display width of a string in terminal columns."""
    if not s:
        return 0
    return sum(char_width(c) for c in s)


def clip_to_width(s, max_w):
    """Clip a string so its visual display width does not exceed max_w."""
    if not s or max_w <= 0:
        return ""
    cur_w = 0
    out = []
    for c in s:
        w = char_width(c)
        if cur_w + w > max_w:
            break
        out.append(c)
        cur_w += w
    return "".join(out)


def team_row_prefix(lead, star, rank_num):
    """Build the exact 8-visual-column team row prefix (7 cols prefix + 1 space before abbr).

    Visual layout (7 columns of prefix + 1 space before abbreviation):
      - Lead indicator (possession glyph) and star (favorite glyph) cluster on the left.
      - Rank number (e.g. '#12') right-aligned on the right of the 7-column prefix.
      - Trailing space before the team abbreviation.
    Total visual display width is guaranteed to be exactly 8 columns.
    """
    lead_s = lead.strip() if lead else ""
    star_s = star.strip() if star else ""
    rk_s = f"#{rank_num}" if rank_num else ""
    target_prefix_w = 7
    rk_w = str_width(rk_s)
    avail = max(0, target_prefix_w - rk_w)

    icons = ""
    if lead_s and star_s:
        cand = lead_s + star_s
        if str_width(cand) <= avail:
            icons = cand
        elif str_width(star_s) <= avail:
            icons = star_s
        elif str_width(lead_s) <= avail:
            icons = lead_s
    elif lead_s:
        if str_width(lead_s) + 1 <= avail:
            icons = " " + lead_s
        elif str_width(lead_s) <= avail:
            icons = lead_s
    elif star_s:
        if str_width(star_s) + 2 <= avail:
            icons = "  " + star_s
        elif str_width(star_s) + 1 <= avail:
            icons = " " + star_s
        elif str_width(star_s) <= avail:
            icons = star_s

    cur_w = str_width(icons) + rk_w
    pad = max(0, target_prefix_w - cur_w)
    prefix_7 = icons + (" " * pad) + rk_s
    if str_width(prefix_7) > target_prefix_w:
        prefix_7 = clip_to_width(prefix_7, target_prefix_w)
        rem = target_prefix_w - str_width(prefix_7)
        if rem > 0:
            prefix_7 += " " * rem
    return prefix_7 + " "


def timeouts_str(glyphs, remaining, league="cfb"):
    """Render remaining timeouts as a row of dots matching cfbtui; empty when unknown."""
    if remaining is None:
        return ""
    try:
        rem_val = int(remaining)
    except (TypeError, ValueError):
        return ""
    if rem_val < 0:
        return ""
    default_total = 1 if league == "nhl" else 3
    total = max(default_total, rem_val)
    rem = max(0, min(total, rem_val))
    used = total - rem
    t_dot = glyphs.get("timeout", "●")
    u_dot = glyphs.get("timeout_used", "○")
    return (t_dot * rem) + (u_dot * used)


# --------------------------------------------------------------------------
# application
# --------------------------------------------------------------------------

class App:
    def __init__(self, scr, opts):
        self.scr = scr
        self.opts = opts
        self.fetcher = Fetcher()
        self.cache = {}          # key -> (time, value, err)
        self.cfg = self.load_config()
        self.favs = set(self.cfg.get("favorites") or DEFAULT_FAVORITES)
        self.only = getattr(opts, "only", None)
        if self.only not in BY_KEY:
            self.only = None
        self.league_key = self.only or opts.league or self.cfg.get("league") or "cfb"
        if self.league_key not in BY_KEY:
            self.league_key = "cfb"
        self.date = opts.date or today()
        self.week = getattr(opts, "week", None)
        self.layout = opts.layout or self.cfg.get("layout") or "grid"
        self.glyphs = opts.glyphs or self.cfg.get("glyphs") or "nerd"
        self.view = "board"          # board | extra | detail | news | help | group_picker
        self.filter = "all"
        self.group_filter = None     # conference or division ID/key
        self.group_name = None       # human display name
        self.picker_sel = 0
        self.picker_scroll = 0
        self.sel_id = None
        self.scroll = 0
        self.extra_kind = None       # ranks | stand
        self.extra_tab = 0
        self.extra_group = 0
        self.extra_sel = 0
        self.extra_scroll = 0
        self.detail_game = None
        self.detail_scroll = 0
        self.news_sel = 0
        self.news_scroll = 0
        self.news_story = None       # None or (headline, body_text, web_url)
        self.notice = ("", 0.0)
        self.last_error = ""
        self.init_colors()
        if self.scr:
            try:
                curses.curs_set(0)
            except curses.error:
                pass
            self.scr.keypad(True)
            self.scr.timeout(200)

    # -- config ------------------------------------------------------------
    def load_config(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {"favorites": list(DEFAULT_FAVORITES)}

    def save_config(self):
        data = {
            "league": self.league_key,
            "layout": self.layout,
            "glyphs": self.glyphs,
            "favorites": sorted(self.favs),
        }
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
                fh.write("\n")
        except OSError:
            pass

    # -- colours -----------------------------------------------------------
    def init_colors(self):
        if not self.scr:
            self.colours = False
            self.pairs = {}
            return
        try:
            self.colours = curses.has_colors()
        except curses.error:
            self.colours = False
            self.pairs = {}
            return
        self.pairs = {}
        self.next_pair = 20
        if not self.colours:
            return
        try:
            curses.start_color()
            curses.use_default_colors()
        except curses.error:
            pass
        if curses.COLORS >= 256:
            self.fg, self.dim, self.live = 252, 244, 203
            self.accent, self.good, self.focus_col = 214, 114, 81
            self.bg_sel, self.bg_panel = 236, 235
        else:
            self.fg, self.dim, self.live = curses.COLOR_WHITE, curses.COLOR_CYAN, curses.COLOR_RED
            self.accent, self.good, self.focus_col = curses.COLOR_YELLOW, curses.COLOR_GREEN, curses.COLOR_CYAN
            self.bg_sel, self.bg_panel = curses.COLOR_BLUE, curses.COLOR_BLACK

    def pair(self, fg, bg=-1):
        if not self.colours:
            return curses.A_NORMAL
        key = (fg, bg)
        if key in self.pairs:
            return curses.color_pair(self.pairs[key])
        if self.next_pair > curses.COLOR_PAIRS - 1:
            return curses.A_NORMAL
        try:
            curses.init_pair(self.next_pair, fg, bg)
        except curses.error:
            return curses.A_NORMAL
        self.pairs[key] = self.next_pair
        self.next_pair += 1
        return curses.color_pair(self.pairs[key])

    def team_bar_attr(self, colour, bold=False, dim=False):
        """cfbtui's signature look: full-bleed team background color bar with high-contrast text."""
        if not self.colours:
            return curses.A_BOLD if bold else curses.A_NORMAL
        if curses.COLORS >= 256:
            bg = hex_to_xterm(colour)
            r, g, b = xterm_to_rgb(bg)
            bright = (299 * r + 587 * g + 114 * b) / 255000.0
            fg = 16 if bright > 0.5 else 231
            attr = self.pair(fg, bg)
        else:
            bg = hex_to_basic(colour)
            fg = curses.COLOR_BLACK if bg in (curses.COLOR_YELLOW, curses.COLOR_WHITE, curses.COLOR_CYAN, curses.COLOR_GREEN) else curses.COLOR_WHITE
            attr = self.pair(fg, bg)
        if bold:
            attr |= curses.A_BOLD
        elif dim:
            attr |= curses.A_DIM
        return attr

    def team_fg_attr(self, colour, bold=False):
        """Readable foreground color on dark terminal background (for sparklines & stat bars)."""
        if not self.colours:
            return curses.A_BOLD if bold else curses.A_NORMAL
        code = readable_fg_xterm(colour) if curses.COLORS >= 256 else hex_to_basic(colour)
        attr = self.pair(code)
        if bold:
            attr |= curses.A_BOLD
        return attr

    def attr(self, kind):
        if not self.colours:
            return curses.A_BOLD if kind in ("live", "accent", "focus") else curses.A_NORMAL
        if kind == "base":
            return self.pair(self.fg)
        if kind == "dim":
            return self.pair(self.dim)
        if kind == "live":
            return self.pair(self.live) | curses.A_BOLD
        if kind == "accent":
            return self.pair(self.accent) | curses.A_BOLD
        if kind == "good":
            return self.pair(self.good) | curses.A_BOLD
        if kind == "focus":
            return self.pair(self.focus_col) | curses.A_BOLD
        if kind == "section":
            return self.pair(self.dim) | curses.A_BOLD
        if kind == "panel":
            return self.pair(self.dim, self.bg_panel) if curses.COLORS >= 256 else self.pair(self.dim)
        if kind == "key":
            return (self.pair(self.accent, self.bg_panel) if curses.COLORS >= 256 else self.pair(self.accent)) | curses.A_BOLD
        if kind == "key_label":
            return self.pair(self.fg, self.bg_panel) if curses.COLORS >= 256 else self.pair(self.fg)
        if kind == "bar":
            return (self.pair(16, self.focus_col) if curses.COLORS >= 256 else curses.A_REVERSE) | curses.A_BOLD
        return curses.A_NORMAL

    # -- data --------------------------------------------------------------
    def cache_get(self, key):
        ent = self.cache.get(key)
        return ent[1] if ent else None

    def ensure(self, key, fn, ttl):
        ent = self.cache.get(key)
        now = time.time()
        if ent and now - ent[0] < ttl:
            return ent[1]
        self.fetcher.request(key, fn)
        return ent[1] if ent else None

    def ttl(self, games):
        live = any(g["state"] == "in" for g in (games or []))
        return 20 if live else 60

    def board_key(self):
        if self.week is not None and self.league_key in ("cfb", "nfl"):
            return "board:%s:w%d" % (self.league_key, self.week)
        return "board:%s:%s" % (self.league_key, self.date.isoformat())

    def pump(self):
        for key, value, err in self.fetcher.poll():
            if err:
                self.last_error = err
                if key not in self.cache:
                    self.cache[key] = (time.time(), None, err)
                else:
                    ts, old, _ = self.cache[key]
                    self.cache[key] = (ts, old, err)
            else:
                self.last_error = ""
                self.cache[key] = (time.time(), value, None)

    # -- helpers -----------------------------------------------------------
    def lg(self):
        return BY_KEY[self.league_key]

    def g(self):
        return GLYPHS.get(self.glyphs, GLYPHS["unicode"])

    def kickoff_str(self, start_dt):
        if start_dt is None:
            return ""
        et = start_dt.astimezone(EASTERN)
        far = abs((et.date() - today()).days) > 5
        fmt = "%a %b %-d %-I:%M %p ET" if far else "%a %-I:%M %p ET"
        return et.strftime(fmt)

    def status_text(self, game):
        g = self.g()
        if game["state"] == "in":
            if game.get("is_halftime"):
                return "%s Halftime" % g["halftime"]
            pl = period_label(game["league"], game.get("period"))
            clk = game.get("clock") or ""
            if pl and clk and game["league"] != "mlb":
                return "%s %s %s" % (g["live"], pl, clk)
            return "%s %s" % (g["live"], game["short"] or game["detail"] or "Live")
        if game["state"] == "post":
            ot = "/OT" if game.get("is_overtime") and "ot" not in (game["short"] or "").lower() else ""
            base = game["short"] or "Final"
            return "%s %s%s" % (g["final"], base, ot)
        if game.get("status_name") not in ("STATUS_SCHEDULED", None, ""):
            return "%s %s" % (g["pregame"], game["short"] or game["detail"])
        return "%s %s" % (g["pregame"], self.kickoff_str(game["start"]))

    def extra_text(self, game):
        if game["state"] == "pre":
            sp = spread_text(game["odds"])
            return sp if sp else (game.get("tv") or "").split(",")[0]
        if game["state"] == "in":
            sit = game.get("situation")
            if sit and sit.get("down_dist"):
                return sit["down_dist"]
        return ""

    def is_fav(self, side, game=None):
        lg = (game.get("league") if game else None) or self.league_key
        if lg != "all":
            return "%s:%s" % (lg, side["abbr"]) in self.favs
        return any(f.endswith(":" + side["abbr"]) for f in self.favs)

    def game_fav(self, game):
        return self.is_fav(game["away"], game) or self.is_fav(game["home"], game)

    def visible(self, games):
        rows = list(games or [])
        if self.group_filter and self.group_filter != "all":
            if self.league_key in ("cfb", "cbb"):
                rows = [g for g in rows if g["away"].get("conf_id") == self.group_filter or g["home"].get("conf_id") == self.group_filter]
            elif self.league_key != "all":
                mapping = PRO_TEAM_GROUPS.get(self.league_key, {})
                rows = [
                    g for g in rows
                    if self.group_filter in mapping.get(g["away"]["abbr"], ()) or self.group_filter in mapping.get(g["home"]["abbr"], ())
                ]
        if self.filter == "live":
            rows = [g for g in rows if g["state"] == "in"]
        elif self.filter == "top25":
            rows = [g for g in rows if g["away"]["rank"] or g["home"]["rank"]]
        elif self.filter == "fav":
            rows = [g for g in rows if self.game_fav(g)]
        elif self.filter == "upsets":
            rows = [g for g in rows if g.get("upset")]
        order = {"in": 0, "pre": 1, "post": 2}
        rows.sort(key=lambda g: (
            0 if self.game_fav(g) else 1,
            order.get(g["state"], 3),
            g["start"] or dt.datetime.max.replace(tzinfo=dt.timezone.utc),
            g["id"],
        ))
        return rows

    def selected_index(self, rows):
        for i, row in enumerate(rows):
            if row["id"] == self.sel_id:
                return i
        return 0

    def say(self, text, secs=3.0):
        self.notice = (text, time.time() + secs)

    # -- drawing primitives ------------------------------------------------
    def put(self, y, x, text, attr=curses.A_NORMAL, width=None, reverse=False):
        if y < 0 or x < 0:
            return
        h, w = self.scr.getmaxyx()
        if y >= h or x >= w:
            return
        limit = w - x if width is None else min(width, w - x)
        if limit <= 0:
            return
        text = clip_to_width(text, limit)
        if reverse:
            attr |= curses.A_REVERSE
        try:
            self.scr.addstr(y, x, text, attr)
        except curses.error:
            pass

    def segment(self, y, x, segs, width, reverse=False):
        for text, attr in segs:
            if width <= 0:
                break
            text = clip_to_width(text, width)
            self.put(y, x, text, attr, reverse=reverse)
            tw = str_width(text)
            x += tw
            width -= tw

    def fill_line(self, y, x, width, attr):
        self.put(y, x, " " * max(0, width), attr, width=width)

    def clear_line(self, y, attr=curses.A_NORMAL):
        h, w = self.scr.getmaxyx()
        if y < 0 or y >= h:
            return
        try:
            self.scr.move(y, 0)
            self.scr.clrtoeol()
            if attr != curses.A_NORMAL:
                self.scr.addstr(y, 0, " " * max(0, w - 1), attr)
        except curses.error:
            pass

    def draw_box(self, y, x, height, width, border_attr, title="", heavy=False):
        g = self.g()
        tl = g["tl_heavy"] if heavy else g["tl_round"]
        tr = g["tr_heavy"] if heavy else g["tr_round"]
        bl = g["bl_heavy"] if heavy else g["bl_round"]
        br = g["br_heavy"] if heavy else g["br_round"]
        hz = g["h_heavy"] if heavy else g["h"]
        vt = g["v_heavy"] if heavy else g["v"]
        inner = max(0, width - 2)
        if title:
            title_clipped = clip_to_width(title, max(0, inner - 4))
            t_str = " %s " % title_clipped
            rem_hz = max(0, inner - 1 - str_width(t_str))
            top_bar = tl + hz + t_str + hz * rem_hz + tr
        else:
            top_bar = tl + hz * inner + tr
        self.put(y, x, top_bar, border_attr, width=width)
        for row in range(1, height - 1):
            self.put(y + row, x, vt, border_attr)
            self.put(y + row, x + width - 1, vt, border_attr)
        self.put(y + height - 1, x, bl + hz * inner + br, border_attr, width=width)

    # -- chrome ------------------------------------------------------------
    def draw(self):
        self.scr.erase()
        h, w = self.scr.getmaxyx()
        if h < 12 or w < 50:
            self.put(0, 0, "terminal too small - need at least 50x12", self.attr("live"))
            self.scr.refresh()
            return

        # In standalone mode (cfbtui, nbatui, etc.), board starts at row 0 just like WPTK/cfbtui!
        # In combined sportstui mode, row 0 shows the 1-6 league switcher bar.
        if self.only:
            body_top = 0
        else:
            self.draw_league_tabs(w)
            body_top = 1

        # Bottom 2 rows are always StatusBar + Footer keybar.
        # On the board view (when height >= 24), 6 rows above StatusBar are the cfbtui ticker!
        show_ticker = (self.view in ("board", "group_picker") and h >= 24)
        ticker_h = 6 if show_ticker else 0
        body_h = h - body_top - 2 - ticker_h

        if self.view in ("board", "group_picker"):
            self.draw_board(body_top, body_h, w)
            if show_ticker:
                self.draw_ticker(h - 2 - ticker_h, ticker_h, w)
            if self.view == "group_picker":
                self.draw_group_picker(h, w)
        elif self.view == "extra":
            self.draw_extra(body_top, body_h, w)
        elif self.view == "detail":
            self.draw_detail(body_top, body_h, w)
        elif self.view == "news":
            self.draw_news(body_top, body_h, w)
        elif self.view == "help":
            self.draw_help(body_top, body_h, w)

        self.draw_status_bar(h - 2, w)
        self.draw_footer_bar(h - 1, w)
        self.scr.refresh()

    def draw_league_tabs(self, w):
        self.clear_line(0, self.attr("panel"))
        segs = []
        visible_tabs = [self.lg()] if self.only else LEAGUES
        for i, lg in enumerate(visible_tabs):
            active = lg["key"] == self.league_key
            label = " %d %s " % (i + 1, lg["name"])
            segs.append((label, self.attr("bar") if active else self.attr("panel")))
            segs.append((" ", self.attr("panel")))
        games = self.cache_get(self.board_key()) or []
        game_week = (games[0].get("week") if games else None) or self.week
        wk_str = ("Week %d · " % game_week) if (game_week and self.league_key in ("cfb", "nfl")) else ""
        right = "%s%s " % (wk_str, self.date.strftime("%a %b %-d"))
        used = sum(str_width(s) for s, _ in segs)
        right_w = str_width(right)
        if w - used - right_w > 0:
            segs.append((" " * (w - used - right_w), self.attr("panel")))
            segs.append((right, self.attr("panel")))
        self.segment(0, 0, segs, w)

    def draw_status_bar(self, y, w):
        """cfbtui-style status line: freshness, next poll, week/date + league, layout/filter, live count, version, glyphs, clock."""
        self.clear_line(y, self.attr("panel"))
        g = self.g()
        ent = self.cache.get(self.board_key())
        games = ent[1] if ent and ent[1] is not None else []
        ttl = self.ttl(games)
        now = time.time()

        if notice := (self.notice[0] if now < self.notice[1] else ""):
            self.put(y, 1, "%s %s" % (g["fresh"], notice), self.attr("accent"))
            return

        if ent is None:
            health = "%s loading" % g["loading"]
            next_str = "%s polling" % g["refresh"]
        elif self.last_error:
            age = format_age(now - ent[0])
            health = "%s ERROR (showing data %s old)" % (g["error"], age)
            next_str = None
        else:
            age_s = now - ent[0]
            health = "%s updated %s ago" % (g["fresh"], format_age(age_s))
            if self.fetcher.is_busy():
                next_str = "%s polling" % g["refresh"]
            else:
                rem = max(0, ttl - age_s)
                next_str = "next %s" % format_age(rem)

        game_week = (games[0].get("week") if games else None) or self.week
        if self.league_key == "all":
            context = "ALL %s" % self.date.strftime("%a %b %-d")
        elif game_week and self.league_key in ("cfb", "nfl"):
            context = "Week %d %s" % (game_week, self.lg()["label"])
        else:
            context = "%s %s" % (self.lg()["label"], self.date.strftime("%a %b %-d"))

        notes = [self.layout]
        if self.filter != "all":
            notes.append(self.filter)
        if self.group_name:
            notes.append(self.group_name)
        note_str = " · ".join(notes)

        live_cnt = sum(1 for gm in games if gm["state"] == "in")
        live_str = "%d live of %d" % (live_cnt, len(games)) if ent is not None else ""

        parts = [health]
        if next_str:
            parts.append(next_str)
        parts.append(context)
        parts.append(note_str)
        if live_str:
            parts.append(live_str)
        parts.append("v%s" % VERSION)
        parts.append("glyphs: %s" % self.glyphs)
        parts.append(dt.datetime.now().strftime("%a %H:%M:%S"))

        sep = g["dot"]
        while len(parts) > 2 and len(sep.join(parts)) > w - 2:
            parts.pop(-2)
        line = " " + sep.join(parts)
        self.put(y, 0, line, self.attr("live") if self.last_error else self.attr("panel"), width=w)

    def draw_footer_bar(self, y, w):
        """cfbtui-style keybind footer with bold yellow keys and white labels."""
        self.clear_line(y, self.attr("panel"))
        if self.view in ("detail", "extra", "news", "help"):
            items = [("esc", "Back"), ("c", "Copy"), ("q", "Quit")]
            if self.view == "extra":
                items.insert(1, ("←/→", "Switch Group/Poll"))
            elif self.view == "news":
                items.insert(1, ("⏎", "Read"))
                items.insert(2, ("o", "Browser"))
        elif self.view == "group_picker":
            items = [("esc", "Cancel"), ("⏎", "Select"), ("q", "Quit")]
        else:
            is_college = self.league_key in ("cfb", "cbb")
            items = [
                ("q", "Quit"),
                ("?", "Help"),
                ("⏎", "Detail"),
                ("v", "Layout"),
                ("l", "Filter"),
                ("o", "Conf" if is_college else "Div"),
                ("R", "Rankings"),
                ("T", "Standings"),
                ("N", "News"),
                ("c", "Copy"),
            ]
            if not self.only:
                items.append(("1-6", "League"))
        segs = [(" ", self.attr("panel"))]
        for k, lbl in items:
            segs.append((k, self.attr("key")))
            segs.append((" %s  " % lbl, self.attr("key_label")))
        right = "│ [ ] day  t today "
        used = sum(str_width(s) for s, _ in segs)
        right_w = str_width(right)
        if w - used - right_w > 0:
            segs.append((" " * (w - used - right_w), self.attr("panel")))
            segs.append((right, self.attr("panel")))
        self.segment(y, 0, segs, w)

    # -- ticker ------------------------------------------------------------
    def draw_ticker(self, top, height, width):
        g = self.g()
        title = "%sticker%s" % (g["h"], g["h"] * max(0, width - 7))
        self.put(top, 0, title, self.attr("dim"), width=width)
        games = self.cache_get(self.board_key()) or []
        events = []
        # Build ticker feed from live games, upsets, finals, and upcoming games
        for gm in games:
            fav = self.game_fav(gm)
            aw, hm = gm["away"], gm["home"]
            sc = "%s %s - %s %s" % (aw["abbr"], aw["score"], hm["abbr"], hm["score"])
            matchup = "%s @ %s" % (aw["abbr"], hm["abbr"])
            up = gm.get("upset")
            sit = gm.get("situation")
            lg_pfx = ("[%s] " % gm["league"].upper()) if self.league_key == "all" else ""
            if up and up["confirmed"]:
                u_tag = ("#%s %s" % (up["underdog"]["rank"], up["underdog"]["abbr"])) if up["underdog"]["rank"] else up["underdog"]["abbr"]
                f_tag = ("#%s %s" % (up["favorite"]["rank"], up["favorite"]["abbr"])) if up["favorite"]["rank"] else up["favorite"]["abbr"]
                events.append((0 if fav else 1, fav, "live", "%s UPSET  %s%s beats %s  %s" % (g["upset"], lg_pfx, u_tag, f_tag, sc)))
            elif up and not up["confirmed"]:
                u_tag = ("#%s %s" % (up["underdog"]["rank"], up["underdog"]["abbr"])) if up["underdog"]["rank"] else up["underdog"]["abbr"]
                f_tag = ("#%s %s" % (up["favorite"]["rank"], up["favorite"]["abbr"])) if up["favorite"]["rank"] else up["favorite"]["abbr"]
                events.append((0 if fav else 1, fav, "accent", "%s UPSET WATCH  %s%s leads %s  %s  %s" % (g["upset_watch"], lg_pfx, u_tag, f_tag, sc, gm["short"])))
            elif gm["state"] == "in" and sit and sit.get("red_zone"):
                events.append((0 if fav else 2, fav, "live", "%s RED ZONE  %s%s  %s  %s" % (g["red_zone"], lg_pfx, matchup, sc, sit.get("down_dist") or gm["short"])))
            elif gm["state"] == "in":
                lp = ("  ·  " + sit["last_play"][:55]) if (sit and sit.get("last_play")) else ""
                events.append((0 if fav else 3, fav, "good", "%s LIVE  %s%s  (%s)%s" % (g["live"], lg_pfx, sc, gm["short"] or "In Progress", lp)))
            elif gm["state"] == "post":
                ot = " (OT)" if gm.get("is_overtime") else ""
                events.append((0 if fav else 4, fav, "base", "%s FINAL%s  %s%s" % (g["final"], ot, lg_pfx, sc)))
            elif gm["state"] == "pre":
                sp = spread_text(gm["odds"])
                sp_str = ("  ·  " + sp) if sp else ""
                events.append((0 if fav else 5, fav, "dim", "%s %s%s  %s%s" % (g["pregame"], lg_pfx, matchup, self.kickoff_str(gm["start"]), sp_str)))

        events.sort(key=lambda x: x[0])
        avail = height - 1
        if not events:
            self.put(top + 1, 2, "Waiting for scoreboard events...", self.attr("dim"))
            return
        for i, (_, fav, kind, text) in enumerate(events[:avail]):
            y = top + 1 + i
            segs = [(" ", self.attr("base"))]
            if fav:
                segs.append(("%s " % g["star"], self.attr("accent")))
                segs.append((" " + text + " ", self.attr(kind) | curses.A_REVERSE))
            else:
                segs.append((text, self.attr(kind)))
            self.segment(y, 0, segs, width - 1)

    # -- board -------------------------------------------------------------
    def grid_cols(self, width):
        return max(1, width // 36)

    def card_layout(self, width, cols):
        avail = max(cols * 34, (width - 2) - (cols - 1))
        base_cw = avail // cols
        rem = avail % cols
        layout = []
        curr_x = 1
        for i in range(cols):
            w = base_cw + (1 if i < rem else 0)
            layout.append((curr_x, w))
            curr_x += w + 1
        return layout

    def draw_board(self, top, height, width):
        key = self.board_key()
        games = self.cache_get(key)
        ttl = self.ttl(games)
        if self.league_key == "all":
            self.ensure(key, lambda: parse_all_boards(self.date), ttl)
        else:
            self.ensure(key, lambda: parse_board(self.lg(), self.date, self.week), ttl)
        games = self.cache_get(key)
        if games is None:
            if self.last_error:
                self.put(top + 1, 2, "%s Could not reach ESPN (%s). Retrying..." % (self.g()["error"], self.last_error), self.attr("live"))
            else:
                self.put(top + 1, 2, "%s Loading %s scoreboard..." % (self.g()["loading"], self.lg()["name"]), self.attr("dim"))
            return
        rows = self.visible(games)
        if not rows:
            self.put(top + 1, 2, "No games on the board (filter: %s). Press l to cycle filters or [ / ] to change date." % self.filter, self.attr("dim"))
            return
        if self.layout == "grid":
            self.draw_grid(rows, top, height, width)
        else:
            self.draw_list(rows, top, height, width)

    # -- list layout (cfbtui list.png exact style) -------------------------
    def draw_list(self, rows, top, height, width):
        g = self.g()
        idx = self.selected_index(rows)
        starred = [gm for gm in rows if self.game_fav(gm)]
        rest = [gm for gm in rows if not self.game_fav(gm)]

        # Build visual display lines: ("header", text) or ("game", game_index, game)
        vlines = []
        if starred:
            vlines.append(("header", "  %s Favorites" % g["star"]))
            for gm in starred:
                vlines.append(("game", rows.index(gm), gm))
            if rest:
                vlines.append(("header", "  Other games"))
        for gm in rest:
            vlines.append(("game", rows.index(gm), gm))

        # Find visual row of selected game
        sel_vrow = 0
        for vi, item in enumerate(vlines):
            if item[0] == "game" and item[1] == idx:
                sel_vrow = vi
                break

        if sel_vrow < self.scroll:
            self.scroll = sel_vrow
            if self.scroll == 1 and vlines[0][0] == "header":
                self.scroll = 0
        if sel_vrow >= self.scroll + height:
            self.scroll = sel_vrow - height + 1
        self.scroll = max(0, min(self.scroll, max(0, len(vlines) - height)))

        for vi in range(self.scroll, min(len(vlines), self.scroll + height)):
            y = top + (vi - self.scroll)
            self.clear_line(y)
            item = vlines[vi]
            if item[0] == "header":
                self.put(y, 0, item[1], self.attr("section"))
            else:
                _, g_idx, game = item
                self.draw_list_row(game, y, width, g_idx == idx)

    def _team_cell_text(self, game, side, is_away, cell_w=40):
        g = self.g()
        live = game["state"] == "in"
        sit = game.get("situation") if live else None
        poss = g["poss"] if (sit and sit.get("possession") == side["id"] and side["id"]) else ""
        fav = self.is_fav(side, game)
        star = g["star"] if fav else ""
        rank_num = side.get("rank")

        # In card mode (cell_w >= 30), exact aligned block matching cfbtui:
        # Every team abbr starts at exact visual column 8
        if cell_w >= 30:
            prefix = team_row_prefix(poss, star, rank_num)
            abbr = side["abbr"][:5]
            rec = f" {side['record'][:6]}" if side.get("record") else ""
            left = prefix + f"{abbr:<5}{rec}"
            t_str = ""
            if live and sit:
                rem = sit.get("away_timeouts" if is_away else "home_timeouts")
                t_str = timeouts_str(g, rem, game.get("league", "cfb"))

            score = side.get("score") if game["state"] != "pre" else None
            if score is not None:
                if t_str:
                    sc_fmt = f"{t_str} {score:>3}"
                else:
                    sc_fmt = f"{score:>3} "
            else:
                sc_fmt = "    "
            pad = max(1, cell_w - str_width(left) - str_width(sc_fmt))
            return left + (" " * pad) + sc_fmt

        # In compact list mode (cell_w around 21)
        icon = f"{poss} " if poss else (f"{star} " if star else "")
        rk_str = f"#{rank_num}" if rank_num else ""
        left = "%s%s%-5s %-6s" % (
            icon if (fav or poss) else "",
            (rk_str + " ") if rk_str else "",
            side["abbr"][:5],
            (side.get("record") or "")[:6],
        )
        score_str = str(side["score"]) if game["state"] != "pre" and side.get("score") is not None else ""
        pad = max(1, cell_w - str_width(left) - str_width(score_str))
        return left + (" " * pad) + score_str

    def draw_list_row(self, game, y, width, selected):
        g = self.g()
        away, home = game["away"], game["home"]
        final = game["state"] == "post"
        live = game["state"] == "in"
        aw_lead = game["state"] != "pre" and away["score_int"] > home["score_int"]
        hm_lead = game["state"] != "pre" and home["score_int"] > away["score_int"]

        aw_attr = self.team_bar_attr(away["color"], bold=aw_lead, dim=(final and hm_lead))
        hm_attr = self.team_bar_attr(home["color"], bold=hm_lead, dim=(final and aw_lead))

        aw_txt = self._team_cell_text(game, away, True, 21)
        hm_txt = self._team_cell_text(game, home, False, 21)

        cursor = "▸" if selected else " "
        status = self.status_text(game)
        extra = self.extra_text(game)
        up = game.get("upset")
        sit = game.get("situation")

        lg_tag = ("%-4s " % game["league"].upper()) if self.league_key == "all" else ""
        segs = [
            (cursor + " " + lg_tag, self.attr("focus") if selected else self.attr("base")),
            (aw_txt, aw_attr),
            (" @ ", self.attr("focus") if selected else self.attr("dim")),
            (hm_txt, hm_attr),
            ("   " + status, self.attr("live") if live else (self.attr("focus") if selected else self.attr("base"))),
        ]
        if extra:
            segs.append(("  " + extra, self.attr("dim")))
        if up:
            lbl = ("  %s UPSET" % g["upset"]) if up["confirmed"] else ("  %s UPSET WATCH" % g["upset_watch"])
            segs.append((lbl, self.attr("accent")))
        if live and sit and sit.get("red_zone"):
            segs.append(("  %s RED ZONE" % g["red_zone"], self.attr("live")))
        self.segment(y, 0, segs, width)

    # -- grid layout (cfbtui grid.png exact style) -------------------------
    def draw_grid(self, rows, top, height, width):
        g = self.g()
        ch = 5
        cols = self.grid_cols(width)
        layout = self.card_layout(width, cols)
        idx = self.selected_index(rows)

        starred = [gm for gm in rows if self.game_fav(gm)]
        rest = [gm for gm in rows if not self.game_fav(gm)]

        # Build grid bands: either ("header", y_height=1, text) or ("card_row", y_height=5, [(g_idx, game), ...])
        bands = []
        if starred:
            bands.append(("header", 1, "  %s Favorites" % g["star"]))
            for r_start in range(0, len(starred), cols):
                chunk = [(rows.index(gm), gm) for gm in starred[r_start:r_start + cols]]
                bands.append(("cards", ch, chunk))
            if rest:
                bands.append(("header", 1, "  Other games"))
        for r_start in range(0, len(rest), cols):
            chunk = [(rows.index(gm), gm) for gm in rest[r_start:r_start + cols]]
            bands.append(("cards", ch, chunk))

        # Find which band holds the selected card
        sel_band = 0
        for bi, b in enumerate(bands):
            if b[0] == "cards" and any(gi == idx for gi, _ in b[2]):
                sel_band = bi
                break

        # Adjust band scroll so sel_band is visible within height
        if sel_band < self.scroll:
            self.scroll = sel_band
            if self.scroll > 0 and bands[self.scroll - 1][0] == "header":
                self.scroll -= 1
        while sel_band > self.scroll:
            used_h = sum(b[1] for b in bands[self.scroll:sel_band + 1])
            if used_h <= height:
                break
            self.scroll += 1

        y = top
        for bi in range(self.scroll, len(bands)):
            btype, bh, payload = bands[bi]
            if y + bh > top + height:
                break
            if btype == "header":
                self.put(y, 0, payload, self.attr("section"))
                y += 1
            else:
                for col_i, (gi, game) in enumerate(payload):
                    x, cw = layout[col_i]
                    self.draw_card(game, y, x, cw, gi == idx)
                y += ch

    def draw_card(self, game, y, x, cw, selected):
        g = self.g()
        away, home = game["away"], game["home"]
        inner = cw - 2
        live = game["state"] == "in"
        final = game["state"] == "post"
        up = game.get("upset")
        sit = game.get("situation") if live else None
        red_zone = bool(sit and sit.get("red_zone"))

        # Border & Title (matching cfbtui's GameCard)
        titles = []
        if self.league_key == "all":
            titles.append(game["league"].upper())
        if up:
            titles.append(("%s UPSET" % g["upset"]) if up["confirmed"] else ("%s UPSET WATCH" % g["upset_watch"]))
        if red_zone:
            titles.append("%s RED ZONE" % g["red_zone"])
        if selected:
            titles.append("▸")
        title_str = " ".join(titles)

        heavy = bool(selected or up or red_zone)
        if selected:
            border_attr = self.attr("focus")
        elif red_zone:
            border_attr = self.attr("live")
        elif up:
            border_attr = self.attr("accent")
        elif live:
            border_attr = self.attr("good")
        else:
            border_attr = self.attr("dim")

        self.draw_box(y, x, 5, cw, border_attr, title=title_str, heavy=heavy)

        # Away and Home full-bleed team color rows
        aw_lead = game["state"] != "pre" and away["score_int"] > home["score_int"]
        hm_lead = game["state"] != "pre" and home["score_int"] > away["score_int"]
        for i, (side, is_lead, is_trail) in enumerate((
            (away, aw_lead, final and hm_lead),
            (home, hm_lead, final and aw_lead),
        )):
            t_attr = self.team_bar_attr(side["color"], bold=is_lead, dim=is_trail)
            row_txt = self._team_cell_text(game, side, i == 0, inner)
            self.put(y + 1 + i, x + 1, row_txt, t_attr, width=inner)

        # Status row (row 3 inside card)
        status = self.status_text(game)
        extra = self.extra_text(game)
        st_w = str_width(status)
        ex_w = str_width(extra)
        avail_for_extra = inner - (1 + st_w) - 1
        if ex_w > avail_for_extra:
            extra = clip_to_width(extra, max(0, avail_for_extra))
            ex_w = str_width(extra)
        pad = max(1, inner - (1 + st_w) - ex_w)
        st_attr = self.attr("live") if live else (self.attr("focus") if selected else self.attr("base"))
        self.fill_line(y + 3, x + 1, inner, self.attr("base"))
        segs = [
            (" " + status, st_attr),
            (" " * pad, self.attr("base")),
            (extra, self.attr("dim")),
        ]
        self.segment(y + 3, x + 1, segs, inner)

    # -- extra views: side-by-side Rankings (R) & Standings (T) ------------
    def draw_extra(self, top, height, width):
        lg = self.lg()
        if self.extra_kind == "ranks":
            key = "ranks:%s" % self.league_key
            data = self.ensure(key, lambda: parse_rankings(lg), 300)
            if data is None:
                self.put(top + 1, 2, "%s Loading polls..." % self.g()["loading"], self.attr("dim"))
                return
            self.draw_ranks(data, top, height, width)
        else:
            key = "stand:%s" % self.league_key
            data = self.ensure(key, lambda: parse_standings(lg), 300)
            if data is None:
                self.put(top + 1, 2, "%s Loading standings..." % self.g()["loading"], self.attr("dim"))
                return
            self.draw_standings(data, top, height, width)

    def draw_ranks(self, polls, top, height, width):
        """cfbtui rankings.png style: side-by-side bordered poll boxes with full-bleed team color bars."""
        if not polls:
            self.put(top + 1, 2, "No polls published for %s." % self.lg()["name"], self.attr("dim"))
            return
        max_rows = max(len(p["ranks"]) for p in polls)
        avail_rows = max(1, height - 3)
        self.extra_scroll = max(0, min(self.extra_scroll, max(0, max_rows - avail_rows)))

        # Side-by-side when terminal width >= 104 and >= 2 polls
        side_by_side = (width >= 104 and len(polls) >= 2)
        if side_by_side:
            visible_polls = polls[:2]
            box_w = (width - 4) // 2
        else:
            self.extra_tab = max(0, min(self.extra_tab, len(polls) - 1))
            visible_polls = [polls[self.extra_tab]]
            box_w = min(width - 4, 68)

        for idx, poll in enumerate(visible_polls):
            bx = 2 + idx * (box_w + 2)
            wk = ("  Week %s" % poll["week"]) if poll.get("week") else ""
            title = "%s%s" % (poll["name"], wk)
            box_h = min(height, len(poll["ranks"]) - self.extra_scroll + 3)
            self.draw_box(top, bx, max(4, box_h), box_w, self.attr("dim"), title=title)

            # Column headers inside box
            team_w = max(16, box_w - 28)
            hdr = " %3s  %-*s  %6s %6s %4s" % ("#", team_w, "Team", "Rec", "Pts", "Chg")
            self.put(top + 1, bx + 1, hdr[:box_w - 2], self.attr("section"))

            rows = poll["ranks"][self.extra_scroll:self.extra_scroll + avail_rows]
            for ri, r in enumerate(rows):
                ry = top + 2 + ri
                votes = (" (%d)" % r["first"]) if r["first"] else ""
                t_name = "%-5s %s%s" % (r["abbr"][:5], r["team"], votes)
                t_bar = self.team_bar_attr(r["color"], bold=True)
                try:
                    pts = "%d" % int(float(r["points"])) if r["points"] else ""
                except (TypeError, ValueError):
                    pts = str(r["points"] or "")
                trend = r["trend"] or ""
                if trend in ("-", "0"):
                    trend = ""
                elif not trend and not r.get("prev"):
                    trend = "new"
                tr_attr = self.attr("good") if trend.startswith("+") else (self.attr("live") if trend.startswith("-") else self.attr("dim"))

                segs = [
                    (" ", self.attr("base")),
                    ("%3d " % r["rank"], t_bar),
                    (" ", self.attr("base")),
                    (" %-*s " % (team_w - 2, t_name[:team_w - 2]), t_bar),
                    (" %6s %6s " % (r["record"][:6], pts[:6]), self.attr("base")),
                    ("%4s" % trend[:4], tr_attr),
                ]
                self.segment(ry, bx + 1, segs, box_w - 2)

    def draw_standings(self, groups, top, height, width):
        """Side-by-side or tabbed conference/division bordered boxes with full-bleed team color bars."""
        if not groups:
            self.put(top + 1, 2, "No standings available.", self.attr("dim"))
            return
        self.extra_group = max(0, min(self.extra_group, len(groups) - 1))

        # Group selector tabs along top row if > 2 groups (e.g. CFB / CBB conferences)
        y_box = top
        if len(groups) > 2:
            x_tab = 2
            for gi, grp in enumerate(groups):
                lbl = " %s " % grp["name"].replace(" Conference", "").replace("American Athletic", "AAC")[:14]
                if x_tab + len(lbl) >= width - 2:
                    break
                self.put(top, x_tab, lbl, self.attr("bar") if gi == self.extra_group else self.attr("dim"))
                x_tab += len(lbl) + 1
            y_box = top + 2
            height -= 2

        side_by_side = (width >= 108 and len(groups) == 2)
        if side_by_side:
            vis_groups = groups[:2]
            box_w = (width - 4) // 2
        else:
            vis_groups = [groups[self.extra_group]]
            box_w = min(width - 4, 74)

        avail_rows = max(1, height - 3)
        max_rows = max(len(g["rows"]) for g in vis_groups)
        self.extra_scroll = max(0, min(self.extra_scroll, max(0, max_rows - avail_rows)))

        cols_spec = STANDING_COLS.get(self.league_key, [])
        for idx, grp in enumerate(vis_groups):
            bx = 2 + idx * (box_w + 2)
            cols = [(k, h) for k, h in cols_spec if any(r["stats"].get(k) not in (None, "") for r in grp["rows"])]
            if not cols:
                cols = cols_spec[:4]
            stat_w = 7 * len(cols)
            team_w = max(16, box_w - stat_w - 8)
            box_h = min(height, len(grp["rows"]) - self.extra_scroll + 3)
            self.draw_box(y_box, bx, max(4, box_h), box_w, self.attr("dim"), title=grp["name"])

            hdr = " %3s %-*s" % ("#", team_w, "Team") + "".join("%7s" % h for _, h in cols)
            self.put(y_box + 1, bx + 1, hdr[:box_w - 2], self.attr("section"))

            rows = grp["rows"][self.extra_scroll:self.extra_scroll + avail_rows]
            for ri, row in enumerate(rows):
                ry = y_box + 2 + ri
                rank_num = self.extra_scroll + ri + 1
                t_bar = self.team_bar_attr(row["color"], bold=True)
                star = self.g()["star"] if ("%s:%s" % (self.league_key, row["abbr"]) in self.favs) else " "
                t_label = "%s%-4s %s" % (star, row["abbr"][:4], row["team"])
                segs = [
                    (" %2d " % rank_num, self.attr("dim")),
                    (" %-*s " % (team_w - 2, t_label[:team_w - 2]), t_bar),
                ]
                for k, _ in cols:
                    val = str(row["stats"].get(k) or "-")
                    segs.append(("%7s" % val[:6], self.attr("base")))
                self.segment(ry, bx + 1, segs, box_w - 2)

    # -- detail (cfbtui detail.png exact layout) ---------------------------
    def draw_detail(self, top, height, width):
        game = self.detail_game
        if not game:
            self.put(top, 2, "No game selected.", self.attr("dim"))
            return
        g = self.g()
        key = "detail:%s:%s" % (game["league"], game["id"])
        lg = BY_KEY.get(game["league"], self.lg())
        data = self.ensure(key, lambda: parse_detail(lg, game["id"]), 20 if game["state"] == "in" else 120)

        away, home = game["away"], game["home"]
        final = game["state"] == "post"
        aw_lead = game["state"] != "pre" and away["score_int"] > home["score_int"]
        hm_lead = game["state"] != "pre" and home["score_int"] > away["score_int"]

        # 1. Top Full-Bleed Team Banners (matching detail.png)
        banner_w = max(32, max(len(away["full"]), len(home["full"])) + 18)
        live = game["state"] == "in"
        sit = game.get("situation") if live else None
        for i, (side, prefix, is_lead) in enumerate(((away, "", aw_lead), (home, "@ ", hm_lead))):
            rk = ("#%d " % side["rank"]) if side["rank"] else ""
            left = " %s%s%s  %s" % (prefix, rk, side["full"], side["record"])
            t_str = ""
            if live and sit:
                rem = sit.get("away_timeouts" if i == 0 else "home_timeouts")
                t_str = timeouts_str(g, rem, game.get("league", "cfb"))
            sc = str(side["score"]) if game["state"] != "pre" else ""
            sc_part = f"{t_str}  {sc}" if t_str else sc
            pad = max(2, banner_w - str_width(left) - str_width(sc_part) - 1)
            line = left + (" " * pad) + sc_part + " "
            self.put(top + i, 2, line, self.team_bar_attr(side["color"], bold=is_lead, dim=(final and not is_lead)))

        y = top + 2
        self.put(y, 2, self.status_text(game), self.attr("live") if game["state"] == "in" else self.attr("dim"))
        y += 1
        loc = (data.get("location") if data else None) or game.get("venue") or ""
        tv = game.get("tv") or ""
        sp = spread_text(game["odds"])
        info_str = "  ·  ".join(x for x in (loc, tv, ("Line: " + sp) if sp else "") if x)
        if info_str:
            self.put(y, 2, info_str[:width - 4], self.attr("dim"))
            y += 1

        if data is None:
            self.put(y + 1, 2, "%s Loading game summary..." % g["loading"], self.attr("dim"))
            return

        # Build virtual scrollable lines for the rest of the detail screen
        vlines = []  # list of list-of-(text, attr) segments

        # 2. Win Probability Bar & Whole-Game Sparkline (detail.png)
        if data.get("winprob"):
            vlines.append([])
            a_prob, h_prob = data["winprob"]
            bar_w = 28
            filled_h = int(round(h_prob * bar_w))
            filled_a = bar_w - filled_h
            aw_fg = self.team_fg_attr(away["color"], bold=True)
            hm_fg = self.team_fg_attr(home["color"], bold=True)
            vlines.append([
                ("%s %.0f%% " % (away["abbr"], a_prob * 100), self.attr("base")),
                (g["bar_full"] * filled_a, aw_fg),
                (g["bar_empty"] * filled_h if filled_h == 0 else g["bar_full"] * filled_h, hm_fg),
                (" %.0f%% %s" % (h_prob * 100, home["abbr"]), self.attr("base")),
            ])
        series = data.get("wp_series") or []
        if len(series) >= 2:
            vlines.append([])
            vlines.append([("Win probability, whole game", self.attr("dim"))])
            spark_w = min(len(series), 36)
            spark_chars = g["spark"]
            levels = len(spark_chars) - 1
            aw_fg = self.team_fg_attr(away["color"], bold=True)
            hm_fg = self.team_fg_attr(home["color"], bold=True)
            s_segs = [("%-4s " % away["abbr"], self.attr("base"))]
            for i in range(spark_w):
                p = min(1.0, max(0.0, series[int(round(i * (len(series) - 1) / max(1, spark_w - 1)))]))
                ch = spark_chars[int(round(p * levels))]
                s_segs.append((ch, hm_fg if p >= 0.5 else aw_fg))
            s_segs.append((" %s" % home["abbr"], self.attr("base")))
            vlines.append(s_segs)

        # 3. Score by period table (detail.png)
        ls_a = data["linescores"].get("away") or []
        ls_h = data["linescores"].get("home") or []
        if ls_a or ls_h:
            vlines.append([])
            vlines.append([("Score by period", self.attr("base") | curses.A_BOLD | curses.A_UNDERLINE)])
            n_per = max(len(ls_a), len(ls_h))
            hdr = "      " + "".join("%4s" % period_label(game["league"], p).replace("Inn ", "") for p in range(1, n_per + 1)) + "    T"
            vlines.append([(hdr, self.attr("base") | curses.A_BOLD)])
            for side, scores in ((away, ls_a), (home, ls_h)):
                row_segs = [(" %-5s" % side["abbr"][:5], self.team_bar_attr(side["color"], bold=True))]
                row_segs.append(("".join("%4s" % (scores[i] if i < len(scores) else "-") for i in range(n_per)), self.attr("base")))
                row_segs.append(("%5s" % side["score"], self.attr("base") | curses.A_BOLD))
                vlines.append(row_segs)

        # 4. Leaders
        if data.get("leaders"):
            vlines.append([])
            title = "Season leaders" if game["state"] == "pre" else "Game leaders"
            vlines.append([(title, self.attr("base") | curses.A_BOLD | curses.A_UNDERLINE)])
            for ld in data["leaders"]:
                segs = [(" %-5s" % ld["abbr"][:5], self.team_bar_attr(ld["color"], bold=True)), ("  ", self.attr("base"))]
                for cname, who, val in ld["cats"][:3]:
                    segs.append(("%s: " % cname, self.attr("dim")))
                    segs.append(("%s (%s)   " % (who, val), self.attr("base")))
                vlines.append(segs)

        # 5. Scoring plays (chronological with running score [AWAY X - HOME Y], matching detail.png)
        vlines.append([])
        vlines.append([("Scoring plays", self.attr("base") | curses.A_BOLD | curses.A_UNDERLINE)])
        plays = data.get("plays") or []
        if not plays:
            vlines.append([("No scoring plays yet.", self.attr("dim"))])
        else:
            for p in plays:
                per = period_label(game["league"], p["period"]) or (p["period_disp"][:5] if p.get("period_disp") else "")
                clk = p["clock"]
                when = ("%s %s" % (per, clk)).strip()
                st = p.get("stype") or ""
                icon = g["fg"] if ("field-goal" in st or "field goal" in st or "fg" in st) else (g["td"] if ("touchdown" in st or "td" in st) else g["score"])
                sc_bracket = ""
                if p.get("away_score") is not None and p.get("home_score") is not None:
                    sc_bracket = "  [%s %s - %s %s]" % (away["abbr"], p["away_score"], home["abbr"], p["home_score"])
                vlines.append([
                    ("%-9s " % when[:9], self.attr("base")),
                    ("%s %-5s " % (icon, p["team"][:5]), self.attr("accent") if p["team"] else self.attr("base")),
                    (p["text"], self.attr("base")),
                    (sc_bracket, self.attr("dim")),
                ])

        avail = max(1, top + height - y)
        self.detail_scroll = max(0, min(self.detail_scroll, max(0, len(vlines) - avail)))
        for i in range(self.detail_scroll, min(len(vlines), self.detail_scroll + avail)):
            self.segment(y + (i - self.detail_scroll), 2, vlines[i], width - 4)

    # -- news screen (N) ---------------------------------------------------
    def draw_news(self, top, height, width):
        lg = self.lg()
        g = self.g()
        if self.news_story:
            headline, body, web_url = self.news_story
            self.put(top, 2, headline[:width - 4], self.attr("accent"))
            if web_url:
                self.put(top + 1, 2, web_url[:width - 4], self.attr("dim"))
            lines = []
            for para in body.splitlines():
                if not para:
                    lines.append("")
                    continue
                while len(para) > width - 6:
                    cut = para.rfind(" ", 0, width - 6)
                    if cut <= 0:
                        cut = width - 6
                    lines.append(para[:cut])
                    para = para[cut:].lstrip()
                lines.append(para)
            avail = max(1, height - 3)
            self.news_scroll = max(0, min(self.news_scroll, max(0, len(lines) - avail)))
            for i in range(self.news_scroll, min(len(lines), self.news_scroll + avail)):
                self.put(top + 3 + (i - self.news_scroll), 2, lines[i], self.attr("base"))
            return

        key = "news:%s" % self.league_key
        items = self.ensure(key, lambda: parse_news(lg), 300)
        if items is None:
            self.put(top + 1, 2, "%s Loading %s news..." % (g["loading"], lg["name"]), self.attr("dim"))
            return
        if not items:
            self.put(top + 1, 2, "No news articles found.", self.attr("dim"))
            return

        box_w = min(width - 4, 110)
        self.draw_box(top, 2, height, box_w, self.attr("dim"), title="%s News (%d stories)" % (lg["name"], len(items)))
        avail = max(1, (height - 2) // 2)
        self.news_sel = max(0, min(self.news_sel, len(items) - 1))
        if self.news_sel < self.news_scroll:
            self.news_scroll = self.news_sel
        if self.news_sel >= self.news_scroll + avail:
            self.news_scroll = self.news_sel - avail + 1

        for idx in range(self.news_scroll, min(len(items), self.news_scroll + avail)):
            art = items[idx]
            ry = top + 1 + (idx - self.news_scroll) * 2
            sel = idx == self.news_sel
            age = format_age(time.time() - art["published"].timestamp()) + " ago" if art["published"] else ""
            tags = (" [%s]" % ", ".join(art["teams"])) if art["teams"] else ""
            cursor = "▸ " if sel else "  "
            self.segment(ry, 3, [
                (cursor, self.attr("focus") if sel else self.attr("base")),
                (art["headline"][:box_w - 24], self.attr("focus") if sel else (self.attr("base") | curses.A_BOLD)),
                (tags, self.attr("accent")),
                ("  " + age, self.attr("dim")),
            ], box_w - 4)
            if art["description"] and ry + 1 < top + height - 1:
                self.put(ry + 1, 5, art["description"][:box_w - 8], self.attr("dim"))

    # -- help --------------------------------------------------------------
    def draw_help(self, top, height, width):
        box_w = min(width - 4, 76)
        lines = [
            ("NAVIGATION & VIEWS", "accent"),
            ("  Arrow keys / hjkl   Move between game cards (2D grid or list)", "base"),
            ("  1-7 / Tab           Switch league (1: ALL, 2: CFB, 3: NFL, 4: NHL, 5: NBA, 6: CBB, 7: MLB)" if not self.only else
             "  Standalone Mode     Locked to %s scoreboard" % self.lg()["name"], "base"),
            ("  Enter               Open game detail (linescore, win prob, plays)", "base"),
            ("  R                   Poll rankings (AP / Coaches / CFP side-by-side)", "base"),
            ("  T                   Conference & Division standings tables", "base"),
            ("  N                   League news feed (Enter to read, o for browser)", "base"),
            ("  [ / ]               Previous / next day", "base"),
            ("  w / W               Next / previous week (CFB & NFL)", "base"),
            ("  t                   Jump to today", "base"),
            ("", "base"),
            ("DISPLAY & ACTIONS", "accent"),
            ("  v                   Toggle card grid vs compact list layout", "base"),
            ("  l                   Filter: all / live / favorites / top25 / upsets", "base"),
            ("  o                   Filter by conference (CFB/CBB) or division (pro)", "base"),
            ("  a / h (or ! / @)    Star / unstar away or home team as favorite", "base"),
            ("  c / C               Copy selected game (c) or whole board (C) for Discord", "base"),
            ("  g                   Cycle icon set: nerd / unicode / emoji / ascii", "base"),
            ("  r                   Force refresh immediately", "base"),
            ("  Esc                 Back to scoreboard", "base"),
            ("  q                   Quit", "base"),
            ("", "base"),
            ("STARRED FAVORITES", "accent"),
            ("  " + "  ".join(sorted(self.favs))[:box_w - 6], "dim"),
        ]
        self.draw_box(top, 2, min(height, len(lines) + 2), box_w, self.attr("dim"), title="sportstui Help")
        for i, (text, kind) in enumerate(lines[:max(1, height - 2)]):
            self.put(top + 1 + i, 3, text[:box_w - 4], self.attr(kind))

    # -- group picker modal (cfbtui conferences.py exact modal) -----------
    def get_group_options(self):
        is_college = self.league_key in ("cfb", "cbb")
        first_label = "All conferences" if is_college else "All divisions / conferences"
        return [("all", first_label)] + LEAGUE_GROUPS.get(self.league_key, [])

    def draw_group_picker(self, h, w):
        is_college = self.league_key in ("cfb", "cbb")
        title = "Conference" if is_college else "Division / Conference"
        options = self.get_group_options()

        box_w = min(w - 6, 44)
        box_h = min(h - 4, len(options) + 2)
        by = max(1, (h - box_h) // 2)
        bx = max(2, (w - box_w) // 2)

        # Clear background of modal box
        for row in range(box_h):
            self.fill_line(by + row, bx, box_w, self.attr("panel"))
        self.draw_box(by, bx, box_h, box_w, self.attr("focus"), title=title, heavy=True)

        avail = box_h - 2
        if self.picker_sel < self.picker_scroll:
            self.picker_scroll = self.picker_sel
        if self.picker_sel >= self.picker_scroll + avail:
            self.picker_scroll = self.picker_sel - avail + 1

        for idx in range(self.picker_scroll, min(len(options), self.picker_scroll + avail)):
            gid, gname = options[idx]
            ry = by + 1 + (idx - self.picker_scroll)
            sel = (idx == self.picker_sel)
            is_cur = (self.group_filter == gid) or (not self.group_filter and gid == "all")
            cursor = "▸ " if sel else ("• " if is_cur else "  ")
            txt = cursor + gname
            attr = self.attr("focus") if sel else (self.attr("accent") if is_cur else self.attr("base"))
            self.put(ry, bx + 2, txt[:box_w - 4], attr)

    def open_group_picker(self):
        options = self.get_group_options()
        self.view = "group_picker"
        cur = self.group_filter or "all"
        for i, (gid, _) in enumerate(options):
            if gid == cur:
                self.picker_sel = i
                break
        else:
            self.picker_sel = 0
        self.picker_scroll = max(0, self.picker_sel - 5)
        self.scr.clear()

    def handle_group_picker(self, ch):
        options = self.get_group_options()
        if ch in (curses.KEY_UP, ord("k")):
            self.picker_sel = max(0, self.picker_sel - 1)
        elif ch in (curses.KEY_DOWN, ord("j")):
            self.picker_sel = min(len(options) - 1, self.picker_sel + 1)
        elif ch in (curses.KEY_ENTER, 10, 13):
            gid, name = options[self.picker_sel]
            self.group_filter = None if gid == "all" else gid
            self.group_name = None if gid == "all" else name
            self.view = "board"
            self.scroll = 0
            self.scr.clear()
            self.say("Showing: %s" % (name if gid != "all" else "all"))
        elif ch in (27, ord("q"), ord("o")):
            self.view = "board"
            self.scr.clear()
        return True

    # -- Discord copy ------------------------------------------------------
    def copy_game_discord(self, game):
        aw, hm = game["away"], game["home"]
        if game["state"] == "pre":
            sp = spread_text(game["odds"])
            line = "%s (%s) @ %s (%s) · %s%s" % (
                aw["abbr"], aw["record"], hm["abbr"], hm["record"],
                self.kickoff_str(game["start"]), (" · " + sp) if sp else "")
        else:
            aw_s = "**%s %s**" % (aw["abbr"], aw["score"]) if aw["score_int"] > hm["score_int"] else "%s %s" % (aw["abbr"], aw["score"])
            hm_s = "**%s %s**" % (hm["abbr"], hm["score"]) if hm["score_int"] > aw["score_int"] else "%s %s" % (hm["abbr"], hm["score"])
            line = "%s @ %s (%s)" % (aw_s, hm_s, game["short"] or game["detail"] or "Final")
        if copy_to_clipboard(line):
            self.say("Copied game for Discord")
        else:
            self.say("Clipboard tool (wl-copy/xclip) not found")

    def copy_board_discord(self, rows):
        if not rows:
            self.say("No games to copy")
            return
        lines = ["```", "%s — %s" % (self.lg()["name"], self.date.strftime("%a %b %d"))]
        for gm in rows[:35]:
            aw, hm = gm["away"], gm["home"]
            tail = spread_text(gm["odds"]) if gm["state"] == "pre" else ("%s-%s (%s)" % (aw["score"], hm["score"], gm["short"] or "Final"))
            lines.append("%-5s @ %-5s  %s" % (aw["abbr"], hm["abbr"], tail))
        lines.append("```")
        if copy_to_clipboard("\n".join(lines)):
            self.say("Copied board (%d games) for Discord" % min(len(rows), 35))
        else:
            self.say("Clipboard tool (wl-copy/xclip) not found")

    # -- input -------------------------------------------------------------
    def handle(self, ch):
        if ch == ord("q"):
            return False
        if ch == 27:  # Esc
            if self.view == "news" and self.news_story:
                self.news_story = None
                self.news_scroll = 0
            elif self.view in ("extra", "detail", "news", "help", "group_picker"):
                self.view = "board"
                self.scroll = 0
            self.scr.clear()
            return True
        if ch == ord("?"):
            self.view = "help" if self.view != "help" else "board"
            self.scr.clear()
            return True
        if ch == ord("r"):
            self.cache.clear()
            self.say("Refreshing...")
            return True
        if ch == ord("g"):
            order = ["nerd", "unicode", "emoji", "ascii"]
            self.glyphs = order[(order.index(self.glyphs) + 1) % len(order)] if self.glyphs in order else "unicode"
            self.save_config()
            self.say("glyphs: %s" % self.glyphs)
            return True

        if self.view == "help":
            self.view = "board"
            return True
        if self.view == "group_picker":
            return self.handle_group_picker(ch)
        if self.view == "board":
            return self.handle_board(ch)
        if self.view == "extra":
            return self.handle_extra(ch)
        if self.view == "detail":
            return self.handle_detail(ch)
        if self.view == "news":
            return self.handle_news(ch)
        return True

    def handle_board(self, ch):
        _, w = self.scr.getmaxyx()
        games = self.cache_get(self.board_key()) or []
        rows = self.visible(games)
        cols = self.grid_cols(w) if self.layout == "grid" else 1

        if ch in (ord("1"), ord("2"), ord("3"), ord("4"), ord("5"), ord("6"), ord("7")):
            if not self.only:
                self.switch_league(LEAGUES[int(chr(ch)) - 1]["key"])
            elif ch in (ord("1"), ord("2")) and rows:
                # In standalone league mode (like cfbtui), 1 and 2 star away/home!
                cur_gm = rows[self.selected_index(rows)]
                side = cur_gm["away" if ch == ord("1") else "home"]
                self.toggle_fav(side, cur_gm)
        elif ch == 9 and not self.only:  # Tab
            i = [lg["key"] for lg in LEAGUES].index(self.league_key)
            self.switch_league(LEAGUES[(i + 1) % len(LEAGUES)]["key"])
        elif ch == curses.KEY_BTAB and not self.only:
            i = [lg["key"] for lg in LEAGUES].index(self.league_key)
            self.switch_league(LEAGUES[(i - 1) % len(LEAGUES)]["key"])
        elif ch == curses.KEY_LEFT:
            self.move(-1, rows)
        elif ch == curses.KEY_RIGHT:
            self.move(1, rows)
        elif ch in (curses.KEY_UP, ord("k")):
            self.move(-cols, rows)
        elif ch in (curses.KEY_DOWN, ord("j")):
            self.move(cols, rows)
        elif ch == curses.KEY_NPAGE:
            self.move(cols * 4, rows)
        elif ch == curses.KEY_PPAGE:
            self.move(-cols * 4, rows)
        elif ch in (curses.KEY_ENTER, 10, 13):
            if rows:
                self.detail_game = rows[self.selected_index(rows)]
                self.detail_scroll = 0
                self.view = "detail"
                self.scr.clear()
        elif ch == ord("["):
            self.week = None
            self.date -= dt.timedelta(days=1)
            self.scroll = 0
            self.scr.clear()
        elif ch == ord("]"):
            self.week = None
            self.date += dt.timedelta(days=1)
            self.scroll = 0
            self.scr.clear()
        elif ch in (ord("w"), ord("W")) and self.lg()["key"] in ("cfb", "nfl"):
            cur_week = self.week or (games[0].get("week") if games else 1)
            delta = 1 if ch == ord("w") else -1
            self.week = max(1, cur_week + delta)
            self.date += dt.timedelta(weeks=delta)
            self.scroll = 0
            self.scr.clear()
            self.say("Week %d" % self.week)
        elif ch == ord("t"):
            self.week = None
            self.date = today()
            self.scroll = 0
            self.scr.clear()
        elif ch == ord("v"):
            self.layout = "list" if self.layout == "grid" else "grid"
            self.scroll = 0
            self.scr.clear()
            self.save_config()
        elif ch == ord("l"):
            options = ["all", "live", "fav", "upsets"] + (["top25"] if self.lg()["poll"] else [])
            self.filter = options[(options.index(self.filter) + 1) % len(options)] if self.filter in options else "all"
            self.scroll = 0
            self.scr.clear()
            self.say("filter: %s" % self.filter)
        elif ch == ord("o"):
            self.open_group_picker()
        elif ch == ord("R"):
            if not self.lg()["poll"]:
                self.say("%s has no poll — showing standings" % self.lg()["name"])
                self.open_extra("stand")
            else:
                self.open_extra("ranks")
        elif ch == ord("T"):
            self.open_extra("stand")
        elif ch == ord("N"):
            self.view = "news"
            self.news_sel = self.news_scroll = 0
            self.news_story = None
            self.scr.clear()
        elif ch in (ord("a"), ord("!")) and rows:
            cur_gm = rows[self.selected_index(rows)]
            self.toggle_fav(cur_gm["away"], cur_gm)
        elif ch in (ord("h"), ord("@")) and rows:
            cur_gm = rows[self.selected_index(rows)]
            self.toggle_fav(cur_gm["home"], cur_gm)
        elif ch == ord("c") and rows:
            self.copy_game_discord(rows[self.selected_index(rows)])
        elif ch == ord("C"):
            self.copy_board_discord(rows)
        return True

    def handle_detail(self, ch):
        if ch in (curses.KEY_UP, ord("k")):
            self.detail_scroll = max(0, self.detail_scroll - 1)
        elif ch in (curses.KEY_DOWN, ord("j")):
            self.detail_scroll += 1
        elif ch == curses.KEY_NPAGE:
            self.detail_scroll += 8
        elif ch == curses.KEY_PPAGE:
            self.detail_scroll = max(0, self.detail_scroll - 8)
        elif ch == ord("c") and self.detail_game:
            self.copy_game_discord(self.detail_game)
        elif ch in (curses.KEY_ENTER, 10, 13, ord("b")):
            self.view = "board"
        return True

    def handle_extra(self, ch):
        if ch in (ord("1"), ord("2"), ord("3"), ord("4"), ord("5"), ord("6"), ord("7")) and not self.only:
            self.switch_league(LEAGUES[int(chr(ch)) - 1]["key"])
        elif ch == ord("R"):
            if self.extra_kind == "ranks":
                self.view = "board"
            elif self.lg()["poll"]:
                self.open_extra("ranks")
        elif ch == ord("T"):
            if self.extra_kind == "stand":
                self.view = "board"
            else:
                self.open_extra("stand")
        elif ch in (curses.KEY_UP, ord("k")):
            self.extra_scroll = max(0, self.extra_scroll - 1)
        elif ch in (curses.KEY_DOWN, ord("j")):
            self.extra_scroll += 1
        elif ch in (curses.KEY_LEFT, ord("h")):
            if self.extra_kind == "ranks":
                self.extra_tab = max(0, self.extra_tab - 1)
            else:
                self.extra_group = max(0, self.extra_group - 1)
            self.extra_scroll = 0
        elif ch in (curses.KEY_RIGHT, ord("l")):
            if self.extra_kind == "ranks":
                polls = self.cache_get("ranks:%s" % self.league_key) or []
                self.extra_tab = min(max(0, len(polls) - 1), self.extra_tab + 1)
            else:
                groups = self.cache_get("stand:%s" % self.league_key) or []
                self.extra_group = min(max(0, len(groups) - 1), self.extra_group + 1)
            self.extra_scroll = 0
        return True

    def handle_news(self, ch):
        items = self.cache_get("news:%s" % self.league_key) or []
        if self.news_story:
            if ch in (curses.KEY_UP, ord("k")):
                self.news_scroll = max(0, self.news_scroll - 1)
            elif ch in (curses.KEY_DOWN, ord("j")):
                self.news_scroll += 1
            elif ch == ord("o") and self.news_story[2]:
                webbrowser.open(self.news_story[2])
                self.say("Opened story in browser")
            elif ch in (curses.KEY_ENTER, 10, 13, ord("b")):
                self.news_story = None
                self.news_scroll = 0
            return True

        if ch == ord("N"):
            self.view = "board"
        elif ch in (curses.KEY_UP, ord("k")):
            self.news_sel = max(0, self.news_sel - 1)
        elif ch in (curses.KEY_DOWN, ord("j")):
            if items:
                self.news_sel = min(len(items) - 1, self.news_sel + 1)
        elif ch == ord("o") and items:
            art = items[self.news_sel]
            if art.get("web_url"):
                webbrowser.open(art["web_url"])
                self.say("Opened in browser")
        elif ch in (curses.KEY_ENTER, 10, 13) and items:
            art = items[self.news_sel]
            body = art.get("description") or "No preview text available. Press 'o' to open the full article in your browser."
            if art.get("story_url"):
                try:
                    st_data = fetch_json(art["story_url"], timeout=6)
                    raw_body = dig(st_data, "headlines", 0, "story") or ""
                    if raw_body:
                        body = strip_html(raw_body)
                except Exception:  # noqa: BLE001
                    pass
            self.news_story = (art["headline"], body, art.get("web_url") or "")
            self.news_scroll = 0
        return True

    def switch_league(self, key):
        if key == self.league_key:
            return
        self.league_key = key
        self.week = None
        self.group_filter = None
        self.group_name = None
        self.sel_id = None
        self.scroll = 0
        self.extra_tab = self.extra_group = self.extra_sel = self.extra_scroll = 0
        self.view = "board"
        self.filter = "all"
        if self.scr:
            self.scr.clear()
        self.save_config()

    def move(self, delta, rows):
        if not rows:
            return
        idx = self.selected_index(rows)
        idx = max(0, min(len(rows) - 1, idx + delta))
        self.sel_id = rows[idx]["id"]

    def toggle_fav(self, side, game=None):
        lg = (game.get("league") if game else None) or (self.league_key if self.league_key != "all" else "cfb")
        key = "%s:%s" % (lg, side["abbr"])
        if key in self.favs:
            self.favs.discard(key)
            self.say("Unstarred %s %s" % (lg.upper(), side["abbr"]))
        else:
            self.favs.add(key)
            self.say("Starred %s %s" % (lg.upper(), side["abbr"]))
        if self.scr:
            self.scr.clear()
        self.save_config()

    def open_extra(self, kind):
        self.view = "extra"
        self.extra_kind = kind
        self.extra_sel = self.extra_scroll = 0
        self.extra_group = 0
        self.extra_tab = 0
        if self.scr:
            self.scr.clear()


# --------------------------------------------------------------------------
# plain mode
# --------------------------------------------------------------------------

def plain(args):
    target = args.league or getattr(args, "only", None)
    if target == "all":
        target = None
    leagues = [BY_KEY[target]] if target else SPORT_LEAGUES
    if target and target not in BY_KEY:
        print("unknown league: %s (choose %s)" % (target, ", ".join(BY_KEY)), file=sys.stderr)
        return 2
    date = args.date or today()
    week = getattr(args, "week", None)
    for lg in leagues:
        try:
            games = parse_board(lg, date, week=week if lg["key"] in ("cfb", "nfl") else None)
        except Exception as exc:  # noqa: BLE001
            print("%-4s  error: %s" % (lg["name"], exc))
            continue
        game_week = (games[0].get("week") if games else None) or week
        wk_str = (" Week %d " % game_week) if (game_week and lg["key"] in ("cfb", "nfl")) else " "
        print("== %s%s%s  (%d games)" % (lg["name"], wk_str, date.strftime("%a %b %d"), len(games)))
        if not games:
            print("   no games")
            continue
        order = {"in": 0, "pre": 1, "post": 2}
        games.sort(key=lambda g: (order.get(g["state"], 3), g["start"] or dt.datetime.max.replace(tzinfo=dt.timezone.utc)))
        for g in games:
            away, home = g["away"], g["home"]
            if g["state"] == "pre":
                status = g["start"].strftime("%a %H:%M") if g["start"] else ""
                tail = spread_text(g["odds"])
            else:
                status = g["short"] or g["detail"]
                tail = "%s-%s" % (away["score"], home["score"])
            print("   %-5s %-5s @ %-5s %-5s  %-14s %s" % (
                away["abbr"], away["record"], home["abbr"], home["record"], status[:14], tail))
    return 0


# --------------------------------------------------------------------------
# entry points
# --------------------------------------------------------------------------

def run(scr, args):
    app = App(scr, args)
    try:
        while True:
            app.pump()
            app.draw()
            ch = scr.getch()
            if ch == -1:
                continue
            if ch == curses.KEY_RESIZE:
                app.scroll = 0
                continue
            if not app.handle(ch):
                break
    finally:
        app.save_config()


ALIASES = {
    "cfbtui": "cfb",
    "ncaabtui": "cbb",
    "cbbtui": "cbb",
    "nbatui": "nba",
    "nhltui": "nhl",
    "mlbtui": "mlb",
    "nfltui": "nfl",
}


def build_parser(prog="sportstui"):
    only = ALIASES.get(prog)
    parser = argparse.ArgumentParser(
        prog=prog,
        description=("A terminal scoreboard for %s." % BY_KEY[only]["name"])
        if only else "A terminal scoreboard for CFB, NFL, NHL, NBA, CBB and MLB.",
    )
    parser.add_argument("--league", choices=list(BY_KEY),
                        help="start on this league (combined board only)")
    parser.add_argument("--date", type=lambda s: dt.date.fromisoformat(s), help="YYYY-MM-DD")
    parser.add_argument("--week", type=int, help="start on week N (CFB / NFL only)")
    parser.add_argument("--layout", choices=["grid", "list"])
    parser.add_argument("--glyphs", choices=list(GLYPHS))
    parser.add_argument("--plain", action="store_true", help="print the board and exit")
    parser.add_argument("--version", action="version", version="%s %s" % (prog, VERSION))
    return parser


def parse_args(argv=None, prog="sportstui"):
    parser = build_parser(prog)
    args = parser.parse_args(argv)
    args.only = ALIASES.get(prog)
    return args


def main(argv=None):
    prog = os.path.basename(sys.argv[0]) if argv is None else "sportstui"
    args = parse_args(argv, prog=prog)
    if args.only and args.league and args.league != args.only:
        sys.exit("%s only shows %s" % (prog, args.only.upper()))
    if args.week and args.only and args.only not in ("cfb", "nfl"):
        sys.exit("--week only applies to CFB and NFL")
    if args.plain:
        return plain(args)
    if os.environ.get("TERM") in (None, "", "dumb"):
        os.environ["TERM"] = "xterm-256color"
    curses.wrapper(run, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
