from __future__ import annotations

from pathlib import Path


def prune_monitor_screenshots(monitor_id: int, screenshot_dir: str | Path, keep: int) -> None:
    directory = Path(screenshot_dir)
    if keep <= 0 or not directory.exists():
        return

    files = sorted(
        directory.glob(f"monitor_{monitor_id}_*.png"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    for stale in files[keep:]:
        stale.unlink(missing_ok=True)

