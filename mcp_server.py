import contextlib
import os
from collections.abc import AsyncIterator

import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Mount

from rcm_agent.core import search_code_catalog as find_codes
from rcm_agent.core import submit_claim_tool


mcp = FastMCP(
    "rcm-tools",
    stateless_http=True,
    json_response=True,
)


@mcp.tool()
def verify_insurance(insurance_number: str) -> dict[str, object]:
    """Check an insurance number with the test rule."""
    number = insurance_number.strip().upper()
    return {
        "insurance_number": number,
        "verified": number.startswith(("AET", "BLU")),
    }


@mcp.tool()
def search_code_catalog(query: str) -> list[dict[str, str]]:
    """Search the ICD-10 code catalog."""
    return find_codes(query)


@mcp.tool()
async def submit_claim(codes: list[str], verified: bool) -> dict[str, object]:
    """Send a test claim with diagnosis codes."""
    return await submit_claim_tool(codes, verified)


@mcp.tool()
def calculate_issue_score(issues: list[str]) -> dict[str, object]:
    """Count claim issues."""
    return {"issue_score": len(issues), "issues": issues}


@contextlib.asynccontextmanager
async def lifespan(_: Starlette) -> AsyncIterator[None]:
    async with mcp.session_manager.run():
        yield


app = Starlette(
    routes=[Mount("/", app=mcp.streamable_http_app())],
    lifespan=lifespan,
)


if __name__ == "__main__":
    if os.getenv("MCP_TRANSPORT", "stdio") == "http":
        uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8002")))
    else:
        mcp.run(transport="stdio")
