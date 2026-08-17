from __future__ import annotations

import json
import os
from datetime import date
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .domain import DocumentPolicy, EvidenceStatus, Role, can_transition, evaluate_policy
from .ml import extract_document
from .repository import Repository

repository = Repository(os.getenv("DATABASE_PATH", "./data/evidence.db"))
app = FastAPI(title="Supplier Document Intelligence API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

POLICIES = {
    "insurance_certificate": DocumentPolicy("insurance_certificate", 0.65, 365),
    "tax_certificate": DocumentPolicy("tax_certificate", 0.7, 365),
    "sanctions_screening": DocumentPolicy("sanctions_screening", 0.8, 180),
    "quality_certificate": DocumentPolicy("quality_certificate", 0.65, 1095),
}


def actor(x_role: Annotated[str, Header(alias="X-Role")] = "analyst", x_actor: Annotated[str, Header(alias="X-Actor")] = "local-analyst") -> tuple[Role, str]:
    try: return Role(x_role), x_actor
    except ValueError: raise HTTPException(status_code=403, detail="Unknown role")


def require(*allowed: Role):
    def guard(identity: tuple[Role, str] = Depends(actor)) -> tuple[Role, str]:
        if identity[0] not in allowed: raise HTTPException(status_code=403, detail="Role is not authorized for this operation")
        return identity
    return guard


class SupplierCreate(BaseModel): name: str = Field(min_length=2, max_length=180)
class ReviewDecision(BaseModel): decision: EvidenceStatus; note: str = Field(min_length=3, max_length=500)


@app.get("/health")
def health() -> dict[str, str]: return {"status": "ok"}


@app.post("/suppliers", status_code=201)
def create_supplier(payload: SupplierCreate, identity: tuple[Role, str] = Depends(require(Role.ADMIN, Role.ANALYST))):
    supplier = repository.create_supplier(payload.name); repository.audit(identity[1], "supplier", supplier["id"], "created", f"Created supplier {supplier['name']}"); return supplier


@app.get("/evidence")
def list_evidence(supplier_id: int | None = None, identity: tuple[Role, str] = Depends(require(Role.ADMIN, Role.ANALYST, Role.REVIEWER))): return repository.list_evidence(supplier_id)


@app.post("/evidence", status_code=201)
async def upload_evidence(supplier_id: Annotated[int, Form()], document_type: Annotated[str, Form()], expires_on: Annotated[str | None, Form()] = None, hint_text: Annotated[str, Form()] = "", file: UploadFile = File(...), identity: tuple[Role, str] = Depends(require(Role.ADMIN, Role.ANALYST))):
    if document_type not in POLICIES: raise HTTPException(status_code=422, detail="Unsupported document policy")
    if not repository.supplier(supplier_id): raise HTTPException(status_code=404, detail="Supplier not found")
    if not file.filename or not file.filename.lower().endswith((".png", ".jpg", ".jpeg", ".pdf")): raise HTTPException(status_code=422, detail="Only PDF and image evidence files are supported")
    content = await file.read()
    if len(content) > 10_000_000: raise HTTPException(status_code=413, detail="Evidence file exceeds the 10 MB safety limit")
    evidence = repository.create_evidence({"supplier_id": supplier_id, "filename": file.filename, "document_type": document_type, "status": EvidenceStatus.UPLOADED, "created_by": identity[1], "days_until_expiry": None})
    repository.audit(identity[1], "evidence", evidence["id"], "uploaded", f"Uploaded {file.filename}")
    repository.update_evidence(evidence["id"], {"status": EvidenceStatus.PROCESSING})
    result = extract_document(content, file.filename, hint_text)
    days = (date.fromisoformat(expires_on) - date.today()).days if expires_on else None
    outcome, findings = evaluate_policy(result, POLICIES[document_type], days)
    evidence = repository.update_evidence(evidence["id"], {"status": EvidenceStatus.REVIEW, "policy_outcome": outcome, "quality_score": result.quality_score, "confidence": result.confidence, "extracted_text": result.text, "explanation_json": json.dumps(result.explanation), "findings_json": json.dumps(findings), "days_until_expiry": days})
    repository.audit(identity[1], "evidence", evidence["id"], "processed", f"Classified as {result.classification} with {result.confidence:.0%} confidence")
    return evidence


@app.post("/evidence/{evidence_id}/review")
def review_evidence(evidence_id: int, payload: ReviewDecision, identity: tuple[Role, str] = Depends(require(Role.ADMIN, Role.REVIEWER))):
    evidence = repository.evidence(evidence_id)
    if not evidence: raise HTTPException(status_code=404, detail="Evidence not found")
    if payload.decision not in (EvidenceStatus.ACCEPTED, EvidenceStatus.CORRECTION_REQUESTED, EvidenceStatus.REJECTED): raise HTTPException(status_code=422, detail="Invalid review decision")
    if not can_transition(EvidenceStatus(evidence["status"]), payload.decision): raise HTTPException(status_code=409, detail="Evidence cannot transition from its current state")
    updated = repository.update_evidence(evidence_id, {"status": payload.decision})
    repository.audit(identity[1], "evidence", evidence_id, payload.decision, payload.note)
    return updated


@app.get("/audit")
def audit(entity_type: str | None = None, entity_id: str | None = None, identity: tuple[Role, str] = Depends(require(Role.ADMIN, Role.REVIEWER))): return repository.list_audit(entity_type, entity_id)


@app.websocket("/ws/evidence/{evidence_id}")
async def evidence_status(websocket: WebSocket, evidence_id: int):
    await websocket.accept(); evidence = repository.evidence(evidence_id)
    await websocket.send_json({"evidence_id": evidence_id, "status": evidence["status"] if evidence else "not_found"}); await websocket.close()
