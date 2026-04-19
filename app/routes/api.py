from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException, Request

from app.config import get_settings
from app.db import get_db
from app.models import Alert, Monitor, Profile
from app.schemas import HealthResponse, MonitorCreate, MonitorRead
from app.services.notifications import NotificationService


router = APIRouter(prefix="/api", tags=["api"])


def _apply_payload(monitor: Monitor, payload: MonitorCreate) -> Monitor:
    monitor.name = payload.name
    monitor.event_title = payload.event_title
    monitor.page_url = payload.page_url
    monitor.date_label = payload.date_label
    monitor.round_label = payload.round_label
    monitor.poll_interval_seconds = payload.poll_interval_seconds
    monitor.jitter_min_seconds = payload.jitter_min_seconds
    monitor.jitter_max_seconds = payload.jitter_max_seconds
    monitor.notification_cooldown_seconds = payload.notification_cooldown_seconds
    monitor.enabled = payload.enabled
    monitor.parser_profile = payload.parser_profile
    monitor.profile_id = payload.profile_id
    monitor.headless = payload.headless
    monitor.notify_on_first_seen_available = payload.notify_on_first_seen_available
    monitor.set_seat_categories(payload.seat_categories)
    monitor.set_selectors(payload.selectors_json)
    return monitor


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@router.get("/monitors", response_model=list[MonitorRead])
def list_monitors(db: Session = Depends(get_db)):
    return list(db.execute(select(Monitor).order_by(Monitor.id.asc())).scalars())


@router.post("/monitors", response_model=MonitorRead)
def create_monitor(payload: MonitorCreate, db: Session = Depends(get_db)):
    if payload.profile_id is not None and db.get(Profile, payload.profile_id) is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    monitor = _apply_payload(Monitor(), payload)
    db.add(monitor)
    db.commit()
    db.refresh(monitor)
    return monitor


@router.post("/monitors/{monitor_id}/run")
def run_monitor(monitor_id: int, request: Request, db: Session = Depends(get_db)):
    if db.get(Monitor, monitor_id) is None:
        raise HTTPException(status_code=404, detail="Monitor not found")
    result = request.app.state.scheduler.run_monitor_now(monitor_id)
    return result.__dict__


@router.post("/monitors/{monitor_id}/toggle")
def toggle_monitor(monitor_id: int, request: Request, db: Session = Depends(get_db)):
    monitor = db.get(Monitor, monitor_id)
    if monitor is None:
        raise HTTPException(status_code=404, detail="Monitor not found")
    monitor.enabled = not monitor.enabled
    db.add(monitor)
    db.commit()
    request.app.state.scheduler.sync_monitors()
    return {"id": monitor.id, "enabled": monitor.enabled}


@router.get("/alerts")
def list_alerts(db: Session = Depends(get_db)):
    alerts = list(db.execute(select(Alert).order_by(Alert.sent_at.desc()).limit(100)).scalars())
    return [
        {
            "id": alert.id,
            "monitor_id": alert.monitor_id,
            "category_name": alert.category_name,
            "old_count": alert.old_count,
            "new_count": alert.new_count,
            "message": alert.message,
            "sent_at": alert.sent_at.isoformat(),
            "success": alert.success,
        }
        for alert in alerts
    ]


@router.post("/test-notification")
def test_notification(db: Session = Depends(get_db)):
    result = NotificationService(get_settings()).send_test_notification(db)
    return result.__dict__


@router.post("/profiles/open-session")
def open_profile_session(profile_id: int, request: Request, db: Session = Depends(get_db)):
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    from app.browser.playwright_manager import start_login_session_thread

    start_login_session_thread(
        profile_path=profile.profile_path,
        start_url="https://tickets.interpark.com/goods/26005670",
        browser_type=profile.browser_type,
    )
    return {"status": "started", "profile_id": profile.id}
