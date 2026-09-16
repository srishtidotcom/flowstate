import asyncio
import json
import os
from contextlib import contextmanager

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import backend.core.activity.engine as activity_engine
import backend.governance.service as review_service
import backend.ingestion.service as ingestion_service
import backend.ingestion.upload as upload_api
import backend.api.integrations as integrations_api
import backend.infrastructure.connectors.service as connector_service
from backend.api.main import app
from backend.db.orm import Base


class ControlledQueue:
    def __init__(self):
        self.messages = []
        self.delivery_keys = set()

    def enqueue_once(self, queue_name, delivery_key, payload):
        if delivery_key in self.delivery_keys:
            return False
        self.delivery_keys.add(delivery_key)
        self.messages.insert(0, (queue_name, payload))
        return True

    def pop_job(self):
        _, payload = self.messages.pop()
        return json.loads(payload)


@pytest.fixture
def isolated_db(monkeypatch):
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    @contextmanager
    def test_get_db():
        with Session(engine) as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

    monkeypatch.setattr(ingestion_service, "get_db", test_get_db)
    monkeypatch.setattr(activity_engine, "get_db", test_get_db)
    monkeypatch.setattr(review_service, "get_db", test_get_db)
    monkeypatch.setattr(connector_service, "get_db", test_get_db)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def controlled_queue(monkeypatch):
    queue = ControlledQueue()
    monkeypatch.setattr(upload_api, "r", queue)
    monkeypatch.setattr(integrations_api, "r", queue)
    return queue


@pytest.fixture
def api_request():
    def request(method, path, **kwargs):
        async def send():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                return await client.request(method, path, **kwargs)

        return asyncio.run(send())

    return request
