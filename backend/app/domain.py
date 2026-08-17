from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable


class Role(StrEnum):
    ADMIN = "admin"
    ANALYST = "analyst"
    REVIEWER = "reviewer"


class EvidenceStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    REVIEW = "review"
    ACCEPTED = "accepted"
    CORRECTION_REQUESTED = "correction_requested"
    REJECTED = "rejected"


class PolicyOutcome(StrEnum):
    PASS = "pass"
    REVIEW = "review"
    FAIL = "fail"


@dataclass(frozen=True)
class DocumentPolicy:
    document_type: str
    minimum_confidence: float
    maximum_age_days: int
    required: bool = True


@dataclass(frozen=True)
class ExtractionResult:
    text: str
    quality_score: float
    classification: str
    confidence: float
    explanation: dict[str, float]


def evaluate_policy(result: ExtractionResult, policy: DocumentPolicy, days_until_expiry: int | None) -> tuple[PolicyOutcome, list[str]]:
    findings: list[str] = []
    if result.quality_score < 0.45:
        findings.append("Image quality is below the review threshold")
    if result.confidence < policy.minimum_confidence:
        findings.append("Classification confidence is below the policy threshold")
    if result.classification != policy.document_type:
        findings.append("Document classification does not match the required policy")
    if days_until_expiry is not None and days_until_expiry < 0:
        findings.append("Document has expired")
    if days_until_expiry is not None and days_until_expiry <= 30:
        findings.append("Document expiry is within 30 days")
    if any("expired" in finding or "does not match" in finding for finding in findings):
        return PolicyOutcome.FAIL, findings
    if findings:
        return PolicyOutcome.REVIEW, findings
    return PolicyOutcome.PASS, findings


def can_transition(current: EvidenceStatus, next_status: EvidenceStatus) -> bool:
    paths: dict[EvidenceStatus, set[EvidenceStatus]] = {
        EvidenceStatus.UPLOADED: {EvidenceStatus.PROCESSING},
        EvidenceStatus.PROCESSING: {EvidenceStatus.REVIEW},
        EvidenceStatus.REVIEW: {EvidenceStatus.ACCEPTED, EvidenceStatus.CORRECTION_REQUESTED, EvidenceStatus.REJECTED},
        EvidenceStatus.CORRECTION_REQUESTED: {EvidenceStatus.UPLOADED},
        EvidenceStatus.ACCEPTED: set(),
        EvidenceStatus.REJECTED: set(),
    }
    return next_status in paths[current]


def validate_policy_weights(weights: Iterable[float]) -> None:
    items = list(weights)
    if not items or any(weight <= 0 for weight in items):
        raise ValueError("Policy weights must be positive")
    if abs(sum(items) - 1) > 0.0001:
        raise ValueError("Policy weights must sum to 1")
