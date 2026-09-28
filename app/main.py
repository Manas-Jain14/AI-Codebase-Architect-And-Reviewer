from __future__ import annotations

from fastapi import FastAPI

from app.config import settings
from app.database import get_engine, init_db
from app.routes import router


app = FastAPI(title="AI Codebase Architect & Engineering Reviewer")
app.include_router(router)


@app.on_event("startup")
async def validate_startup_environment() -> None:
	"""Validate the environment at startup.

	This is async because it runs during the FastAPI startup lifecycle.
	"""

	settings.validate_required()
	get_engine()
	await init_db()
	print("DATABASE_URL loaded successfully")
	print("GEMINI_API_KEY loaded successfully")
	print(f"Gemini model loaded: {settings.MODEL_NAME}")

