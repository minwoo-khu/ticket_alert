# Ticket Availability Alert MVP

Local-first MVP for monitoring Interpark-style ticket pages and sending Discord webhook alerts when watched seat categories move from `0` to `1+`.

Two sample monitors are seeded for:

- `https://tickets.interpark.com/goods/26005670` on `2026-08-08`
- `https://tickets.interpark.com/goods/26005670` on `2026-08-09`

## What This App Does

- Opens a local dashboard with monitor/profile/settings pages
- Stores monitors, runs, seat states, and alerts in SQLite
- Reuses a persistent Playwright browser profile for one-time manual login
- Polls conservatively with per-monitor jitter and failure backoff
- Parses seat summary text into category counts
- Sends Discord webhook notifications on `0 -> 1+` transitions

## What This App Does Not Do

- Auto-purchase tickets
- Fill forms automatically
- Bypass login, CAPTCHA, queues, or anti-bot protections

## Stack

- Python 3.11+
- FastAPI
- Playwright (Python)
- SQLite + SQLAlchemy
- APScheduler
- Jinja2 server-rendered dashboard
- Discord webhook notifications

## Project Layout

```text
app/
  browser/
  parsers/
  routes/
  services/
  static/
  templates/
tests/
fixtures/
profiles/
screenshots/
data/
```

## Setup

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
Copy-Item .env.example .env
python -m app.main migrate-or-init
python -m app.main runserver
```

### macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
python -m app.main migrate-or-init
python -m app.main runserver
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Discord Webhook Setup

1. Create a Discord channel you can keep private.
2. Edit the channel settings and create an incoming webhook.
3. Put the webhook URL in `.env` or save it from the dashboard settings page.
4. Enable Discord mobile notifications for that channel/server on your phone.
5. Use the dashboard `Test Notification` button or run:

```bash
python -m app.main test-discord
```

## Manual Login Profile Setup

The app never stores plaintext passwords. It expects manual login with a persistent browser profile.

### Dashboard flow

1. Open `/profiles`
2. Save a profile
3. Click `Open Login Session`
4. Log in manually in the headed Chromium window
5. Close the browser window

### CLI flow

```bash
python -m app.main init-profile --name interpark_main --url "https://tickets.interpark.com/goods/26005670"
```

## Creating or Editing Monitors

From the dashboard:

1. Open `New Monitor`
2. Set the Interpark URL
3. Set `date_label` to `2026-08-08` or `2026-08-09`
4. Leave seat categories blank to watch every parsed category, or enter specific names
5. Pick a profile
6. Save the monitor
7. Enable it and use `Run Now` to verify extraction

## CLI Commands

```bash
python -m app.main migrate-or-init
python -m app.main seed-samples
python -m app.main runserver
python -m app.main run-monitor --id 1
python -m app.main test-discord
python -m app.main init-profile --name interpark_main --url "https://tickets.interpark.com/goods/26005670"
```

## Tests

Run the parser, transition, and mock-runner tests with:

```bash
python -m unittest discover -s tests
```

## Selector Tips

- Prefer visible-text selectors first
- Use `seat_summary_selector` when the DOM stabilizes
- Keep `date_button_text` and `round_button_text` editable per monitor
- If extraction fails, check run history and the saved screenshot path

Example advanced selectors JSON:

```json
{
  "date_picker_container": ".date-panel",
  "date_button_text": "9",
  "round_button_text": "1st / 19:00",
  "seat_summary_selector": ".seat-summary",
  "seat_summary_text_hint": "ReservedA"
}
```

## Docker

```bash
docker compose up --build
```

The container stores SQLite data, profiles, and screenshots in the local `data/`, `profiles/`, and `screenshots/` directories.

## Troubleshooting

- If notifications do not arrive, confirm the Discord webhook URL and phone notification settings.
- If extraction fails after the site updates, edit the monitor selectors JSON and test with `Run Now`.
- If the login expires, reopen the saved browser profile and log in manually again.
- If Playwright is missing Chromium, run `playwright install chromium`.
