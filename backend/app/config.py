"""Validated backend configuration, loaded once when imported."""

from pathlib import Path
from typing import Annotated

from pydantic import AnyHttpUrl, Field, PostgresDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        str_strip_whitespace=True,
        hide_input_in_errors=True,
    )

    supabase_url: AnyHttpUrl
    supabase_anon_key: SecretStr = Field(min_length=1)
    supabase_service_role_key: SecretStr = Field(min_length=1)
    database_url: SecretStr = Field(min_length=1)
    openai_api_key: SecretStr = Field(min_length=1)
    openai_embedding_model: str = Field(default="text-embedding-3-small", min_length=1)
    openai_embedding_dimensions: int = Field(default=1536, gt=0)
    allowed_origins: Annotated[list[str], NoDecode] = Field(min_length=1)

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        print(f"Validating database_url: {value.get_secret_value()}")
        PostgresDsn(value.get_secret_value())
        return value

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def split_allowed_origins(cls, value: object) -> object:
        print(f"Splitting allowed_origins: {value}")
        if isinstance(value, str):
            return value.split(",")
        return value

    @field_validator("allowed_origins")
    @classmethod
    def validate_allowed_origins(cls, origins: list[str]) -> list[str]:
        print(f"Validating allowed_origins: {origins}")
        normalized = []
        for origin in origins:
            url = AnyHttpUrl(origin)
            if (
                url.username is not None
                or url.password is not None
                or url.path not in (None, "/")
                or url.query is not None
                or url.fragment is not None
            ):
                raise ValueError(
                    "ALLOWED_ORIGINS must contain only scheme, host and optional port"
                )
            # Browser Origin headers have no trailing slash.
            normalized.append(str(url).rstrip("/"))
        return normalized


settings: Settings = Settings()
