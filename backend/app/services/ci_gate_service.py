"""CI gating service — blocks submissions on verification failure."""
from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import tempfile
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from app.services.model_verification_service import PackageVerificationReport, VerificationResult
from app.services.submission_gate_service import SubmissionGateService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CiGateResult:
    blocked: bool
    quarantine_source: Optional[str]
    reason: str
    report: Optional[PackageVerificationReport] = None

    def to_dict(self) -> dict:
        return {
            "blocked": self.blocked,
            "quarantine_source": self.quarantine_source,
            "reason": self.reason,
            "report": self.report.to_dict() if self.report else None,
        }


class CiGateService:
    @staticmethod
    def block_if_invalid(model_path: str, *, source_key: str = "default", strict: bool = True) -> CiGateResult:
        allowed, reason = SubmissionGateService.allow_submission(source_key)
        if not allowed:
            return CiGateResult(blocked=True, quarantine_source=source_key, reason=reason)
        report = None
        try:
            report = _run_internal_ci(model_path, strict=strict)
        except Exception as exc:
            detail = "".join(traceback.format_exception_only(type(exc), exc)).strip()
            SubmissionGateService.record_failure(source_key, reason=f"ci_failed: {detail}")
            return CiGateResult(blocked=True, quarantine_source=source_key, reason=f"ci_failed: {detail}")
        if report.overall.value != "passed":
            SubmissionGateService.record_failure(source_key, reason=report.failed_checks()[0].detail if report.failed_checks() else "verification_failed")
            return CiGateResult(blocked=True, quarantine_source=source_key, reason=f"verification_failed: {report.failed_checks()[0].detail}", report=report)
        SubmissionGateService.record_success(source_key)
        return CiGateResult(blocked=False, quarantine_source=None, reason="verification_passed", report=report)


def _run_internal_ci(model_path: str, *, strict: bool = True) -> PackageVerificationReport:
    model_dir = Path(model_path).expanduser().resolve()
    if not model_dir.exists():
        raise FileNotFoundError(f"model_path does not exist: {model_dir}")
    return _verify_model_package(str(model_dir), strict=strict)


def _verify_model_package(model_path: str, *, strict: bool = True) -> PackageVerificationReport:
    from app.services.model_verification_service import ModelVerificationService
    return ModelVerificationService.verify_package(model_path, strict=strict)
