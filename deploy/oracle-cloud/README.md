# Oracle Cloud Deploy

This is the recommended path if you want the worker to keep running while your own computer is turned off.

## Why Oracle Cloud

Oracle Cloud Free Tier includes Always Free compute instances that can run a small long-lived worker without requiring a paid background-worker platform.

Official references:

- [Oracle Cloud Free Tier](https://www.oracle.com/cloud/free/)
- [Always Free compute resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)

## Recommended VM Choice

Recommended for this project:

- `Ubuntu 24.04`
- `VM.Standard.A1.Flex`
- `1 OCPU / 6 GB RAM` or larger within the Always Free allowance

This recommendation is an inference from the app's runtime needs, not an Oracle requirement:

- Playwright + Chromium + `xvfb` is usually too tight on the `E2.1.Micro` 1 GB shape.

If you had to fall back to `VM.Standard.E2.1.Micro`:

- it may still fail under load
- the bootstrap script now creates swap automatically on low-memory shapes to improve survival odds
- treat it as a temporary workaround, not the ideal long-term shape

## Important Note About Always Free

Oracle's docs say idle Always Free compute instances may be reclaimed when CPU, network, and memory usage stay low for an extended period.

Because this worker is intentionally lightweight, there is some reclaim risk on Always Free. That is provider behavior, not an app bug.

## Network

This worker does not need any inbound HTTP port.

You only need:

- SSH access to the VM
- outbound internet access for Interpark/NOL and Discord webhook calls

## Fastest Setup

After creating and SSHing into the Ubuntu VM:

```bash
sudo apt-get update
sudo apt-get install -y git
git clone https://github.com/minwoo-khu/ticket_alert.git
cd ticket_alert
bash deploy/oracle-cloud/bootstrap-ubuntu.sh
```

Reconnect SSH once, then:

```bash
cd ~/ticket_alert
APP_DIR=/opt/ticket_alert REPO_URL=https://github.com/minwoo-khu/ticket_alert.git bash deploy/oracle-cloud/update-and-run.sh
cd /opt/ticket_alert
nano .env
nano worker.json
bash deploy/oracle-cloud/update-and-run.sh
```

## What To Edit On The VM

In `.env`:

- `DISCORD_WEBHOOK_URL`

In `worker.json`:

- target `page_url`
- `date_label`
- `round_label`
- `poll_interval_seconds`

## Daily Commands

Start or update after a new push:

```bash
cd /opt/ticket_alert
bash deploy/oracle-cloud/update-and-run.sh
```

Check logs:

```bash
cd /opt/ticket_alert
docker compose logs -f
```

Check container state:

```bash
cd /opt/ticket_alert
docker compose ps
```

Stop the worker:

```bash
cd /opt/ticket_alert
docker compose down
```

## Persistence

The worker stores state in:

- `runtime/state.json`
- `runtime/screenshots/`
- `runtime/profiles/`

Because `docker-compose.yml` bind-mounts `./runtime:/app/runtime`, those files stay on the VM disk across container restarts and reboots.
