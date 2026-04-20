from __future__ import annotations

import argparse
import logging
import time

from app.worker_config import WorkerConfig, WorkerMonitorConfig, load_worker_config
from app.worker_runtime import build_provider, default_monitor_state, is_monitor_due, run_monitor_once
from app.worker_state import load_worker_state, save_worker_state


logger = logging.getLogger(__name__)


def configure_worker_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def _select_monitors(config: WorkerConfig, monitor_ids: set[str] | None) -> list[WorkerMonitorConfig]:
    monitors = [monitor for monitor in config.monitors if monitor.enabled]
    if not monitor_ids:
        return monitors
    return [monitor for monitor in monitors if monitor.id in monitor_ids]


def run_cycle(
    *,
    config: WorkerConfig,
    state: dict,
    provider,
    monitor_ids: set[str] | None = None,
    force: bool = False,
) -> bool:
    selected_monitors = _select_monitors(config, monitor_ids)
    if not selected_monitors:
        logger.warning("No enabled monitors matched the current selection.")
        return False

    ran_any = False

    from app.utils.time import now_utc

    now_dt = now_utc()
    for monitor in selected_monitors:
        monitor_state = state.setdefault("monitors", {}).setdefault(
            monitor.id,
            default_monitor_state(),
        )
        if not force and not is_monitor_due(monitor, monitor_state, now_dt):
            continue
        result = run_monitor_once(
            monitor=monitor,
            config=config,
            state=state,
            provider=provider,
        )
        ran_any = True
        if result.status == "success":
            logger.info("Monitor %s success: %s", monitor.id, result.parsed_counts)
        else:
            logger.warning("Monitor %s error: %s", monitor.id, result.error_message)
        save_worker_state(config.state_path, state)

    return ran_any


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ticket alert background worker")
    parser.add_argument("--config", default=None, help="Path to worker.json")
    parser.add_argument("--once", action="store_true", help="Run the selected monitors once and exit")
    parser.add_argument(
        "--monitor",
        action="append",
        dest="monitor_ids",
        help="Run only the given monitor id (can be provided multiple times)",
    )
    args = parser.parse_args()

    configure_worker_logging()
    config = load_worker_config(args.config)
    state = load_worker_state(config.state_path)
    monitor_ids = set(args.monitor_ids or [])
    provider = build_provider(config.discord)

    logger.info(
        "Loaded worker config with %d monitor(s). State file: %s",
        len(config.monitors),
        config.state_path,
    )

    if args.once:
        run_cycle(config=config, state=state, provider=provider, monitor_ids=monitor_ids, force=True)
        save_worker_state(config.state_path, state)
        return

    while True:
        ran_any = run_cycle(
            config=config,
            state=state,
            provider=provider,
            monitor_ids=monitor_ids,
            force=False,
        )
        if not ran_any:
            time.sleep(config.idle_sleep_seconds)


if __name__ == "__main__":
    main()
