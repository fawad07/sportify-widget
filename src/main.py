#!/usr/bin/env python3
"""Sportify Widget - Entry point"""

import logging
import sys

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from .widget import SportWidget


def main():
    """Main entry point"""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    # Enable high DPI support (must be set before QApplication is created)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("Sportify Widget")

    widget = SportWidget()
    widget.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
