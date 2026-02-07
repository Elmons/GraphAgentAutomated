from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "GraphAgentAutomated"
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8008

    database_url: str = "sqlite:///./graph_agent_automated.db"
    sql_echo: bool = False

    chat2graph_root: str = ""
    chat2graph_runtime_mode: str = "mock"  # mock|sdk
    chat2graph_schema_file: str = ""
    sdk_runtime_timeout_seconds: float = Field(default=30.0, gt=0.0, le=300.0)
    sdk_runtime_max_retries: int = Field(default=2, ge=0, le=10)
    sdk_runtime_retry_backoff_seconds: float = Field(default=0.5, ge=0.0, le=30.0)
    sdk_runtime_circuit_failure_threshold: int = Field(default=5, ge=1, le=100)
    sdk_runtime_circuit_reset_seconds: float = Field(default=30.0, gt=0.0, le=600.0)

    openai_api_key: str = ""
    openai_base_url: str = ""
    judge_backend: str = "mock"  # mock|openai
    judge_model: str = "gpt-4.1-mini"
    auth_enabled: bool = False
    auth_api_keys_json: str = "{}"
    auth_jwt_keys_json: str = "{}"
    auth_jwt_issuer: str = ""
    auth_jwt_audience: str = ""
    auth_jwt_clock_skew_seconds: int = Field(default=30, ge=0, le=600)
    auth_default_tenant_id: str = "default"
    failure_taxonomy_rules_file: str = ""

    default_dataset_size: int = Field(default=12, ge=6, le=30)
    max_search_rounds: int = Field(default=10, ge=1, le=100)
    max_expansions_per_round: int = Field(default=3, ge=1, le=10)
    max_prompt_candidates: int = Field(default=4, ge=2, le=8)
    train_ratio: float = Field(default=0.6, gt=0.4, lt=0.9)
    val_ratio: float = Field(default=0.2, gt=0.05, lt=0.4)
    test_ratio: float = Field(default=0.2, gt=0.05, lt=0.4)

    artifacts_dir: str = "./artifacts"
    manual_blueprints_dir: str = "./artifacts/manual_blueprints"
    artifact_store_backend: str = "local"

    @property
    def artifacts_path(self) -> Path:
        return Path(self.artifacts_dir).resolve()

    @property
    def manual_blueprints_path(self) -> Path:
        return Path(self.manual_blueprints_dir).resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings singleton."""
    settings = Settings()
    settings.artifacts_path.mkdir(parents=True, exist_ok=True)
    settings.manual_blueprints_path.mkdir(parents=True, exist_ok=True)
    return settings
