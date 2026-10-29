#!/usr/bin/env python3
"""Automatically transcribe newly published articles from explicitly licensed sources."""
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
config = json.loads((ROOT / "audio_sources.json").read_text(encoding="utf-8"))
allowed = config.get("authorized_publishers", {})
existing = ROOT / "transcripts/index.json"
completed = json.loads(existing.read_text(encoding="utf-8")) if existing.exists() else {}
news = json.loads((ROOT / "news.json").read_text(encoding="utf-8"))
limit = max(0, min(int(config.get("max_transcriptions_per_run", 2)), 4))
processed = 0
seen = set()
for section, stories in news.get("categories", {}).items():
    for article in stories:
        url = article.get("url", "")
        host = urlparse(url).hostname
        if not host or urlparse(url).scheme != "https" or url in seen or url in completed:
            continue
        seen.add(url)
        # Require publisher-specific proof of reuse rights in the config.
        policy = allowed.get(host, {})
        if not (policy.get("audio_reproduction_allowed") is True and
                policy.get("transcript_republication_allowed") is True and
                policy.get("license_reference")):
            continue
        if processed >= limit:
            break
        try:
            source = subprocess.run(
                [sys.executable, str(ROOT / "scripts/find_article_audio.py"), url],
                check=True, capture_output=True, text=True, timeout=45
            ).stdout.strip()
            subprocess.run(
                [sys.executable, str(ROOT / "scripts/transcribe_authorized_audio.py"),
                 "--article-url", url, "--audio-url", source,
                 "--title", article.get("title", "Audio article"),
                 "--rights-confirmed"],
                check=True, timeout=900, cwd=str(ROOT)
            )
            processed += 1
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError) as exc:
            print(f"Skipping {url}: {exc}", file=sys.stderr)
    if processed >= limit:
        break
print(f"New authorized transcripts: {processed}")
