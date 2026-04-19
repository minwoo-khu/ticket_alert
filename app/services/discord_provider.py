from __future__ import annotations

from dataclasses import dataclass
import json
from urllib import error, request


@dataclass
class NotificationResult:
    success: bool
    status_code: int | None
    response_text: str


class DiscordWebhookProvider:
    def __init__(self, webhook_url: str, username: str = "", avatar_url: str = "") -> None:
        self.webhook_url = webhook_url
        self.username = username
        self.avatar_url = avatar_url

    def send(self, content: str) -> NotificationResult:
        if not self.webhook_url:
            return NotificationResult(
                success=False,
                status_code=None,
                response_text="Discord webhook URL is not configured.",
            )

        payload = {"content": content}
        if self.username:
            payload["username"] = self.username
        if self.avatar_url:
            payload["avatar_url"] = self.avatar_url

        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            self.webhook_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=15) as response:
                response_body = response.read().decode("utf-8", errors="ignore")
                return NotificationResult(
                    success=200 <= response.status < 300,
                    status_code=response.status,
                    response_text=response_body,
                )
        except error.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="ignore")
            return NotificationResult(
                success=False,
                status_code=exc.code,
                response_text=response_body,
            )
        except Exception as exc:  # pragma: no cover - network behavior is environment-dependent
            return NotificationResult(
                success=False,
                status_code=None,
                response_text=str(exc),
            )

