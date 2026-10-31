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
| `sportstui` | **All** | Combined multi-league scoreboard (press `1`–`7` or `Tab` to switch) |
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
| `1` | **ALL**: view all sports together on one unified board |
| `2` – `7` / `Tab` | Switch between **2: CFB**, **3: NFL**, **4: NHL**, **5: NBA**, **6: CBB**, and **7: MLB** *(combined mode only)* |
| `[` / `]` | Previous / next day |
| `w` / `W` | Next / previous week *(CFB and NFL only)* |
| `t` | Jump to today's games |
| `←` `↓` `↑` `→` (`j` / `k`) | 2D card navigation in grid view; row navigation in list view |
| `PageUp` / `PageDown` | Fast scroll game list or detail view |
| `Enter` | Open game details (team banners, win probability bar & sparkline, linescore by period, team stats, leaders, and scoring plays) |
| `v` | Toggle card **grid** vs compact **list** view |
| `l` | Cycle status filters: **all** → **live** → **fav** → **upsets** → **top 25** |
| `o` | Open **Conference / Division** filter modal (B1G, SEC, ACC, Big 12, NFC/AFC North/South/East/West, etc.) |
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

## Responsive Grid Layout & Auto-Reflow

`sportstui` dynamically calculates column layouts to match terminal geometry:
- **Widescreen / Fullscreen** (`width >= 180`): Renders **5 columns** of game cards across the display.
- **Half-page / Tiled Split** (`72 <= width < 108`): Renders **2 columns** of game cards, ideal for 50/50 window splits on 14" Chromebooks (e.g. ASUS CM34 Flip).
- **Standard Terminal** (`108 <= width < 144`): Renders **3 columns** (`~132` cols).
- **Wide Terminal** (`144 <= width < 180`): Renders **4 columns**.
- **Compact Window** (`width < 72`): Automatically collapses into a single-column layout.

Card widths expand dynamically (`width: 1fr` behavior matching `cfbtui`) while preserving the 8-column visual prefix, 40-column inner text alignment, and full clock digits.

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
