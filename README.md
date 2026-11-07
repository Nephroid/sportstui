# sportstui

**Eight leagues, one scoreboard, zero dependencies.**

`sportstui` is a fast, colorful terminal scoreboard and sports ticker written in pure Python using standard library `curses` and `urllib`. It replicates the exact visual design of `WPTK/cfbtui` — full-bleed team color background bars with WCAG luminance contrast, timeouts remaining dots (`●●○`), `★ Favorites` / `Other games` sections, `⚡ UPSET` & `⚑ RED ZONE` heavy card borders, a live bottom `─ticker───` panel, side-by-side poll/standings boxes, and rich play-by-play game detail screens — across eight major sports and combat leagues:

- **CFB**: College Football (NCAA FBS)
- **NFL**: National Football League
- **NHL**: National Hockey League
- **NBA**: National Basketball Association
- **CBB**: Men's College Basketball (NCAA Division I)
- **MLB**: Major League Baseball
- **UFC**: Ultimate Fighting Championship / MMA Fight Cards & Bouts
- **BOX**: Professional Boxing Schedules, Cards & Verified Results

---

## Launcher Commands

You can run `sportstui` as a combined multi-league app or launch directly into any individual league:

| Command | League | Description |
| :--- | :--- | :--- |
| `sportstui` | **All** | Combined multi-league scoreboard (press `1`–`9` or `Tab` to switch) |
| `cfbtui` | **CFB** | College Football scoreboard & Top 25 rankings |
| `nfltui` | **NFL** | NFL scoreboard, weekly slates, and division standings |
| `nhltui` | **NHL** | NHL scoreboard, standings, and division tables |
| `nbatui` | **NBA** | NBA scoreboard, standings, and box scores |
| `cbbtui` / `ncaabtui` | **CBB** | Men's College Basketball & Top 25 rankings |
| `mlbtui` | **MLB** | Major League Baseball scoreboard and standings |
| `ufctui` / `mmalui` | **UFC** | UFC / MMA fight cards, Tale of the Tape, and P4P rankings |
| `boxtui` | **BOX** | Professional Boxing fight schedule, cards, and stoppage results |

---

## Interactive Hotkeys

| Key | Action |
| :--- | :--- |
| `1` | **ALL**: view all sports together on one unified board |
| `2` – `9` / `Tab` | Switch between **2: CFB**, **3: NFL**, **4: NHL**, **5: NBA**, **6: CBB**, **7: MLB**, **8: UFC**, and **9: BOX** *(combined mode only)* |
| `[` / `]` | Previous / next day |
| `w` / `W` | Next / previous week *(CFB and NFL only)* |
| `t` | Jump to today's games / fights |
| `←` `↓` `↑` `→` (`j` / `k`) | 2D card navigation in grid view; row navigation in list view |
| `PageUp` / `PageDown` | Fast scroll game list or detail view |
| `Enter` | Open game/bout details (Tale of the Tape, fight stats, team banners, win prob bar, linescores) |
| `v` | Toggle card **grid** vs compact **list** view |
| `l` | Cycle status filters: **all** → **live** → **final** → **fav** → **upsets** → **top 25** |
| `o` | Open **Conference / Division / Weight Class** filter modal (B1G, SEC, AFC/NFC, Heavyweight, Welterweight, etc.) |
| `R` | Open side-by-side Rankings (AP/Coaches Top 25 for CFB/CBB; Men's & Women's P4P for UFC) |
| `T` | Open side-by-side or tabbed Conference / Division Standings tables |
| `N` | Open League News headlines (`Enter` to read story, `o` to open in browser) |
| `a` / `!` (or `1` in single-league mode) | Toggle star on **away / blue corner** as favorite |
| `h` / `@` (or `2` in single-league mode) | Toggle star on **home / red corner** as favorite |
| `c` / `C` | Copy selected game/bout (`c`) or full board (`C`) formatted for Discord |
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

## Responsive Grid Layout & Auto-Reflow

`sportstui` dynamically calculates column layouts to match terminal geometry:
- **Ultra-Wide / Fullscreen** (`width >= 200`): Renders **6 columns** of game cards across the display (ideal for fullscreen on 14" Chromebooks like ASUS CM34 Flip in `foot` ~206 cols).
- **Widescreen** (`170 <= width < 200`): Renders **5 columns** of game cards.
- **Wide Terminal** (`136 <= width < 170`): Renders **4 columns** (`~144` cols).
- **Standard Terminal** (`105 <= width < 136`): Renders **3 columns** (`~132` cols).
- **Half-page / Tiled Split** (`70 <= width < 105`): Renders **2 columns** of game cards, ideal for 50/50 window splits on 14" Chromebooks (~100–104 cols).
- **Compact Window** (`width < 70`): Automatically collapses into a single-column layout.

You can also force any column count manually via the CLI or config:
```bash
sportstui --cols 6    # or -c 6
```
Or in `~/.config/sportstui/config.json`:
```json
{
  "cols": 6
}
```

Card widths expand dynamically (`width: 1fr` behavior matching `cfbtui`) while preserving the 8-column visual prefix, team alignment, timeouts indicators (`●●●`), and clock digits.

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
