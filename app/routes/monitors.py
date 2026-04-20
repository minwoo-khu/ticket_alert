from __future__ import annotations

import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.db import get_db
from app.models import Monitor, Profile
from app.web import templates


router = APIRouter(prefix="/monitors", tags=["monitors"])


def _split_categories(raw: str) -> list[str]:
    parts = re.split(r"[\n,]", raw or "")
    return [part.strip() for part in parts if part.strip()]


def _load_selectors(raw: str) -> dict:
    if not raw.strip():
        return {}
    return json.loads(raw)


def _bool_from_form(value: str | None) -> bool:
    return value is not None and value.lower() in {"on", "true", "1", "yes"}


def _monitor_form_context(db: Session, monitor: Monitor | None = None, error: str = "") -> dict:
    profiles = list(db.execute(select(Profile).order_by(Profile.name.asc())).scalars())
    data = {
        "name": monitor.name if monitor else "",
        "event_title": monitor.event_title if monitor else "",
        "page_url": monitor.page_url if monitor else "https://tickets.interpark.com/goods/26005670",
        "date_label": monitor.date_label if monitor else "",
        "round_label": monitor.round_label if monitor else "",
        "seat_categories": ", ".join(monitor.seat_category_list) if monitor else "",
        "poll_interval_seconds": monitor.poll_interval_seconds if monitor else 45,
        "jitter_min_seconds": monitor.jitter_min_seconds if monitor else 5,
        "jitter_max_seconds": monitor.jitter_max_seconds if monitor else 12,
        "notification_cooldown_seconds": monitor.notification_cooldown_seconds if monitor else 0,
        "enabled": monitor.enabled if monitor else False,
        "selectors_json": json.dumps(monitor.selectors, ensure_ascii=False, indent=2) if monitor else "{\n  \"date_button_text\": \"8\"\n}",
        "parser_profile": monitor.parser_profile if monitor else "default",
        "profile_id": monitor.profile_id if monitor else "",
        "headless": monitor.headless if monitor else False,
        "notify_on_first_seen_available": monitor.notify_on_first_seen_available if monitor else False,
    }
    return {"profiles": profiles, "data": data, "error": error, "monitor": monitor}


def _apply_monitor_form(
    *,
    monitor: Monitor,
    name: str,
    event_title: str,
    page_url: str,
    date_label: str,
    round_label: str,
    seat_categories: str,
    poll_interval_seconds: int,
    jitter_min_seconds: int,
    jitter_max_seconds: int,
    notification_cooldown_seconds: int,
    enabled: bool,
    selectors_json: str,
    parser_profile: str,
    profile_id: str,
    headless: bool,
    notify_on_first_seen_available: bool,
) -> None:
    monitor.name = name.strip()
    monitor.event_title = event_title.strip()
    monitor.page_url = page_url.strip()
    monitor.date_label = date_label.strip()
    monitor.round_label = round_label.strip()
    monitor.poll_interval_seconds = poll_interval_seconds
    monitor.jitter_min_seconds = jitter_min_seconds
    monitor.jitter_max_seconds = jitter_max_seconds
    monitor.notification_cooldown_seconds = notification_cooldown_seconds
    monitor.enabled = enabled
    monitor.parser_profile = parser_profile.strip() or "default"
    monitor.profile_id = int(profile_id) if profile_id.strip() else None
    monitor.headless = headless
    monitor.notify_on_first_seen_available = notify_on_first_seen_available
    monitor.set_seat_categories(_split_categories(seat_categories))
    monitor.set_selectors(_load_selectors(selectors_json))


@router.get("/new")
def new_monitor(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request,
        "monitor_form.html",
        {"request": request, **_monitor_form_context(db)},
    )


@router.get("/{monitor_id}/edit")
def edit_monitor(monitor_id: int, request: Request, db: Session = Depends(get_db)):
    monitor = db.get(Monitor, monitor_id)
    if monitor is None:
        raise HTTPException(status_code=404, detail="Monitor not found")
    return templates.TemplateResponse(
        request,
        "monitor_form.html",
        {"request": request, **_monitor_form_context(db, monitor=monitor)},
    )


@router.post("")
def create_monitor(
    request: Request,
    name: str = Form(...),
    event_title: str = Form(""),
    page_url: str = Form(...),
    date_label: str = Form(""),
    round_label: str = Form(""),
    seat_categories: str = Form(""),
    poll_interval_seconds: int = Form(45),
    jitter_min_seconds: int = Form(5),
    jitter_max_seconds: int = Form(12),
    notification_cooldown_seconds: int = Form(0),
    enabled: str | None = Form(None),
    selectors_json: str = Form("{}"),
    parser_profile: str = Form("default"),
    profile_id: str = Form(""),
    headless: str | None = Form(None),
    notify_on_first_seen_available: str | None = Form(None),
    db: Session = Depends(get_db),
):
    monitor = Monitor()
    try:
        _apply_monitor_form(
            monitor=monitor,
            name=name,
            event_title=event_title,
            page_url=page_url,
            date_label=date_label,
            round_label=round_label,
            seat_categories=seat_categories,
            poll_interval_seconds=poll_interval_seconds,
            jitter_min_seconds=jitter_min_seconds,
            jitter_max_seconds=jitter_max_seconds,
            notification_cooldown_seconds=notification_cooldown_seconds,
            enabled=_bool_from_form(enabled),
            selectors_json=selectors_json,
            parser_profile=parser_profile,
            profile_id=profile_id,
            headless=_bool_from_form(headless),
            notify_on_first_seen_available=_bool_from_form(notify_on_first_seen_available),
        )
    except json.JSONDecodeError as exc:
        return templates.TemplateResponse(
            request,
            "monitor_form.html",
            {
                "request": request,
                **_monitor_form_context(db, error=f"Invalid selectors JSON: {exc}"),
            },
            status_code=400,
        )

    db.add(monitor)
    db.commit()
    request.app.state.scheduler.sync_monitors()
    return RedirectResponse(url="/", status_code=303)


@router.post("/{monitor_id}")
def update_monitor(
    monitor_id: int,
    request: Request,
    name: str = Form(...),
    event_title: str = Form(""),
    page_url: str = Form(...),
    date_label: str = Form(""),
    round_label: str = Form(""),
    seat_categories: str = Form(""),
    poll_interval_seconds: int = Form(45),
    jitter_min_seconds: int = Form(5),
    jitter_max_seconds: int = Form(12),
    notification_cooldown_seconds: int = Form(0),
    enabled: str | None = Form(None),
    selectors_json: str = Form("{}"),
    parser_profile: str = Form("default"),
    profile_id: str = Form(""),
    headless: str | None = Form(None),
    notify_on_first_seen_available: str | None = Form(None),
    db: Session = Depends(get_db),
):
    monitor = db.get(Monitor, monitor_id)
    if monitor is None:
        raise HTTPException(status_code=404, detail="Monitor not found")

    try:
        _apply_monitor_form(
            monitor=monitor,
            name=name,
            event_title=event_title,
            page_url=page_url,
            date_label=date_label,
            round_label=round_label,
            seat_categories=seat_categories,
            poll_interval_seconds=poll_interval_seconds,
            jitter_min_seconds=jitter_min_seconds,
            jitter_max_seconds=jitter_max_seconds,
            notification_cooldown_seconds=notification_cooldown_seconds,
            enabled=_bool_from_form(enabled),
            selectors_json=selectors_json,
            parser_profile=parser_profile,
            profile_id=profile_id,
            headless=_bool_from_form(headless),
            notify_on_first_seen_available=_bool_from_form(notify_on_first_seen_available),
        )
    except json.JSONDecodeError as exc:
        return templates.TemplateResponse(
            request,
            "monitor_form.html",
            {
                "request": request,
                **_monitor_form_context(db, monitor=monitor, error=f"Invalid selectors JSON: {exc}"),
            },
            status_code=400,
        )

    db.add(monitor)
    db.commit()
    request.app.state.scheduler.sync_monitors()
    return RedirectResponse(url="/", status_code=303)


@router.post("/{monitor_id}/toggle")
def toggle_monitor(monitor_id: int, request: Request, db: Session = Depends(get_db)):
    monitor = db.get(Monitor, monitor_id)
    if monitor is None:
        raise HTTPException(status_code=404, detail="Monitor not found")
    monitor.enabled = not monitor.enabled
    db.add(monitor)
    db.commit()
    request.app.state.scheduler.sync_monitors()
    return RedirectResponse(url="/", status_code=303)


@router.post("/{monitor_id}/run")
def run_monitor_now(monitor_id: int, request: Request):
    request.app.state.scheduler.run_monitor_now(monitor_id)
    return RedirectResponse(url="/", status_code=303)
