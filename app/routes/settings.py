from __future__ import annotations

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.db import get_db
from app.services.app_settings import get_notification_config, set_setting
from app.services.notifications import NotificationService
from app.web import templates


router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
def settings_page(request: Request, db: Session = Depends(get_db)):
    config = get_notification_config(db, get_settings())
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "request": request,
            "config": config,
            "test_result": request.query_params.get("result", ""),
        },
    )


@router.post("")
def save_settings(
    discord_webhook_url: str = Form(""),
    discord_username: str = Form("Ticket Alert Bot"),
    discord_avatar_url: str = Form(""),
    enable_discord: str | None = Form(None),
    db: Session = Depends(get_db),
):
    set_setting(db, "discord_webhook_url", discord_webhook_url.strip())
    set_setting(db, "discord_username", discord_username.strip())
    set_setting(db, "discord_avatar_url", discord_avatar_url.strip())
    set_setting(db, "enable_discord", "true" if enable_discord is not None else "false")
    db.commit()
    return RedirectResponse(url="/settings?result=saved", status_code=303)


@router.post("/test")
def test_notification(db: Session = Depends(get_db)):
    service = NotificationService(get_settings())
    result = service.send_test_notification(db)
    suffix = "ok" if result.success else "failed"
    return RedirectResponse(url=f"/settings?result={suffix}", status_code=303)
