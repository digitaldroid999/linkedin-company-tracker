"""Entry point for LinkedIn Company Tracker."""

import sys

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from config.paths import get_base_path
from ui.main_window import MainWindow

_APP_ICON = get_base_path() / "assets" / "app_icon.svg"


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("LinkedIn Company Tracker")
    if _APP_ICON.exists():
        app.setWindowIcon(QIcon(str(_APP_ICON)))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
