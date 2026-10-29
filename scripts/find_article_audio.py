#!/usr/bin/env python3
"""Discover a native audio element in a publicly accessible article HTML page."""
import sys
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

class Finder(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inside = False
        self.urls = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
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
    with urlopen(req, timeout=30) as response:
        if "text/html" not in response.headers.get("Content-Type", "").lower():
            raise ValueError("Expected HTML response")
        content = response.read(5 * 1024 * 1024).decode("utf-8", "replace")
    finder = Finder()
    finder.feed(content)
    for source in finder.urls:
        resolved = urljoin(url, source)
        if urlparse(resolved).scheme == "https":
            return resolved
    raise ValueError("No direct audio source found in initial HTML")

if __name__ == "__main__":
    print(find(sys.argv[1]))
