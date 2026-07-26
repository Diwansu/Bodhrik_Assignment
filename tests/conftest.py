import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

# Import app components
from app.database import Base, get_db
from app.main import app
from app.config import settings
from app import models, rbac

# --- Setup Test SQLite Database ---
# sqlite:///:memory: with StaticPool is perfect for fast, isolated tests.
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    """Creates a fresh test database for each test function and rolls it back after."""
    Base.metadata.create_all(bind=engine)
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    # Seed basic records required for relational FK constraints
    seed_test_data(session)

    yield session

    session.close()
    transaction.rollback()
    connection.close()
    Base.metadata.drop_all(bind=engine)


def seed_test_data(db_session):
    """Seed base entities for test assertions (users, students)."""
    pwd = rbac.get_password_hash("password123")

    # Create Users
    admin = models.User(
        id=1,
        email="admin@test.com",
        name="Admin User",
        hashed_password=pwd,
        role="admin",
    )
    t1 = models.User(
        id=2,
        email="teacher1@test.com",
        name="Teacher One",
        hashed_password=pwd,
        role="teacher",
    )
    t2 = models.User(
        id=3,
        email="teacher2@test.com",
        name="Teacher Two",
        hashed_password=pwd,
        role="teacher",
    )
    p1 = models.User(
        id=4,
        email="parent1@test.com",
        name="Parent One",
        hashed_password=pwd,
        role="parent",
    )
    p2 = models.User(
        id=5,
        email="parent2@test.com",
        name="Parent Two",
        hashed_password=pwd,
        role="parent",
    )
    db_session.add_all([admin, t1, t2, p1, p2])
    db_session.commit()

    # Create Students linked to Parents
    s1 = models.Student(id=1, name="Student John", parent_id=4)
    s2 = models.Student(id=2, name="Student Jane", parent_id=4)
    s3 = models.Student(id=3, name="Student Bob", parent_id=5)
    db_session.add_all([s1, s2, s3])
    db_session.commit()


# --- Mock Redis Caching ---
@pytest.fixture(autouse=True)
def mock_redis(monkeypatch):
    """Mocks Redis client methods to prevent network attempts during tests."""
    mock_client = MagicMock()
    mock_client.get.return_value = None
    mock_client.set.return_value = True
    mock_client.delete.return_value = 1

    # Monkeypatch the redis client inside cache module
    monkeypatch.setattr("app.cache.redis_client", mock_client)
    # Also disable celery tasks calling delay directly, mock Celery task delay
    monkeypatch.setattr("app.worker.run_evaluation_job.delay", MagicMock())
    return mock_client


# --- Setup FastAPI TestClient with Overridden Dependency ---
@pytest.fixture(scope="function")
def client(db):
    """Returns a TestClient with overridden get_db dependency pointing to the test DB."""

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# --- Auth Headers Fixtures ---
def generate_token_headers(email: str, role: str, user_id: int) -> dict:
    access_token = rbac.create_access_token(
        data={"sub": email, "role": role, "user_id": user_id},
        expires_delta=timedelta(minutes=15),
    )
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def admin_headers():
    return generate_token_headers("admin@test.com", "admin", 1)


@pytest.fixture
def teacher1_headers():
    return generate_token_headers("teacher1@test.com", "teacher", 2)


@pytest.fixture
def teacher2_headers():
    return generate_token_headers("teacher2@test.com", "teacher", 3)


@pytest.fixture
def parent1_headers():
    return generate_token_headers("parent1@test.com", "parent", 4)


@pytest.fixture
def parent2_headers():
    return generate_token_headers("parent2@test.com", "parent", 5)
