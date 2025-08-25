import threading
import time
from datetime import datetime
from typing import Dict, List
from flask import Flask
from ..services.storage import get_storage
from ..crawler.nature import NatureCrawler
from ..crawler.nature_rss import NatureRSSCrawler


class Scheduler:
    def __init__(self, app: Flask):
        self.app = app
        self.thread = None
        self.stop_event = threading.Event()
        self.last_run_at = None
        self.last_result_count = 0

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _run_loop(self):
        interval = self._cron_to_interval_seconds(self.app.config.get("SCHEDULER_CRON", "*/30 * * * *"))
        while not self.stop_event.is_set():
            self.run_once()
            # sleep with small steps to be responsive to stop
            slept = 0
            while slept < interval and not self.stop_event.is_set():
                time.sleep(min(5, interval - slept))
                slept += min(5, interval - slept)

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
            papers = []
            try:
                crawler = NatureCrawler(user_agent=ua)
                papers.extend(crawler.fetch_latest(max_items=max_items))
            except Exception:
                pass
            # RSS crawlers for portfolio journals
            feeds = [f for f in (self.app.config.get("FEEDS") or []) if f]
            if feeds:
                try:
                    rss = NatureRSSCrawler(feeds=feeds, user_agent=ua)
                    papers.extend(rss.fetch_latest(max_items=max_items))
                except Exception:
                    pass
            count = storage.upsert_papers(papers)
            self.last_run_at = datetime.utcnow().isoformat()
            self.last_result_count = count
            return count

    def status(self) -> Dict:
        return {
            "last_run_at": self.last_run_at,
            "last_result_count": self.last_result_count,
            "running": self.thread.is_alive() if self.thread else False,
        }


def get_scheduler(app: Flask) -> Scheduler:
    # Singleton per app instance
    if not hasattr(app, "_scheduler"):
        app._scheduler = Scheduler(app)
        app._scheduler.start()
    return app._scheduler
