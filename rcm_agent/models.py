from typing import Literal

from pydantic import BaseModel, Field


class ClaimRequest(BaseModel):
    patient_id: str = Field(min_length=1, max_length=40)
    insurance_number: str = Field(min_length=3, max_length=40)
    visit_reason: str = Field(min_length=3, max_length=1000)
    history: list[str] = Field(default_factory=list)
    retry_count: int = Field(default=0, ge=0, le=3)


class VerifiedClaim(ClaimRequest):
    insurance_verified: bool


class CodedClaim(VerifiedClaim):
    codes: list[str] = Field(default_factory=list)
    needs_human_review: bool = False
    coding_source: Literal["gemini", "heuristic"] = "gemini"


class ClaimDecision(CodedClaim):
    status: Literal["Submitted", "Rejected", "NeedsReview"]
    claim_id: str | None = None
    operation_id: str | None = None
    denial_reason: str | None = None


class AuditedClaim(ClaimDecision):
    audit_issues: list[str] = Field(default_factory=list)
    issue_score: int = Field(default=0, ge=0)
    retry_needed: bool = False


class ClaimResult(AuditedClaim):
    appeal: str | None = None
    summary: str
    context_summary: str = ""
    memory_id: str | None = None


class PipelineResponse(BaseModel):
    session_id: str
    result: ClaimResult


class PipelineRequest(BaseModel):
    patient_id: str = Field(min_length=1, max_length=40)
    insurance_number: str = Field(min_length=3, max_length=40)
    visit_reason: str = Field(min_length=3, max_length=1000)
    session_id: str | None = None
    user_id: str = "api_user"
