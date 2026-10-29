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
attempted = 0
MAX_ATTEMPTS = 8
failures = []
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
        if attempted >= MAX_ATTEMPTS:
            break
        attempted += 1
        try:
            source = subprocess.run(
                [sys.executable, str(ROOT / "scripts/find_article_audio.py"), url],
                check=True, capture_output=True, text=True, timeout=45
            )
            if not source.stdout.strip():
                raise ValueError('Audio extractor returned an empty URL')
            print(f'Discovered audio for {url}', flush=True)
            subprocess.run(
                [sys.executable, str(ROOT / "scripts/transcribe_authorized_audio.py"),
                 "--article-url", url, "--audio-url", source.stdout.strip(),
                 "--title", article.get("title", "Audio article"),
                 "--rights-confirmed"],
                check=True, timeout=900, cwd=str(ROOT)
            )
            processed += 1
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError) as exc:
            detail = (getattr(exc, "stderr", "") or str(exc)).strip()
            if "\\n" in detail:
                detail = detail.splitlines()[-1]
            failures.append({"url": url, "error": detail[:600]})
            print(f"Skipping {url}: {detail}", file=sys.stderr, flush=True)
    if processed >= limit:
        break
report = {"attempted": attempted, "published": processed, "failures": failures[:30]}
(ROOT / "audio-diagnostics.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(f"Audio scan: attempted={attempted}, published={processed}, errors={len(failures)}")
if attempted and not processed:
    raise SystemExit("Audio pipeline processed no recordings: see audio-diagnostics.json")
