"""Main application window for LinkedIn Company Tracker."""

from __future__ import annotations

import sys
from datetime import datetime

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QGroupBox,
    QCheckBox,
    QMessageBox,
    QStatusBar,
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QRect, QSize, QTimer
from PyQt6.QtGui import QFont, QGuiApplication, QPainter, QColor, QPen, QPainterPath, QIcon, QPixmap

from config.constants import SHEETS_LINK, AUTO_SCRAPE_HOUR, AUTO_SCRAPE_MINUTE
from config.paths import get_base_path
from services.sheets_service import SheetsService
from services.scrape_runner import run_scrape
from services.scheduler import ScrapeScheduler
from services.email_service import send_summary_email
from services.linkedin_scraper import LinkedInAPIError


DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Path to checkmark SVG for checkbox indicator
_CHECKMARK_SVG = get_base_path() / "assets" / "checkmark.svg"
# Path to app icon
_APP_ICON_SVG = get_base_path() / "assets" / "app_icon.svg"


def _draw_checkmark_path(painter: QPainter, rect: QRect, color: QColor, pen_width: float = 1.5) -> None:
    """Draw a checkmark (✓) inside rect. Proportions match checkmark.svg."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    x0, y0 = rect.x(), rect.y()
    w, h = rect.width(), rect.height()
    # SVG path M5 13 L9 17 L19 7 (viewBox 24x24) - scale to rect
    path = QPainterPath()
    path.moveTo(x0 + w * (5 / 24), y0 + h * (13 / 24))
    path.lineTo(x0 + w * (9 / 24), y0 + h * (17 / 24))
    path.lineTo(x0 + w * (19 / 24), y0 + h * (7 / 24))
    painter.setPen(QPen(color, pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(path)
    painter.restore()


def _make_copy_icon(size: int = 24) -> QIcon:
    """Create a polished, modern copy/clipboard icon."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    pad = size * 0.1
    w, h = size - 2 * pad, size - 2 * pad
    # Soft shadow layer
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(0x80, 0x80, 0x80, 50))
    p.drawRoundedRect(int(pad + 2), int(pad + 2), int(w), int(h), 4, 4)
    # Main clipboard body (clean white)
    p.setBrush(QColor(0xFA, 0xFA, 0xFA))
    p.setPen(QPen(QColor(0xB0, 0xB0, 0xB0), 1))
    p.drawRoundedRect(int(pad), int(pad), int(w), int(h), 4, 4)
    # Top bar (LinkedIn blue accent)
    bar_h = h * 0.2
    bar_w = w * 0.55
    bar_x = pad + (w - bar_w) / 2
    bar_y = pad + h * 0.05
    p.setBrush(QColor(0x0A, 0x66, 0xC2))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(int(bar_x), int(bar_y), int(bar_w), int(bar_h), 2, 2)
    # Copy symbol: two overlapping squares (document duplicate)
    sq = size * 0.2
    cx, cy = size / 2, size / 2 + size * 0.02
    p.setPen(QPen(QColor(0x0A, 0x66, 0xC2), 1.5))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(int(cx - sq - 2.5), int(cy - sq), int(sq), int(sq), 1, 1)
    p.drawRoundedRect(int(cx + 2.5), int(cy + 2), int(sq), int(sq), 1, 1)
    p.end()
    icon = QIcon()
    icon.addPixmap(pix)
    return icon


def _make_linked_checkmark_icon(size: int = 24) -> QIcon:
    """Create a polished 'linked' state icon: circular badge with checkmark."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    cx, cy = size / 2, size / 2
    r = size * 0.4
    # Subtle outer glow
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(0x0F, 0x9D, 0x58, 40))
    p.drawEllipse(int(cx - r - 2), int(cy - r - 2), int(2 * r + 4), int(2 * r + 4))
    # Main circle (Google green)
    p.setBrush(QColor(0x0F, 0x9D, 0x58))
    p.drawEllipse(int(cx - r), int(cy - r), int(2 * r), int(2 * r))
    # White checkmark (same style as checkboxes)
    check_pad = size * 0.24
    check_rect = QRect(int(check_pad), int(check_pad), int(size - 2 * check_pad), int(size - 2 * check_pad))
    _draw_checkmark_path(p, check_rect, QColor(255, 255, 255), pen_width=2.2)
    p.end()
    icon = QIcon()
    icon.addPixmap(pix)
    return icon

class CopyIconButton(QPushButton):
    """Beautiful copy button: icon-only, shows linked checkmark when copied."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("")
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            "QPushButton { background: transparent; border: none; padding: 6px; border-radius: 8px; }"
            "QPushButton:hover { background-color: #E3F2FD; }"
            "QPushButton:pressed { background-color: #BBDEFB; }"
        )
        self.setFixedSize(36, 36)
        self.setIconSize(QSize(24, 24))
        self._copy_icon = _make_copy_icon(24)
        self._linked_icon = _make_linked_checkmark_icon(24)
        self.setIcon(self._copy_icon)
        self.setToolTip("Copy Google Sheets link")

    def show_copied_feedback(self):
        """Switch to linked checkmark icon, revert after delay."""
        self.setIcon(self._linked_icon)
        self.setToolTip("Link copied to clipboard")
        def _revert():
            self.setIcon(self._copy_icon)
            self.setToolTip("Copy Google Sheets link")
        QTimer.singleShot(1800, _revert)


class ScrapeWorker(QThread):
    status = pyqtSignal(str)
    progress = pyqtSignal(str, int, int)
    finished_with_result = pyqtSignal(int, int, int, list, list)
    api_error = pyqtSignal(str)

    def run(self):
        try:
            def on_status(msg):
                self.status.emit(msg)

            def on_progress(profile, n_follows, n_unfollows):
                self.progress.emit(profile, n_follows, n_unfollows)

            result = run_scrape(on_status=on_status, on_progress=on_progress)
            self.finished_with_result.emit(*result)
        except LinkedInAPIError as e:
            self.finished_with_result.emit(0, 0, 0, [], [])
            self.status.emit(str(e))
            self.api_error.emit(str(e))
        except Exception as e:
            self.finished_with_result.emit(0, 0, 0, [], [])
            self.status.emit(f"Error: {e}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._running = False
        self._worker: ScrapeWorker | None = None
        self._sheets = SheetsService()
        self._scrape_scheduler = ScrapeScheduler(run_callback=self._on_scheduled_run, hour=AUTO_SCRAPE_HOUR, minute=AUTO_SCRAPE_MINUTE)
        self._build_ui()
        self._refresh_profile_count()
        self._update_next_run_status()
        self._scrape_scheduler.start()

    def _build_ui(self):
        self.setWindowTitle("LinkedIn Company Tracker")
        if _APP_ICON_SVG.exists():
            self.setWindowIcon(QIcon(str(_APP_ICON_SVG)))
        self.setMinimumWidth(520)
        self.setMinimumHeight(380)
        self.resize(760, 420)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Row 1: profile count (left), sheets link + copy (right)
        row1 = QHBoxLayout()
        row1.setSpacing(4)
        self._profile_count_label = QLabel("Profiles in tracking: 0")
        self._profile_count_label.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        row1.addWidget(self._profile_count_label)
        row1.addStretch()
        link_label = QLabel("Google Sheets Link")
        link_label.setStyleSheet("color: #0d47a1;")
        row1.addWidget(link_label)
        self._copy_btn = CopyIconButton()
        self._copy_btn.clicked.connect(self._copy_sheets_link)
        row1.addWidget(self._copy_btn)
        layout.addLayout(row1)

        # Row 2: Add/Remove group
        row2_group = QGroupBox("Manage profiles")
        row2_layout = QHBoxLayout(row2_group)
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("Name")
        self._name_input.setMinimumHeight(32)
        self._name_input.setMaximumWidth(180)
        row2_layout.addWidget(self._name_input)
        self._profile_input = QLineEdit()
        self._profile_input.setPlaceholderText("LinkedIn profile URL or username (e.g. john-doe)")
        self._profile_input.setMinimumHeight(32)
        row2_layout.addWidget(self._profile_input)
        _btn_style = (
            "QPushButton { background-color: #0A66C2; color: white; border-radius: 6px; font-weight: bold; }"
            "QPushButton:hover { background-color: #004182; }"
            "QPushButton:disabled { background-color: #ccc; color: #666; }"
        )
        self._add_btn = QPushButton("Add")
        self._add_btn.setMinimumWidth(80)
        self._add_btn.setMinimumHeight(36)
        self._add_btn.setStyleSheet(_btn_style)
        self._add_btn.clicked.connect(self._on_add)
        row2_layout.addWidget(self._add_btn)
        self._remove_btn = QPushButton("Remove")
        self._remove_btn.setMinimumWidth(80)
        self._remove_btn.setMinimumHeight(36)
        self._remove_btn.setStyleSheet(_btn_style)
        self._remove_btn.clicked.connect(self._on_remove)
        row2_layout.addWidget(self._remove_btn)
        layout.addWidget(row2_group)

        # Row 3: Settings
        settings_group = QGroupBox("Settings")
        settings_layout = QVBoxLayout(settings_group)

        days_group = QGroupBox("Auto-scrape on these days (9:00 AM local time)")
        days_group.setObjectName("DaysGroup")
        days_layout = QHBoxLayout(days_group)
        days_layout.setSpacing(8)
        self._day_checks = []
        for day in DAY_LABELS:
            cb = QCheckBox(day)
            cb.setObjectName("EnhancedCheckBox")
            cb.setMinimumHeight(32)
            if day == "Mon":
                cb.setChecked(True)
            cb.stateChanged.connect(self._on_days_changed)
            self._day_checks.append((day, cb))
            days_layout.addWidget(cb)
        days_layout.addStretch()
        settings_layout.addWidget(days_group)

        self._email_check = QCheckBox("Email me the scrape summary when finished")
        self._email_check.setObjectName("EnhancedCheckBox")
        self._email_check.setMinimumHeight(32)
        self._email_check.setChecked(False)
        settings_layout.addWidget(self._email_check)
        layout.addWidget(settings_group)

        # Row 4: Run button
        run_layout = QHBoxLayout()
        run_layout.addStretch()
        self._run_btn = QPushButton("Run")
        self._run_btn.setMinimumWidth(120)
        self._run_btn.setMinimumHeight(36)
        self._run_btn.setStyleSheet(_btn_style)
        self._run_btn.clicked.connect(self._start_run)
        run_layout.addWidget(self._run_btn)
        run_layout.addStretch()
        layout.addLayout(run_layout)

        # Row 5: Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Next auto-scraping: —")

        # Style: customized default checkboxes with enhanced checkmark
        _checkmark_path = str(_CHECKMARK_SVG.resolve()).replace("\\", "/") if _CHECKMARK_SVG.exists() else ""
        _indicator_checked = f'image: url("{_checkmark_path}");' if _checkmark_path else "background-color: #0A66C2;"
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{ background-color: #f5f5f5; }}
            QGroupBox {{ font-weight: bold; border: 1px solid #ddd; border-radius: 6px; margin-top: 10px; padding-top: 10px; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 6px; }}
            QLineEdit {{ padding: 6px 10px; border: 1px solid #ccc; border-radius: 4px; }}
            QPushButton {{ padding: 6px 14px; border-radius: 4px; }}
            QCheckBox::indicator {{
                width: 15px;
                height: 15px;
                border: 2px solid #999;
                border-radius: 4px;
                background-color: white;
            }}
            QCheckBox::indicator:unchecked {{
                border: 2px solid #999;
                background-color: white;
            }}
            QCheckBox::indicator:checked {{
                border: 2px solid #0A66C2;
                {_indicator_checked}
            }}
            /* Enhanced checkboxes: chip-style with hover and selected state */
            QCheckBox#EnhancedCheckBox {{
                padding: 6px 12px;
                border: 1px solid transparent;
                border-radius: 6px;
                spacing: 8px;
                min-width: 48px;
            }}
            QCheckBox#EnhancedCheckBox:hover {{
                background-color: #e8e8e8;
                border-color: #ccc;
            }}
            QCheckBox#EnhancedCheckBox:checked {{
                background-color: #E8F0FE;
                border-color: #0A66C2;
                color: #0A66C2;
                font-weight: 600;
            }}
        """)

    def _refresh_profile_count(self):
        try:
            n = self._sheets.get_profile_count()
            self._profile_count_label.setText(f"Profiles in tracking: {n}")
        except Exception as e:
            self._profile_count_label.setText("Profiles: (error loading)")

    def _copy_sheets_link(self):
        cb = QGuiApplication.clipboard()
        if cb:
            cb.setText(SHEETS_LINK)
            self._copy_btn.show_copied_feedback()
            self.statusBar().showMessage("Link copied to clipboard", 2000)

    def _on_add(self):
        if self._running:
            return
        name = self._name_input.text().strip()
        profile = self._profile_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Add profile", "Please enter a name for the profile.")
            return
        if not profile:
            QMessageBox.warning(self, "Add profile", "Please enter a LinkedIn profile URL or username.")
            return
        if not self._is_valid_profile_input(profile):
            QMessageBox.warning(self, "Add profile", "Please enter a valid LinkedIn profile URL or username.")
            return
        try:
            added = self._sheets.add_profile(name, profile)
            if added:
                self._name_input.clear()
                self._profile_input.clear()
                self._refresh_profile_count()
                QMessageBox.information(self, "Add profile", "Profile added successfully.")
            else:
                QMessageBox.warning(self, "Add profile", "This profile is already in the list.")
        except Exception as e:
            QMessageBox.critical(self, "Add profile", f"Failed to add profile: {e}")

    def _is_valid_profile_input(self, text: str) -> bool:
        if not text or len(text) > 500:
            return False
        if text.startswith("http"):
            return "linkedin.com" in text and "/in/" in text
        return bool(text.replace("-", "").replace("_", "").isalnum() or text.replace("-", "").replace("_", "").replace(".", "").isalnum())

    def _on_remove(self):
        if self._running:
            return
        name = self._name_input.text().strip()
        profile = self._profile_input.text().strip()
        # Prefer profile if both filled; otherwise use whichever is non-empty
        if profile:
            identifier = profile
            exists = self._sheets.profile_exists(profile)
        elif name:
            identifier = name
            exists = self._sheets.name_exists(name)
        else:
            QMessageBox.warning(self, "Remove profile", "Please enter the Name or LinkedIn profile URL/username to remove.")
            return
        if not exists:
            QMessageBox.warning(self, "Remove profile", "This profile is not in the list.")
            return
        reply = QMessageBox.question(
            self,
            "Remove profile",
            "This will remove the profile from the tracking list and delete all existing records related to this profile from every sheet (Overall List, New Follows, New Unfollows).\n\nDo you want to continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            removed = self._sheets.remove_profile_and_related_records(identifier)
            if removed:
                self._name_input.clear()
                self._profile_input.clear()
                self._refresh_profile_count()
                QMessageBox.information(self, "Remove profile", "Profile and all related records have been removed.")
            else:
                QMessageBox.warning(self, "Remove profile", "This profile is not in the list.")
        except Exception as e:
            QMessageBox.critical(self, "Remove profile", f"Failed to remove: {e}")

    def _on_days_changed(self):
        selected = [day for day, cb in self._day_checks if cb.isChecked()]
        self._scrape_scheduler.set_days(selected)
        self._scrape_scheduler.start()
        self._update_next_run_status()

    def _update_next_run_status(self):
        next_dt = self._scrape_scheduler.get_next_run_time()
        if next_dt:
            self._status_bar.showMessage(f"Next auto-scraping at 9:00 AM on {next_dt.strftime('%b %d, %Y')}")
        else:
            self._status_bar.showMessage("No auto-scraping scheduled (select at least one day).")

    def _on_scheduled_run(self):
        self._start_run()

    def _set_running(self, running: bool):
        self._running = running
        self._run_btn.setEnabled(not running)
        self._run_btn.setText("Running..." if running else "Run")
        self._add_btn.setEnabled(not running)
        self._remove_btn.setEnabled(not running)
        self._name_input.setEnabled(not running)
        self._profile_input.setEnabled(not running)

    def _start_run(self):
        if self._running:
            return
        self._set_running(True)
        self._status_bar.showMessage("Scraping…")
        self._worker = ScrapeWorker()
        self._worker.status.connect(self._on_worker_status)
        self._worker.progress.connect(self._on_worker_progress)
        self._worker.finished_with_result.connect(self._on_worker_finished)
        self._worker.api_error.connect(self._on_api_error)
        self._worker.start()

    def _on_worker_status(self, msg: str):
        self._status_bar.showMessage(f"Scraping {msg}")

    def _on_worker_progress(self, profile: str, n_follows: int, n_unfollows: int):
        self._status_bar.showMessage(f"Scraping {profile}  |  Found {n_follows} new follows, {n_unfollows} new unfollows.")

    def _on_api_error(self, message: str):
        QMessageBox.warning(
            self,
            "API Error",
            message + "\n\nPlease recheck your API key status and try again.",
        )

    def _on_worker_finished(self, profiles_processed: int, new_follows: int, new_unfollows: int,
                            new_follows_list: list, new_unfollows_list: list):
        self._set_running(False)
        self._refresh_profile_count()
        self._update_next_run_status()
        next_dt = self._scrape_scheduler.get_next_run_time()
        if next_dt:
            self._status_bar.showMessage(
                f"Done. Processed {profiles_processed} profiles; {new_follows} new follows, {new_unfollows} new unfollows. "
                f"Next auto-scraping at 9:00 AM on {next_dt.strftime('%b %d, %Y')}."
            )
        else:
            self._status_bar.showMessage(f"Done. Processed {profiles_processed} profiles; {new_follows} new follows, {new_unfollows} new unfollows.")
        if self._email_check.isChecked():
            ok, msg = send_summary_email(
                profiles_processed, new_follows, new_unfollows,
                new_follows_list, new_unfollows_list,sender_email="tejas021012@gmail.com", sender_password="kmg1012$$"
            )
            if not ok:
                QMessageBox.warning(self, "Email", f"Could not send summary email: {msg}")
        self._worker = None

    def closeEvent(self, event):
        if self._running:
            QMessageBox.warning(
                self,
                "Scraping in progress",
                "Please wait for the current scraping to finish before closing.",
            )
            event.ignore()
            return
        self._scrape_scheduler.stop()
        event.accept()
