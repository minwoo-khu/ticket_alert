from __future__ import annotations

import json

from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR, get_settings
from app.utils.time import format_local


templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))
templates.env.filters["datetime_local"] = lambda value: format_local(value, get_settings().timezone)
templates.env.filters["json_pretty"] = lambda value: json.dumps(value, ensure_ascii=False, indent=2)

