import asyncio

from rcm_agent.core import (
    audit_claim,
    build_fallback_result,
    compact_context,
    heuristic_coding,
    parse_claim_fallback,
    prepare_coding_retry,
    submit_claim,
    validate_codes,
    verify_insurance,
)
from rcm_agent.models import ClaimRequest, CodedClaim


def make_request(insurance_number: str = "AET123") -> ClaimRequest:
    return ClaimRequest(
        patient_id="P001",
        insurance_number=insurance_number,
        visit_reason="Type 2 diabetes and high blood pressure",
    )


def test_valid_claim_is_submitted() -> None:
    verified = verify_insurance(make_request())
    coded = heuristic_coding(verified)
    decision = asyncio.run(submit_claim(validate_codes(coded)))
    audited = audit_claim(decision)

    assert decision.status == "Submitted"
    assert decision.claim_id is not None
    assert audited.issue_score == 0
    assert audited.retry_needed is False


def test_invalid_insurance_is_rejected() -> None:
    verified = verify_insurance(make_request("XYZ999"))
    coded = heuristic_coding(verified)
    decision = asyncio.run(submit_claim(validate_codes(coded)))
    audited = audit_claim(decision)
    result = build_fallback_result(audited)

    assert decision.status == "Rejected"
    assert result.appeal is not None
    assert "Insurance is not verified" in audited.audit_issues


def test_missing_codes_routes_to_retry() -> None:
    verified = verify_insurance(make_request())
    coded = CodedClaim(
        **verified.model_dump(),
        codes=["NOT-A-CODE"],
        needs_human_review=False,
        coding_source="gemini",
    )
    decision = asyncio.run(submit_claim(validate_codes(coded)))
    audited = audit_claim(decision)
    retry = prepare_coding_retry(audited)

    assert audited.retry_needed is True
    assert retry.retry_count == 1


def test_intake_and_context_fallbacks() -> None:
    claim = parse_claim_fallback(
        "Patient ID: P009\nInsurance number: BLU123\nVisit reason: Fever"
    )
    summary = compact_context(["a" * 300, "b" * 300])

    assert claim.patient_id == "P009"
    assert claim.insurance_number == "BLU123"
    assert claim.visit_reason == "Fever"
    assert len(summary) == 500

