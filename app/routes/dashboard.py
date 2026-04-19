from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, Request

from app.db import get_db
from app.models import Alert, Monitor, MonitorRun, SeatState
from app.web import templates


router = APIRouter()


@router.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    monitors = list(db.execute(select(Monitor).order_by(Monitor.id.asc())).scalars())
    recent_alerts = list(
        db.execute(select(Alert).order_by(Alert.sent_at.desc()).limit(10)).scalars()
    )
    recent_runs = list(
        db.execute(select(MonitorRun).order_by(MonitorRun.started_at.desc()).limit(20)).scalars()
    )
    alert_counts = Counter(
        db.execute(select(Alert.monitor_id)).scalars()
    )

    state_rows = list(db.execute(select(SeatState)).scalars())
    state_by_monitor: dict[int, list[SeatState]] = {}
    for row in state_rows:
        state_by_monitor.setdefault(row.monitor_id, []).append(row)

    monitor_cards = []
    for monitor in monitors:
        states = state_by_monitor.get(monitor.id, [])
        current_counts = ", ".join(
            f"{state.category_name}={state.last_count}"
            for state in sorted(states, key=lambda item: item.category_name)
        ) or "-"

        monitor_cards.append(
            {
                "monitor": monitor,
                "watched_categories": ", ".join(monitor.seat_category_list) or "All categories",
                "current_counts": current_counts,
                "alerts_sent": alert_counts.get(monitor.id, 0),
            }
        )

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "monitor_cards": monitor_cards,
            "recent_alerts": recent_alerts,
            "recent_runs": recent_runs,
        },
    )


@router.get("/history")
def history(request: Request, db: Session = Depends(get_db)):
    runs = list(
        db.execute(select(MonitorRun).order_by(MonitorRun.started_at.desc()).limit(100)).scalars()
    )
    alerts = list(
        db.execute(select(Alert).order_by(Alert.sent_at.desc()).limit(100)).scalars()
    )
    return templates.TemplateResponse(
        "history.html",
        {
            "request": request,
            "runs": runs,
            "alerts": alerts,
        },
    )
