import os
from uuid import uuid4

from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types

from rcm_agent.agent import root_agent
from rcm_agent.models import ClaimResult, PipelineResponse


APP_NAME = "rcm_agent"
SESSION_DB_URL = os.getenv(
    "RUNTIME_SESSION_DB_URL",
    "sqlite+aiosqlite:///./sessions.db",
)
session_service = DatabaseSessionService(db_url=SESSION_DB_URL)
runner = Runner(
    agent=root_agent,
    app_name=APP_NAME,
    session_service=session_service,
)


async def run_structured_claim(
    patient_id: str,
    insurance_number: str,
    visit_reason: str,
    session_id: str | None = None,
    user_id: str = "api_user",
) -> PipelineResponse:
    active_session_id = session_id or uuid4().hex
    session = await session_service.get_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=active_session_id,
    )
    if session is None:
        await session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=active_session_id,
        )

    message = (
        f"Patient ID: {patient_id}\n"
        f"Insurance number: {insurance_number}\n"
        f"Visit reason: {visit_reason}"
    )
    content = types.Content(role="user", parts=[types.Part(text=message)])
    final_text = ""

    events = runner.run_async(
        user_id=user_id,
        session_id=active_session_id,
        new_message=content,
    )
    async for event in events:
        if event.is_final_response() and event.content and event.content.parts:
            final_text = event.content.parts[0].text or ""

    result = ClaimResult.model_validate_json(final_text)
    return PipelineResponse(session_id=active_session_id, result=result)
