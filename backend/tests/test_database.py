from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
import pytest
from sqlalchemy import inspect

from app.core.config import Settings
from app.core.database import Base, SessionLocal, get_db
from app.main import lifespan
from app.models.base import BaseModel


def test_database_url_is_loaded_from_environment(monkeypatch):
    database_url = "postgresql+psycopg://test:test@db:5432/test_db"
    monkeypatch.setenv("DATABASE_URL", database_url)

    settings = Settings(_env_file=None)

    assert settings.database_url == database_url


def test_session_factory_and_dependency_are_available(monkeypatch):
    class FakeSession:
        closed = False

        def close(self):
            self.closed = True

    session = FakeSession()
    monkeypatch.setattr("app.core.database.SessionLocal", lambda: session)

    dependency = get_db()
    yielded = next(dependency)

    assert yielded is session
    dependency.close()
    assert session.closed is True
    assert callable(SessionLocal)


def test_base_model_columns_are_available_to_subclasses():
    class SampleModel(BaseModel):
        __tablename__ = "database_layer_sample"

    columns = inspect(SampleModel).columns

    assert {column.name for column in columns} == {"id", "created_at", "updated_at"}
    assert columns.id.primary_key is True
    assert columns.created_at.server_default is not None
    assert columns.updated_at.onupdate is not None

    Base.metadata.remove(SampleModel.__table__)


def test_alembic_configuration_discovers_initial_migration():
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    scripts = ScriptDirectory.from_config(config)

    assert scripts.dir == str(backend_dir / "alembic")
    assert scripts.get_current_head() == "0001_enable_postgis"
    assert Base.metadata.tables == {}


@pytest.mark.asyncio
async def test_application_lifespan_checks_database_connectivity(monkeypatch):
    class FakeConnection:
        def __init__(self):
            self.queries = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, query):
            self.queries.append(str(query))

    class FakeEngine:
        def __init__(self):
            self.connection = FakeConnection()

        def connect(self):
            return self.connection

    fake_engine = FakeEngine()
    monkeypatch.setattr("app.main.engine", fake_engine)

    async with lifespan(None):
        pass

    assert fake_engine.connection.queries == ["SELECT 1"]


@pytest.mark.asyncio
async def test_application_lifespan_propagates_database_failure(monkeypatch):
    class FailingEngine:
        def connect(self):
            raise ConnectionError("database unavailable")

    monkeypatch.setattr("app.main.engine", FailingEngine())

    with pytest.raises(ConnectionError, match="database unavailable"):
        async with lifespan(None):
            pass
