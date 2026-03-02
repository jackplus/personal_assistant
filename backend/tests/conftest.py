from __future__ import annotations

from collections.abc import Generator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base, get_db
from app.main import app
import app.main as main_module


@pytest.fixture()
def session_factory(tmp_path) -> sessionmaker:
    db_path = tmp_path / "test_assistant.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal


@pytest.fixture()
def db(session_factory: sessionmaker) -> Generator[Session, None, None]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(session_factory: sessionmaker, monkeypatch) -> Generator[TestClient, None, None]:
    test_engine = session_factory.kw["bind"]

    def override_get_db() -> Generator[Session, None, None]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(main_module, "engine", test_engine)
    monkeypatch.setattr(main_module, "start_scheduler", lambda: None)
    monkeypatch.setattr(main_module, "stop_scheduler", lambda: None)

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def now() -> datetime:
    return datetime.utcnow()
