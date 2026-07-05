#!/usr/bin/env python3
"""Sportify Widget - Entry point"""

import logging
import sys

from PySide6.QtWidgets import QApplication

from .widget import SportWidget


def main():
    """Main entry point"""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    # Qt 6 enables high-DPI scaling by default
    app = QApplication(sys.argv)
    app.setApplicationName("Sportify Widget")

    widget = SportWidget()
    widget.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
