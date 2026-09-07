"""Submission quarantine + rate limiting."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class QuarantineRecord:
    source_key: str
    first_failed_at: float
    last_resubmitted_at: float
    consecutive_failures: int = 0
    cooldown_until: float = 0.0
    reason: str = ""

    def is_quarantined(self, *, now: Optional[float] = None) -> bool:
        now = now if now is not None else time.time()
        return now < self.cooldown_until

    def record_failure(self, *, now: Optional[float] = None, backoff_multiplier: float = 2.0, max_backoff: float = 600.0, max_consecutive: int = 5, reason: str = "") -> Optional[float]:
        now = now if now is not None else time.time()
        self.consecutive_failures += 1
        self.last_resubmitted_at = now
        self.reason = reason
        if self.first_failed_at == 0:
            self.first_failed_at = now
        if self.consecutive_failures >= max_consecutive:
            self.cooldown_until = now + max_backoff
            return self.cooldown_until
        if self.first_failed_at > 0 and (now - self.first_failed_at) < 600:
            self.cooldown_until = now + min(30.0 * (backoff_multiplier ** (self.consecutive_failures - 1)), max_backoff)
            return self.cooldown_until
        return None

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.cooldown_until = 0.0
        self.reason = ""


class SubmissionGateService:
    _records: Dict[str, QuarantineRecord] = {}

    @classmethod
    def _record(cls, source_key: str) -> QuarantineRecord:
        if source_key not in cls._records:
            cls._records[source_key] = QuarantineRecord(source_key=source_key, first_failed_at=0.0, last_resubmitted_at=0.0)
        return cls._records[source_key]

    @classmethod
    def allow_submission(cls, source_key: str, *, now: Optional[float] = None) -> tuple[bool, Optional[str]]:
        record = cls._record(source_key)
        if record.is_quarantined(now=now):
            return False, f"quarantine_active: {record.reason or 'structural_failure'}"
        return True, None

    @classmethod
    def record_failure(cls, source_key: str, *, now: Optional[float] = None, reason: str = "") -> Optional[float]:
        record = cls._record(source_key)
        return record.record_failure(now=now, reason=reason)

    @classmethod
    def record_success(cls, source_key: str) -> None:
        record = cls._record(source_key)
        record.record_success()

    @classmethod
    def reset(cls, source_key: Optional[str] = None) -> None:
        if source_key is None:
            cls._records.clear()
            return
        cls._records.pop(source_key, None)

    @classmethod
    def state(cls) -> Dict[str, Dict[str, Any]]:
        now = time.time()
        return {
            key: {
                "source_key": record.source_key,
                "consecutive_failures": record.consecutive_failures,
                "cooldown_until": record.cooldown_until,
                "remaining_cooldown": max(0.0, record.cooldown_until - now),
                "reason": record.reason,
            }
            for key, record in cls._records.items()
        }
