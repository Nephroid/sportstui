#!/usr/bin/env python3
"""sportstui - six leagues, one scoreboard, zero dependencies.

A terminal scoreboard for CFB, CBB, NHL, NBA, MLB and NFL.
Data comes from ESPN's public (undocumented) scoreboard API.

Keys:  1-6 or Tab switch league   [ ] prev/next day   t today
       v layout   l filter   R rankings   T standings
       Enter game detail   a/h star away/home   ? help   q quit
"""

import argparse
import curses
import datetime as dt
import json
import os
import queue
import sys
import threading
import time
import urllib.error
import urllib.request

VERSION = "1.0.0"
UA = "sportstui/1.0 (terminal scoreboard)"
SITE = "https://site.api.espn.com/apis/site/v2/sports"
CORE = "https://site.api.espn.com/apis/v2/sports"
CONFIG_PATH = os.path.expanduser(
    os.environ.get("SPORTSTUI_CONFIG", "~/.config/sportstui/config.json")
)
HERE = os.path.dirname(os.path.realpath(__file__))

LEAGUES = [
    {"key": "cfb", "name": "CFB", "path": "football/college-football", "poll": True},
    {"key": "cbb", "name": "CBB", "path": "basketball/mens-college-basketball", "poll": True},
    {"key": "nhl", "name": "NHL", "path": "hockey/nhl", "poll": False},
    {"key": "nba", "name": "NBA", "path": "basketball/nba", "poll": False},
    {"key": "mlb", "name": "MLB", "path": "baseball/mlb", "poll": False},
    {"key": "nfl", "name": "NFL", "path": "football/nfl", "poll": False},
]
BY_KEY = {lg["key"]: lg for lg in LEAGUES}

# Imported from your cfbtui config (team ids 127, 251, 87 -> MSU, TEX, ND).
DEFAULT_FAVORITES = [
    "cfb:MSU", "cfb:ND", "cfb:TEX",
    "cbb:MSU",
    "nba:PHI", "nba:DET",
    "nhl:DET",
    "mlb:DET",
    "nfl:DET",
]

GLYPHS = {
    "nerd": {"tl": "┌", "tr": "┐", "bl": "└", "br": "┘", "h": "─", "v": "│",
             "live": "●", "star": "★", "dot": "·"},
    "unicode": {"tl": "┌", "tr": "┐", "bl": "└", "br": "┘", "h": "─", "v": "│",
                "live": "●", "star": "★", "dot": "·"},
    "ascii": {"tl": "+", "tr": "+", "bl": "+", "br": "+", "h": "-", "v": "|",
              "live": "*", "star": "*", "dot": "-"},
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


# --------------------------------------------------------------------------
# parsers
# --------------------------------------------------------------------------

def scoreboard_url(lg, date, week=None):
    url = "%s/%s/scoreboard?limit=250" % (SITE, lg["path"])
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
        if (r.get("type") or "").lower() in ("total", "overall"):
            rec = r.get("summary") or ""
            break
    if not rec and records:
        rec = records[0].get("summary") or ""
    rank = dig(comp, "curatedRank", "current")
    if rank in (0, 99, None):
        rank = None
    return {
        "abbr": team.get("abbreviation") or team.get("shortDisplayName") or "?",
        "name": team.get("shortDisplayName") or team.get("name") or "?",
        "full": team.get("displayName") or "",
        "color": (team.get("color") or "888888").lstrip("#"),
        "score": comp.get("score"),
        "record": rec,
        "rank": rank,
        "winner": bool(comp.get("winner")),
        "logo": dig(team, "logo"),
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


def parse_game(ev, lg):
    comp = dig(ev, "competitions", 0, default={}) or {}
    status = dig(ev, "status", "type", default={}) or {}
    sides = {}
    for c in comp.get("competitors") or []:
        ha = c.get("homeAway")
        if ha in ("home", "away"):
            sides[ha] = parse_side(c)
    if "home" not in sides or "away" not in sides:
        return None
    odds = (comp.get("odds") or [{}])[0]
    broadcasts = comp.get("broadcasts") or []
    tv = ", ".join(dig(b, "names", 0, default="") for b in broadcasts).strip(", ")
    return {
        "id": str(ev.get("id")),
        "league": lg["key"],
        "start": parse_iso(ev.get("date")),
        "week": dig(ev, "week", "number"),
        "state": status.get("state") or "pre",
        "detail": status.get("detail") or "",
        "short": status.get("shortDetail") or "",
        "clock": dig(ev, "status", "displayClock", default="") or "",
        "period": dig(ev, "status", "period", default=0) or 0,
        "away": sides["away"],
        "home": sides["home"],
        "odds": odds,
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


def parse_rankings(lg):
    data = fetch_json("%s/%s/rankings" % (SITE, lg["path"]))
    polls = []
    for poll in data.get("rankings") or []:
        ptype = (poll.get("type") or "").lower()
        name = poll.get("name") or ""
        if lg["key"] == "cfb":
            if ptype not in ("ap", "coaches", "cfp"):
                continue
        elif ptype not in ("ap", "coaches"):
            continue
        ranks = []
        for r in poll.get("ranks") or []:
            team = r.get("team") or {}
            ranks.append({
                "rank": r.get("current") or 0,
                "prev": r.get("previous") or 0,
                "team": team.get("shortDisplayName") or team.get("nickname") or "?",
                "abbr": team.get("abbreviation") or "",
                "record": r.get("recordSummary") or "",
                "points": r.get("points") or 0,
                "first": r.get("firstPlaceVotes") or 0,
                "trend": r.get("trend") or "",
            })
        if ranks:
            polls.append({"name": name, "type": ptype, "ranks": ranks})
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
                    stats[s.get("name") or ""] = s.get("displayValue")
                rows.append({
                    "team": team.get("shortDisplayName") or team.get("name") or "?",
                    "abbr": team.get("abbreviation") or "",
                    "color": (team.get("color") or "888888").lstrip("#"),
                    "stats": stats,
                })

            def order(row):
                try:
                    pct = float(row["stats"].get("winPercent") or -1)
                except (TypeError, ValueError):
                    pct = -1.0
                try:
                    wins = float(row["stats"].get("wins") or 0)
                except (TypeError, ValueError):
                    wins = 0.0
                return (-pct, -wins, row["team"])

            if any("winPercent" in r["stats"] for r in rows):
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
    "nba": [("wins", "W"), ("losses", "L"), ("winPercent", "PCT"),
            ("gamesBehind", "GB"), ("streak", "STRK")],
    "nhl": [("wins", "W"), ("losses", "L"), ("otLosses", "OTL"), ("points", "PTS"),
            ("winPercent", "PCT"), ("streak", "STRK")],
    "mlb": [("wins", "W"), ("losses", "L"), ("winPercent", "PCT"),
            ("gamesBehind", "GB"), ("streak", "STRK")],
    "nfl": [("wins", "W"), ("losses", "L"), ("ties", "T"),
            ("winPercent", "PCT"), ("streak", "STRK")],
    "cfb": [("wins", "W"), ("losses", "L"), ("winPercent", "PCT"), ("streak", "STRK")],
    "cbb": [("wins", "W"), ("losses", "L"), ("winPercent", "PCT"), ("streak", "STRK")],
}


def parse_detail(lg, event_id):
    url = "%s/%s/summary?event=%s" % (SITE, lg["path"], event_id)
    data = fetch_json(url)
    plays = []
    for p in data.get("plays") or []:
        if not p.get("scoringPlay"):
            continue
        plays.append({
            "clock": dig(p, "clock", "displayValue", default="") or "",
            "period": dig(p, "period", "number", default=0) or 0,
            "team": dig(p, "team", "abbreviation", default="") or "",
            "text": (p.get("text") or "").strip(),
        })
    leaders = []
    for tm in data.get("leaders") or []:
        abbr = dig(tm, "team", "abbreviation", default="") or ""
        cats = []
        for cat in tm.get("leaders") or []:
            top = (cat.get("leaders") or [{}])[0]
            who = (dig(top, "athlete", "displayName") or top.get("displayName") or "").strip()
            cats.append("%s: %s %s" % (
                cat.get("displayName") or cat.get("name") or "",
                who,
                top.get("displayValue") or "",
            ))
        if cats:
            leaders.append((abbr, cats))
    winprob = None
    wp = data.get("winprobability") or []
    if wp:
        last = wp[-1]
        home = last.get("homeWinPercentage")
        if home is not None:
            winprob = (1.0 - float(home), float(home))
    return {"plays": plays, "leaders": leaders, "winprob": winprob}


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

    def _run(self):
        while True:
            key, fn = self.req.get()
            try:
                value, err = fn(), None
            except Exception as exc:  # noqa: BLE001 - surface any fetch failure
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
# colours
# --------------------------------------------------------------------------

def hex_rgb(value):
    value = (value or "").lstrip("#")
    if len(value) != 6:
        return (136, 136, 136)
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (136, 136, 136)


def hex_to_xterm(value):
    r, g, b = hex_rgb(value)
    if max(r, g, b) - min(r, g, b) < 14:
        grey = int(round((r - 8) / 10))
        return 232 + max(0, min(23, grey))
    steps = (0, 95, 135, 175, 215, 255)

    def near(v):
        return min(range(6), key=lambda i: abs(steps[i] - v))

    return 16 + 36 * near(r) + 6 * near(g) + near(b)


BASIC = [
    (curses.COLOR_BLACK, (0, 0, 0)), (curses.COLOR_RED, (205, 49, 49)),
    (curses.COLOR_GREEN, (13, 188, 121)), (curses.COLOR_YELLOW, (229, 229, 16)),
    (curses.COLOR_BLUE, (36, 114, 200)), (curses.COLOR_MAGENTA, (188, 63, 188)),
    (curses.COLOR_CYAN, (17, 168, 205)), (curses.COLOR_WHITE, (229, 229, 229)),
]


def hex_to_basic(value):
    r, g, b = hex_rgb(value)
    best, dist = curses.COLOR_WHITE, None
    for code, (br, bg, bb) in BASIC:
        d = (r - br) ** 2 + (g - bg) ** 2 + (b - bb) ** 2
        if dist is None or d < dist:
            best, dist = code, d
    return best


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
        self.favs = set(self.cfg.get("favorites") or [])
        self.only = getattr(opts, "only", None)   # set when run as <league>tui
        if self.only not in BY_KEY:
            self.only = None
        self.league_key = self.only or opts.league or self.cfg.get("league") or "cfb"
        if self.league_key not in BY_KEY:
            self.league_key = "cfb"
        self.date = opts.date or today()
        self.week = getattr(opts, "week", None)
        self.layout = opts.layout or self.cfg.get("layout") or "grid"
        self.glyphs = opts.glyphs or self.cfg.get("glyphs") or "nerd"
        self.view = "board"          # board | extra | detail | help
        self.filter = "all"
        self.sel_id = None
        self.scroll = 0
        self.extra_kind = None       # ranks | standings
        self.extra_tab = 0
        self.extra_group = 0
        self.extra_sel = 0
        self.extra_scroll = 0
        self.detail_game = None
        self.detail_sel = 0
        self.notice = ("", 0.0)
        self.last_error = ""
        self.dirty = False
        self.init_colors()
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
        self.colours = curses.has_colors()
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
            self.accent, self.good = 214, 114
            self.bg_sel = 236
        else:
            self.fg, self.dim, self.live = curses.COLOR_WHITE, curses.COLOR_CYAN, curses.COLOR_RED
            self.accent, self.good = curses.COLOR_YELLOW, curses.COLOR_GREEN
            self.bg_sel = curses.COLOR_BLUE

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

    def team_attr(self, colour):
        code = hex_to_xterm(colour) if curses.COLORS >= 256 else hex_to_basic(colour)
        return self.pair(code)

    def attr(self, kind):
        if not self.colours:
            return curses.A_BOLD if kind in ("live", "accent") else curses.A_NORMAL
        if kind == "base":
            return self.pair(self.fg)
        if kind == "dim":
            return self.pair(self.dim)
        if kind == "live":
            return self.pair(self.live) | curses.A_BOLD
        if kind == "accent":
            return self.pair(self.accent) | curses.A_BOLD
        if kind == "good":
            return self.pair(self.good)
        if kind == "bar":
            return self.pair(self.bg_sel, self.fg) if curses.COLORS >= 256 else curses.A_REVERSE
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
        if not ent:
            self.fetcher.request(key, fn)
        elif now - ent[0] >= ttl:
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

    def status_text(self, game):
        if game["state"] == "in":
            return game["short"] or game["detail"] or "Live"
        if game["state"] == "post":
            return game["short"] or "Final"
        start = game["start"]
        if start is None:
            return ""
        if start.date() == today():
            return start.strftime("%a %-I:%M %p")
        return start.strftime("%b %-d %-I:%M %p")

    def is_fav(self, side):
        return "%s:%s" % (self.league_key, side["abbr"]) in self.favs

    def game_fav(self, game):
        return self.is_fav(game["away"]) or self.is_fav(game["home"])

    def visible(self, games):
        rows = list(games or [])
        if self.filter == "live":
            rows = [g for g in rows if g["state"] == "in"]
        elif self.filter == "top25":
            rows = [g for g in rows if g["away"]["rank"] or g["home"]["rank"]]
        elif self.filter == "fav":
            rows = [g for g in rows if self.game_fav(g)]
        order = {"in": 0, "pre": 1, "post": 2}
        rows.sort(key=lambda g: (
            0 if self.game_fav(g) else 1,
            order.get(g["state"], 3),
            g["start"] or dt.datetime.max,
            g["id"],
        ))
        return rows

    def selected_index(self, rows):
        for i, row in enumerate(rows):
            if row["id"] == self.sel_id:
                return i
        return 0

    def keep_visible(self, count, height):
        if self.scroll > max(0, count - height):
            self.scroll = max(0, count - height)

    def say(self, text, secs=2.5):
        self.notice = (text, time.time() + secs)

    # -- drawing helpers ---------------------------------------------------
    def put(self, y, x, text, attr=curses.A_NORMAL, width=None, reverse=False):
        if y < 0:
            return
        h, w = self.scr.getmaxyx()
        if y >= h or x >= w:
            return
        if width is not None:
            text = text[:max(0, min(width, w - x))]
        else:
            text = text[:max(0, w - x)]
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
            text = text[:width]
            self.put(y, x, text, attr, reverse=reverse)
            x += len(text)
            width -= len(text)

    def clear_line(self, y, reverse=False):
        h, w = self.scr.getmaxyx()
        if y < 0 or y >= h:
            return
        try:
            self.scr.move(y, 0)
            self.scr.clrtoeol()
            if reverse:
                self.scr.addstr(y, 0, " " * max(0, w - 1), curses.A_REVERSE)
        except curses.error:
            pass

    # -- chrome ------------------------------------------------------------
    def draw(self):
        self.scr.erase()
        h, w = self.scr.getmaxyx()
        if h < 10 or w < 50:
            self.put(0, 0, "terminal too small - need at least 50x10", self.attr("live"))
            self.scr.refresh()
            return
        self.draw_header()
        body_top, body_h = 2, h - 3
        if self.view == "board":
            self.draw_board(body_top, body_h, w)
        elif self.view == "extra":
            self.draw_extra(body_top, body_h, w)
        elif self.view == "detail":
            self.draw_detail(body_top, body_h, w)
        elif self.view == "help":
            self.draw_help(body_top, body_h, w)
        self.draw_footer(h, w)
        self.scr.refresh()

    def draw_header(self):
        h, w = self.scr.getmaxyx()
        self.clear_line(0)
        segs = []
        if self.only:
            label = " %s " % self.lg()["name"]
            segs.append((label, self.attr("bar")))
            segs.append((" sportstui", self.attr("dim")))
        else:
            for i, lg in enumerate(LEAGUES):
                active = lg["key"] == self.league_key
                label = " %d %s " % (i + 1, lg["name"])
                segs.append((label, self.attr("bar") if active else self.attr("dim")))
        used = sum(len(s) for s, _ in segs)
        games = self.cache_get(self.board_key()) or []
        game_week = (games[0].get("week") if games else None) or getattr(self, "week", None)
        wk_str = ("Wk %d · " % game_week) if (game_week and self.league_key in ("cfb", "nfl")) else ""
        right = wk_str + self.date.strftime("%a %b %-d")
        if w - used - len(right) - 1 > 0:
            segs.append((" " * max(1, w - used - len(right) - 1), self.attr("base")))
            segs.append((right + " ", self.attr("dim")))
        self.segment(0, 0, segs, w)
        self.clear_line(1)

    def draw_footer(self, h, w):
        self.clear_line(h - 2)
        self.clear_line(h - 1)
        games = self.cache_get(self.board_key()) or []
        live = sum(1 for g in games if g["state"] == "in")
        ent = self.cache.get(self.board_key())
        age = int(time.time() - ent[0]) if ent else None
        if last := self.notice[0] if time.time() < self.notice[1] else "":
            left = " " + last
        elif self.view == "board":
            filt = "all" if self.filter == "all" else self.filter
            left = " %s · %s · %s" % (self.lg()["name"], self.date.strftime("%a %-d %b"), filt)
        elif self.view == "extra":
            left = " %s · %s" % (self.lg()["name"], "rankings" if self.extra_kind == "ranks" else "standings")
        elif self.view == "detail":
            left = " game detail"
        else:
            left = " help"
        status = "%d games · %d live" % (len(games), live) if ent is not None else "loading"
        if age is not None:
            status += " · %ds ago" % age
        if self.last_error and time.time() < self.notice[1] + 30:
            status = "offline - last data shown"
        right = status + " "
        self.put(h - 2, 0, left, self.attr("bar"))
        if w > len(left) + len(right):
            self.put(h - 2, w - len(right), right, self.attr("bar"))
        hint = (" [ ] day   v layout   l filter   R ranks   T table   ⏎ detail   a/h star   ? help   q quit "
                if self.only else
                " 1-6 league   [ ] day   v layout   l filter   R ranks   T table   ⏎ detail   a/h star   ? help   q quit ")
        self.put(h - 1, 0, hint, self.attr("dim"))

    # -- board -------------------------------------------------------------
    def draw_board(self, top, height, width):
        key = self.board_key()
        games = self.cache_get(key)
        ttl = self.ttl(games)
        self.ensure(key, lambda: parse_board(self.lg(), self.date, getattr(self, "week", None)), ttl)
        games = self.cache_get(key)
        if games is None:
            if self.last_error:
                self.put(top + 1, 2, "offline / error: %s" % self.last_error, self.attr("live"))
            else:
                self.put(top + 1, 2, "fetching %s..." % self.lg()["name"], self.attr("dim"))
            return
        rows = self.visible(games)
        if not rows:
            self.put(top + 1, 2, "no games", self.attr("dim"))
            return
        if self.layout == "grid":
            self.draw_grid(rows, top, height, width)
        else:
            self.draw_list(rows, top, height, width)

    # list ----------------------------------------------------------------
    def draw_list(self, rows, top, height, width):
        idx = self.selected_index(rows)
        if idx < self.scroll:
            self.scroll = idx
        if idx >= self.scroll + height:
            self.scroll = idx - height + 1
        self.scroll = max(0, min(self.scroll, max(0, len(rows) - height)))
        for i in range(self.scroll, min(len(rows), self.scroll + height)):
            y = top + (i - self.scroll)
            self.draw_row(rows[i], y, width, i == idx)

    def draw_row(self, game, y, width, selected):
        g = self.g()
        away, home = game["away"], game["home"]
        if selected:
            self.put(y, 0, " " * max(0, width - 1), self.attr("bar"))
        star = g["star"] if self.game_fav(game) else " "
        live = g["live"] if game["state"] == "in" else " "
        ra = ("#%-2s " % away["rank"]) if away["rank"] else "    "
        rh = ("#%-2s " % home["rank"]) if home["rank"] else "    "
        segs = [
            (star, self.attr("accent")),
            (live + " ", self.attr("live")),
            (ra, self.attr("dim")),
            ("%-5s" % away["abbr"], self.team_attr(away["color"])),
            (" %-6s" % away["record"], self.attr("dim")),
            (" @ ", self.attr("dim")),
            (rh, self.attr("dim")),
            ("%-5s" % home["abbr"], self.team_attr(home["color"])),
            (" %-6s" % home["record"], self.attr("dim")),
        ]
        left = "".join(s for s, _ in segs)
        status = self.status_text(game)
        if game["state"] == "pre":
            tail = spread_text(game["odds"])
        else:
            tail = "%s-%s" % (away["score"], home["score"])
        right = status[:16].ljust(16) + "  " + tail
        gap = max(1, width - len(left) - len(right))
        segs.append((" " * gap, self.attr("base")))
        segs.append((status[:16], self.attr("live") if game["state"] == "in" else self.attr("base")))
        segs.append((" " * max(2, width - len(left) - gap - len(status[:16]) - len(tail)), self.attr("base")))
        segs.append((tail, self.attr("base")))
        self.segment(y, 0, segs, width, reverse=selected)

    # grid ----------------------------------------------------------------
    def draw_grid(self, rows, top, height, width):
        g = self.g()
        cw, ch = 34, 5
        cols = max(1, width // (cw + 1))
        cell_rows = max(1, (height + 1) // ch)
        idx = self.selected_index(rows)
        sel_row = idx // cols
        if sel_row < self.scroll:
            self.scroll = sel_row
        if sel_row >= self.scroll + cell_rows:
            self.scroll = sel_row - cell_rows + 1
        self.scroll = max(0, min(self.scroll, max(0, (len(rows) + cols - 1) // cols - cell_rows)))
        start = self.scroll * cols
        for n in range(start, min(len(rows), start + cols * cell_rows)):
            pos = n - start
            y = top + (pos // cols) * ch
            x = (pos % cols) * (cw + 1)
            if y + ch > top + height + 1:
                break
            self.draw_card(rows[n], y, x, cw, n == idx)

    def draw_card(self, game, y, x, cw, selected):
        g = self.g()
        away, home = game["away"], game["home"]
        inner = cw - 2
        border = self.attr("live") if selected else self.attr("dim")
        self.put(y, x, g["tl"] + g["h"] * inner + g["tr"], border)
        self.put(y + 4, x, g["bl"] + g["h"] * inner + g["br"], border)
        for yy in range(1, 4):
            self.put(y + yy, x, g["v"], border)
            self.put(y + yy, x + cw - 1, g["v"], border)
            self.put(y + yy, x + 1, " " * inner, self.attr("base"))
        show_score = game["state"] != "pre"
        status = self.status_text(game)
        tail = ("%s-%s" % (away["score"], home["score"])) if show_score else spread_text(game["odds"])
        for i, side in enumerate((away, home)):
            rank = ("#%s " % side["rank"]) if side["rank"] else ""
            score = str(side["score"]) if show_score else ""
            mark = (g["star"] if self.game_fav(game) else " ") if i == 0 else " "
            segs = [(mark + " ", self.attr("accent")),
                    (rank, self.attr("dim")),
                    ("%-5s" % side["abbr"], self.team_attr(side["color"])),
                    (" %-5s" % side["record"], self.attr("dim"))]
            used = sum(len(s) for s, _ in segs)
            segs.append((" " * max(1, inner - used - len(score)), self.attr("base")))
            if score:
                segs.append((score, self.attr("base")))
            self.segment(y + 1 + i, x + 1, segs, inner, reverse=selected)
        dot = (g["live"] + " ") if game["state"] == "in" else ""
        csegs = [(" " + dot + status, self.attr("live") if game["state"] == "in" else self.attr("base"))]
        gap = max(1, inner - len(status) - len(dot) - 1 - len(tail))
        csegs.append((" " * gap, self.attr("base")))
        if tail:
            csegs.append((tail, self.attr("base")))
        self.segment(y + 3, x + 1, csegs, inner, reverse=selected)

    # -- extra views -------------------------------------------------------
    def draw_extra(self, top, height, width):
        lg = self.lg()
        if self.extra_kind == "ranks":
            key = "ranks:%s" % self.league_key
            data = self.ensure(key, lambda: parse_rankings(lg), 300)
            if data is None:
                self.put(top + 1, 2, "fetching rankings...", self.attr("dim"))
                return
            self.draw_ranks(data, top, height, width)
        else:
            key = "stand:%s" % self.league_key
            data = self.ensure(key, lambda: parse_standings(lg), 300)
            if data is None:
                self.put(top + 1, 2, "fetching standings...", self.attr("dim"))
                return
            self.draw_standings(data, top, height, width)

    def draw_ranks(self, polls, top, height, width):
        if not polls:
            self.put(top + 1, 2, "no poll published", self.attr("dim"))
            return
        self.extra_tab = min(self.extra_tab, len(polls) - 1)
        x = 1
        for i, poll in enumerate(polls):
            label = " %s " % poll["name"]
            self.put(top, x, label, self.attr("bar") if i == self.extra_tab else self.attr("dim"))
            x += len(label) + 1
        poll = polls[self.extra_tab]
        y0 = top + 2
        self.put(y0, 1, " #   " + "TEAM".ljust(20) + "REC".ljust(8) + "PTS".rjust(7) + "  TREND",
                 self.attr("dim"))
        rows = poll["ranks"]
        avail = height - 3
        self.extra_sel = max(0, min(self.extra_sel, len(rows) - 1))
        if self.extra_sel < self.extra_scroll:
            self.extra_scroll = self.extra_sel
        if self.extra_sel >= self.extra_scroll + avail:
            self.extra_scroll = self.extra_sel - avail + 1
        for i in range(self.extra_scroll, min(len(rows), self.extra_scroll + avail)):
            r = rows[i]
            y = y0 + 1 + (i - self.extra_scroll)
            trend = r["trend"] or ""
            try:
                pts = "%d" % int(float(r["points"]))
            except (TypeError, ValueError):
                pts = str(r["points"] or "")
            segs = [
                (" %-3d " % r["rank"], self.attr("accent")),
                ("%-20s" % r["team"][:20], self.attr("base")),
                ("%-8s" % r["record"], self.attr("dim")),
                ("%7s" % pts, self.attr("dim")),
                ("  " + trend.rjust(4), self.attr("good") if trend.startswith("+")
                 else self.attr("live") if trend.startswith("-") else self.attr("dim")),
            ]
            self.segment(y, 1, segs, width - 2, reverse=(i == self.extra_sel))

    def draw_standings(self, groups, top, height, width):
        if not groups:
            self.put(top + 1, 2, "no standings available", self.attr("dim"))
            return
        self.extra_group = max(0, min(self.extra_group, len(groups) - 1))
        panel = min(30, max(18, width // 5))
        first = max(0, self.extra_group - max(0, height - 2))
        for i in range(first, min(len(groups), first + height)):
            y = top + (i - first)
            label = groups[i]["name"]
            if len(label) > panel - 2:
                label = label[:panel - 4] + ".."
            self.put(y, 0, " " + label.ljust(panel - 1),
                     self.attr("bar") if i == self.extra_group else self.attr("dim"))
        grp = groups[self.extra_group]
        cols = [(k, h) for k, h in STANDING_COLS.get(self.league_key, [])
                if any(k in row["stats"] and row["stats"].get(k) not in (None, "", "-") for row in grp["rows"])]
        x = panel + 1
        maxcols = max(1, (width - x - 19) // 6)
        cols = cols[:min(6, maxcols)]
        header = "%-18s" % "TEAM" + "".join("%6s" % h for _, h in cols)
        self.put(top, x, header, self.attr("dim"))
        avail = height - 2
        self.extra_sel = max(0, min(self.extra_sel, len(grp["rows"]) - 1))
        if self.extra_sel < self.extra_scroll:
            self.extra_scroll = self.extra_sel
        if self.extra_sel >= self.extra_scroll + avail:
            self.extra_scroll = self.extra_sel - avail + 1
        for i in range(self.extra_scroll, min(len(grp["rows"]), self.extra_scroll + avail)):
            row = grp["rows"][i]
            segs = [("%-18s" % row["team"][:18], self.team_attr(row["color"]))]
            for key, _ in cols:
                segs.append(("%6s" % (row["stats"].get(key) or "-"), self.attr("base")))
            self.segment(top + 1 + (i - self.extra_scroll), x, segs, width - x, reverse=(i == self.extra_sel))

    # -- detail ------------------------------------------------------------
    def draw_detail(self, top, height, width):
        game = self.detail_game
        if not game:
            self.put(top, 2, "no game selected", self.attr("dim"))
            return
        key = "detail:%s:%s" % (game["league"], game["id"])
        data = self.ensure(key, lambda: parse_detail(self.lg(), game["id"]), 30)
        if data is None:
            self.put(top, 2, "loading game...", self.attr("dim"))
            return
        away, home = game["away"], game["home"]
        head = [
            (" %s " % away["abbr"], self.team_attr(away["color"])),
            ("%s" % (away["score"] if game["state"] != "pre" else ""), self.attr("base")),
            ("  @  ", self.attr("dim")),
            (" %s " % home["abbr"], self.team_attr(home["color"])),
            ("%s" % (home["score"] if game["state"] != "pre" else ""), self.attr("base")),
            ("   " + self.status_text(game), self.attr("live") if game["state"] == "in" else self.attr("dim")),
        ]
        self.segment(top, 1, head, width - 2)
        y = top + 2
        venue = game.get("venue") or ""
        tv = game.get("tv") or ""
        extra = " · ".join(x for x in (self.status_text(game) if game["state"] == "pre" else "", venue, tv) if x)
        if extra:
            self.put(y, 1, extra[:width - 2], self.attr("dim"))
            y += 1
        if data["winprob"]:
            a, h = data["winprob"]
            self.put(y, 1, "win probability  %s %.0f%%  ·  %s %.0f%%" % (
                away["abbr"], a * 100, home["abbr"], h * 100), self.attr("dim"))
            y += 2
        if data["leaders"] and y < top + height - 4:
            y += 1
            self.put(y, 1, "LEADERS", self.attr("accent"))
            y += 1
            for abbr, cats in data["leaders"]:
                line = " %-4s %s" % (abbr, "   ".join(cats))
                self.put(y, 1, line[:width - 2], self.attr("base"))
                y += 1
                if y >= top + height - 10:
                    break
            y += 1
        self.put(y, 1, "SCORING", self.attr("accent"))
        y += 1
        plays = list(reversed(data["plays"]))
        if not plays:
            self.put(y, 1, " no scoring plays yet", self.attr("dim"))
        for p in plays:
            if y >= top + height:
                break
            label = " %-8s %-4s %s" % ((p["clock"] or ""), (p["team"] or ""), p["text"])
            self.put(y, 1, label[:width - 2], self.attr("base"))
            y += 1

    # -- help --------------------------------------------------------------
    def draw_help(self, top, height, width):
        lines = [
            ("KEYS", "accent"),
            ("  1-6 / Tab      switch league" if not self.only else
             "  %s           this board is %s only" % (self.lg()["name"], self.lg()["name"]), "base"),
            ("  [ ]            previous / next day", "base"),
            ("  w / W          next / prev week (CFB, NFL)", "base"),
            ("  t              today", "base"),
            ("  Up/Down j/k    move selection", "base"),
            ("  Enter          game detail", "base"),
            ("  R              rankings (CFB, CBB)", "base"),
            ("  T              standings", "base"),
            ("  v              cards / list layout", "base"),
            ("  l              filter: all / top 25 / live / favorites", "base"),
            ("  a / h          star away / home team", "base"),
            ("  g              glyph set: nerd / unicode / ascii", "base"),
            ("  r              refresh now", "base"),
            ("  Esc            back", "base"),
            ("  q              quit", "base"),
            ("", "base"),
            ("FAVORITES", "accent"),
            ("  nba: PHI DET   nhl: DET   mlb: DET   nfl: DET", "dim"),
            ("  cbb: MSU       cfb: MSU ND TEX", "dim"),
        ]
        for i, (text, kind) in enumerate(lines[:height]):
            self.put(top + i, 2, text[:width - 4], self.attr(kind))

    # -- input -------------------------------------------------------------
    def handle(self, ch):
        if ch == ord("q"):
            return False
        if ch == 27:  # Esc
            if self.view in ("extra", "detail", "help"):
                self.view = "board"
                self.scroll = 0
            return True
        if ch == ord("?"):
            self.view = "help" if self.view != "help" else "board"
            return True
        if ch == ord("r"):
            self.cache.clear()
            self.say("refreshing")
            return True
        if ch == ord("g"):
            order = ["nerd", "unicode", "ascii"]
            self.glyphs = order[(order.index(self.glyphs) + 1) % len(order)] if self.glyphs in order else "unicode"
            self.say("glyphs: %s" % self.glyphs)
            return True

        if self.view == "help":
            self.view = "board"
            return True

        if self.view == "board":
            return self.handle_board(ch)
        if self.view == "extra":
            return self.handle_extra(ch)
        if self.view == "detail":
            if ch in (curses.KEY_UP, ord("k")):
                self.detail_sel = max(0, self.detail_sel - 1)
            elif ch in (curses.KEY_DOWN, ord("j")):
                self.detail_sel += 1
            elif ch in (curses.KEY_ENTER, 10, 13):
                self.view = "board"
            return True
        return True

    def handle_board(self, ch):
        h, w = self.scr.getmaxyx()
        games = self.cache_get(self.board_key()) or []
        rows = self.visible(games)
        if ch in (ord("1"), ord("2"), ord("3"), ord("4"), ord("5"), ord("6")):
            if not self.only:
                self.switch_league(LEAGUES[int(chr(ch)) - 1]["key"])
        elif ch == 9:  # Tab
            if not self.only:
                i = [lg["key"] for lg in LEAGUES].index(self.league_key)
                self.switch_league(LEAGUES[(i + 1) % len(LEAGUES)]["key"])
        elif ch == curses.KEY_BTAB:
            if not self.only:
                i = [lg["key"] for lg in LEAGUES].index(self.league_key)
                self.switch_league(LEAGUES[(i - 1) % len(LEAGUES)]["key"])
        elif ch in (curses.KEY_UP, ord("k")):
            self.move(-1, rows)
        elif ch in (curses.KEY_DOWN, ord("j")):
            self.move(1, rows)
        elif ch in (curses.KEY_NPAGE,):
            self.move(10, rows)
        elif ch in (curses.KEY_PPAGE,):
            self.move(-10, rows)
        elif ch in (curses.KEY_ENTER, 10, 13):
            if rows:
                self.detail_game = rows[self.selected_index(rows)]
                self.view = "detail"
        elif ch == ord("["):
            self.date -= dt.timedelta(days=1)
            self.scroll = 0
        elif ch == ord("]"):
            self.date += dt.timedelta(days=1)
            self.scroll = 0
        elif ch in (ord("w"), ord("W")) and self.lg()["key"] in ("cfb", "nfl"):
            games = self.cache_get(self.board_key()) or []
            cur_week = getattr(self, "week", None) or (games[0].get("week") if games else 1)
            delta = 1 if ch == ord("w") else -1
            self.week = max(1, cur_week + delta)
            self.date += dt.timedelta(weeks=delta)
            self.scroll = 0
            self.say("week %d" % self.week)
        elif ch == ord("t"):
            self.date = today()
            self.scroll = 0
        elif ch == ord("v"):
            self.layout = "list" if self.layout == "grid" else "grid"
            self.scroll = 0
        elif ch == ord("l"):
            options = ["all", "live", "fav"] + (["top25"] if self.lg()["poll"] else [])
            self.filter = options[(options.index(self.filter) + 1) % len(options)] if self.filter in options else "all"
            self.scroll = 0
            self.say("filter: %s" % self.filter)
        elif ch == ord("R"):
            if not self.lg()["poll"]:
                self.say("%s has no poll - press T for standings" % self.lg()["name"])
            else:
                self.open_extra("ranks")
        elif ch == ord("T"):
            self.open_extra("stand")
        elif ch == ord("a") and rows:
            self.toggle_fav(rows[self.selected_index(rows)]["away"])
        elif ch == ord("h") and rows:
            self.toggle_fav(rows[self.selected_index(rows)]["home"])
        return True

    def handle_extra(self, ch):
        if ch == ord("1") and not self.only:
            self.switch_league("cfb")
            self.view = "board"
        elif ch == ord("R"):
            if self.lg()["poll"]:
                self.open_extra("ranks")
        elif ch == ord("T"):
            self.open_extra("stand")
        elif ch in (curses.KEY_UP, ord("k")):
            self.extra_sel = max(0, self.extra_sel - 1)
        elif ch in (curses.KEY_DOWN, ord("j")):
            self.extra_sel += 1
        elif ch in (curses.KEY_LEFT, ord("h")):
            if self.extra_kind == "ranks":
                self.extra_tab = max(0, self.extra_tab - 1)
            else:
                self.extra_group = max(0, self.extra_group - 1)
                self.extra_sel = self.extra_scroll = 0
        elif ch in (curses.KEY_RIGHT, ord("l")):
            if self.extra_kind == "ranks":
                polls = self.cache_get("ranks:%s" % self.league_key) or []
                self.extra_tab = min(max(0, len(polls) - 1), self.extra_tab + 1)
            else:
                groups = self.cache_get("stand:%s" % self.league_key) or []
                self.extra_group = min(max(0, len(groups) - 1), self.extra_group + 1)
                self.extra_sel = self.extra_scroll = 0
        return True

    def switch_league(self, key):
        if key == self.league_key:
            return
        self.league_key = key
        self.week = None
        self.sel_id = None
        self.scroll = 0
        self.extra_tab = self.extra_group = self.extra_sel = self.extra_scroll = 0
        self.view = "board"
        self.filter = "all"

    def move(self, delta, rows):
        if not rows:
            return
        idx = self.selected_index(rows)
        idx = max(0, min(len(rows) - 1, idx + delta))
        self.sel_id = rows[idx]["id"]

    def toggle_fav(self, side):
        key = "%s:%s" % (self.league_key, side["abbr"])
        if key in self.favs:
            self.favs.discard(key)
            self.say("unstarred %s %s" % (self.league_key.upper(), side["abbr"]))
        else:
            self.favs.add(key)
            self.say("starred %s %s" % (self.league_key.upper(), side["abbr"]))
        self.save_config()

    def open_extra(self, kind):
        self.view = "extra"
        self.extra_kind = kind
        self.extra_sel = self.extra_scroll = 0
        self.extra_group = 0
        self.extra_tab = 0
        if kind == "ranks" and not self.lg()["poll"]:
            self.view = "board"
            self.say("%s has no poll" % self.lg()["name"])


# --------------------------------------------------------------------------
# plain mode
# --------------------------------------------------------------------------

def plain(args):
    target = args.league or getattr(args, "only", None)
    leagues = [BY_KEY[target]] if target else LEAGUES
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
        games.sort(key=lambda g: (order.get(g["state"], 3), g["start"] or dt.datetime.max))
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


def main(argv=None):
    prog = os.path.basename(sys.argv[0]) if argv is None else "sportstui"
    only = ALIASES.get(prog)
    parser = argparse.ArgumentParser(
        prog=prog,
        description=("A terminal scoreboard for %s." % BY_KEY[only]["name"])
        if only else "A terminal scoreboard for CFB, CBB, NHL, NBA, MLB and NFL.",
    )
    parser.add_argument("--league", choices=list(BY_KEY),
                        help="start on this league (combined board only)")
    parser.add_argument("--date", type=lambda s: dt.date.fromisoformat(s), help="YYYY-MM-DD")
    parser.add_argument("--week", type=int, help="start on week N (CFB / NFL only)")
    parser.add_argument("--layout", choices=["grid", "list"])
    parser.add_argument("--glyphs", choices=list(GLYPHS))
    parser.add_argument("--plain", action="store_true", help="print the board and exit")
    parser.add_argument("--version", action="version", version="%s %s" % (prog, VERSION))
    args = parser.parse_args(argv)
    args.only = only
    if args.only and args.league and args.league != args.only:
        parser.error("%s only shows %s" % (prog, args.only.upper()))
    if args.week and args.only and args.only not in ("cfb", "nfl"):
        parser.error("--week only applies to CFB and NFL")
    if args.plain:
        return plain(args)
    curses.wrapper(run, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
