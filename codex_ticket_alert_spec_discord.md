# Codex Build Spec — Ticket Availability Alert App

## 1) Mission
Build a **working MVP** that monitors a ticket product page like the one shown in the reference screenshots and sends a **phone notification** when any watched seat category changes from **`0석` to `1석 이상`**.

This is **not** an auto-purchase bot. It is only a **monitor + alert** tool.

The MVP should be good enough for local use on a laptop or desktop first, and easy to deploy later on a small VPS.

---

## 2) Hard constraints / guardrails

1. **Do not implement auto-purchase, auto-form-fill, queue bypass, CAPTCHA bypass, login bypass, or any anti-bot evasion.**
2. The app may use normal browser automation only for:
   - opening the page
   - selecting date / round if needed
   - reading visible seat counts
   - taking screenshots for debugging
3. The app must assume the user will do **manual login** once if the website requires authentication.
4. Use a **conservative polling interval** with **random jitter** to avoid hammering the site.
5. Build the system so selectors are **editable/configurable**, because the site DOM can change.
6. The app must be usable even if the website structure changes slightly.

---

## 3) Product outcome

Create a local-first app with these capabilities:

- Monitor one or more ticket pages.
- For each monitored item, store:
  - page URL
  - event title
  - watched date
  - watched round/time
  - seat categories to watch
  - polling interval
  - whether to use Discord webhook notifications
- Read seat summaries such as:
  - `스탠딩R 0석`
  - `스탠딩S 0석`
  - `지정석R 0석`
  - `지정석S 0석`
  - `지정석A 0석`
  - `지정석B 0석`
- Detect **state transitions**:
  - notify when `0 -> 1+`
  - do **not** spam repeated notifications while the count remains above zero
  - notify again only after the count goes back to zero and later rises again, or after a configurable cooldown if we choose to support reminder alerts
- Push the alert to the user’s phone through a **Discord webhook** as the default provider.
- Store logs, snapshots, and last-seen seat state in SQLite.
- Expose a minimal local dashboard for setup and status.

---

## 4) Best implementation choice

Use this stack:

- **Python 3.11+**
- **FastAPI** for local dashboard + API
- **Playwright (Python)** for browser automation
- **SQLite** with SQLAlchemy
- **APScheduler** for background jobs
- **Jinja2 + HTMX** or simple server-rendered HTML for the dashboard
- **Discord webhook** for push alerts
- Optional Docker support

Notification design note:
- use a **Discord webhook URL**, not a full bot client, for the MVP
- assume the user creates a dedicated channel and enables phone push notifications in the Discord mobile app

Why this stack:

- Playwright is strong for dynamic pages.
- Python is fast to build and easy to debug.
- FastAPI + SQLite is enough for a reliable local MVP.
- Discord webhook notifications are simple to implement, easy to test, and arrive on the phone through the Discord mobile app.

---

## 5) Deliverables

Build a working repository containing:

1. **Application code**
2. **README.md** with setup and usage
3. **.env.example**
4. **database migrations or auto-create schema**
5. **sample config / sample monitors**
6. **tests** for parsing and transition logic
7. **Dockerfile** and optional `docker-compose.yml`
8. **fixtures** for local parser testing without hitting the live site

This should be a **real working MVP**, not just a plan or pseudocode.

---

## 6) User story

As a user, I want to:

1. open a local dashboard,
2. add a monitor for a ticket page,
3. set the date / round / seat categories I care about,
4. connect a Discord webhook URL, preferably for a dedicated private channel,
5. do a one-time manual login in a persistent browser profile if needed,
6. let the app check periodically,
7. get a phone alert the moment a watched category changes from `0석` to `1석 이상`.

---

## 7) Reference behavior from the screenshot

Assume the page has a structure similar to this:

- right-side date box with a selected date (example: `2026.08.09`)
- round/session selector (example: `1회 19:00`)
- seat summary text line below showing categories and counts such as:
  - `스탠딩R 0석 / 스탠딩S 0석 / 지정석R 0석 / 지정석S 0석 / 지정석A 0석 / 지정석B 0석`
- a main booking button (`예매하기`)

The live DOM may differ. Therefore:

- Prefer **text-based Playwright locators** and **fallback parsing strategies**.
- Make selectors configurable in the dashboard and/or a YAML/JSON file.
- Store the parsed raw seat-summary text for debugging.

---

## 8) Core features

### A. Monitor management

Create monitors with these fields:

- `name`
- `event_title`
- `page_url`
- `date_label` (example: `2026-08-09` or `8/9`)
- `round_label` (example: `1회 19:00`)
- `seat_categories` (list of category names to watch)
- `poll_interval_seconds`
- `jitter_min_seconds`
- `jitter_max_seconds`
- `enabled`
- `selectors_json` or `parser_profile`
- `notification_cooldown_seconds`
- `headless` (bool)
- `profile_name` (persistent browser profile to reuse login)

### B. Persistent browser session

Implement a setup flow so the user can log in manually once.

Required behavior:

- The app can launch Playwright with a **persistent browser context**.
- A setup page/button should open the browser in **headed** mode.
- The user logs in manually.
- The profile is saved locally and reused by monitor jobs.
- The app never asks the user to store plaintext passwords.

### C. Seat reading

Implement a monitor worker that:

1. opens the target page,
2. optionally selects the target date,
3. optionally selects the target round,
4. reads the seat-summary section,
5. parses category counts,
6. compares against previous state,
7. stores current state,
8. sends notification on `0 -> 1+` transitions.

### D. Transition logic

For each category:

- If previous count is `0` and current count is `> 0`, trigger alert.
- If previous count is `None` (first run), **do not** alert unless `notify_on_first_seen_available=true` is enabled.
- If current count is unchanged and still `> 0`, do not alert repeatedly.
- If count goes from `> 0` back to `0`, reset the state so the next `0 -> 1+` can alert again.

### E. Notifications

Implement a notification abstraction with **Discord webhook first**.

Discord webhook requirements:

- environment variable for webhook URL and optional username/avatar overrides
- test notification button in dashboard
- message format should work with a plain webhook POST and look readable on mobile

Example payload content:

```text
[좌석 알림]
오피셜히게단디즘 아시아 투어 2026 in SEOUL
날짜: 2026-08-09
회차: 1회 19:00
카테고리: 지정석A
변화: 0석 -> 1석 이상 감지
URL: <page_url>
체크시각: 2026-04-19 21:30:00
```

Preferred implementation details:
- send either `content` text only or a simple embed
- include screenshot file path in the message if attaching files is inconvenient
- support multiple changed categories in one message
- keep the payload small and robust
- document that phone push depends on the user enabling Discord mobile notifications for that channel/server

### F. Dashboard

Create a simple local dashboard with pages:

1. **Home / status**
   - list monitors
   - enabled/disabled status
   - last check time
   - last result summary
   - current known counts
   - recent alerts
2. **Create/Edit monitor**
3. **Profiles / session setup**
4. **Logs / history**
5. **Settings / notifications**

### G. Debugging support

For each run, optionally store:

- raw extracted seat summary text
- structured parsed counts
- screenshot file path
- error message if failed
- browser console errors if useful

Keep only recent screenshots/logs to avoid uncontrolled disk growth.

---

## 9) Parsing requirements

Build robust parsing that can handle strings like:

```text
스탠딩R 0석 / 스탠딩S 0석 / 지정석R 0석 / 지정석S 0석 / 지정석A 0석 / 지정석B 0석
```

Expected parsed output example:

```json
{
  "스탠딩R": 0,
  "스탠딩S": 0,
  "지정석R": 0,
  "지정석S": 0,
  "지정석A": 0,
  "지정석B": 0
}
```

Requirements:

- Support Korean category names.
- Ignore spacing differences.
- Handle separators like `/`, `·`, `,`, line breaks, or extra whitespace.
- Handle counts shown as `0석`, `1석`, `12석`.
- If the page uses different wording, store raw text and fail gracefully.

Suggested parser approach:

- Use regex such as `([가-힣A-Za-z0-9]+)\s*(\d+)석`
- Add normalization rules for category labels
- Keep parser unit-tested

---

## 10) Selector strategy

Do **not** rely on one fragile selector.

Implement a layered approach:

1. Preferred: locate date/round/seat summary by visible text or accessible role.
2. Fallback: configurable CSS selectors.
3. Fallback: search page text for a line containing multiple `석` tokens.

Per monitor, support configuration fields such as:

```json
{
  "date_picker_container": "optional css",
  "date_button_text": "9",
  "round_button_text": "1회 19:00",
  "seat_summary_selector": "optional css",
  "seat_summary_text_hint": "스탠딩R"
}
```

Behavior:

- If a selector fails, log the failure.
- Take a screenshot.
- Do not crash the whole app.

---

## 11) Polling and rate limiting

Default values:

- `poll_interval_seconds = 45`
- `jitter_min_seconds = 5`
- `jitter_max_seconds = 12`
- exponential backoff on repeated failures, capped reasonably

Rules:

- stagger multiple monitors so they do not all fire at once
- sleep random jitter before each check
- after repeated errors, increase wait time temporarily

---

## 12) Data model

Use SQLite with tables roughly like:

### `profiles`
- `id`
- `name`
- `browser_type`
- `profile_path`
- `created_at`
- `updated_at`

### `monitors`
- `id`
- `name`
- `event_title`
- `page_url`
- `date_label`
- `round_label`
- `seat_categories_json`
- `poll_interval_seconds`
- `jitter_min_seconds`
- `jitter_max_seconds`
- `notification_cooldown_seconds`
- `enabled`
- `selectors_json`
- `parser_profile`
- `profile_id`
- `headless`
- `created_at`
- `updated_at`

### `monitor_runs`
- `id`
- `monitor_id`
- `started_at`
- `finished_at`
- `status` (`success`, `error`, `partial`)
- `raw_summary_text`
- `parsed_counts_json`
- `screenshot_path`
- `error_message`

### `seat_states`
- `id`
- `monitor_id`
- `category_name`
- `last_count`
- `last_seen_at`
- `last_alerted_at`
- `is_currently_available`

### `alerts`
- `id`
- `monitor_id`
- `category_name`
- `old_count`
- `new_count`
- `message`
- `sent_at`
- `provider`
- `success`
- `provider_response`

### `app_settings`
- `key`
- `value`

---

## 13) Suggested project structure

```text
seat-alert/
  app/
    main.py
    config.py
    db.py
    models.py
    schemas.py
    deps.py
    templates/
    static/
    routes/
      dashboard.py
      monitors.py
      profiles.py
      settings.py
      api.py
    services/
      scheduler.py
      monitor_runner.py
      transition_logic.py
      notifications.py
      discord_provider.py
      screenshot_retention.py
    browser/
      playwright_manager.py
      selector_helpers.py
      extraction.py
    parsers/
      seat_parser.py
      normalizers.py
    utils/
      time.py
      logging.py
      files.py
  tests/
    test_seat_parser.py
    test_transition_logic.py
    test_monitor_runner_mock.py
  fixtures/
    sample_seat_summary_01.html
    sample_seat_summary_02.html
  profiles/
  screenshots/
  data/
    app.db
  .env.example
  requirements.txt
  README.md
  Dockerfile
  docker-compose.yml
```

---

## 14) UX requirements

Keep the UI minimal and functional.

### Dashboard table columns
- Name
- Event
- Date
- Round
- Watched categories
- Last check
- Current counts
- Status
- Alerts sent
- Actions

### Monitor form fields
- Name
- Event title
- Page URL
- Date label
- Round label
- Seat categories (comma-separated or tag UI)
- Poll interval
- Profile
- Headless on/off
- Enable/disable
- Selectors JSON / advanced config

### Buttons
- Save monitor
- Run now
- Pause / Resume
- Test notification
- Open login session setup
- View last screenshot

---

## 15) Session setup flow

Implement this explicitly.

### Desired behavior

1. User clicks `Open Login Session`.
2. App launches Playwright Chromium with `launch_persistent_context()` in headed mode.
3. Browser opens target page.
4. User logs in manually if needed.
5. User closes browser or clicks `Save Session`.
6. Profile is now reusable by background jobs.

Also provide a CLI fallback:

```bash
python -m app.main init-profile --name interpark_main --url "https://tickets.interpark.com/goods/26005670"
```

---

## 16) Monitor runner algorithm

Implement the monitor algorithm roughly like this:

1. Load monitor config and profile.
2. Sleep random jitter.
3. Launch/reuse Playwright persistent context.
4. Open target URL.
5. Wait for page readiness.
6. Try to select target date if configured.
7. Try to select target round if configured.
8. Extract seat summary text.
9. Parse counts.
10. Filter to watched categories.
11. Load previous state from DB.
12. For each watched category, apply transition logic.
13. Send alerts if needed.
14. Save monitor run history.
15. Save screenshot on error or optionally on every run.
16. Return structured result.

The runner must never crash the whole scheduler because one monitor fails.

---

## 17) Error handling

Handle these cases gracefully:

- network timeout
- site login expired
- selector not found
- unexpected page structure
- empty seat summary text
- parser extracted no categories
- Discord webhook send failed
- browser launch failed

Rules:

- log the error with timestamp
- save screenshot if possible
- show last error in dashboard
- continue future runs
- optionally send one error notification after N consecutive failures

---

## 18) Configuration and environment variables

Create `.env.example` with variables like:

```env
APP_ENV=development
APP_HOST=127.0.0.1
APP_PORT=8000
DATABASE_URL=sqlite:///./data/app.db
TIMEZONE=Asia/Seoul
DEFAULT_SCREENSHOT_DIR=./screenshots
DEFAULT_PROFILE_DIR=./profiles
DISCORD_WEBHOOK_URL=
DISCORD_USERNAME=Seat Alert Bot
DISCORD_AVATAR_URL=
ENABLE_DISCORD=true
MAX_SCREENSHOTS_PER_MONITOR=30
```

---

## 19) API endpoints (if useful)

If you build JSON APIs, include simple endpoints such as:

- `GET /api/health`
- `GET /api/monitors`
- `POST /api/monitors`
- `POST /api/monitors/{id}/run`
- `POST /api/monitors/{id}/toggle`
- `GET /api/alerts`
- `POST /api/test-notification`
- `POST /api/profiles/open-session`

But the app can also stay mostly server-rendered.

---

## 20) Testing requirements

At minimum, write tests for:

### Parser tests
- standard single-line input
- multiple spaces
- line breaks
- mixed separators
- categories with Korean labels
- multi-digit counts
- bad input returns empty dict or structured parse error

### Transition tests
- first observation with zero count -> no alert
- `0 -> 1` -> alert
- `0 -> 5` -> alert
- `2 -> 3` -> no alert for MVP
- `3 -> 0` -> reset availability state
- `0 -> 1` after reset -> alert again

### Mock runner tests
- use fixture HTML instead of live site
- simulate extraction success/failure

---

## 21) Acceptance criteria

The project is complete when all of these are true:

1. I can start the app locally.
2. I can create a monitor from the dashboard.
3. I can open a headed browser and manually log in once using a persistent profile.
4. The app can periodically visit the page and extract seat counts.
5. The app stores past state in SQLite.
6. When a watched category changes from `0석` to `1석 이상`, a Discord notification arrives on my phone through the configured channel.
7. Repeated checks do not spam the same availability unless the count returned to zero and became available again.
8. Errors are visible in the dashboard.
9. The repo includes setup instructions and tests.

---

## 22) Nice-to-have features after MVP

Only implement these **after** the core MVP works:

1. Multiple notification providers:
   - Telegram Bot
   - Slack webhook
   - email
   - Twilio SMS
2. Browserless parsing fallback if page HTML is simple enough
3. Keyword-based watch rules
4. Per-monitor quiet hours
5. Grouped notifications for multiple categories
6. CSV export of alert history
7. Mobile-friendly dashboard layout
8. Dark mode
9. Auto-pruning of old monitor runs
10. Play sound locally when alert fires

---

## 23) What not to do

Do not:

- over-engineer the UI
- build a full mobile app first
- require cloud deployment for MVP
- add queue bypass behavior
- add auto-click purchase flows
- add CAPTCHA solving
- hide the scraping behavior in deceptive ways

Focus on a **stable local monitoring MVP**.

---

## 24) Implementation priority order

Implement in this exact order:

1. project scaffold
2. DB models
3. seat parser + tests
4. transition logic + tests
5. Playwright persistent profile flow
6. single monitor runner using fixture HTML first
7. real page extraction with configurable selectors
8. Discord webhook notifications
9. scheduler
10. dashboard pages
11. error handling / screenshots / retention
12. README + Docker support

---

## 25) README requirements

README must include:

- what the app does
- what it does **not** do
- Python setup steps
- Playwright install steps
- `.env` setup
- Discord webhook setup steps
- how to initialize a profile
- how to run the server
- how to create a monitor
- how to test Discord notifications
- troubleshooting tips for selector breakage/login expiry

---

## 26) Setup commands to support

The final repo should support something close to:

```bash
python -m venv .venv
source .venv/bin/activate  # or Windows equivalent
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
python -m app.main migrate-or-init
python -m app.main runserver
```

If you prefer a different entrypoint, keep it simple and document it clearly.

---

## 27) Optional CLI commands

If convenient, add commands like:

```bash
python -m app.main runserver
python -m app.main init-profile --name interpark_main --url "https://tickets.interpark.com/goods/26005670"
python -m app.main run-monitor --id 1
python -m app.main test-discord
```

---

## 28) Sample monitor seed data

Seed at least one example monitor configuration for local testing:

```json
{
  "name": "Hige Dandism Seoul 8/9",
  "event_title": "오피셜히게단디즘 아시아 투어 2026 in SEOUL",
  "page_url": "https://tickets.interpark.com/goods/26005670",
  "date_label": "2026-08-09",
  "round_label": "1회 19:00",
  "seat_categories": ["지정석A", "지정석B", "스탠딩R"],
  "poll_interval_seconds": 45,
  "jitter_min_seconds": 5,
  "jitter_max_seconds": 12,
  "enabled": false,
  "headless": false,
  "selectors_json": {
    "date_button_text": "9",
    "round_button_text": "1회 19:00",
    "seat_summary_text_hint": "지정석A"
  }
}
```

---

## 29) Quality bar

Write clean, understandable code.

- use type hints where reasonable
- add docstrings to core services
- keep functions focused
- avoid giant route files
- prefer straightforward code over clever abstractions

This project should feel like a real MVP that can actually be run, debugged, and extended.

---

## 30) Final instruction

Build the repository now.

Use Discord webhook as the default notification provider for the MVP.
Do not answer with only architecture notes or pseudocode. Create the actual working codebase for the MVP described above.
