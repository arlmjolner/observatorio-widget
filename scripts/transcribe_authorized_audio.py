#!/usr/bin/env python3
"""Transcribe audio that the publisher has authorized for reuse on El Observatorio."""
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

MAX_BYTES = 100 * 1024 * 1024

def download(url: str, target: Path) -> None:
    p = urlparse(url)
    if p.scheme != "https" or not p.hostname:
        raise ValueError("Audio URL must be HTTPS")
    request = Request(url, headers={"User-Agent": "ElObservatorio-AudioProcessor/1.0"})
    with urlopen(request, timeout=30) as response:
        content_type = response.headers.get("Content-Type", "").split(";")[0].lower()
        if not (content_type.startswith("audio/") or content_type == "application/octet-stream"):
            raise ValueError(f"Unexpected media type: {content_type}")
        length = int(response.headers.get("Content-Length", "0"))
        if length > MAX_BYTES:
            raise ValueError("Audio exceeds 100 MB limit")
        with target.open("wb") as output:
            size = 0
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ValueError("Audio exceeds 100 MB limit")
                output.write(chunk)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio-url", required=True)
    parser.add_argument("--article-url", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--rights-confirmed", action="store_true")
    args = parser.parse_args()
    if not args.rights_confirmed:
        raise SystemExit("Permission to reproduce the audio and full transcript must be confirmed.")
    if urlparse(args.article_url).scheme != "https":
        raise SystemExit("Article URL must be HTTPS")
    from faster_whisper import WhisperModel
    temp = Path("/tmp/observatorio-authorized-audio.mp3")
    download(args.audio_url, temp)
    model = WhisperModel("small", device="cpu", compute_type="int8")
    segments, info = model.transcribe(str(temp), beam_size=3, vad_filter=True)
    transcript = "\n".join(segment.text.strip() for segment in segments)
    digest = hashlib.sha256(args.article_url.encode()).hexdigest()[:16]
    out = Path("transcripts")
    out.mkdir(exist_ok=True)
    title = html.escape(args.title)
    source = html.escape(args.article_url, quote=True)
    safe_text = html.escape(transcript)
    page = f"""<!doctype html>
<html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · Transcripción · El Observatorio</title>
<style>body{{margin:0;background:#101216;color:#f0eee9;font:18px/1.7 Georgia,serif}}
main{{max-width:760px;margin:4rem auto;padding:1rem}}
a{{color:#c6ac81}}pre{{white-space:pre-wrap;font:inherit}}small{{color:#aeb4bc}}</style>
<main><p><a href="../">← El Observatorio</a></p><h1>{title}</h1>
<p><small>Transcripción automática de audio con derechos de reproducción confirmados. Puede contener errores.</small></p>
<p>Fuente: <a href="{source}" rel="noopener noreferrer">Artículo original</a></p>
<pre>{safe_text}</pre></main></html>"""
    (out / f"{digest}.html").write_text(page, encoding="utf-8")
    index_file = out / "index.json"
    index = json.loads(index_file.read_text(encoding="utf-8")) if index_file.exists() else {}
    index[args.article_url] = {"transcript": f"transcripts/{digest}.html", "audio": args.audio_url, "title": args.title, "language": info.language}
    index_file.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Generated transcripts/{digest}.html (language: {info.language})")

if __name__ == "__main__":
    main()
