# tarkovOCEserverhealth

Docker-deployable service that renders a live **ISP latency → DataPacket
Sydney DC** trend graph (the data centre hosting Escape from Tarkov) and
keeps a single "latest-only" graph message refreshed in a Discord channel
via a webhook.

```
Telstra ~12 ms · Optus ~2 ms · Aussie Broadband ~5 ms · TPG ~3 ms · Vodafone ~3 ms · iPrimus ~145 ms
Updated 13/10 16:13 AEST · last 24h · DataPacket Sydney DC · best-in route
[ two-panel latency chart: low-latency routes + higher route ]
```

## How it works

- `render.py` — polls DataPacket's public latency API
  (`public-as.datapacket.com/v1/agr/198/<ISP probe IP>/<start>/<end>?slave=SYD`)
  for each configured ISP, picks a smoothed curve, and renders a two-panel
  matplotlib chart (low-latency routes + any high-latency route) with AEST
  time axis.
- `webhook.py` — posts the chart to a Discord webhook. **Delete-then-post**
  strategy: it deletes the previous live graph message and posts exactly one
  fresh one, so the channel never accumulates stale or stacked images
  (a known Discord webhook quirk: `PATCH` edits stack attachments, and
  `attachments: []` is rejected with HTTP 400).
- `app.py` — the entrypoint. Loops every `REFRESH_INTERVAL` seconds
  (default 1800 = 30 min). Also supports `--once` (single run, for cron)
  and `--health` (exit 0 if the last refresh succeeded recently).

## Quick start (Docker Compose)

```bash
git clone https://github.com/afraidsupra/tarkovOCEserverhealth
cd tarkovOCEserverhealth
cp .env.example .env
# edit .env -> set DISCORD_WEBHOOK_URL (required)
docker compose up -d --build
docker compose logs -f
```

That's it. The container renders the graph, posts it to your Discord
channel, and repeats every 30 minutes, always keeping exactly one
latest-only graph message.

## Run a plain Docker image

```bash
docker build -t afraidsupra/tarkov-oce-server-health .
docker run -d --name tarkov-oce-server-health \
  --env-file .env \
  -v $(pwd)/data:/data \
  --restart unless-stopped \
  afraidsupra/tarkov-oce-server-health
```

## Configuration (env vars)

| Var | Required | Default | Purpose |
|---|---|---|---|
| `DISCORD_WEBHOOK_URL` | ✅ | — | Discord webhook of the target channel |
| `REFRESH_INTERVAL` | | `1800` | seconds between refreshes |
| `HOURS` | | `24` | how far back to plot |
| `BOT_NAME` | | `Tarkov SYD latency` | webhook display name |
| `ISPS_LOW` | | 5 AU ISPs | main panel probes: `Name=IP,Name=IP` |
| `ISPS_HIGH` | | `iPrimus (Vocus)=203.134.85.40` | high-latency panel probes |
| `CHART_TITLE` | | built-in | chart suptitle |
| `CHART_OUT` | | `/data/tarkov_au_isp_latency.png` | PNG path |
| `STATE_DIR` | | `/data` | where the live-message id is stored |
| `DRY_RUN` | | — | `1` = render only, don't touch Discord |

Example custom ISP set:

```env
ISPS_LOW=Telstra=210.57.5.137,Optus=211.29.152.162,iiNet=203.50.11.139
ISPS_HIGH=iPrimus (Vocus)=203.134.85.40
```

## Data source notes

- Data: DataPacket public latency API, Sydney slave (`slave=SYD`),
  location id `198`.
- Probe IPs are per-ISP "best-in" routes (the lowest non-lost route each
  ISP has to the DC). DataPacket's own probe set includes edge caches
  (0 ms / 100 % loss) — those are deliberately excluded.
- Bucket cadence is ~3–5 minutes; 24 h ≈ 300–500 points per ISP.

## Smoke test without posting to Discord

```bash
docker run --rm --env-file .env \
  -e DRY_RUN=1 \
  -v $(pwd)/smoke:/data \
  afraidsupra/tarkov-oce-server-health --once
# -> prints readings JSON; smoke/tarkov_au_isp_latency.png is the chart
```

## Healthcheck

The image ships a `HEALTHCHECK` that runs `python app.py --health`
every 5 min — it exits 0 only if the last successful refresh is younger
than 2× `REFRESH_INTERVAL`. `docker compose ps` will show `unhealthy` if
the Discord webhook or DataPacket stops responding for a while.

## Files

| File | Role |
|---|---|
| `render.py` | data fetch + matplotlib chart |
| `webhook.py` | Discord webhook delete-then-post |
| `app.py` | entrypoint: loop / --once / --health |
| `Dockerfile` | python:3.11-slim, non-root, tzdata, healthcheck |
| `docker-compose.yml` | one-service compose file |
| `.env.example` | copy to `.env` and edit |
| `requirements.txt` | matplotlib + pytz |
