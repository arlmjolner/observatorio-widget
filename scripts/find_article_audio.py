#!/usr/bin/env python3
"""Discover a native audio element in a publicly accessible article HTML page."""
import sys
import urllib.error
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

class Finder(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inside = False
        self.urls = []
        self.meta_urls = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta" and attrs.get("property") in ("og:audio", "og:audio:url", "og:audio:secure_url") and attrs.get("content"):
            self.meta_urls.append(attrs["content"])
        if tag == "audio":
            self.inside = True
            if attrs.get("src"):
                self.urls.append(attrs["src"])
        if tag == "source" and self.inside and attrs.get("src"):
            self.urls.append(attrs["src"])
    def handle_endtag(self, tag):
        if tag == "audio":
            self.inside = False

def find(url):
    if urlparse(url).scheme != "https":
        raise ValueError("HTTPS article URL required")
    req = Request(url, headers={"User-Agent": "ElObservatorio-AudioProcessor/1.0"})
    try:
        with urlopen(req, timeout=30) as response:
            if "text/html" not in response.headers.get("Content-Type", "").lower():
                raise ValueError("Expected HTML response")
            content = response.read(5 * 1024 * 1024).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        raise ValueError(f"Publisher HTML request returned HTTP {exc.code}; access may require an authorized publisher integration") from None
    except urllib.error.URLError as exc:
        raise ValueError(f"Publisher HTML request failed: {exc.reason}") from None
    finder = Finder()
    finder.feed(content)
    # Prefer a native audio player; accept explicit Open Graph audio metadata.
    for source in finder.urls + finder.meta_urls:
        resolved = urljoin(url, source)
        if urlparse(resolved).scheme == "https":
            return resolved
    raise ValueError("No audio tag or og:audio metadata found in the server HTML; the player may be rendered by JavaScript or unavailable for this article")

if __name__ == "__main__":
    try:
        print(find(sys.argv[1]))
    except ValueError as exc:
        sys.exit(f"Audio source discovery failed: {exc}")
