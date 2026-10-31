# sportstui

**Six leagues, one scoreboard, zero dependencies.**

`sportstui` is a fast, colorful terminal scoreboard and sports ticker written in pure Python using standard library `curses` and `urllib`. It replicates the exact visual design of `WPTK/cfbtui` — full-bleed team color background bars with WCAG luminance contrast, `★ Favorites` / `Other games` sections, `⚡ UPSET` & `⚑ RED ZONE` heavy card borders, a live bottom `─ticker───` panel, side-by-side poll/standings boxes, and rich play-by-play game detail screens — across six major sports leagues:

- **CFB**: College Football (NCAA FBS)
- **NFL**: National Football League
- **NHL**: National Hockey League
- **NBA**: National Basketball Association
- **CBB**: Men's College Basketball (NCAA Division I)
- **MLB**: Major League Baseball

---

## Launcher Commands

You can run `sportstui` as a combined multi-league app or launch directly into any individual league:

| Command | League | Description |
| :--- | :--- | :--- |
| `sportstui` | **All** | Combined multi-league scoreboard (press `1`–`6` or `Tab` to switch) |
| `cfbtui` | **CFB** | College Football scoreboard & Top 25 rankings |
| `nfltui` | **NFL** | NFL scoreboard, weekly slates, and division standings |
| `nhltui` | **NHL** | NHL scoreboard, standings, and division tables |
| `nbatui` | **NBA** | NBA scoreboard, standings, and box scores |
| `cbbtui` / `ncaabtui` | **CBB** | Men's College Basketball & Top 25 rankings |
| `mlbtui` | **MLB** | Major League Baseball scoreboard and standings |

---

## Interactive Hotkeys

| Key | Action |
| :--- | :--- |
| `1` – `6` / `Tab` | Switch between CFB, NFL, NHL, NBA, CBB, and MLB *(combined mode only)* |
| `[` / `]` | Previous / next day |
| `w` / `W` | Next / previous week *(CFB and NFL only)* |
| `t` | Jump to today's games |
| `←` `↓` `↑` `→` (`j` / `k`) | 2D card navigation in grid view; row navigation in list view |
| `PageUp` / `PageDown` | Fast scroll game list or detail view |
| `Enter` | Open game details (team banners, win probability bar & sparkline, linescore by period, team stats, leaders, and scoring plays) |
| `v` | Toggle card **grid** vs compact **list** view |
| `l` | Cycle filters: **all** → **live** → **fav** → **upsets** → **top 25** |
| `R` | Open side-by-side Poll Rankings (AP Top 25 + AFCA Coaches Poll for CFB & CBB) |
| `T` | Open side-by-side or tabbed Conference / Division Standings tables |
| `N` | Open League News headlines (`Enter` to read story, `o` to open in browser) |
| `a` / `!` (or `1` in single-league mode) | Toggle star on **away** team as favorite |
| `h` / `@` (or `2` in single-league mode) | Toggle star on **home** team as favorite |
| `c` / `C` | Copy selected game (`c`) or full board (`C`) formatted for Discord |
| `g` | Cycle glyph styles: **nerd** → **unicode** → **emoji** → **ascii** |
| `r` | Force refresh data immediately |
| `Esc` | Return to scoreboard from detail / rankings / standings / news / help |
| `?` | Toggle help overlay |
| `q` | Quit |

---

## Plain / Scriptable Mode

Append `--plain` to any command for instant, non-interactive shell output:

```bash
cfbtui --plain
nbatui --plain
sportstui --plain
sportstui --league cfb --week 8 --plain
```

---

## Configuration & Favorites

Favorites and layout settings are stored in `~/.config/sportstui/config.json`:

```json
{
  "league": "cfb",
  "layout": "grid",
  "glyphs": "nerd",
  "favorites": [
    "cfb:MSU",
    "cfb:ND",
    "cfb:TEX",
    "cbb:MSU",
    "nba:DET",
    "nba:PHI",
    "nhl:DET",
    "nfl:DET",
    "mlb:DET"
  ]
}
```

- Games featuring your starred favorites are prioritized at the top of the scoreboard with a star glyph (`★`).
- Pressing `a` or `h` while highlighting any game toggles favorites and saves automatically.

---

## Installation & Updates

To re-link or install on another machine:

```bash
git clone https://github.com/your-username/sportstui.git ~/Work/sportstui
cd ~/Work/sportstui
./install.sh
```

---

## Automated Tests

Run the test suite using standard Python `unittest`:

```bash
cd ~/Work/sportstui
python3 -m unittest discover -s tests -v
```
