"""Stylesheets for the sports widget"""

DARK_STYLE = """
/* Global Styles */
QMainWindow {
    background-color: transparent;
}

QWidget {
    background-color: transparent;
    color: #eeeeee;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 11px;
}

/* Main Widget */
#mainWidget {
    background-color: rgba(26, 26, 46, 240);
    border-radius: 16px;
    border: 1px solid #3d3d6b;
}

/* Ticker bar */
#tickerBar {
    background-color: rgba(26, 26, 46, 240);
    border-radius: 14px;
    border: 1px solid #3d3d6b;
}

#league-label {
    color: #e94560;
    font-size: 15px;
    font-weight: bold;
}

#ticker-text {
    color: #eeeeee;
    font-size: 15px;
}

#statusLabel {
    color: #00d2d3;
    font-size: 12px;
}

/* Match Cards */
#match-card {
    background-color: rgba(15, 52, 96, 180);
    border-radius: 10px;
    padding: 10px;
    margin: 3px 5px;
}

#match-card:hover {
    background-color: rgba(26, 74, 122, 200);
}

#team-name {
    color: #eeeeee;
    font-size: 13px;
    font-weight: 500;
}

#team-score {
    color: #e94560;
    font-size: 18px;
    font-weight: bold;
}

#match-status {
    color: #feca57;
    font-size: 10px;
}

/* Standings */
#standings-header {
    color: #8892b0;
    font-size: 10px;
    padding: 4px 0;
    border-bottom: 1px solid #3d3d6b;
}

#rank-label {
    color: #8892b0;
    font-size: 10px;
}

#team-label {
    color: #eeeeee;
    font-size: 11px;
}

/* Scrollbar */
QScrollBar:vertical {
    background: rgba(26, 26, 46, 0);
    width: 6px;
    border-radius: 3px;
}

QScrollBar::handle:vertical {
    background: #3d3d6b;
    border-radius: 3px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background: #533483;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Section Headers */
#section-header {
    color: #e94560;
    font-size: 12px;
    font-weight: bold;
    padding: 8px 5px 4px 5px;
    border-bottom: 1px solid #3d3d6b;
}

/* Buttons */
QPushButton {
    background-color: rgba(15, 52, 96, 150);
    color: #eeeeee;
    border: 1px solid #3d3d6b;
    border-radius: 8px;
    padding: 5px 12px;
    font-size: 10px;
}

QPushButton:hover {
    background-color: rgba(26, 74, 122, 200);
    border-color: #533483;
}

QPushButton:pressed {
    background-color: #533483;
}

/* ComboBox */
QComboBox {
    background-color: rgba(15, 52, 96, 150);
    color: #eeeeee;
    border: 1px solid #3d3d6b;
    border-radius: 8px;
    padding: 4px 8px;
}

QComboBox:hover {
    border-color: #533483;
}

QComboBox::drop-down {
    border: none;
}

QComboBox::down-arrow {
    image: none;
}

/* Tooltip */
QToolTip {
    background-color: #1a1a2e;
    color: #eeeeee;
    border: 1px solid #3d3d6b;
    border-radius: 6px;
    padding: 4px 8px;
}
"""


def get_style() -> str:
    """Get the stylesheet for the widget"""
    return DARK_STYLE
