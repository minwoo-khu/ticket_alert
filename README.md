# Ticket Alert Worker

Cloud-friendly ticket availability watcher for Interpark-style event pages.

This version is optimized for one job:

- keep checking ticket pages in the background
- detect `0 -> 1+` seat transitions
- send Discord webhook alerts
- keep running without your personal computer turned on

It no longer requires the dashboard or SQLite database to do the core monitoring job. The worker stores only lightweight runtime state in a JSON file.

## How It Works

- `worker.json` defines which pages to watch
- `runtime/state.json` stores the last observed seat counts
- `python -m app.worker` runs a long-lived background loop
- Discord alerts are sent when any watched category changes from `0` to a positive count

## Why The Worker Uses Headed Chromium In Docker

NOL / Interpark pages often hide or change seat data in true headless mode.

Because of that, the Docker image runs the worker with `xvfb-run`, which gives Chromium a virtual display in the cloud while still running without a visible desktop.

Default sample monitors therefore use:

- `headless: false`
- ephemeral browser profiles

## Files

- [worker.json](/C:/Users/minwo/Desktop/ticket_alert/worker.json): monitor configuration
- [app/worker.py](/C:/Users/minwo/Desktop/ticket_alert/app/worker.py): long-running worker entrypoint
- [app/worker_config.py](/C:/Users/minwo/Desktop/ticket_alert/app/worker_config.py): config loader
- [app/worker_runtime.py](/C:/Users/minwo/Desktop/ticket_alert/app/worker_runtime.py): monitor execution and transition logic
- [runtime/state.json](</C:/Users/minwo/Desktop/ticket_alert/runtime/state.json>): last observed counts and status after running locally
- [deploy/oracle-cloud/README.md](/C:/Users/minwo/Desktop/ticket_alert/deploy/oracle-cloud/README.md): Oracle Cloud VM deployment guide
- [deploy/oracle-cloud/bootstrap-ubuntu.sh](/C:/Users/minwo/Desktop/ticket_alert/deploy/oracle-cloud/bootstrap-ubuntu.sh): one-time VM bootstrap
- [deploy/oracle-cloud/update-and-run.sh](/C:/Users/minwo/Desktop/ticket_alert/deploy/oracle-cloud/update-and-run.sh): pull latest code and restart the worker
- [render.yaml](/C:/Users/minwo/Desktop/ticket_alert/render.yaml): Render background worker blueprint

## Quick Start

### 1. Install dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
```

### 2. Configure Discord

Copy `.env.example` to `.env` and set:

```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

You can also set `DISCORD_USERNAME` and `DISCORD_AVATAR_URL` if you want.

### 3. Edit monitors

Update [worker.json](/C:/Users/minwo/Desktop/ticket_alert/worker.json).

Important fields per monitor:

- `page_url`: event page
- `date_label`: date text to click
- `round_label`: optional round text
- `selectors.date_button_text`: optional day button text override
- `poll_interval_seconds`: how often to re-check
- `seat_categories`: leave empty to watch every parsed category
- `headless`: keep `false` for Interpark/NOL unless you verify headless works
- `persist_profile`: set `true` only when you really need saved cookies/login

### 4. Test one run

```powershell
python -m app.worker --once
```

Or a single monitor:

```powershell
python -m app.worker --once --monitor interpark-2026-08-08
```

### 5. Run forever

```powershell
python -m app.worker
```

## State And Persistence

The worker keeps the last seat counts in `runtime/state.json`.

That file matters because it lets the worker know whether a category changed from `0` to `1+`.

If the worker restarts with no saved state:

- it can still run
- but it may miss a transition that happened before restart

So for real cloud use, mount persistent storage to `/app/runtime`.

## Oracle Cloud Deployment

If you want the worker to keep running for free while your own PC is off, Oracle Cloud Always Free is the best fit for this repo.

Official references:

- [Oracle Cloud Free Tier](https://www.oracle.com/cloud/free/)
- [Always Free compute resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)

Recommended path:

1. Create an Ubuntu VM on Oracle Cloud.
2. Prefer `VM.Standard.A1.Flex` over the tiny `E2.1.Micro` shape.
3. SSH into the VM.
4. Follow [deploy/oracle-cloud/README.md](/C:/Users/minwo/Desktop/ticket_alert/deploy/oracle-cloud/README.md).

Recommended sizing here is an inference from this app's runtime:

- Chromium + Playwright + `xvfb` is memory-hungry, so the 1 GB micro shape is usually too tight.

Important:

- Oracle docs say idle Always Free instances may be reclaimed.
- This worker is intentionally light, so Always Free is convenient but not a hard reliability guarantee.

## Render Deployment

Render is a good fit because this app is a long-running background worker, not a serverless function.

Official references:

- [Render Background Workers](https://render.com/docs/background-workers)
- [Render Docker Deploys](https://render.com/docs/docker)
- [Render Blueprint YAML Reference](https://render.com/docs/blueprint-spec)
- [Render Persistent Disks](https://render.com/docs/disks)

### Recommended setup on Render

1. Push this repo to GitHub.
2. In Render, create a new Blueprint or background worker from the repo.
3. Use the included [render.yaml](/C:/Users/minwo/Desktop/ticket_alert/render.yaml).
4. Add secret env var:
   `DISCORD_WEBHOOK_URL`
5. The included Blueprint already declares a persistent disk mounted at:
   `/app/runtime`

That disk keeps:

- `state.json`
- screenshots
- optional persistent browser profiles

### Notes

- Render background workers are paid services.
- If you skip the disk, the worker still runs, but state resets on redeploy/restart.

## Railway / Fly.io

This worker can also run on Railway or Fly.io because it already has a Dockerfile.

But the same rule applies:

- no DB required
- one long-running worker process
- persistent storage is still recommended for `runtime/state.json`

## Config Reference

Top-level `worker.json` fields:

```json
{
  "timezone": "Asia/Seoul",
  "request_timeout_seconds": 45,
  "idle_sleep_seconds": 5,
  "state_path": "./runtime/state.json",
  "screenshot_dir": "./runtime/screenshots",
  "profile_dir": "./runtime/profiles",
  "discord": {
    "webhook_url": "",
    "username": "Ticket Alert Bot",
    "avatar_url": "",
    "enabled": true
  },
  "monitors": []
}
```

Per-monitor fields:

```json
{
  "id": "interpark-2026-08-08",
  "name": "Interpark 8/8 Watch",
  "page_url": "https://tickets.interpark.com/goods/26005670",
  "date_label": "2026-08-08",
  "round_label": "",
  "seat_categories": [],
  "selectors": {
    "date_button_text": "8"
  },
  "poll_interval_seconds": 45,
  "headless": false,
  "browser_type": "chromium",
  "persist_profile": false,
  "notification_cooldown_seconds": 0,
  "notify_on_first_seen_available": false,
  "enabled": true
}
```

## Environment Variables

Supported env vars:

- `DISCORD_WEBHOOK_URL`
- `DISCORD_USERNAME`
- `DISCORD_AVATAR_URL`
- `ENABLE_DISCORD`
- `TIMEZONE`
- `WORKER_CONFIG_PATH`
- `WORKER_STATE_PATH`
- `WORKER_PROFILE_DIR`
- `WORKER_SCREENSHOT_DIR`
- `DEFAULT_BROWSER_TYPE`
- `REQUEST_TIMEOUT_SECONDS`

## Legacy Dashboard

The old FastAPI dashboard code is still in the repository for now, but the Docker default entrypoint is the background worker:

```powershell
python -m app.worker
```

If you still want to open the legacy dashboard locally, you can run:

```powershell
python -m app.main runserver
```
