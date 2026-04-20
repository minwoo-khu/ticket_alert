from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.db import get_db
from app.models import Profile
from app.browser.playwright_manager import start_login_session_thread
from app.utils.files import ensure_directory, slugify
from app.web import templates


router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("")
def list_profiles(request: Request, db: Session = Depends(get_db)):
    profiles = list(db.execute(select(Profile).order_by(Profile.name.asc())).scalars())
    return templates.TemplateResponse(
        request,
        "profiles.html",
        {"request": request, "profiles": profiles},
    )


@router.post("")
def create_profile(
    request: Request,
    name: str = Form(...),
    browser_type: str = Form("chromium"),
    profile_path: str = Form(""),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    final_path = profile_path.strip() or str(
        ensure_directory(settings.default_profile_dir / slugify(name))
    )
    profile = Profile(
        name=name.strip(),
        browser_type=browser_type.strip() or "chromium",
        profile_path=final_path,
    )
    db.add(profile)
    db.commit()
    return RedirectResponse(url="/profiles", status_code=303)


@router.post("/{profile_id}/open-session")
def open_session(
    profile_id: int,
    request: Request,
    start_url: str = Form("https://tickets.interpark.com/goods/26005670"),
    db: Session = Depends(get_db),
):
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    ensure_directory(Path(profile.profile_path))
    start_login_session_thread(
        profile_path=profile.profile_path,
        start_url=start_url,
        browser_type=profile.browser_type,
    )
    return RedirectResponse(url="/profiles", status_code=303)
