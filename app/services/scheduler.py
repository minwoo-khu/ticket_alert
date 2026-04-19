from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from app.config import Settings
from app.db import session_scope
from app.models import Monitor
from app.services.monitor_runner import MonitorRunner


class SchedulerService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.runner = MonitorRunner(settings)
        self.scheduler = BackgroundScheduler(timezone=settings.timezone)
        self.started = False

    def start(self) -> None:
        if self.started:
            return

        self.scheduler.add_job(
            self.sync_monitors,
            trigger=IntervalTrigger(seconds=self.settings.scheduler_sync_seconds),
            id="sync-monitors",
            replace_existing=True,
            max_instances=1,
        )
        self.scheduler.start()
        self.sync_monitors()
        self.started = True

    def shutdown(self) -> None:
        if not self.started:
            return
        self.scheduler.shutdown(wait=False)
        self.started = False

    def run_monitor_now(self, monitor_id: int):
        return self.runner.run_monitor(monitor_id, force=True)

    def sync_monitors(self) -> None:
        if not self.scheduler.running:
            return

        enabled_job_ids: set[str] = set()

        with session_scope() as session:
            monitors = list(session.execute(select(Monitor)).scalars())

        for monitor in monitors:
            job_id = self._job_id(monitor.id)
            if not monitor.enabled:
                if self.scheduler.get_job(job_id):
                    self.scheduler.remove_job(job_id)
                continue

            enabled_job_ids.add(job_id)
            self.scheduler.add_job(
                self.runner.run_monitor,
                trigger=IntervalTrigger(seconds=max(15, monitor.poll_interval_seconds)),
                kwargs={"monitor_id": monitor.id},
                id=job_id,
                replace_existing=True,
                coalesce=True,
                max_instances=1,
                misfire_grace_time=max(30, monitor.poll_interval_seconds),
            )

        for job in self.scheduler.get_jobs():
            if job.id.startswith("monitor-") and job.id not in enabled_job_ids:
                self.scheduler.remove_job(job.id)

    @staticmethod
    def _job_id(monitor_id: int) -> str:
        return f"monitor-{monitor_id}"

