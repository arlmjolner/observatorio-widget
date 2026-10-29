# El Observatorio — Audio gateway

Self-hosted authenticated audio intake for **direct audio URLs that the publisher has approved for reuse**. It does not fetch NYT article HTML, proxy protected webpages, or bypass publisher HTTP 403 restrictions.

## Deploy

```bash
docker build -t observatorio-audio-gateway ./gateway
docker run -d --name observatorio-audio -p 127.0.0.1:8080:8080 \
  -e GATEWAY_TOKEN="<generate-a-long-random-secret>" \
  -e AUDIO_ALLOWED_HOSTS="your-authorized-audio-host.example" \
  -v observatorio-audio:/data/audio \
  observatorio-audio-gateway
```

Place behind a TLS reverse proxy and restrict access to trusted clients. Do **not** expose port 8080 publicly without HTTPS. Define exact allowed media hostnames (not wildcards). A secret is required; no default credential exists.

```bash
curl -X POST https://your-gateway.example/ingest \
  -H "Authorization: Bearer <secret>" \
  -H "Content-Type: application/json" \
  -d '{"article_id":"example-123","audio_url":"https://your-authorized-audio-host.example/episode.mp3"}'
```

A successful request stores an MP3 under the persistent Docker volume. A 403 from the original publisher is **not** bypassed. This gateway is an intake component, not a public audio server or an NYT extraction service.

## Limits
- Exact allowlisted public HTTPS hosts, no redirects, public-address DNS checks.
- Token authentication, 50 MB maximum per recording.
- For production, add network egress filtering, rate limiting, request audit logs, and a private container network. DNS resolution can change between validation and connection; enforce egress policy outside the app too.
- Audio files are not automatically transferred to GitHub Actions. A trusted integration or secure object storage is needed for that stage.
