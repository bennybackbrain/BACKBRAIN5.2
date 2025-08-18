from __future__ import annotations

from functools import lru_cache
import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
	api_name: str = "Backbrain5.2 API"
	summary_model: str = "gpt-4o-mini"
	summarizer_provider: str = "heuristic"  # heuristic|openai (fallback to heuristic if misconfigured)
	debug: bool = False  # controls verbosity / error detail
	job_max_retries: int = 3
	job_retry_delay_seconds: int = 10
	secret_key: str = "dev-secret-change"
	access_token_expire_minutes: int = 30
	refresh_token_expire_minutes: int = 60 * 24
	default_admin_username: str | None = None
	default_admin_password: str | None = None
	inbox_dir: str = "BACKBRAIN5.2/01_inbox"  # canonical NC path for entries
	summaries_dir: str = "BACKBRAIN5.2/summaries"  # canonical NC path for summaries
	errors_dir: str = "05_errors"
	max_text_file_bytes: int = 256 * 1024  # safeguard for write-file endpoints
	# --- Newly added integration settings (loaded from .env if present) ---
	webdav_url: str | None = None  # WEBDAV_URL
	webdav_username: str | None = None  # WEBDAV_USERNAME
	webdav_password: str | None = None  # WEBDAV_PASSWORD
	openai_api_key: str | None = None  # OPENAI_API_KEY
	openai_base_url: str | None = None  # OPENAI_BASE_URL (optional override)
	confirm_use_prod_key: bool = False  # CONFIRM_USE_PROD_KEY explicit opt-in to use real OpenAI key
	search_backend: str = "basic"  # basic|vector (vector planned)
	rate_limit_requests_per_minute: int = 120
	redis_url: str | None = None  # REDIS_URL for optional redis rate limiting
	allowed_origins: str | None = None  # comma separated list for CORS
	manual_uploads_dir: str = "BACKBRAIN5.2/manual_uploads"  # optional zweiter Eingang (manueller Drop)
	# --- Auto Ingest (Drag&Drop Scanner) ---
	auto_ingest_enabled: bool = False  # AUTO_INGEST_ENABLED=1 aktiviert Hintergrund-Scan
	auto_ingest_interval_seconds: int = 120  # AUTO_INGEST_INTERVAL_SECONDS (Standard 2min)
	auto_ingest_min_interval_seconds: int = 2  # AUTO_INGEST_MIN_INTERVAL_SECONDS Untergrenze für Scan (Standard 2s)
	auto_ingest_max_files_per_cycle: int = 10  # Begrenzung pro Scan um Last zu kontrollieren
	ingest_allowed_extensions: str = ".txt,.md,.pdf"  # INGEST_ALLOWED_EXTENSIONS kommasepariert (inkl. Punkt)
	pdf_max_pages: int = 8  # PDF_MAX_PAGES maximale Seiten für einfache Extraktion
	enable_public_alias: bool = False  # steuert öffentliche Alias-Routen (False default for safety)
	enable_diag: bool = False  # /diag route exposure
	public_writefile_limit_per_minute: int = 30  # rate limit for unauthenticated public write-file (0 = disable limit)
	rate_limit_bypass_paths: str | None = None  # comma-separated paths that bypass global rate limiter (in addition to built-ins)
	public_write_enabled: bool = True  # PUBLIC_WRITE_ENABLED (allow unauthenticated write-file)
	rate_limit_key_strategy: str = "ip"  # RATE_LIMIT_KEY_STRATEGY=apikey|ip
	api_key_rate_limit_window: str | None = None  # API_KEY_RATE_LIMIT_WINDOW like '60/min'
	access_log_enabled: bool = True  # ACCESS_LOG_ENABLED toggle structured JSON access log middleware

	# Allow unknown extra env vars (so future additions don't break startup/tests)
	model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")


@lru_cache
def get_settings() -> Settings:
	s = Settings()  # type: ignore[call-arg]
	# --- Backward compatibility for earlier NC_* variable naming ---
	# If the new canonical vars (WEBDAV_URL/USERNAME/PASSWORD) are missing, fall back.
	if not s.webdav_url:
		legacy = os.getenv("NC_WEBDAV_BASE")
		if legacy:
			s.webdav_url = legacy.rstrip("/")
	if not s.webdav_username:
		legacy_user = os.getenv("NC_USER")
		if legacy_user:
			s.webdav_username = legacy_user
	if not s.webdav_password:
		legacy_pwd = os.getenv("NC_APP_PASSWORD")
		if legacy_pwd:
			s.webdav_password = legacy_pwd
	return s


settings = get_settings()
# --- Summary Cache (Turbo-Layer) ---

def get_summary_cache_enabled() -> bool:
	return os.getenv("SUMMARY_CACHE_ENABLED", "true").lower() == "true"

def get_summary_cache_dir() -> str:
	return os.getenv("SUMMARY_CACHE_DIR", "/data/BB52_cache/summaries")

def ensure_summary_cache_dir(path: str):
	try:
		os.makedirs(path, exist_ok=True)
	except Exception as e:
		import logging
		logging.getLogger("app.config").warning(f"Could not ensure dir {path}: {e}")

# --- Summary Cache (Turbo-Layer) ---
import os
import logging
SUMMARY_CACHE_ENABLED = os.getenv("SUMMARY_CACHE_ENABLED", "true").lower() == "true"
SUMMARY_CACHE_DIR = os.getenv("SUMMARY_CACHE_DIR", "/data/BB52_cache/summaries")

def _ensure_dir(path: str):
	try:
		os.makedirs(path, exist_ok=True)
	except Exception as e:
		logging.getLogger("app.config").warning(f"Could not ensure dir {path}: {e}")

if SUMMARY_CACHE_ENABLED:
	_ensure_dir(SUMMARY_CACHE_DIR)

def reload_settings_for_tests():  # pragma: no cover - test utility
	"""Force reload of settings (for tests that mutate env like enabling public alias).

	Usage in tests: from app.core.config import reload_settings_for_tests, settings
	then call reload_settings_for_tests(); re-import modules if necessary for routers.
	"""
	global settings
	get_settings.cache_clear()  # type: ignore[attr-defined]
	settings = get_settings()

