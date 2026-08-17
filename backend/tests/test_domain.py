from app.domain import DocumentPolicy, EvidenceStatus, ExtractionResult, PolicyOutcome, can_transition, evaluate_policy


def test_policy_routes_low_confidence_document_to_review():
    policy = DocumentPolicy("insurance_certificate", 0.75, 365)
    result = ExtractionResult("insurance policy", 0.8, "insurance_certificate", 0.62, {"insurance": 1.0})
    outcome, findings = evaluate_policy(result, policy, 120)
    assert outcome == PolicyOutcome.REVIEW
    assert "Classification confidence is below the policy threshold" in findings


def test_expired_document_fails_policy():
    policy = DocumentPolicy("tax_certificate", 0.65, 365)
    result = ExtractionResult("tax registration", 0.8, "tax_certificate", 0.9, {"tax": 1.0})
    outcome, findings = evaluate_policy(result, policy, -1)
    assert outcome == PolicyOutcome.FAIL
    assert "Document has expired" in findings


def test_evidence_state_transitions_are_guarded():
    assert can_transition(EvidenceStatus.REVIEW, EvidenceStatus.ACCEPTED)
    assert not can_transition(EvidenceStatus.ACCEPTED, EvidenceStatus.REVIEW)
