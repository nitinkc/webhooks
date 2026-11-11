"""FastAPI entrypoint — mounts the webhook routers.

Run:  uv run uvicorn app.main:app --reload
Docs: http://localhost:8000/docs
"""

import logging

from fastapi import FastAPI

from app.routers import sms, voice

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")

app = FastAPI(
    title="Patient Companion Webhooks",
    version="0.1.0",
    description="Local sandbox for the Twilio webhook flows a patient companion app needs.",
)

app.include_router(sms.router)
app.include_router(voice.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
