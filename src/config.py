"""Centralized configuration via Pydantic BaseSettings.

Each service has its own settings class with an env_prefix.
Settings are only loaded when the specific client calls ``from_env()``.
"""

from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings


def _read_secret(path: str | Path, default: str = "") -> str:
    """Read a secret from a file, returning default if missing."""
    p = Path(path)
    if p.exists():
        return p.read_text().strip()
    return default


class GithubSettings(BaseSettings):
    """GitHub App authentication settings."""

    app_id: str = ""
    private_key: str = ""
    webhook_secret: str = ""

    # File paths for secret loading (not env-prefixed — explicit paths)
    app_id_file: str = "/secrets/app-id"
    private_key_file: str = "/secrets/private-key.pem"
    webhook_secret_file: str = "/secrets/webhook-secret"

    model_config = {"env_prefix": "GITHUB_"}

    @model_validator(mode="after")
    def _load_file_secrets(self) -> "GithubSettings":
        """Load secrets from files if the direct values are empty."""
        if not self.app_id:
            self.app_id = _read_secret(self.app_id_file)
        if not self.private_key:
            self.private_key = _read_secret(self.private_key_file)
        if not self.webhook_secret:
            self.webhook_secret = _read_secret(self.webhook_secret_file)
        return self


class GcpSettings(BaseSettings):
    """GCP service account settings."""

    sa_key_file: str = "/secrets/gcp-service-account.json"
    project_id: str = ""
    project_file: str = "/secrets/gcp-project"

    model_config = {"env_prefix": "GCP_"}

    @model_validator(mode="after")
    def _load_project_id(self) -> "GcpSettings":
        if not self.project_id:
            self.project_id = _read_secret(self.project_file)
        return self


class GeminiSettings(BaseSettings):
    """Gemini API settings."""

    model: str = "gemini-2.5-pro-preview-05-06"
    temperature: float = 0.7
    max_output_tokens: int = 4096
    max_diff_chars: int = 30_000

    model_config = {"env_prefix": "GEMINI_"}


class JulianSettings(BaseSettings):
    """Top-level Julian app settings."""

    log_level: str = "INFO"
    log_buffer_size: int = 200
    guidelines_dir: str = Field(default="guidelines")
    review_delay_seconds: int = Field(default=30)

    model_config = {"env_prefix": "JULIAN_"}
