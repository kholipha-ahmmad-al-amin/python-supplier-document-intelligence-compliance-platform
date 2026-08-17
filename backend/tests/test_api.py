import os
from pathlib import Path

os.environ["DATABASE_PATH"] = str(Path("/tmp/document-intelligence-test.db"))
Path(os.environ["DATABASE_PATH"]).unlink(missing_ok=True)

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
HEADERS = {"X-Role": "admin", "X-Actor": "test-admin"}


def test_supplier_upload_and_review_audit_loop():
    supplier = client.post("/suppliers", json={"name": "Northstar Industrial"}, headers=HEADERS)
    assert supplier.status_code == 201
    evidence = client.post("/evidence", headers=HEADERS, data={"supplier_id": supplier.json()["id"], "document_type": "insurance_certificate", "hint_text": "insurance policy coverage insurer", "expires_on": "2030-01-01"}, files={"file": ("certificate.png", b"image-bytes", "image/png")})
    assert evidence.status_code == 201
    assert evidence.json()["status"] == "review"
    review = client.post(f"/evidence/{evidence.json()['id']}/review", headers={"X-Role": "reviewer", "X-Actor": "test-reviewer"}, json={"decision": "accepted", "note": "Verified against policy"})
    assert review.status_code == 200
    assert review.json()["status"] == "accepted"
    audit = client.get("/audit?entity_type=evidence&entity_id=" + str(evidence.json()["id"]), headers={"X-Role": "admin"})
    assert audit.status_code == 200
    assert len(audit.json()) >= 3


def test_analyst_cannot_review_evidence():
    response = client.post("/evidence/999/review", headers={"X-Role": "analyst"}, json={"decision": "accepted", "note": "Not allowed"})
    assert response.status_code == 403
