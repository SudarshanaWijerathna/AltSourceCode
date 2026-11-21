"""Runtime configuration. `today` is configurable so evals are reproducible."""

from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = REPO_ROOT / "docs" / "ceylon-compass-dataset"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", extra="ignore", env_ignore_empty=True
    )

    mira_today: date = date(2026, 11, 19)
    dataset_dir: Path = DATASET_DIR
    mira_db_url: str = f"sqlite:///{REPO_ROOT / 'data' / 'mira.db'}"

    llm_provider: str = "google"
    google_api_key: str | None = Field(
        default=None, validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_API_KEY")
    )
    mira_model_large: str = "gemini-3.8-flash"
    mira_model_small: str = "gemini-3.5-flash-lite"

    # Optional margin overrides (e.g. 0.32). Unset -> use the workbook's Settings tab.
    mira_margin_day_tour: float | None = Field(default=None, ge=0, lt=1)
    mira_margin_multi_day: float | None = Field(default=None, ge=0, lt=1)

    # Staff accounts "name:role:key,..." (roles: staff, approver). Demo-only defaults for local use.
    mira_staff_users: str = "sam:staff:demo-staff-key,ana:approver:demo-approver-key"
    # Approved AI-written pages are written here (runtime data; the dataset is never modified).
    mira_published_dir: Path = REPO_ROOT / "data" / "published_content"

    mira_tracing: bool = True  # MIRA_TRACING=false disables Langfuse (unit tests)
    mira_environment: str = "development"  # Langfuse environment: development | eval | production

    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = Field(
        default="https://cloud.langfuse.com",
        validation_alias=AliasChoices("LANGFUSE_BASE_URL", "LANGFUSE_HOST"),
    )

    @property
    def content_dir(self) -> Path:
        return self.dataset_dir / "content"

    @property
    def rate_workbook(self) -> Path:
        return self.dataset_dir / "rates" / "rate_sheet_2026-27.xlsx"

    @property
    def brand_pack(self) -> Path:
        return self.dataset_dir / "brand" / "brand_pack.json"

    @property
    def eval_seed(self) -> Path:
        return self.dataset_dir / "evals" / "eval_seed.jsonl"


@lru_cache
def get_settings() -> Settings:
    return Settings()
