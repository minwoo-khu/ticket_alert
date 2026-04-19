from __future__ import annotations

import argparse

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.browser.playwright_manager import open_login_session
from app.config import BASE_DIR, get_settings
from app.db import configure_engine, init_db, session_scope
from app.routes import api, dashboard, monitors, profiles, settings as settings_routes
from app.services.monitor_runner import MonitorRunner
from app.services.notifications import NotificationService
from app.services.scheduler import SchedulerService
from app.services.seeds import seed_defaults
from app.utils.files import ensure_directory
from app.utils.logging import configure_logging


def prepare_runtime() -> None:
    settings = get_settings()
    configure_logging()
    ensure_directory(settings.default_profile_dir)
    ensure_directory(settings.default_screenshot_dir)
    configure_engine(settings.database_url)
    init_db()
    with session_scope() as session:
        seed_defaults(session, settings)


def create_app() -> FastAPI:
    app = FastAPI(title="Ticket Availability Alert")
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")
    app.include_router(dashboard.router)
    app.include_router(monitors.router)
    app.include_router(profiles.router)
    app.include_router(settings_routes.router)
    app.include_router(api.router)

    @app.on_event("startup")
    def startup_event() -> None:
        prepare_runtime()
        app.state.scheduler = SchedulerService(get_settings())
        app.state.scheduler.start()

    @app.on_event("shutdown")
    def shutdown_event() -> None:
        scheduler = getattr(app.state, "scheduler", None)
        if scheduler is not None:
            scheduler.shutdown()

    return app


app = create_app()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ticket alert MVP")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("migrate-or-init", help="Initialize database schema")
    subparsers.add_parser("seed-samples", help="Seed sample profiles and monitors")
    subparsers.add_parser("runserver", help="Run the local FastAPI server")

    run_monitor_parser = subparsers.add_parser("run-monitor", help="Run one monitor immediately")
    run_monitor_parser.add_argument("--id", type=int, required=True, dest="monitor_id")

    test_discord_parser = subparsers.add_parser("test-discord", help="Send a test Discord message")
    test_discord_parser.add_argument("--message", default="[Ticket Alert] CLI test notification")

    init_profile_parser = subparsers.add_parser("init-profile", help="Open a headed profile session")
    init_profile_parser.add_argument("--name", required=True)
    init_profile_parser.add_argument("--url", required=True)
    init_profile_parser.add_argument("--browser-type", default="chromium")

    args = parser.parse_args()
    prepare_runtime()

    if args.command == "migrate-or-init":
        return

    if args.command == "seed-samples":
        with session_scope() as session:
            seed_defaults(session, get_settings())
        return

    if args.command == "runserver":
        settings = get_settings()
        uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port, reload=False)
        return

    if args.command == "run-monitor":
        runner = MonitorRunner(get_settings())
        result = runner.run_monitor(args.monitor_id, force=True)
        print(result)
        return

    if args.command == "test-discord":
        with session_scope() as session:
            result = NotificationService(get_settings()).send_test_notification(session, args.message)
        print(result)
        return

    if args.command == "init-profile":
        settings = get_settings()
        profile_path = ensure_directory(settings.default_profile_dir / args.name)
        open_login_session(profile_path, args.url, browser_type=args.browser_type)


if __name__ == "__main__":
    main()
