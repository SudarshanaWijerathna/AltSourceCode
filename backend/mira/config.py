"""Runtime configuration. `today` is configurable so evals are reproducible."""

from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = REPO_ROOT / "docs" / "ceylon-compass-dataset"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    mira_today: date = date(2026, 11, 19)
    dataset_dir: Path = DATASET_DIR
    mira_db_url: str = f"sqlite:///{REPO_ROOT / 'data' / 'mira.db'}"

    llm_provider: str = "anthropic"
    mira_model_large: str = "claude-sonnet-5-5"
    mira_model_small: str = "claude-haiku-5-5"

    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"

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
