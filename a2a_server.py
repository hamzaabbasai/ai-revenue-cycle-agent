import os

import uvicorn
from google.adk.a2a.utils.agent_to_a2a import to_a2a

from rcm_agent.agent import root_agent


PORT = int(os.getenv("PORT", "8001"))
app = to_a2a(root_agent, port=PORT)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

