from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
	api_name: str = "Backbrain5.2 API"
	summary_model: str = "gpt-4o-mini"
	job_max_retries: int = 3
	job_retry_delay_seconds: int = 10
	secret_key: str = "dev-secret-change"
	access_token_expire_minutes: int = 30
	default_admin_username: str | None = None
	default_admin_password: str | None = None
	# Integrations
	n8n_write_file_webhook_url: str | None = None  # env: N8N_WRITE_FILE_WEBHOOK_URL

	model_config = ConfigDict(env_file=".env", case_sensitive=False)  # type: ignore[arg-type]


@lru_cache
def get_settings() -> Settings:
	return Settings()  # type: ignore[call-arg]


settings = get_settings()

