import asyncio
import os
import re
from uuid import uuid4

from .models import (
    AuditedClaim,
    ClaimDecision,
    ClaimRequest,
    ClaimResult,
    CodedClaim,
    VerifiedClaim,
)


MAX_CODING_RETRIES = 2
ALLOWED_CODES = {"E11.9", "I10", "J10.1", "R50.9", "R69"}
CODE_CATALOG = {
    "E11.9": "Type 2 diabetes without complications",
    "I10": "High blood pressure",
    "J10.1": "Flu with breathing symptoms",
    "R50.9": "Fever, cause not known",
    "R69": "Illness, cause not clear",
}


def add_history(history: list[str], message: str) -> list[str]:
    return [*history, message]


def parse_claim_fallback(text: str) -> ClaimRequest:
    """Read a simple claim message when the intake model is unavailable."""
    fields: dict[str, str] = {}
    patterns = {
        "patient_id": r"patient\s*id\s*:\s*(.+)",
        "insurance_number": r"insurance(?:\s*number)?\s*:\s*(.+)",
        "visit_reason": r"visit\s*reason\s*:\s*(.+)",
    }

    for name, pattern in patterns.items():
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            fields[name] = match.group(1).strip()

    return ClaimRequest(
        patient_id=fields.get("patient_id", "UNKNOWN"),
        insurance_number=fields.get("insurance_number", "UNKNOWN"),
        visit_reason=fields.get("visit_reason", text.strip() or "Unknown visit reason"),
        history=["Intake used the local fallback parser"],
    )


def verify_insurance(claim: ClaimRequest) -> VerifiedClaim:
    """Check an insurance number with a fixed test rule."""
    number = claim.insurance_number.strip().upper()
    verified = number.startswith(("AET", "BLU"))
    return VerifiedClaim(
        **claim.model_dump(exclude={"insurance_number", "history"}),
        insurance_number=number,
        insurance_verified=verified,
        history=add_history(claim.history, f"Insurance verified: {verified}"),
    )


def search_code_catalog(query: str) -> list[dict[str, str]]:
    """Search the diagnosis catalog used by this prototype."""
    words = set(re.findall(r"[a-z0-9]+", query.lower()))
    results = []
    for code, description in CODE_CATALOG.items():
        text = f"{code} {description}".lower()
        if any(word in text for word in words):
            results.append({"code": code, "description": description})
    return results or [{"code": "R69", "description": CODE_CATALOG["R69"]}]


def heuristic_coding(claim: VerifiedClaim) -> CodedClaim:
    """Suggest codes with fixed rules when Gemini is unavailable."""
    text = claim.visit_reason.lower()
    codes: list[str] = []

    if "type 2 diabetes" in text or "diabetes" in text:
        codes.append("E11.9")
    if "hypertension" in text or "high blood pressure" in text:
        codes.append("I10")
    if "flu" in text or "influenza" in text:
        codes.append("J10.1")
    elif "fever" in text:
        codes.append("R50.9")

    needs_review = not codes
    if needs_review:
        codes = ["R69"]

    return CodedClaim(
        **claim.model_dump(exclude={"history"}),
        codes=codes,
        needs_human_review=needs_review,
        coding_source="heuristic",
        history=add_history(claim.history, f"Heuristic coding returned: {codes}"),
    )


def validate_codes(claim: CodedClaim) -> CodedClaim:
    """Remove unsupported codes and mark unclear results for review."""
    original = [code.upper().strip() for code in claim.codes]
    codes = list(dict.fromkeys(code for code in original if code in ALLOWED_CODES))
    removed = [code for code in original if code not in ALLOWED_CODES]
    needs_review = claim.needs_human_review or not codes or "R69" in codes

    message = f"Validated codes: {codes or 'none'}"
    if removed:
        message += f"; removed unsupported codes: {removed}"

    return claim.model_copy(
        update={
            "codes": codes,
            "needs_human_review": needs_review,
            "history": add_history(claim.history, message),
        }
    )


async def submit_claim(claim: CodedClaim) -> ClaimDecision:
    """Simulate a slow external claim service without blocking the server."""
    delay = float(os.getenv("CLAIM_API_DELAY_SECONDS", "0.25"))
    operation_id = f"OP-{uuid4().hex[:10].upper()}"
    await asyncio.sleep(max(0.0, min(delay, 3.0)))

    values = claim.model_dump(exclude={"history"})
    history = add_history(claim.history, f"Claim operation completed: {operation_id}")

    if not claim.insurance_verified:
        return ClaimDecision(
            **values,
            history=history,
            status="Rejected",
            operation_id=operation_id,
            denial_reason="Insurance could not be verified",
        )

    if not claim.codes:
        return ClaimDecision(
            **values,
            history=history,
            status="NeedsReview",
            operation_id=operation_id,
            denial_reason="No valid diagnosis code was found",
        )

    if claim.needs_human_review:
        return ClaimDecision(
            **values,
            history=history,
            status="NeedsReview",
            operation_id=operation_id,
            denial_reason="A coding specialist must review this claim",
        )

    claim_id = f"CLM-{uuid4().hex[:12].upper()}"
    return ClaimDecision(
        **values,
        history=add_history(history, f"Claim submitted: {claim_id}"),
        status="Submitted",
        claim_id=claim_id,
        operation_id=operation_id,
    )


def audit_claim(claim: ClaimDecision) -> AuditedClaim:
    """Evaluate the claim and decide whether coding should run again."""
    issues: list[str] = []

    if not claim.insurance_verified:
        issues.append("Insurance is not verified")
    if not claim.codes:
        issues.append("No diagnosis code was found")
    if claim.needs_human_review:
        issues.append("A human coding review is required")
    if claim.status == "Rejected":
        issues.append("The claim was rejected")

    retry_needed = not claim.codes and claim.retry_count < MAX_CODING_RETRIES
    issue_score = len(issues)
    history = add_history(
        claim.history,
        f"Audit score: {issue_score}; retry needed: {retry_needed}",
    )
    return AuditedClaim(
        **claim.model_dump(exclude={"history"}),
        history=history,
        audit_issues=issues,
        issue_score=issue_score,
        retry_needed=retry_needed,
    )


def prepare_coding_retry(claim: AuditedClaim) -> VerifiedClaim:
    """Prepare the original claim for another coding attempt."""
    retry_count = claim.retry_count + 1
    return VerifiedClaim(
        patient_id=claim.patient_id,
        insurance_number=claim.insurance_number,
        visit_reason=claim.visit_reason,
        insurance_verified=claim.insurance_verified,
        retry_count=retry_count,
        history=add_history(claim.history, f"Starting coding retry {retry_count}"),
    )


def compact_context(history: list[str], max_chars: int = 500) -> str:
    """Keep a short summary of the latest workflow events."""
    return " | ".join(history)[-max_chars:]


def build_fallback_result(claim: AuditedClaim) -> ClaimResult:
    """Build the final answer when the appeal model is unavailable."""
    appeal = None
    if claim.status == "Rejected":
        appeal = (
            "Dear Medical Review Team,\n\n"
            f"Please review the denied claim for patient {claim.patient_id}. "
            f"The recorded denial reason is: {claim.denial_reason or 'Unknown reason'}. "
            f"The submitted diagnosis codes were: {', '.join(claim.codes) or 'None'}.\n\n"
            "Please reconsider the claim using the available visit record.\n\n"
            "Sincerely,\nRCM Billing Team"
        )

    summary = (
        f"Claim status: {claim.status}. Codes: {', '.join(claim.codes) or 'None'}. "
        f"Audit score: {claim.issue_score}."
    )
    return ClaimResult(
        **claim.model_dump(),
        appeal=appeal,
        summary=summary,
        context_summary=compact_context(claim.history),
    )


async def submit_claim_tool(codes: list[str], verified: bool) -> dict[str, object]:
    """Raw-input wrapper used by the MCP server."""
    claim = CodedClaim(
        patient_id="MCP-TEST",
        insurance_number="MCP-TEST",
        visit_reason="MCP tool call",
        insurance_verified=verified,
        codes=codes,
        needs_human_review=not codes,
        coding_source="heuristic",
    )
    return (await submit_claim(validate_codes(claim))).model_dump()
