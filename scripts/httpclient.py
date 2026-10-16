"""Polite HTTP client: robots.txt, per-host delay, timeout, retries with backoff."""
from __future__ import annotations

import time
from urllib import robotparser
from urllib.parse import urlparse

import requests

# Identifies the project. NSE tarpits User-Agents that contain a URL, so none is included.
USER_AGENT = "Mozilla/5.0 market-dashboard/1.0 (personal project)"
TIMEOUT = 15
ATTEMPTS = 3


class RobotsDisallowed(Exception):
    pass


class Client:
    def __init__(self, delay=1.0, sleep=time.sleep, session=None):
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.delay = delay          # minimum seconds between requests to one host
        self.sleep = sleep          # injectable so tests do not wait
        self.state = set()          # scratch space for providers (e.g. "nse warmed up")
        self._last = {}             # host -> time of last request
        self._robots = {}           # host -> RobotFileParser or None (unreadable = allow)

    def _allowed(self, url):
        parts = urlparse(url)
        host = f"{parts.scheme}://{parts.netloc}"
        if host not in self._robots:
            rp = robotparser.RobotFileParser()
            try:
                resp = self.session.get(host + "/robots.txt", timeout=TIMEOUT)
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                else:
                    rp = None
            except requests.RequestException:
                rp = None
            self._robots[host] = rp
        rp = self._robots[host]
        return rp is None or rp.can_fetch(USER_AGENT, url)

    def _wait(self, host):
        wait = self._last.get(host, 0) + self.delay - time.monotonic()
        if wait > 0:
            self.sleep(wait)
        self._last[host] = time.monotonic()

    def get(self, url, **kwargs):
        """GET with robots check, host delay and 3 attempts (1s, 2s backoff)."""
        if not self._allowed(url):
            raise RobotsDisallowed(f"robots.txt disallows {url}")
        host = urlparse(url).netloc
        last_error = None
        for attempt in range(ATTEMPTS):
            if attempt:
                self.sleep(2 ** (attempt - 1))
            self._wait(host)
            try:
                resp = self.session.get(url, timeout=TIMEOUT, **kwargs)
                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                last_error = exc
        raise last_error
