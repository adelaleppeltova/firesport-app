"""Bounded, paced HTTP retrieval with per-run caching and optional browser rendering."""

import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


class Fetcher:
    def __init__(self, delay=0.3, timeout=30, max_bytes=30_000_000):
        self.delay, self.timeout, self.max_bytes = delay, timeout, max_bytes
        self.cache = {}
        self.last = 0

    def get(self, url):
        if url in self.cache:
            return self.cache[url]
        if urlsplit(url).scheme not in {"http", "https"}:
            raise ValueError("Only HTTP(S) sources are supported")
        time.sleep(max(0, self.delay - (time.monotonic() - self.last)))
        try:
            with urlopen(
                Request(
                    url,
                    headers={
                        "User-Agent": "FlammaResultsImporter/1.0",
                        "Accept-Language": "cs",
                    },
                ),
                timeout=self.timeout,
            ) as response:
                data = response.read(self.max_bytes + 1)
                if len(data) > self.max_bytes:
                    raise ValueError("Source exceeds size limit")
                result = (data, response.geturl())
        finally:
            self.last = time.monotonic()
        self.cache[url] = result
        return result


def source_type(data):
    if data.lstrip().startswith(b"%PDF-"):
        return "pdf"
    if (
        b"<html" in data[:8192].lower()
        or b"<table" in data.lower()
        or b"<!doctype html" in data[:8192].lower()
    ):
        return "html"
    raise ValueError("Unsupported source content (neither HTML nor PDF)")


def render_html(url):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(locale="cs-CZ")
            page.goto(url, wait_until="networkidle", timeout=60000)
            page.locator("table").first.wait_for(timeout=30000)
            return page.content().encode("utf-8")
        finally:
            browser.close()
