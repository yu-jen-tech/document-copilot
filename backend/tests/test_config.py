import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from pydantic import ValidationError

REQUIRED_ENV = {
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_ANON_KEY": "test-anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
    "DATABASE_URL": "postgresql://postgres:test-password@localhost:5432/postgres",
    "OPENAI_API_KEY": "test-openai-key",
    "ALLOWED_ORIGINS": "http://localhost:5173",
}
BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture
def config(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    names = {*REQUIRED_ENV, "OPENAI_EMBEDDING_MODEL", "OPENAI_EMBEDDING_DIMENSIONS"}
    for name in tuple(os.environ):
        if name.upper() in names:
            monkeypatch.delenv(name)
    for name, value in REQUIRED_ENV.items():
        monkeypatch.setenv(name, value)
    return importlib.import_module("app.config")


def test_environment_values_and_defaults(config: ModuleType) -> None:
    settings = config.Settings(_env_file=None)

    assert str(settings.supabase_url) == "https://example.supabase.co/"
    assert (
        settings.supabase_anon_key.get_secret_value()
        == REQUIRED_ENV["SUPABASE_ANON_KEY"]
    )
    assert (
        settings.supabase_service_role_key.get_secret_value()
        == REQUIRED_ENV["SUPABASE_SERVICE_ROLE_KEY"]
    )
    assert settings.database_url.get_secret_value() == REQUIRED_ENV["DATABASE_URL"]
    assert settings.openai_api_key.get_secret_value() == REQUIRED_ENV["OPENAI_API_KEY"]
    assert settings.openai_embedding_model == "text-embedding-3-small"
    assert settings.openai_embedding_dimensions == 1536
    assert settings.allowed_origins == ["http://localhost:5173"]
    for name in (
        "SUPABASE_ANON_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "DATABASE_URL",
        "OPENAI_API_KEY",
    ):
        assert REQUIRED_ENV[name] not in repr(settings)
        assert REQUIRED_ENV[name] not in settings.model_dump_json()


@pytest.mark.parametrize("name", REQUIRED_ENV)
def test_missing_required_values_fail(
    config: ModuleType, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    monkeypatch.delenv(name)

    with pytest.raises(ValidationError) as error:
        config.Settings(_env_file=None)

    assert error.value.errors(include_input=False)[0]["loc"] == (name.lower(),)


@pytest.mark.parametrize("name", REQUIRED_ENV)
@pytest.mark.parametrize("value", ["", " \t "])
def test_empty_required_values_fail(
    config: ModuleType, monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        config.Settings(_env_file=None)


def test_dotenv_loading_and_environment_precedence(
    config: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(f"{name}={value}" for name, value in REQUIRED_ENV.items())
        + "\nOPENAI_EMBEDDING_MODEL=test-embedding-model\nOPENAI_EMBEDDING_DIMENSIONS=512\n",
        encoding="utf-8",
    )
    for name in REQUIRED_ENV:
        monkeypatch.delenv(name)
    monkeypatch.setenv("OPENAI_API_KEY", "environment-key")
    monkeypatch.setenv(
        "ALLOWED_ORIGINS", " http://localhost:5173/, https://app.example.com/ "
    )

    settings = config.Settings(_env_file=env_file)

    assert settings.openai_api_key.get_secret_value() == "environment-key"
    assert settings.openai_embedding_model == "test-embedding-model"
    assert settings.openai_embedding_dimensions == 512
    assert settings.allowed_origins == [
        "http://localhost:5173",
        "https://app.example.com",
    ]


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("SUPABASE_URL", "not-a-url"),
        ("DATABASE_URL", "mysql://user:private-password@localhost/database"),
        ("OPENAI_EMBEDDING_MODEL", " "),
        ("OPENAI_EMBEDDING_DIMENSIONS", "0"),
        ("OPENAI_EMBEDDING_DIMENSIONS", "-1"),
        ("OPENAI_EMBEDDING_DIMENSIONS", "not-an-integer"),
        ("ALLOWED_ORIGINS", "*"),
        ("ALLOWED_ORIGINS", "http://localhost:5173,"),
        ("ALLOWED_ORIGINS", "https://example.com/path"),
        ("ALLOWED_ORIGINS", "https://example.com?query=value"),
        ("ALLOWED_ORIGINS", "https://example.com#fragment"),
        ("ALLOWED_ORIGINS", "https://user:password@example.com"),
    ],
)
def test_invalid_values_fail_without_exposing_input(
    config: ModuleType, monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError) as error:
        config.Settings(_env_file=None)

    assert error.value.errors(include_input=False)[0]["loc"][0] == name.lower()
    assert "input_value" not in str(error.value)
    assert "private-password" not in str(error.value)


def test_import_fails_without_configuration_and_loads_dotenv_from_backend(
    tmp_path: Path,
) -> None:
    # Isolate startup from the developer's real .env and credentials.
    backend = tmp_path / "backend"
    shutil.copytree(
        BACKEND / "app", backend / "app", ignore=shutil.ignore_patterns("__pycache__")
    )
    env = {"PYTHONPATH": str(backend)}
    command = [sys.executable, "-c", "from app.config import settings"]

    missing = subprocess.run(
        command, cwd=tmp_path, env=env, capture_output=True, text=True, check=False
    )

    assert missing.returncode != 0
    for name in REQUIRED_ENV:
        assert name.lower() in missing.stderr

    (backend / ".env").write_text(
        "\n".join(f"{name}={value}" for name, value in REQUIRED_ENV.items()),
        encoding="utf-8",
    )
    loaded = subprocess.run(
        command, cwd=tmp_path, env=env, capture_output=True, text=True, check=False
    )

    assert loaded.returncode == 0, loaded.stderr
