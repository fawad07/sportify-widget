"""Main widget window — a top-edge ticker bar with an expandable drawer"""

import threading
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QMenu, QPushButton, QScrollArea,
    QSpinBox, QStyle, QSystemTrayIcon, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt, QTimer, Signal, QPropertyAnimation, QEasingCurve, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QIcon

from .config_manager import ConfigManager
from .data_manager import SportDataManager
from .styles import get_style
from .utils import truncate_text

# Display name -> config key for the sports the data manager supports
SPORTS = {
    'World Cup': 'world_cup',
    'Premier League': 'premier_league',
    'La Liga': 'la_liga',
    'Champions League': 'champions_league',
    'NHL': 'nhl',
    'Cricket': 'cricket',
}

BAR_HEIGHT = 46
TICKER_CYCLE_MS = 5000
DRAWER_ANIM_MS = 220
ALERT_DURATION_MS = 6000
FLASH_INTERVAL_MS = 280


class SportWidget(QMainWindow):
    """Ticker bar docked to the top of the screen; the full panel
    slides out beneath it like a drawer."""

    # Emitted from the fetch thread with the fetched data payload
    data_ready = Signal(dict)

    def __init__(self):
        super().__init__()

        # Initialize managers
        self.config = ConfigManager()
        self.data_manager = SportDataManager()

        # Setup UI
        self.setup_ui()
        self.setup_menu()

        # Fetches run on a background thread; results arrive via signal
        self._fetching = False
        self.data_ready.connect(self.render_data)

        # Last seen scores, used to detect changes for alerts/notifications
        self._last_scores = {}

        # Score-alert state (bar pulse + pinned ticker banner)
        self._alert_active = False
        self._alert_token = 0
        self._flash_remaining = 0
        self._flash_timer = QTimer(self)
        self._flash_timer.timeout.connect(self._on_flash_tick)

        # Load initial data
        self.load_data()

        # Setup refresh timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.load_data)
        refresh_interval = self.config.get('refresh_interval', 60) * 1000
        self.timer.start(refresh_interval)

        # Ticker cycling timer
        self.ticker_timer = QTimer(self)
        self.ticker_timer.timeout.connect(self.advance_ticker)
        self.ticker_timer.start(TICKER_CYCLE_MS)

        # Position widget
        self.position_widget()

    def setup_ui(self):
        """Set up the main UI"""
        # Window settings
        self.setWindowTitle("🏆 Sportify Widget")
        # No Qt.Tool: on macOS/Qt6 tool windows are panels that hide
        # whenever the app is inactive. The bundle's LSUIElement already
        # keeps the app out of the Dock.
        flags = Qt.FramelessWindowHint
        if self.config.get('always_on_top', True):
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(self.config.get('opacity', 0.95))

        # Sizing: the bar is always visible; the drawer opens below it
        width = self.config.get('window_width', 540)
        total_height = self.config.get('window_height', 600)
        self.drawer_height = max(240, total_height - BAR_HEIGHT - 4)
        self.setFixedWidth(width)

        # Main widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(4)

        self.create_ticker_bar()
        self.create_drawer()

        # Start collapsed
        self.drawer_open = False
        self.drawer.setMinimumHeight(0)
        self.drawer.setMaximumHeight(0)
        self.drawer.hide()
        self.setFixedHeight(BAR_HEIGHT)

        self.drawer_anim = QPropertyAnimation(self.drawer, b"maximumHeight", self)
        self.drawer_anim.setDuration(DRAWER_ANIM_MS)
        self.drawer_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.drawer_anim.valueChanged.connect(self._sync_drawer_height)
        self.drawer_anim.finished.connect(self._drawer_anim_done)

        # Ticker state
        self.ticker_items = []
        self.ticker_index = 0

        # Apply styles
        self.setStyleSheet(get_style())

        # Dragging state (see mouse event overrides below)
        self.drag_pos = None

    def create_ticker_bar(self):
        """Create the always-visible ticker strip"""
        self.ticker_bar = QWidget()
        self.ticker_bar.setObjectName("tickerBar")
        self.ticker_bar.setFixedHeight(BAR_HEIGHT)

        bar_layout = QHBoxLayout(self.ticker_bar)
        bar_layout.setContentsMargins(16, 0, 8, 0)
        bar_layout.setSpacing(10)

        self.league_label = QLabel("🏆 Sportify")
        self.league_label.setObjectName("league-label")

        self.ticker_label = QLabel("Loading scores…")
        self.ticker_label.setObjectName("ticker-text")

        self.status_label = QLabel("⚪")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setToolTip("Last updated: Waiting...")

        self.toggle_btn = QPushButton("▾")
        self.toggle_btn.setFixedSize(32, 28)
        self.toggle_btn.setToolTip("Show scores and standings")
        self.toggle_btn.clicked.connect(self.toggle_drawer)

        bar_layout.addWidget(self.league_label)
        bar_layout.addWidget(self.ticker_label, 1)
        bar_layout.addWidget(self.status_label)
        bar_layout.addWidget(self.toggle_btn)

        self.main_layout.addWidget(self.ticker_bar)

    def create_drawer(self):
        """Create the expandable drawer panel"""
        self.drawer = QWidget()
        self.drawer.setObjectName("mainWidget")

        self.drawer_layout = QVBoxLayout(self.drawer)
        self.drawer_layout.setContentsMargins(12, 12, 12, 12)
        self.drawer_layout.setSpacing(6)

        self.create_scores_section()
        self.create_standings_section()
        self.create_footer()

        self.main_layout.addWidget(self.drawer)

    def create_scores_section(self):
        """Create the scores section"""
        # Header
        self.scores_header = QLabel("📊 Live Scores")
        self.scores_header.setObjectName("section-header")
        self.drawer_layout.addWidget(self.scores_header)

        # Scores container (scrollable)
        self.scores_scroll = QScrollArea()
        self.scores_scroll.setWidgetResizable(True)
        self.scores_scroll.setMaximumHeight(250)

        self.scores_container = QWidget()
        self.scores_layout = QVBoxLayout(self.scores_container)
        self.scores_layout.setContentsMargins(0, 0, 0, 0)
        self.scores_layout.setSpacing(4)
        self.scores_layout.addStretch()

        self.scores_scroll.setWidget(self.scores_container)
        self.drawer_layout.addWidget(self.scores_scroll)

    def create_standings_section(self):
        """Create the standings section"""
        # Header
        self.standings_header = QLabel("📈 Standings")
        self.standings_header.setObjectName("section-header")
        self.drawer_layout.addWidget(self.standings_header)

        # Standings container
        self.standings_scroll = QScrollArea()
        self.standings_scroll.setWidgetResizable(True)

        self.standings_container = QWidget()
        self.standings_layout = QVBoxLayout(self.standings_container)
        self.standings_layout.setContentsMargins(0, 0, 0, 0)
        self.standings_layout.setSpacing(2)
        self.standings_layout.addStretch()

        self.standings_scroll.setWidget(self.standings_container)
        self.drawer_layout.addWidget(self.standings_scroll)

    def create_footer(self):
        """Create the drawer footer with the controls"""
        footer_widget = QWidget()
        footer_layout = QHBoxLayout(footer_widget)
        footer_layout.setContentsMargins(0, 6, 0, 0)

        # Sport selector
        self.sport_combo = QComboBox()
        self.sport_combo.addItems(list(SPORTS))
        key_to_display = {key: display for display, key in SPORTS.items()}
        current_sport = self.config.get('sport')
        if current_sport in key_to_display:
            self.sport_combo.setCurrentText(key_to_display[current_sport])
        self.sport_combo.currentTextChanged.connect(self.on_sport_changed)

        # Refresh button
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self.load_data)
        self.refresh_btn.setFixedWidth(80)

        # Settings button
        self.settings_btn = QPushButton("⚙️")
        self.settings_btn.setFixedWidth(30)
        self.settings_btn.clicked.connect(self.show_settings)

        # Close button
        self.close_btn = QPushButton("✕")
        self.close_btn.clicked.connect(self.close)
        self.close_btn.setFixedWidth(30)

        footer_layout.addWidget(self.sport_combo)
        footer_layout.addWidget(self.refresh_btn)
        footer_layout.addStretch()
        footer_layout.addWidget(self.settings_btn)
        footer_layout.addWidget(self.close_btn)

        self.drawer_layout.addWidget(footer_widget)

    def setup_menu(self):
        """Setup system tray menu"""
        # Create system tray
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(self.style().standardIcon(QStyle.SP_ComputerIcon)))

        # Create menu
        tray_menu = QMenu()
        show_action = QAction("Show Widget", self)
        show_action.triggered.connect(self.show)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QApplication.instance().quit)

        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    # --- Drawer ---

    def toggle_drawer(self):
        """Slide the drawer open or closed"""
        self.drawer_open = not self.drawer_open
        self.toggle_btn.setText("▴" if self.drawer_open else "▾")
        self.toggle_btn.setToolTip(
            "Hide panel" if self.drawer_open else "Show scores and standings")

        self.drawer_anim.stop()
        self.drawer_anim.setStartValue(self.drawer.maximumHeight())
        if self.drawer_open:
            self.drawer.show()
            self.drawer_anim.setEndValue(self.drawer_height)
        else:
            self.drawer_anim.setEndValue(0)
        self.drawer_anim.start()

    def _sync_drawer_height(self, value):
        value = int(value)
        self.drawer.setMinimumHeight(value)
        if value > 0:
            self.setFixedHeight(BAR_HEIGHT + self.main_layout.spacing() + value)
        else:
            self.setFixedHeight(BAR_HEIGHT)

    def _drawer_anim_done(self):
        if not self.drawer_open:
            self.drawer.hide()
            self.setFixedHeight(BAR_HEIGHT)

    # --- Ticker ---

    def advance_ticker(self):
        """Cycle to the next match on the ticker"""
        if self._alert_active or len(self.ticker_items) < 2:
            return
        self.ticker_index = (self.ticker_index + 1) % len(self.ticker_items)
        self.ticker_label.setText(self.ticker_items[self.ticker_index])

    def _build_ticker_items(self, matches: list) -> list:
        items = []
        for match in matches:
            home = truncate_text(match.get('home_team', ''), 18)
            away = truncate_text(match.get('away_team', ''), 18)
            home_score = match.get('home_score')
            away_score = match.get('away_score')
            status = match.get('status', 'Scheduled')

            if status == 'LIVE':
                suffix = f"LIVE {match.get('period') or ''}".strip()
                if match.get('broadcast'):
                    suffix += f"  ·  📺 {match['broadcast']}"
                items.append(f"{home} {home_score}–{away_score} {away}  ·  {suffix}")
            elif status == 'FT':
                items.append(f"{home} {home_score}–{away_score} {away}  ·  FT")
            else:
                when = match.get('time') or 'Scheduled'
                items.append(f"{home} vs {away}  ·  {when}")
        return items

    # --- Favorite team ---

    def _favorite(self) -> str:
        return (self.config.get('favorite_team') or '').strip().lower()

    def _is_favorite_match(self, match: dict) -> bool:
        favorite = self._favorite()
        if not favorite:
            return False
        return (favorite in match.get('home_team', '').lower()
                or favorite in match.get('away_team', '').lower())

    def _prioritize_favorite(self, matches: list) -> list:
        """Float the favorite team's matches to the top (stable sort)"""
        if not self._favorite():
            return matches
        return sorted(matches, key=lambda m: not self._is_favorite_match(m))

    def _detect_score_changes(self, matches: list) -> list:
        """Return the matches whose score changed since the last refresh"""
        changed = []
        for match in matches:
            key = f"{match.get('home_team')}|{match.get('away_team')}"
            scores = (match.get('home_score'), match.get('away_score'))
            previous = self._last_scores.get(key)
            self._last_scores[key] = scores
            if previous is not None and previous != scores:
                changed.append(match)
        return changed

    # --- Score alert (bar pulse + pinned banner) ---

    def _trigger_score_alert(self, match: dict, icon: str):
        """Grab the eye for a moment: pulse the bar and pin the changed
        match on the ticker with its latest key event."""
        home = truncate_text(match.get('home_team', ''), 16)
        away = truncate_text(match.get('away_team', ''), 16)
        home_score = match.get('home_score')
        away_score = match.get('away_score')
        home_score = '—' if home_score in (None, '') else home_score
        away_score = '—' if away_score in (None, '') else away_score

        banner = f"{icon} {home} {home_score}–{away_score} {away}"
        latest = (match.get('events') or [''])[0]
        if latest:
            banner += f"  ·  {latest}"

        self._alert_active = True
        self.ticker_label.setText(banner)

        self._flash_remaining = 6  # three on/off pulses
        self._apply_bar_alert(True)
        self._flash_timer.start(FLASH_INTERVAL_MS)

        self._alert_token += 1
        token = self._alert_token
        QTimer.singleShot(ALERT_DURATION_MS, lambda: self._end_alert(token))

    def _on_flash_tick(self):
        self._flash_remaining -= 1
        if self._flash_remaining <= 0:
            self._flash_timer.stop()
            self._apply_bar_alert(False)
            return
        self._apply_bar_alert(self._flash_remaining % 2 == 0)

    def _apply_bar_alert(self, on: bool):
        self.ticker_bar.setProperty('alert', on)
        for w in (self.ticker_bar, self.league_label, self.ticker_label):
            w.style().unpolish(w)
            w.style().polish(w)

    def _end_alert(self, token: int):
        if token != self._alert_token:
            return  # a newer alert has taken over
        self._alert_active = False
        if self.ticker_items:
            self.ticker_label.setText(self.ticker_items[self.ticker_index])

    # --- Data ---

    def load_data(self):
        """Kick off a background fetch of the current sport's data"""
        if self._fetching:
            return
        self._fetching = True
        self.status_label.setText("🟡")
        sport = self.config.get('sport', 'world_cup')
        threading.Thread(target=self._fetch_data, args=(sport,), daemon=True).start()

    def _fetch_data(self, sport: str):
        """Fetch data off the UI thread (get_sport_data never raises)"""
        self.data_ready.emit(self.data_manager.get_sport_data(sport))

    def render_data(self, data: dict):
        """Display fetched sports data (runs on the UI thread)"""
        self._fetching = False

        # The user may have switched sport while the fetch was in flight
        current = self.config.get('sport', 'world_cup')
        if current in self.data_manager.sports and data.get('sport') != current:
            self.load_data()
            return

        # Update status
        if data.get('stale'):
            self.status_label.setText("🟠")
            updated = data.get('last_updated', '')[:16].replace('T', ' ')
            self.status_label.setToolTip(
                f"Live update failed: {data.get('error', 'unknown')}\n"
                f"Showing last good data from {updated}")
        elif data.get('error'):
            self.status_label.setText("🔴")
            self.status_label.setToolTip(f"Update failed: {data['error']}")
        else:
            self.status_label.setText("🟢")
            self.status_label.setToolTip(f"Last updated: {datetime.now().strftime('%I:%M:%S %p')}")

        # Favorite team first, then look for score changes
        matches = self._prioritize_favorite(data.get('matches', []))
        changed = self._detect_score_changes(matches)

        # Native notification when the favorite team's score changes
        for match in changed:
            if self._is_favorite_match(match):
                self.tray_icon.showMessage(
                    f"{match.get('home_team')} vs {match.get('away_team')}",
                    f"{match.get('home_score')} – {match.get('away_score')} "
                    f"({match.get('status', '')})",
                    QSystemTrayIcon.Information,
                    5000,
                )

        # Update ticker
        self.ticker_items = self._build_ticker_items(matches) or ["No games scheduled"]
        self.ticker_index = 0
        self.ticker_label.setText(self.ticker_items[0])
        self.league_label.setText(f"{data.get('icon', '🏆')} {data.get('sport_name', 'Sportify')}")

        # Pulse the bar and pin the changed match (favorite's game wins)
        if changed:
            alert_match = next(
                (m for m in changed if self._is_favorite_match(m)), changed[0])
            self._trigger_score_alert(alert_match, data.get('icon', '🏆'))

        # Update drawer sections
        self.update_scores(matches)
        if self.config.get('show_standings', True):
            self.update_standings(data.get('standings', []))

    def update_scores(self, matches: list):
        """Update the scores display"""
        # Clear existing scores (keep stretch)
        while self.scores_layout.count() > 1:
            item = self.scores_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not matches:
            no_data = QLabel("No games scheduled")
            no_data.setStyleSheet("color: #8892b0; padding: 10px;")
            self.scores_layout.insertWidget(0, no_data)
            return

        for match in matches:
            card = self.create_match_card(match)
            self.scores_layout.insertWidget(self.scores_layout.count() - 1, card)

    def create_match_card(self, match: dict) -> QWidget:
        """Create a match card widget"""
        card = QWidget()
        card.setObjectName("match-card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        # Teams and score
        top_layout = QHBoxLayout()
        home = match.get('home_team', 'Team A')
        away = match.get('away_team', 'Team B')
        home_score = match.get('home_score')
        away_score = match.get('away_score')
        home_score = '—' if home_score in (None, '') else home_score
        away_score = '—' if away_score in (None, '') else away_score
        status = match.get('status', 'Scheduled')
        period = match.get('period', '')

        # Home team
        home_label = QLabel(home)
        home_label.setObjectName("team-name")

        # Score
        score_label = QLabel(f"{home_score} - {away_score}")
        score_label.setObjectName("team-score")

        # Away team
        away_label = QLabel(away)
        away_label.setObjectName("team-name")

        top_layout.addWidget(home_label)
        top_layout.addStretch()
        top_layout.addWidget(score_label)
        top_layout.addStretch()
        top_layout.addWidget(away_label)

        layout.addLayout(top_layout)

        # Status bar
        bottom_layout = QHBoxLayout()
        status_text = f"{status}"
        if period:
            status_text += f" • {period}"
        if status == 'Scheduled' and match.get('time'):
            status_text += f" • {match.get('time')}"
        if status == 'LIVE' and match.get('broadcast'):
            status_text += f" • 📺 {match['broadcast']}"

        status_label = QLabel(status_text)
        status_label.setObjectName("match-status")
        if status == 'LIVE':
            status_label.setStyleSheet("color: #e94560; font-weight: bold;")
        elif status == 'FT':
            status_label.setStyleSheet("color: #00d2d3;")

        bottom_layout.addWidget(status_label)
        bottom_layout.addStretch()

        # Opens the official gamecast page (where the legal stream lives)
        if status == 'LIVE' and match.get('link'):
            watch_btn = QPushButton("Watch")
            watch_btn.setFixedSize(56, 20)
            url = match['link']
            watch_btn.clicked.connect(
                lambda _=False, u=url: QDesktopServices.openUrl(QUrl(u)))
            bottom_layout.addWidget(watch_btn)

        layout.addLayout(bottom_layout)

        # Play-by-play for live games (newest first)
        for line in match.get('events', [])[:3]:
            event_label = QLabel(line)
            event_label.setObjectName("event-line")
            layout.addWidget(event_label)

        return card

    def update_standings(self, standings: list):
        """Update the standings display"""
        # Clear existing standings (keep stretch)
        while self.standings_layout.count() > 1:
            item = self.standings_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not standings:
            no_data = QLabel("No standings available")
            no_data.setStyleSheet("color: #8892b0; padding: 10px;")
            self.standings_layout.insertWidget(0, no_data)
            return

        # Header
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 4, 0, 4)

        for text, width in [('#', 25), ('Team', 100), ('W', 25), ('L', 25), ('Pct', 35)]:
            label = QLabel(text)
            label.setObjectName("standings-header")
            label.setFixedWidth(width)
            header_layout.addWidget(label)

        header_layout.addStretch()
        self.standings_layout.insertWidget(0, header_widget)

        # Standings rows
        for team in standings[:10]:  # Show top 10
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 2, 0, 2)

            rank = QLabel(str(team.get('rank', '—')))
            rank.setObjectName("rank-label")
            rank.setFixedWidth(25)

            name = QLabel(truncate_text(team.get('team', 'Unknown'), 15))
            name.setObjectName("team-label")
            name.setFixedWidth(100)

            wins = QLabel(str(team.get('wins', 0)))
            wins.setObjectName("team-label")
            wins.setFixedWidth(25)

            losses = QLabel(str(team.get('losses', 0)))
            losses.setObjectName("team-label")
            losses.setFixedWidth(25)

            pct = QLabel(f"{team.get('pct', 0):.3f}")
            pct.setObjectName("team-label")
            pct.setFixedWidth(35)

            row_layout.addWidget(rank)
            row_layout.addWidget(name)
            row_layout.addWidget(wins)
            row_layout.addWidget(losses)
            row_layout.addWidget(pct)
            row_layout.addStretch()

            self.standings_layout.insertWidget(self.standings_layout.count() - 1, row)

    def position_widget(self):
        """Dock the ticker to the top-center of the screen"""
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.x() + (screen.width() - self.width()) // 2,
                  screen.y() + 8)

    def on_sport_changed(self, sport: str):
        """Handle sport selection change"""
        self.config.set('sport', SPORTS.get(sport, 'world_cup'))
        self.load_data()

    def show_settings(self):
        """Show settings dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Settings")
        dialog.setFixedSize(300, 320)
        dialog.setStyleSheet(get_style())

        layout = QVBoxLayout(dialog)

        # Favorite team
        fav_layout = QHBoxLayout()
        fav_layout.addWidget(QLabel("Favorite team:"))
        fav_edit = QLineEdit(self.config.get('favorite_team', ''))
        fav_edit.setPlaceholderText("e.g. Brazil")
        fav_layout.addWidget(fav_edit)
        layout.addLayout(fav_layout)

        # Refresh interval
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Refresh interval (sec):"))
        interval_spin = QSpinBox()
        interval_spin.setRange(30, 300)
        interval_spin.setValue(self.config.get('refresh_interval', 60))
        interval_layout.addWidget(interval_spin)
        layout.addLayout(interval_layout)

        # Always on top
        top_check = QCheckBox("Always on top")
        top_check.setChecked(self.config.get('always_on_top', True))
        layout.addWidget(top_check)

        # Show standings
        standings_check = QCheckBox("Show standings")
        standings_check.setChecked(self.config.get('show_standings', True))
        layout.addWidget(standings_check)

        # Save button
        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(lambda: self.save_settings(
            dialog, interval_spin.value(), top_check.isChecked(),
            standings_check.isChecked(), fav_edit.text().strip()
        ))
        layout.addWidget(save_btn)

        layout.addStretch()
        dialog.exec()

    def save_settings(self, dialog, interval, always_on_top, show_standings,
                      favorite_team):
        """Save settings from dialog"""
        self.config.set('refresh_interval', interval)
        self.config.set('always_on_top', always_on_top)
        self.config.set('show_standings', show_standings)
        self.config.set('favorite_team', favorite_team)

        # Update timer
        self.timer.stop()
        self.timer.start(interval * 1000)

        # Update window flags
        if always_on_top:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        self.show()

        dialog.accept()

        # Re-render so favorite-team prioritization applies immediately
        self.load_data()

    def mousePressEvent(self, event):
        """Handle mouse press for dragging"""
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging"""
        if self.drag_pos is not None:
            delta = event.globalPosition().toPoint() - self.drag_pos
            self.move(self.pos() + delta)
            self.drag_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        self.drag_pos = None
