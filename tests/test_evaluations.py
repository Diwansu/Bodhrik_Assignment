from fastapi import status
from unittest.mock import MagicMock
from tests.test_sessions import create_db_session
from app import models


# --- Trigger Evaluation Tests ---
def test_trigger_evaluation_teacher_success(client, db, teacher1_headers, monkeypatch):
    s1 = create_db_session(db, "Algebra Intro", teacher_id=2, student_id=1)

    # Mock celery task trigger
    mock_delay = MagicMock()
    monkeypatch.setattr("app.worker.run_evaluation_job.delay", mock_delay)

    # Trigger evaluation
    response = client.post(
        "/evaluations/trigger", json={"session_id": s1.id}, headers=teacher1_headers
    )

    assert response.status_code == status.HTTP_202_ACCEPTED
    data = response.json()
    assert data["session_id"] == s1.id
    assert data["status"] == "pending"
    assert "id" in data

    # Assert background Celery job was enqueued with the correct evaluation ID
    mock_delay.assert_called_once_with(data["id"])


def test_trigger_evaluation_teacher_unauthorized_session(
    client, db, teacher2_headers, monkeypatch
):
    # Session belongs to Teacher 1 (teacher_id=2), but Teacher 2 (teacher_id=3) tries to trigger evaluation
    s1 = create_db_session(db, "Teacher 1 Class", teacher_id=2, student_id=1)

    response = client.post(
        "/evaluations/trigger", json={"session_id": s1.id}, headers=teacher2_headers
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_trigger_evaluation_parent_denied(client, db, parent1_headers):
    s1 = create_db_session(db, "Class", teacher_id=2, student_id=1)

    response = client.post(
        "/evaluations/trigger", json={"session_id": s1.id}, headers=parent1_headers
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_trigger_evaluation_already_running(client, db, teacher1_headers, monkeypatch):
    s1 = create_db_session(db, "Math", teacher_id=2, student_id=1)

    # Pre-create evaluation record with processing status
    eval_rec = models.Evaluation(session_id=s1.id, status="processing")
    db.add(eval_rec)
    db.commit()

    response = client.post(
        "/evaluations/trigger", json={"session_id": s1.id}, headers=teacher1_headers
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "already running" in response.json()["detail"]


# --- Read Evaluation Tests & RBAC ---
def test_read_evaluation_rbac(
    client, db, teacher1_headers, teacher2_headers, parent1_headers, parent2_headers
):
    # Session 1: Teacher 1 teaches Student John (Parent 1)
    s1 = create_db_session(db, "Session 1", teacher_id=2, student_id=1)

    # Create evaluation for Session 1
    eval_rec = models.Evaluation(
        session_id=s1.id, status="completed", feedback="Well done", score=90
    )
    db.add(eval_rec)
    db.commit()
    db.refresh(eval_rec)

    # 1. Teacher 1 can read
    resp = client.get(f"/evaluations/{eval_rec.id}", headers=teacher1_headers)
    assert resp.status_code == 200
    assert resp.json()["score"] == 90
    assert resp.json()["feedback"] == "Well done"

    # 2. Teacher 2 cannot read (Teacher 1's session evaluation)
    resp = client.get(f"/evaluations/{eval_rec.id}", headers=teacher2_headers)
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # 3. Parent 1 can read (John is Parent 1's child)
    resp = client.get(f"/evaluations/{eval_rec.id}", headers=parent1_headers)
    assert resp.status_code == 200
    assert resp.json()["score"] == 90

    # 4. Parent 2 cannot read
    resp = client.get(f"/evaluations/{eval_rec.id}", headers=parent2_headers)
    assert resp.status_code == status.HTTP_403_FORBIDDEN
