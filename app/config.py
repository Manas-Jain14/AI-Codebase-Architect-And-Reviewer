from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
	DATABASE_URL: str = Field(default="")
	GEMINI_API_KEY: str = Field(default="")
	SUPABASE_URL: str = Field(default="")
	SUPABASE_SECRET_KEY: str = Field(default="")
	SUPABASE_BUCKET: str = Field(default="")
	MODEL_NAME: str = Field(default="gemini-3.1-flash-lite")
	BACKEND_URL: str = Field(default="http://localhost:8000")
	UPLOAD_DIR: str = Field(default="uploads")
	EXTRACT_DIR: str = Field(default="extracted_projects")

	model_config = SettingsConfigDict(
		env_file=ROOT_DIR / ".env",
		env_file_encoding="utf-8-sig",
		extra="ignore",
	)

	def validate_required(self) -> None:
		missing = []
		if not self.DATABASE_URL.strip():
			missing.append("DATABASE_URL")
		if not self.GEMINI_API_KEY.strip():
			missing.append("GEMINI_API_KEY")
		if not self.SUPABASE_URL.strip():
			missing.append("SUPABASE_URL")
		if not self.SUPABASE_SECRET_KEY.strip():
			missing.append("SUPABASE_SECRET_KEY")
		if not self.SUPABASE_BUCKET.strip():
			missing.append("SUPABASE_BUCKET")
		if not self.MODEL_NAME.strip():
			missing.append("MODEL_NAME")

		if missing:
			missing_list = ", ".join(missing)
			raise RuntimeError(f"Missing required environment variables: {missing_list}")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
	return Settings()


settings = get_settings()
DATABASE_URL = settings.DATABASE_URL
GEMINI_API_KEY = settings.GEMINI_API_KEY
SUPABASE_URL = settings.SUPABASE_URL
SUPABASE_SECRET_KEY = settings.SUPABASE_SECRET_KEY
SUPABASE_BUCKET = settings.SUPABASE_BUCKET
MODEL_NAME = settings.MODEL_NAME
BACKEND_URL = settings.BACKEND_URL
UPLOAD_DIR = settings.UPLOAD_DIR
EXTRACT_DIR = settings.EXTRACT_DIR
