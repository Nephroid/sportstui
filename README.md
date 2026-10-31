# sportstui

**Six leagues, one scoreboard, zero dependencies.**

`sportstui` is a fast, colorful terminal scoreboard and sports ticker written in pure Python using standard library `curses` and `urllib`. It streams live scores, odds/spreads, rankings, standings, and play-by-play scoring from ESPN's public endpoints for six major sports leagues:

- **CFB**: College Football (NCAA FBS)
- **CBB**: Men's College Basketball (NCAA Division I)
- **NHL**: National Hockey League
- **NBA**: National Basketball Association
- **MLB**: Major League Baseball
- **NFL**: National Football League

---

## Launcher Commands

You can run `sportstui` as a combined multi-league app or launch directly into any individual league:

| Command | League | Description |
| :--- | :--- | :--- |
| `sportstui` | **All** | Combined multi-league scoreboard (press `1`–`6` or `Tab` to switch) |
| `cfbtui` | **CFB** | College Football scoreboard & Top 25 rankings |
| `cbbtui` / `ncaabtui` | **CBB** | Men's College Basketball & Top 25 rankings |
| `nbatui` | **NBA** | NBA scoreboard, standings, and box scores |
| `nhltui` | **NHL** | NHL scoreboard, standings, and division tables |
| `mlbtui` | **MLB** | Major League Baseball scoreboard and standings |
| `nfltui` | **NFL** | NFL scoreboard, weekly slates, and division standings |

---

## Interactive Hotkeys

| Key | Action |
| :--- | :--- |
| `1` – `6` / `Tab` | Switch between CFB, CBB, NHL, NBA, MLB, and NFL *(combined mode only)* |
| `[` / `]` | Previous / next day |
| `w` / `W` | Next / previous week *(CFB and NFL only)* |
| `t` | Jump to today's games |
| `Up` / `Down` (`k` / `j`) | Move game selection cursor |
| `PageUp` / `PageDown` | Fast scroll game list |
| `Enter` | Open game details (scoring plays, team leaders, win probability) |
| `v` | Toggle card **grid** vs compact **list** view |
| `l` | Cycle filters: **all** → **live** → **starred favorites** → **top 25** |
| `R` | Open Poll Rankings (AP Poll / Coaches Poll for CFB & CBB) |
| `T` | Open Conference / Division Standings tables |
| `a` | Toggle star on **away** team as favorite |
| `h` | Toggle star on **home** team as favorite |
| `g` | Cycle glyph styles: **nerd** → **unicode** → **ascii** |
| `r` | Force refresh data immediately |
| `Esc` | Return to scoreboard from detail / rankings / standings / help |
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
