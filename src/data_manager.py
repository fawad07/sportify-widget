"""Data management for sports scores.

Fetches live data from free, keyless public sources:
- ESPN's public site API (soccer, NHL): scoreboard + standings
- ESPNcricinfo's live-scores RSS feed (cricket): scores only
"""

import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from .utils import format_event_time

logger = logging.getLogger(__name__)

ESPN_SCOREBOARD_API = "https://site.api.espn.com/apis/site/v2/sports"
ESPN_STANDINGS_API = "https://site.api.espn.com/apis/v2/sports"
CRICINFO_RSS = "http://static.cricinfo.com/rss/livescores.xml"

# Last successful payload per sport, kept on disk so the widget can show
# real (if stale) data when a feed breaks — network outage or format change
PERSISTENT_CACHE_PATH = Path.home() / ".sportify" / "last_data.json"

REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (Sportify Widget)"}
REQUEST_TIMEOUT = 10  # seconds

STATUS_BY_STATE = {'pre': 'Scheduled', 'in': 'LIVE', 'post': 'FT'}

# One side of a cricket RSS title, e.g. "West Indies 219/4 *" or "England"
CRICKET_SIDE_RE = re.compile(
    r'^(?P<team>.*?)\s*'
    r'(?P<score>\d+(?:/\d+)?(?:\s*&\s*\d+(?:/\d+)?)?)?\s*'
    r'(?P<live>\*)?\s*$'
)


class SportDataManager:
    """Fetches scores and standings for the supported sports"""

    def __init__(self):
        self.cache = {}
        self.cache_duration = 30  # seconds
        self._last_good = self._load_persistent_cache()

        self.sports = {
            'world_cup': {
                'name': 'World Cup', 'icon': '⚽',
                'espn_path': 'soccer/fifa.world',
            },
            'premier_league': {
                'name': 'Premier League', 'icon': '⚽',
                'espn_path': 'soccer/eng.1',
            },
            'la_liga': {
                'name': 'La Liga', 'icon': '⚽',
                'espn_path': 'soccer/esp.1',
            },
            'champions_league': {
                'name': 'Champions League', 'icon': '⚽',
                'espn_path': 'soccer/uefa.champions',
            },
            'nhl': {
                'name': 'NHL', 'icon': '🏒',
                'espn_path': 'hockey/nhl',
            },
            'cricket': {
                'name': 'Cricket', 'icon': '🏏',
                # No espn_path: served by the Cricinfo RSS feed instead
            },
        }

    def get_sport_data(self, sport: str) -> Dict[str, Any]:
        """Fetch data for a specific sport. Never raises; returns an
        'error' key in the result when fetching fails."""
        if sport not in self.sports:
            sport = 'world_cup'
        info = self.sports[sport]

        # Check cache first
        cache_key = f"{sport}_data"
        if cache_key in self.cache:
            cache_time, data = self.cache[cache_key]
            if (time.time() - cache_time) < self.cache_duration:
                return data

        try:
            if 'espn_path' in info:
                data = self._fetch_espn(sport, info)
            else:
                data = self._fetch_cricinfo(sport, info)
            self.cache[cache_key] = (time.time(), data)
            self._store_last_good(sport, data)
            return data
        except Exception as e:
            logger.warning("Error fetching data for %s: %s", sport, e)
            # Fall back to the last successful payload if there is one
            fallback = self._last_good.get(sport)
            if fallback:
                stale = dict(fallback)
                stale['stale'] = True
                stale['error'] = str(e)
                return stale
            return {
                'sport': sport,
                'sport_name': info['name'],
                'icon': info['icon'],
                'matches': [],
                'standings': [],
                'last_updated': datetime.now().isoformat(),
                'error': str(e),
            }

    def _load_persistent_cache(self) -> Dict[str, Any]:
        try:
            with open(PERSISTENT_CACHE_PATH) as f:
                return json.load(f)
        except Exception:
            return {}

    def _store_last_good(self, sport: str, data: Dict[str, Any]):
        self._last_good[sport] = data
        try:
            PERSISTENT_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(PERSISTENT_CACHE_PATH, 'w') as f:
                json.dump(self._last_good, f)
        except Exception as e:
            logger.warning("Could not persist data cache: %s", e)

    def _result(self, sport: str, info: Dict[str, str],
                matches: List[dict], standings: List[dict]) -> Dict[str, Any]:
        return {
            'sport': sport,
            'sport_name': info['name'],
            'icon': info['icon'],
            'matches': matches,
            'standings': standings,
            'last_updated': datetime.now().isoformat(),
        }

    # --- ESPN (soccer, NHL) ---

    def _fetch_espn(self, sport: str, info: Dict[str, str]) -> Dict[str, Any]:
        path = info['espn_path']
        resp = requests.get(f"{ESPN_SCOREBOARD_API}/{path}/scoreboard",
                            headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        events = resp.json().get('events', [])

        matches = []
        for event in events[:12]:
            try:
                matches.append(self._parse_espn_event(event))
            except (KeyError, IndexError, StopIteration) as e:
                logger.warning("Skipping unparsable event: %s", e)

        # Events exist but none parsed: ESPN likely changed its format.
        # Raising sends us to the last-good fallback instead of showing
        # a misleading empty "No games scheduled".
        if events and not matches:
            raise ValueError(
                f"ESPN response format may have changed for {path}: "
                f"{len(events)} events, none parseable")

        standings = self._fetch_espn_standings(path)
        return self._result(sport, info, matches, standings)

    def _parse_espn_event(self, event: dict) -> dict:
        competition = event['competitions'][0]
        competitors = competition['competitors']
        home = next(c for c in competitors if c.get('homeAway') == 'home')
        away = next(c for c in competitors if c.get('homeAway') == 'away')

        state = event['status']['type'].get('state', 'pre')
        status = STATUS_BY_STATE.get(state, 'Scheduled')
        detail = event['status']['type'].get('shortDetail', '')

        return {
            'home_team': home['team'].get('displayName', 'Home'),
            'away_team': away['team'].get('displayName', 'Away'),
            'home_score': home.get('score') if state != 'pre' else None,
            'away_score': away.get('score') if state != 'pre' else None,
            'status': status,
            'time': format_event_time(event.get('date', '')) if state == 'pre' else None,
            'period': detail if state == 'in' else '',
        }

    def _fetch_espn_standings(self, path: str) -> List[dict]:
        """Fetch and flatten standings; returns [] on any failure so a
        standings hiccup never takes down the scores."""
        try:
            resp = requests.get(f"{ESPN_STANDINGS_API}/{path}/standings",
                                headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            payload = resp.json()
        except Exception as e:
            logger.warning("Standings fetch failed for %s: %s", path, e)
            return []

        # Leagues come grouped (conferences, World Cup groups); flatten them
        groups = payload.get('children') or [payload]
        rows = []
        for group in groups:
            for entry in group.get('standings', {}).get('entries', []):
                stats = {s.get('name'): s.get('value') for s in entry.get('stats', [])}
                wins = int(stats.get('wins') or 0)
                losses = int(stats.get('losses') or 0)
                ties = int(stats.get('ties') or 0)
                games = stats.get('gamesPlayed') or (wins + losses + ties)
                pct = stats.get('winPercent')
                if pct is None:
                    pct = wins / games if games else 0.0
                rows.append({
                    'team': entry.get('team', {}).get('displayName', 'Unknown'),
                    'wins': wins,
                    'losses': losses,
                    'pct': round(pct, 3),
                    'points': stats.get('points') or 0,
                })

        rows.sort(key=lambda r: (r['points'], r['pct'], r['wins']), reverse=True)
        for i, row in enumerate(rows):
            row['rank'] = i + 1
        return rows

    # --- Cricinfo RSS (cricket) ---

    def _fetch_cricinfo(self, sport: str, info: Dict[str, str]) -> Dict[str, Any]:
        resp = requests.get(CRICINFO_RSS, headers=REQUEST_HEADERS,
                            timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)

        titles = [(item.findtext('title') or '').strip()
                  for item in root.iter('item')]
        matches = [m for m in (self._parse_cricinfo_title(t) for t in titles) if m]

        # Same format-change guard as ESPN: items exist but none parsed
        if titles and not matches:
            raise ValueError(
                f"Cricinfo feed format may have changed: "
                f"{len(titles)} items, none parseable")

        # The feed has no standings
        return self._result(sport, info, matches[:12], [])

    def _parse_cricinfo_title(self, title: str) -> Optional[dict]:
        """Parse a title like 'West Indies 219/4 * v Sri Lanka 549/9'
        ('*' marks the side currently batting)."""
        if ' v ' not in title:
            return None
        home_raw, away_raw = title.split(' v ', 1)
        home = CRICKET_SIDE_RE.match(home_raw.strip())
        away = CRICKET_SIDE_RE.match(away_raw.strip())
        if not home or not away or not home.group('team') or not away.group('team'):
            return None

        live = bool(home.group('live') or away.group('live'))
        has_score = bool(home.group('score') or away.group('score'))
        if live:
            status = 'LIVE'
        elif has_score:
            status = 'FT'
        else:
            status = 'Scheduled'

        return {
            'home_team': home.group('team'),
            'away_team': away.group('team'),
            'home_score': home.group('score'),
            'away_score': away.group('score'),
            'status': status,
            'time': None,
            'period': '',
        }
