"""Schedule auto-scrape at 9:00 AM on selected weekdays."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger


# Weekday: 0=Mon, 6=Sun (Python Monday=0)
WEEKDAY_MAP = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}


def get_next_run(selected_days: set[int], hour: int = 9, minute: int = 0) -> datetime | None:
    """Return next run time (local) for 9 AM on one of selected_days. selected_days: 0=Mon, 6=Sun."""
    if not selected_days:
        return None
    now = datetime.now()
    today_at_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now.weekday() in selected_days and now < today_at_time:
        return today_at_time
    for d in range(1, 8):
        candidate = today_at_time + timedelta(days=d)
        if candidate.weekday() in selected_days:
            return candidate
    return None


def format_next_run(next_dt: datetime | None) -> str:
    if next_dt is None:
        return "No schedule"
    return next_dt.strftime("%b %d, %Y at %I:%M %p")


class ScrapeScheduler:
    def __init__(self, run_callback: Callable[[], None], hour: int = 9, minute: int = 0):
        self._run_callback = run_callback
        self._hour = hour
        self._minute = minute
        self._scheduler = BackgroundScheduler()
        self._selected_days: set[int] = {0}  # default Mon
        self._job_id = "auto_scrape"

    def set_days(self, day_names: list[str]) -> None:
        """day_names e.g. ['Mon', 'Wed']."""
        self._selected_days = {WEEKDAY_MAP[d] for d in day_names if d in WEEKDAY_MAP}

    def start(self) -> None:
        if not self._selected_days:
            return
        if self._scheduler.get_job(self._job_id):
            self._scheduler.remove_job(self._job_id)
        self._scheduler.add_job(
            self._run_callback,
            CronTrigger(day_of_week=",".join(str(d) for d in sorted(self._selected_days)),
                        hour=self._hour, minute=self._minute),
            id=self._job_id,
        )
        if not self._scheduler.running:
            self._scheduler.start()

    def stop(self) -> None:
        if self._scheduler.get_job(self._job_id):
            self._scheduler.remove_job(self._job_id)

    def get_next_run_time(self) -> datetime | None:
        return get_next_run(self._selected_days, self._hour, self._minute)
