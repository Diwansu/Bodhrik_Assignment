from fastapi import status
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from app import models


# Helper to create a test session in DB directly
def create_db_session(db, title, teacher_id, student_id) -> models.Session:
    now = datetime.now(timezone.utc)
    session = models.Session(
        title=title,
        description="Test session",
        start_time=now,
        end_time=now + timedelta(hours=1),
        teacher_id=teacher_id,
        student_id=student_id,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


# --- Create Session Tests ---
def test_create_session_teacher_success(client, teacher1_headers):
    response = client.post(
        "/sessions",
        json={
            "title": "Math Class",
            "description": "Intro to fractions",
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "student_id": 1,  # Student John
        },
        headers=teacher1_headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["title"] == "Math Class"
    assert data["teacher_id"] == 2  # Teacher 1 ID
    assert data["student_id"] == 1


def test_create_session_teacher_fails_reassigning(client, teacher1_headers):
    # Teacher 1 tries to create session but explicitly assigns to Teacher 2
    response = client.post(
        "/sessions",
        json={
            "title": "Science Class",
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "student_id": 1,
            "teacher_id": 3,  # Teacher 2 ID
        },
        headers=teacher1_headers,
    )
    # RBAC should reject this assignment
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_create_session_admin_assign_teacher_success(client, admin_headers):
    # Admin creates session and assigns it to Teacher 2
    response = client.post(
        "/sessions",
        json={
            "title": "History Class",
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "student_id": 3,  # Student Bob
            "teacher_id": 3,  # Teacher 2 ID
        },
        headers=admin_headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["teacher_id"] == 3


def test_create_session_parent_denied(client, parent1_headers):
    response = client.post(
        "/sessions",
        json={
            "title": "Violin Class",
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "student_id": 1,
        },
        headers=parent1_headers,
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


# --- Read / List Session Tests & RBAC Checks ---
def test_list_sessions_rbac(
    client,
    db,
    admin_headers,
    teacher1_headers,
    teacher2_headers,
    parent1_headers,
    parent2_headers,
):
    # Seed 3 sessions
    # Session 1: Teacher 1 teaches Student John (Parent 1)
    create_db_session(db, "Session T1 to S-John", teacher_id=2, student_id=1)
    # Session 2: Teacher 1 teaches Student Jane (Parent 1)
    create_db_session(db, "Session T1 to S-Jane", teacher_id=2, student_id=2)
    # Session 3: Teacher 2 teaches Student Bob (Parent 2)
    create_db_session(db, "Session T2 to S-Bob", teacher_id=3, student_id=3)

    # 1. Admin reads all sessions
    resp = client.get("/sessions", headers=admin_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 3

    # 2. Teacher 1 reads only their own sessions (T1 sessions: 2)
    resp = client.get("/sessions", headers=teacher1_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2
    titles = [s["title"] for s in resp.json()]
    assert "Session T1 to S-John" in titles
    assert "Session T1 to S-Jane" in titles
    assert "Session T2 to S-Bob" not in titles

    # 3. Teacher 2 reads only their own sessions (T2 sessions: 1)
    resp = client.get("/sessions", headers=teacher2_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["title"] == "Session T2 to S-Bob"

    # 4. Parent 1 reads only their children's sessions (Student John & Jane sessions: 2)
    resp = client.get("/sessions", headers=parent1_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2
    titles = [s["title"] for s in resp.json()]
    assert "Session T1 to S-John" in titles
    assert "Session T1 to S-Jane" in titles

    # 5. Parent 2 reads only their child's sessions (Student Bob sessions: 1)
    resp = client.get("/sessions", headers=parent2_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["title"] == "Session T2 to S-Bob"


def test_read_single_session_rbac(
    client, db, teacher1_headers, teacher2_headers, parent1_headers, parent2_headers
):
    # Session 1: Teacher 1 teaches Student John (Parent 1)
    s1 = create_db_session(db, "Algebra Intro", teacher_id=2, student_id=1)

    # 1. Teacher 1 can read
    resp = client.get(f"/sessions/{s1.id}", headers=teacher1_headers)
    assert resp.status_code == 200

    # 2. Teacher 2 cannot read (Teacher 1's session)
    resp = client.get(f"/sessions/{s1.id}", headers=teacher2_headers)
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # 3. Parent 1 can read (John is Parent 1's child)
    resp = client.get(f"/sessions/{s1.id}", headers=parent1_headers)
    assert resp.status_code == 200

    # 4. Parent 2 cannot read (Bob is Parent 2's child, John is not)
    resp = client.get(f"/sessions/{s1.id}", headers=parent2_headers)
    assert resp.status_code == status.HTTP_403_FORBIDDEN


# --- Caching Tests ---
def test_read_session_cache_flow(client, db, teacher1_headers, monkeypatch):
    s1 = create_db_session(db, "Cache Lesson", teacher_id=2, student_id=1)

    # Track mock function calls
    mock_get = MagicMock(return_value=None)
    mock_set = MagicMock()

    monkeypatch.setattr("app.routes.sessions.get_cached_session", mock_get)
    monkeypatch.setattr("app.routes.sessions.set_cached_session", mock_set)

    # First request: Cache miss -> queries DB and sets cache
    resp = client.get(f"/sessions/{s1.id}", headers=teacher1_headers)
    assert resp.status_code == 200
    mock_get.assert_called_once_with(s1.id)
    mock_set.assert_called_once()

    # Reset mocks
    mock_get.reset_mock()
    mock_set.reset_mock()

    # Second request: Mock cache hit
    cached_payload = {
        "id": s1.id,
        "title": "Cached Lesson Title",
        "description": "Cached data",
        "start_time": s1.start_time.isoformat(),
        "end_time": s1.end_time.isoformat(),
        "teacher_id": 2,
        "student_id": 1,
        "parent_id": 4,  # Parent 1 ID
        "evaluation": None,
    }
    mock_get.return_value = cached_payload

    resp = client.get(f"/sessions/{s1.id}", headers=teacher1_headers)
    assert resp.status_code == 200
    assert (
        resp.json()["title"] == "Cached Lesson Title"
    )  # Asserts data was returned from cache
    mock_get.assert_called_once_with(s1.id)
    mock_set.assert_not_called()  # No set called because of cache hit


# --- Update / Delete Caching Invalidation Tests ---
def test_update_session_invalidates_cache(client, db, teacher1_headers, monkeypatch):
    s1 = create_db_session(db, "Old Session Title", teacher_id=2, student_id=1)

    mock_invalidate = MagicMock()
    monkeypatch.setattr(
        "app.routes.sessions.invalidate_cached_session", mock_invalidate
    )

    response = client.put(
        "/sessions/1", json={"title": "New Session Title"}, headers=teacher1_headers
    )
    assert response.status_code == 200
    mock_invalidate.assert_called_once_with(1)


def test_delete_session_invalidates_cache(client, db, teacher1_headers, monkeypatch):
    s1 = create_db_session(db, "To Delete", teacher_id=2, student_id=1)

    mock_invalidate = MagicMock()
    monkeypatch.setattr(
        "app.routes.sessions.invalidate_cached_session", mock_invalidate
    )

    response = client.delete(f"/sessions/{s1.id}", headers=teacher1_headers)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    mock_invalidate.assert_called_once_with(s1.id)
