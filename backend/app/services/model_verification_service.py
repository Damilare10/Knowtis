"""Model verification and CI gating services."""
from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
import traceback
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class VerificationStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class VerificationResult:
    status: VerificationStatus
    check_name: str
    detail: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "check_name": self.check_name,
            "detail": self.detail,
            "metadata": self.metadata,
        }


@dataclass
class PackageVerificationReport:
    overall: VerificationStatus
    results: List[VerificationResult] = field(default_factory=list)
    model_path: str = ""
    approved_at: Optional[str] = None

    def failed_checks(self) -> List[VerificationResult]:
        return [r for r in self.results if r.status == VerificationStatus.FAILED]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall": self.overall.value,
            "model_path": self.model_path,
            "approved_at": self.approved_at,
            "results": [r.to_dict() for r in self.results],
        }


class ModelVerificationService:
    @staticmethod
    def verify_package(model_path: str, *, strict: bool = True) -> PackageVerificationReport:
        if not os.path.isdir(model_path):
            return PackageVerificationReport(
                overall=VerificationStatus.FAILED,
                model_path=model_path,
                results=[VerificationResult(status=VerificationStatus.FAILED, check_name="path_exists", detail=f"Directory not found: {model_path}")],
            )

        results: List[VerificationResult] = []
        root = Path(model_path)

        results.append(ModelVerificationService._check_model_files(root))
        results.append(ModelVerificationService._check_metadata(root))
        results.append(ModelVerificationService._check_loadable(root, strict=strict))
        results.append(ModelVerificationService._check_inference(root, strict=strict))
        results.append(ModelVerificationService._check_label_contract(root))

        failures = [r for r in results if r.status == VerificationStatus.FAILED]
        overall = VerificationStatus.FAILED if failures else VerificationStatus.PASSED
        return PackageVerificationReport(overall=overall, results=results, model_path=model_path)

    @staticmethod
    def _check_model_files(root: Path) -> VerificationResult:
        required = ["model.safetensors", "model.safetensors.index.json", "config.json", "tokenizer.json", "model_metadata.json"]
        missing = [name for name in required if not (root / name).exists()]
        if missing:
            return VerificationResult(status=VerificationStatus.FAILED, check_name="model_files", detail=f"Missing files: {missing}")
        return VerificationResult(status=VerificationStatus.PASSED, check_name="model_files", detail="All required model files present")

    @staticmethod
    def _check_metadata(root: Path) -> VerificationResult:
        metadata_path = root / "model_metadata.json"
        if not metadata_path.exists():
            return VerificationResult(status=VerificationStatus.FAILED, check_name="metadata_exists", detail="model_metadata.json missing")
        try:
            data = json.loads(metadata_path.read_text(encoding="utf-8"))
            missing_keys = {"labels", "cat_to_id", "id_to_cat"} - set(data.keys())
            if missing_keys:
                return VerificationResult(status=VerificationStatus.FAILED, check_name="metadata_schema", detail=f"Missing metadata keys: {missing_keys}")
            if not isinstance(data.get("labels"), list) or not data["labels"]:
                return VerificationResult(status=VerificationStatus.FAILED, check_name="metadata_labels", detail="labels must be a non-empty list")
            return VerificationResult(status=VerificationStatus.PASSED, check_name="metadata_schema", detail="Metadata schema OK", metadata={"labels": data.get("labels")})
        except json.JSONDecodeError as exc:
            return VerificationResult(status=VerificationStatus.FAILED, check_name="metadata_schema", detail=f"Invalid JSON: {exc}")

    @staticmethod
    def _check_loadable(root: Path, *, strict: bool = True) -> VerificationResult:
        try:
            from setfit import SetFitModel
            model = SetFitModel.from_pretrained(str(root))
            if not hasattr(model, "labels") or model.labels is None or len(getattr(model, "labels", [])) == 0:
                return VerificationResult(status=VerificationStatus.FAILED, check_name="model_loadable", detail="Model loaded but labels are empty/missing")
            return VerificationResult(status=VerificationStatus.PASSED, check_name="model_loadable", detail="Model loads successfully", metadata={"labels": list(getattr(model, "labels", []))})
        except Exception as exc:  # pragma: no cover - defensive against import/runtime failures
            msg = f"{exc.__class__.__name__}: {exc}"
            if strict:
                return VerificationResult(status=VerificationStatus.FAILED, check_name="model_loadable", detail=msg)
            return VerificationResult(status=VerificationStatus.SKIPPED, check_name="model_loadable", detail=f"Skipped in non-strict mode: {msg}")

    @staticmethod
    def _check_inference(root: Path, *, strict: bool = True) -> VerificationResult:
        probes = [
            "Assignment 2 due tomorrow by 10:00 AM",
            "Haha that's funny lol",
            "Class cancelled tomorrow morning",
            "Seminar on AI next Friday",
            "Dr. Taiwo shifted our CSC 301 assessment to Thursday morning",
        ]
        try:
            from training.setfit_classifier_service import SetFitClassifierService
            original_path = getattr(SetFitClassifierService, "_model", None)
            original_failed = getattr(SetFitClassifierService, "_load_failed", False)
            model = None
            try:
                from setfit import SetFitModel
                model = SetFitModel.from_pretrained(str(root))
                SetFitClassifierService._model = model
                SetFitClassifierService._load_failed = False
            except Exception:
                if not strict:
                    return VerificationResult(status=VerificationStatus.SKIPPED, check_name="inference_smoke", detail="Model not loadable; skipped in non-strict mode")
                raise

            failures: List[str] = []
            for text in probes:
                prediction = SetFitClassifierService.classify(text)
                if prediction is None:
                    failures.append(f"no prediction for: {text!r}")
                    continue
                if prediction.confidence <= 0:
                    failures.append(f"zero confidence for: {text!r}")

            if failures:
                return VerificationResult(status=VerificationStatus.FAILED, check_name="inference_smoke", detail="; ".join(failures[:5]))

            return VerificationResult(status=VerificationStatus.PASSED, check_name="inference_smoke", detail=f"All {len(probes)} probe inputs produced non-zero predictions")
        except Exception as exc:
            msg = f"{exc.__class__.__name__}: {exc}"
            detail = f"{msg}\n{traceback.format_exc()}"
            if strict:
                return VerificationResult(status=VerificationStatus.FAILED, check_name="inference_smoke", detail=detail)
            return VerificationResult(status=VerificationStatus.SKIPPED, check_name="inference_smoke", detail=f"Skipped in non-strict mode: {msg}")
        finally:
            if model is not None:
                SetFitClassifierService._model = original_path
                SetFitClassifierService._load_failed = original_failed

    @staticmethod
    def _check_label_contract(root: Path) -> VerificationResult:
        try:
            metadata = json.loads((root / "model_metadata.json").read_text(encoding="utf-8"))
        except Exception as exc:
            return VerificationResult(status=VerificationStatus.FAILED, check_name="label_contract", detail=f"Cannot read metadata: {exc}")
        allowed = {"noise", "assignment_deadline", "exam", "lecture_update", "event", "fee_notice", "general_announcement"}
        unexpected = sorted(set(metadata.get("labels", [])) - allowed)
        if unexpected:
            return VerificationResult(status=VerificationStatus.FAILED, check_name="label_contract", detail=f"Unexpected labels: {unexpected}")
        return VerificationResult(status=VerificationStatus.PASSED, check_name="label_contract", detail="Labels match expected production contract")
