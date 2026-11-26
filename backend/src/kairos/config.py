"""Runtime settings, read from `KAIROS_*` environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    `allowed_hosts` is a JSON list when set through the environment, for example
    `KAIROS_ALLOWED_HOSTS='["localhost", "127.0.0.1"]'`.
    """

    model_config = SettingsConfigDict(env_prefix="KAIROS_")

    data_dir: Path = Path("/data")
    static_dir: Path | None = None
    allowed_hosts: list[str] = ["localhost", "127.0.0.1"]

    @property
    def database_path(self) -> Path:
        """The SQLite file, inside the data directory (a named volume in Docker)."""
        return self.data_dir / "kairos.db"
