from rcm_agent.memory import ClaimMemoryStore
from rcm_agent.models import ClaimResult


def test_claim_memory_round_trip(tmp_path) -> None:
    store = ClaimMemoryStore(str(tmp_path / "memory.db"))
    result = ClaimResult(
        patient_id="P001",
        insurance_number="AET123",
        visit_reason="Type 2 diabetes",
        insurance_verified=True,
        codes=["E11.9"],
        coding_source="heuristic",
        status="Submitted",
        claim_id="CLM-1",
        operation_id="OP-1",
        audit_issues=[],
        issue_score=0,
        retry_needed=False,
        summary="Claim submitted",
        history=["Intake", "Submitted"],
    )

    memory_id = store.save(result)
    records = store.recent(1)

    assert memory_id.startswith("MEM-")
    assert records[0]["claim_id"] == "CLM-1"
    assert records[0]["status"] == "Submitted"

