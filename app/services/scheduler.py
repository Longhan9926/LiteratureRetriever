import os
import threading
import time
from datetime import datetime
from typing import Dict, List, cast
from flask import Flask
from ..services.storage import get_storage
from ..crawler.nature import NatureCrawler
from ..crawler.nature_rss import NatureRSSCrawler


class Scheduler:
    def __init__(self, app: Flask):
        self.app = app
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.last_run_at: str | None = None
        self.last_result_count: int = 0
        # One-off job control
        self._job_lock = threading.Lock()
        self._job_running = False
        # Snapshot interval to avoid accessing app context in background thread
        self.interval = self._cron_to_interval_seconds(app.config.get("SCHEDULER_CRON", "*/30 * * * *"))

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _run_loop(self):
        while not self.stop_event.is_set():
            try:
                self.run_once()
            except Exception:
                # Avoid killing the loop on transient errors
                pass
            # sleep with small steps to be responsive to stop
            slept = 0
            while slept < self.interval and not self.stop_event.is_set():
                step = min(5, self.interval - slept)
                time.sleep(step)
                slept += step

    def _cron_to_interval_seconds(self, cron_expr: str) -> int:
        # For simplicity support formats like '*/N * * * *'
        try:
            minute_field = cron_expr.split()[0]
            if minute_field.startswith("*/"):
                return int(minute_field[2:]) * 60
        except Exception:
            pass
        return 30 * 60

    def run_once(self) -> int:
        with self.app.app_context():
            storage = get_storage(self.app)
            ua = self.app.config.get("USER_AGENT")
            max_items = int(self.app.config.get("MAX_ITEMS_PER_RUN", 50))
            # Native Nature crawler
            papers: List = []
            try:
                papers.extend(NatureCrawler(user_agent=ua).fetch_search("solar cell molecule", max_items=max_items))
            except Exception:
                pass
            # RSS crawlers for portfolio journals
            feeds = [f for f in (self.app.config.get("FEEDS") or []) if f]
            if feeds:
                try:
                    papers.extend(NatureRSSCrawler(feeds=feeds, user_agent=ua).fetch_latest(max_items=max_items))
                except Exception:
                    pass
            count = storage.upsert_papers(papers)
            self.last_run_at = datetime.utcnow().isoformat()
            self.last_result_count = count
            return count

    def run_once_async(self) -> bool:
        """Start a single crawl run in a background thread.
        Returns True if started, False if a job is already running.
        """
        # Prevent overlapping one-off jobs
        with self._job_lock:
            if self._job_running:
                return False
            self._job_running = True

        def _job():
            try:
                self.run_once()
            finally:
                with self._job_lock:
                    self._job_running = False

        threading.Thread(target=_job, daemon=True).start()
        return True

    def status(self) -> Dict:
        return {
            "last_run_at": self.last_run_at,
            "last_result_count": self.last_result_count,
            "running": self.thread.is_alive() if self.thread else False,
            "job_running": self._job_running,
        }


def get_scheduler(app: Flask) -> Scheduler:
    # Unwrap LocalProxy if needed
    real_app_getter = getattr(app, "_get_current_object", None)
    if callable(real_app_getter):
        app = cast(Flask, real_app_getter())
    # Use Flask extensions registry to hold the scheduler instance
    if not hasattr(app, "extensions") or app.extensions is None:
        app.extensions = {}
    if "literature_scheduler" not in app.extensions:
        app.extensions["literature_scheduler"] = Scheduler(app)
        if os.getenv("START_SCHEDULER", "1") == "1":
            app.extensions["literature_scheduler"].start()
    return cast(Scheduler, app.extensions["literature_scheduler"])
