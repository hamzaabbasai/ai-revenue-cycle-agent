import logging
import os

from google.adk import Agent, Context, Workflow
from google.adk.workflow import node

from .core import (
    audit_claim,
    build_fallback_result,
    heuristic_coding,
    parse_claim_fallback,
    prepare_coding_retry,
    submit_claim,
    validate_codes,
    verify_insurance,
)
from .logging_config import configure_logging
from .memory import memory_store
from .models import AuditedClaim, ClaimRequest, ClaimResult, CodedClaim, VerifiedClaim


configure_logging()
logger = logging.getLogger("rcm.workflow")
MODEL = os.getenv("MODEL_NAME", "gemini-2.5-flash")


intake_agent = Agent(
    name="intake_agent",
    model=MODEL,
    instruction=(
        "Read the user's claim details. Return the patient ID, insurance number, "
        "and visit reason. Copy any history and retry count. Do not add missing facts."
    ),
    output_schema=ClaimRequest,
)


coding_agent = Agent(
    name="coding_agent",
    model=MODEL,
    input_schema=VerifiedClaim,
    instruction=(
        "Suggest diagnosis codes for this claim and copy every input field. "
        "Use only E11.9 for type 2 diabetes, I10 for high blood pressure, J10.1 for "
        "flu with breathing symptoms, R50.9 for fever, or R69 when the reason is not "
        "clear. Set coding_source to gemini. Mark unclear results for human review."
    ),
    output_schema=CodedClaim,
)


appeal_agent = Agent(
    name="appeal_agent",
    model=MODEL,
    input_schema=AuditedClaim,
    instruction=(
        "Create the final result and copy every input field. Write a short appeal only "
        "when the status is Rejected. Use only the given facts. For other status values, "
        "set appeal to null. Add a short summary and a compact context summary."
    ),
    output_schema=ClaimResult,
)


@node(name="verify_insurance")
def verify_insurance_node(claim: ClaimRequest) -> VerifiedClaim:
    return verify_insurance(claim)


@node(name="heuristic_coding")
def heuristic_coding_node(claim: VerifiedClaim) -> CodedClaim:
    return heuristic_coding(claim)


@node(name="validate_codes")
def validate_codes_node(claim: CodedClaim) -> CodedClaim:
    return validate_codes(claim)


@node(name="submit_claim")
async def submit_claim_node(claim: CodedClaim):
    return await submit_claim(claim)


@node(name="audit_claim")
def audit_claim_node(claim):
    return audit_claim(claim)


@node(name="prepare_coding_retry")
def prepare_coding_retry_node(claim: AuditedClaim) -> VerifiedClaim:
    return prepare_coding_retry(claim)


@node(name="store_memory")
def store_memory_node(result: ClaimResult) -> ClaimResult:
    memory_id = memory_store.save(result)
    return result.model_copy(update={"memory_id": memory_id})


@node(name="rcm_pipeline", rerun_on_resume=True)
async def rcm_pipeline(ctx: Context, user_request: str) -> ClaimResult:
    try:
        claim = await ctx.run_node(intake_agent, user_request)
    except Exception:
        logger.exception("Intake model failed; using fallback", extra={"step": "intake"})
        claim = parse_claim_fallback(user_request)

    verified = await ctx.run_node(verify_insurance_node, claim)

    while True:
        try:
            coded = await ctx.run_node(coding_agent, verified)
        except Exception:
            logger.exception("Coding model failed; using fallback", extra={"step": "coding"})
            coded = await ctx.run_node(heuristic_coding_node, verified)

        checked = await ctx.run_node(validate_codes_node, coded)
        decision = await ctx.run_node(submit_claim_node, checked)
        audited = await ctx.run_node(audit_claim_node, decision)
        logger.info(
            "Claim audit completed",
            extra={
                "step": "audit",
                "status": audited.status,
                "retry_count": audited.retry_count,
                "issue_score": audited.issue_score,
            },
        )

        if not audited.retry_needed:
            break
        verified = await ctx.run_node(prepare_coding_retry_node, audited)

    try:
        result = await ctx.run_node(appeal_agent, audited)
    except Exception:
        logger.exception("Appeal model failed; using template", extra={"step": "appeal"})
        result = build_fallback_result(audited)

    return await ctx.run_node(store_memory_node, result)


root_agent = Workflow(
    name="rcm_agent",
    description="Reduces claim errors by handling intake, coding, audit, retry, and appeal.",
    edges=[("START", rcm_pipeline)],
)
