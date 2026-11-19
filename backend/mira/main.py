"""FastAPI entrypoint. The AG-UI / CopilotKit endpoint is mounted here."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mira.config import get_settings

app = FastAPI(title="Mira API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    s = get_settings()
    return {"status": "ok", "today": s.mira_today.isoformat()}


# TODO: mount the LangGraph agent over AG-UI (ag-ui-langgraph) at /agent
# TODO: staff routes (/staff/enquiries, /staff/drafts) behind role checks
