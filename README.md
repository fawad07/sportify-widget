# 🏆 Sportify Widget

A desktop widget for live sports scores and standings, built with Qt
(PySide6).

## Data sources

All data comes from free, keyless public feeds:

- **Soccer (World Cup, Premier League, La Liga, Champions League)** and
  **NHL** — ESPN's public site API (scores + standings)
- **Cricket** — ESPNcricinfo's live-scores RSS feed (scores only;
  the feed has no standings)

Fetches run on a background thread so the widget never freezes, and
results are cached for 30 seconds. If a live update fails — network
trouble, or a feed changing its format — the widget falls back to the
last successful data instead of going blank, and keeps that fallback
across restarts (`~/.sportify/last_data.json`).

The status dot shows 🟡 while fetching, 🟢 on success, 🟠 when showing
last-good data after a failed update, and 🔴 when a fetch fails with
nothing to fall back on (hover it for the error).

## Features
- Slim ticker bar docked to the top of the screen, cycling through
  matches every few seconds
- Chevron expands the bar into a drawer with all scores, standings,
  and controls (sport selector, refresh, settings)
- Live scores and standings, auto-refreshed on a configurable interval
- Favorite team: set it in settings and its matches lead the ticker,
  with a native notification whenever its score changes
- Frameless, draggable, always-on-top
- System tray icon with show/quit actions
- Dark theme

## Installation

```bash
git clone https://github.com/fawad07/sportify-widget.git
cd sportify-widget
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python run.py
```

Settings are stored in `~/.sportify/config.json` and can be changed from
the ⚙️ settings dialog in the widget footer.

## Build a standalone app

```bash
pip install pyinstaller
pyinstaller main.spec
```

The bundled app is written to `dist/Sportify.app`.

## Support

Sportify is free and MIT-licensed. If it earns a spot at the top of
your screen, you can [buy me a coffee](https://buymeacoffee.com/fawad07).

## License

MIT — see [LICENSE](LICENSE). Score data comes from unofficial public
endpoints (ESPN, ESPNcricinfo) and is intended for personal,
non-commercial use.

Sportify uses Qt through [PySide6](https://doc.qt.io/qtforpython-6/)
under the LGPLv3. The app bundle ships the unmodified Qt libraries as
separate, replaceable shared libraries (`Sportify.app/Contents/Frameworks`).
