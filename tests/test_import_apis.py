from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ApprovalRecordModel, ClauseChunkModel, ContractModel, PolicyKnowledgeModel


def contract_payload(contract_id: str = "CTR-RAG-001") -> dict:
    return {
        "id": contract_id,
        "type": "procurement",
        "partyAName": "Party A",
        "partyBName": "Party B",
        "currency": "CNY",
        "amountExTax": "500000.00",
        "taxRatePct": "13.00",
        "amountIncTax": "565000.00",
        "signDate": "2026-04-16",
        "effectiveDate": "2026-04-16",
        "endDate": "2027-04-15",
        "performanceSite": "Shanghai",
        "paymentTermsSummary": "Pay within 30 days after acceptance.",
        "businessOwnerDept": "Procurement",
        "riskTier": "MEDIUM",
        "vectorDocId": "doc_ctr_001",
        "notes": "Initial import",
        "chunks": [
            {
                "id": "c001",
                "clauseCode": "PAY",
                "clauseTitle": "Payment Terms",
                "clauseCategory": "Finance",
                "partyFocus": "A",
                "riskFlag": "LOW",
                "sourceSection": "Section 4",
                "textForEmbedding": "Party A pays within 30 days after invoice and acceptance.",
                "relatedAmountField": "amountIncTax",
                "reviewPriority": "P1",
            }
        ],
    }


def test_import_contract_success(client: TestClient, db_session: Session) -> None:
    response = client.post("/api/contracts/import", json=contract_payload())

    assert response.status_code == 200
    assert response.json() == {"contractId": "CTR-RAG-001"}
    assert db_session.get(ContractModel, "CTR-RAG-001") is not None
    chunks = list(db_session.scalars(select(ClauseChunkModel)))
    assert len(chunks) == 1
    assert chunks[0].chunk_id == "c001"


def test_import_contract_conflict(client: TestClient) -> None:
    payload = contract_payload()

    assert client.post("/api/contracts/import", json=payload).status_code == 200
    response = client.post("/api/contracts/import", json=payload)

    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"


def test_import_approval_records_replaces_existing(
    client: TestClient,
    db_session: Session,
) -> None:
    assert client.post("/api/contracts/import", json=contract_payload()).status_code == 200

    first_payload = {
        "records": [
            {
                "id": "AR-001",
                "stepNo": 1,
                "approverRole": "Finance Manager",
                "decision": "APPROVED",
                "decisionTime": "2026-04-16T10:00:00+08:00",
                "commentSummary": "Approved.",
                "linkedPolicyIds": ["POL-TAX-001"],
                "linkedClauseChunkIds": ["c001"],
                "riskItems": [],
                "vectorDocId": "doc_ar_001",
            }
        ]
    }
    second_payload = {
        "records": [
            {
                "id": "AR-002",
                "stepNo": 2,
                "approverRole": "Legal",
                "decision": "CONDITIONAL_APPROVED",
                "commentSummary": "Add invoice exception handling.",
                "linkedPolicyIds": [],
                "linkedClauseChunkIds": ["c001"],
                "riskItems": [
                    {
                        "code": "PAYMENT_TRIGGER",
                        "severity": "MEDIUM",
                        "detail": "Payment trigger needs clearer evidence.",
                        "relatedClauseChunkIds": ["c001"],
                        "relatedPolicyIds": [],
                    }
                ],
            }
        ]
    }

    response = client.post("/api/contracts/CTR-RAG-001/approval-records/import", json=first_payload)
    assert response.status_code == 200
    assert response.json() == {"contractId": "CTR-RAG-001", "importedCount": 1}

    response = client.post(
        "/api/contracts/CTR-RAG-001/approval-records/import",
        json=second_payload,
    )
    assert response.status_code == 200
    records = list(db_session.scalars(select(ApprovalRecordModel)))
    assert len(records) == 1
    assert records[0].approval_record_id == "AR-002"
    assert records[0].risk_items_json[0]["code"] == "PAYMENT_TRIGGER"


def test_import_approval_records_missing_contract(client: TestClient) -> None:
    response = client.post("/api/contracts/MISSING/approval-records/import", json={"records": []})

    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_import_policies_upserts_by_policy_id(client: TestClient, db_session: Session) -> None:
    payload = {
        "policies": [
            {
                "policyId": "POL-FIN-001",
                "policyDomain": "Finance",
                "appliesToContractType": "PROCUREMENT;SERVICE",
                "severity": "HIGH",
                "triggerKeywords": "prepay;payment",
                "controlObjective": "Payment risk",
                "policyTextForEmbedding": "Avoid unsecured full prepayment before acceptance.",
                "requiredEvidence": "payment plan;guarantee",
                "escalationRole": "Finance Lead",
            }
        ]
    }
    updated_payload = {
        "policies": [
            {
                **payload["policies"][0],
                "policyDomain": "Finance Compliance",
                "severity": "MEDIUM",
            }
        ]
    }

    response = client.post("/api/policies/import", json=payload)
    assert response.status_code == 200
    assert response.json()["policyIds"] == ["POL-FIN-001"]

    response = client.post("/api/policies/import", json=updated_payload)
    assert response.status_code == 200
    policies = list(db_session.scalars(select(PolicyKnowledgeModel)))
    assert len(policies) == 1
    assert policies[0].policy_domain == "Finance Compliance"
    assert policies[0].severity == "MEDIUM"
