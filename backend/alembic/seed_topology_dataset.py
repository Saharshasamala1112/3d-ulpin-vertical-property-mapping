from __future__ import annotations

import os
from pathlib import Path


def main() -> None:
    test_database_url = os.environ.get("TEST_DATABASE_URL")
    if not test_database_url:
        raise SystemExit("Set TEST_DATABASE_URL to a dedicated test database before seeding.")

    os.environ["DATABASE_URL"] = test_database_url

    from alembic.config import Config
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from alembic import command
    from tests.fixtures.topology_dataset import seed_topology_dataset

    backend_root = Path(__file__).resolve().parents[1]
    alembic_config = Config(str(backend_root / "alembic.ini"))
    command.upgrade(alembic_config, "head")

    engine = create_engine(test_database_url, pool_pre_ping=True)
    try:
        with Session(engine) as session:
            seed_topology_dataset(session)
            session.commit()
    finally:
        engine.dispose()

    print("Seeded deterministic topology validation scenarios.")


if __name__ == "__main__":
    main()
