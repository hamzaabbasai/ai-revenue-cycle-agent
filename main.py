import os
from pathlib import Path

import gradio as gr
import uvicorn
from fastapi import FastAPI, Query
from google.adk.cli.fast_api import get_fast_api_app

from gradio_app import build_interface
from rcm_agent.memory import memory_store
from rcm_agent.models import PipelineRequest, PipelineResponse
from runtime import run_structured_claim


BASE_DIR = Path(__file__).resolve().parent
SESSION_URI = os.getenv(
    "SESSION_SERVICE_URI",
    "sqlite+aiosqlite:///./sessions.db",
)
WEB_UI = os.getenv("SERVE_WEB_INTERFACE", "true").lower() == "true"
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:8000,http://127.0.0.1:8000",
    ).split(",")
    if origin.strip()
]

app: FastAPI = get_fast_api_app(
    agents_dir=str(BASE_DIR),
    session_service_uri=SESSION_URI,
    allow_origins=ALLOWED_ORIGINS,
    web=WEB_UI,
)


@app.get("/healthz")
async def health() -> dict[str, str]:
    return {"status": "ok", "agent": "rcm_agent"}


@app.post("/a2a/rcm", response_model=PipelineResponse)
async def run_rcm_claim(
    request: PipelineRequest,
) -> PipelineResponse:
    """Compatibility endpoint for structured systems and older clients."""
    return await run_structured_claim(
        patient_id=request.patient_id,
        insurance_number=request.insurance_number,
        visit_reason=request.visit_reason,
        session_id=request.session_id,
        user_id=request.user_id,
    )


@app.get("/memory")
async def recent_memory(limit: int = Query(default=10, ge=1, le=100)):
    return memory_store.recent(limit)


app = gr.mount_gradio_app(app, build_interface(), path="/ui")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
