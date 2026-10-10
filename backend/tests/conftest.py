import os

import pytest
from sqlalchemy.orm import sessionmaker

from app.db import models  # noqa: F401
from app.db.base import Base, make_engine
from app.db.seed import seed_rules

@pytest.fixture(autouse=True)
def no_network_password(monkeypatch):
    """backend/.env may set PROMPTOPT_PASSWORD for a deployed server; the test client counts as another machine."""
    monkeypatch.delenv("PROMPTOPT_PASSWORD", raising=False)


URLS = ["sqlite://"]  # in-memory SQLite
if os.getenv("TEST_POSTGRES_URL"):
    URLS.append(os.environ["TEST_POSTGRES_URL"])


@pytest.fixture(params=URLS, ids=lambda u: u.split(":")[0].split("+")[0])
def db(request):
    engine = make_engine(request.param)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Session() as session:
        seed_rules(session)
        yield session
        session.rollback()
    Base.metadata.drop_all(engine)
    engine.dispose()
