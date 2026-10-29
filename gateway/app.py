"""Authenticated audio intake for explicitly authorized HTTPS media sources."""
import hmac
import ipaddress
import os
import socket
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Observatorio Audio Gateway", docs_url=None, redoc_url=None)
DATA = Path(os.environ.get("AUDIO_DIR", "/data/audio"))
MAX_BYTES = 50 * 1024 * 1024

class Intake(BaseModel):
    article_id: str
    audio_url: str

def require_token(authorization: str | None):
    configured = os.getenv("GATEWAY_TOKEN", "")
    if not configured or not authorization or not hmac.compare_digest(authorization, "Bearer " + configured):
        raise HTTPException(401, "Invalid gateway token")

def valid_target(url: str):
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None,443):
        raise HTTPException(400, "HTTPS public audio URL required")
    allowed = {x.strip().lower() for x in os.getenv("AUDIO_ALLOWED_HOSTS", "").split(",") if x.strip()}
    if parsed.hostname.lower() not in allowed:
        raise HTTPException(403, "Audio hostname not allowlisted")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise HTTPException(400, "Non-public destination")
    except socket.gaierror:
        raise HTTPException(400, "Unable to resolve audio hostname")
    return parsed

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/ingest")
async def ingest(item: Intake, authorization: str | None = Header(default=None)):
    require_token(authorization)
    valid_target(item.audio_url)
    if not item.article_id or len(item.article_id) > 100 or not all(c.isalnum() or c in "-_" for c in item.article_id):
        raise HTTPException(400, "Invalid article ID")
    DATA.mkdir(parents=True, exist_ok=True)
    dest = DATA / (item.article_id + ".mp3")
    temp = DATA / (item.article_id + ".part")
    try:
        async with httpx.AsyncClient(timeout=45, follow_redirects=False, trust_env=False) as client:
            async with client.stream("GET", item.audio_url) as res:
                if res.status_code != 200:
                    raise HTTPException(502, f"Upstream audio returned HTTP {res.status_code}")
                media = res.headers.get("content-type", "").split(";")[0].lower()
                if media not in {"audio/mpeg", "audio/mp3", "application/octet-stream"}:
                    raise HTTPException(415, "Unexpected audio Content-Type")
                total = 0
                with temp.open("wb") as out:
                    async for chunk in res.aiter_bytes(1024 * 1024):
                        total += len(chunk)
                        if total > MAX_BYTES:
                            raise HTTPException(413, "Audio exceeds 50 MB")
                        out.write(chunk)
        temp.replace(dest)
    finally:
        temp.unlink(missing_ok=True)
    return {"article_id": item.article_id, "saved": True, "bytes": dest.stat().st_size}
