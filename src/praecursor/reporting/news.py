"""Serve the cloud index with a local fallback and personal RSS headline cache."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Lock
from time import monotonic
import xml.etree.ElementTree as ET

from praecursor.collectors.news import (
    MAX_SNAPSHOT, RELEASE, STALE_AFTER, fetch, load_snapshot, read_source, timestamp,
)

CACHE_SECONDS = 300


class NewsFeed:
    def __init__(self, cache):
        self.cache = cache
        self.lock = Lock()
        self.next_check = 0
        self.snapshot = None
        self.unreachable = False
        self.headlines = {}
        self.headline_sources = {}

    def _refresh(self, now):
        with ThreadPoolExecutor(max_workers=3) as pool:
            requests = {name: pool.submit(read_source, name, now, personal=True)
                        for name in ("macro", "banking")}
            release = pool.submit(fetch, RELEASE, MAX_SNAPSHOT)
            try:
                state = load_snapshot(release.result())
            except (OSError, ValueError):
                self.unreachable = True
                if self.snapshot is None:
                    try:
                        with self.cache.open("rb") as saved:
                            self.snapshot = load_snapshot(saved.read(MAX_SNAPSHOT + 1))
                    except (OSError, ValueError):
                        pass
            else:
                from praecursor.collectors.news import write_snapshot
                self.snapshot = state
                self.unreachable = False
                try:
                    write_snapshot(self.cache, state)
                except OSError:
                    pass
            for source, request in requests.items():
                try:
                    self.headline_sources[source] = {item["url"]: item["title"] for item in request.result()}
                except (OSError, ValueError, ET.ParseError):
                    continue
            current = {item["url"] for item in (self.snapshot or {}).get("items", [])}
            self.headlines = {
                url: title for url, title in (self.headlines | {
                    url: title for feed in self.headline_sources.values() for url, title in feed.items()
                }).items() if url in current
            }

    def read(self):
        now = datetime.now(timezone.utc)
        with self.lock:
            if monotonic() >= self.next_check:
                self._refresh(now)
                self.next_check = monotonic() + (60 if self.unreachable else CACHE_SECONDS)
            state = self.snapshot
            if not state:
                return dict(status="unavailable", generated_at=None, sources={}, items=[])
            stale = now - timestamp(state["generated_at"]) >= STALE_AFTER
            return dict(state, status="stale" if stale else "cached" if self.unreachable else "ok",
                        items=[dict(item, title=self.headlines.get(item["url"], item["title"]))
                               for item in state["items"]])
