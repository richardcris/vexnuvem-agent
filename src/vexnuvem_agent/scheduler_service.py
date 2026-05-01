from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone, tzinfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from PySide6.QtCore import QObject, Signal

from .models import AppConfig, ScheduleConfig


class SchedulerService(QObject):
    backup_requested = Signal(str)
    next_run_changed = Signal(str)

    def __init__(self, logger) -> None:
        super().__init__()
        self.logger = logger
        self.local_timezone = self._detect_local_timezone()
        self.scheduler = BackgroundScheduler(daemon=True, timezone=self.local_timezone)
        self.scheduler.start()

    def apply_config(self, config: AppConfig) -> None:
        self.scheduler.remove_all_jobs()

        if not config.schedule.enabled:
            self.next_run_changed.emit("Agendamento desativado")
            return

        trigger = self._build_trigger(config.schedule)
        self.scheduler.add_job(
            self._emit_backup_request,
            trigger=trigger,
            id="backup_job",
            max_instances=1,
            replace_existing=True,
            coalesce=True,
            misfire_grace_time=300,
        )
        self.next_run_changed.emit(self.describe_next_run())

    def describe_next_run(self) -> str:
        job = self.scheduler.get_job("backup_job")
        if not job or not job.next_run_time:
            return "Sem proxima execucao"
        next_run = job.next_run_time.astimezone()
        return next_run.strftime("%d/%m/%Y %H:%M")

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def should_run_startup_backup(self, config: AppConfig, reference_time: datetime | None = None) -> bool:
        if not config.schedule.enabled:
            return False

        now = reference_time.astimezone(self.local_timezone) if reference_time else datetime.now(self.local_timezone)
        last_backup_at = self._parse_last_backup_at(config.last_backup_at)
        schedule = config.schedule

        if schedule.mode == "interval":
            if last_backup_at is None:
                return True
            due_at = last_backup_at + timedelta(hours=max(schedule.interval_hours, 1))
            return now >= due_at

        due_at = self._scheduled_datetime_for_day(now.date(), schedule)
        if due_at is None or now < due_at:
            return False
        if last_backup_at is None:
            return True
        return last_backup_at < due_at

    def _emit_backup_request(self) -> None:
        self.logger.info("Disparando backup automatico via scheduler")
        self.backup_requested.emit("automatic")

    def _build_trigger(self, schedule: ScheduleConfig):
        hour, minute = self._parse_time(schedule.time_of_day)
        if schedule.mode == "interval":
            return IntervalTrigger(hours=max(schedule.interval_hours, 1), timezone=self.local_timezone)
        if schedule.mode == "weekdays":
            weekdays = ",".join(schedule.weekdays or ["mon"])
            return CronTrigger(day_of_week=weekdays, hour=hour, minute=minute, timezone=self.local_timezone)
        return CronTrigger(hour=hour, minute=minute, timezone=self.local_timezone)

    @staticmethod
    def _detect_local_timezone() -> tzinfo:
        return datetime.now().astimezone().tzinfo or timezone.utc

    @staticmethod
    def _parse_time(time_of_day: str) -> tuple[int, int]:
        try:
            parsed = datetime.strptime(time_of_day, "%H:%M")
            return parsed.hour, parsed.minute
        except ValueError:
            return 22, 0

    def _scheduled_datetime_for_day(self, target_day: date, schedule: ScheduleConfig) -> datetime | None:
        if schedule.mode == "weekdays":
            weekday_key = target_day.strftime("%a").lower()[:3]
            if weekday_key not in set(schedule.weekdays or []):
                return None

        hour, minute = self._parse_time(schedule.time_of_day)
        local_dt = datetime.combine(target_day, time(hour=hour, minute=minute))
        return local_dt.replace(tzinfo=self.local_timezone)

    def _parse_last_backup_at(self, raw_value: str | None) -> datetime | None:
        if not raw_value:
            return None
        try:
            parsed = datetime.fromisoformat(raw_value)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=self.local_timezone)
        return parsed.astimezone(self.local_timezone)
