from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import logging

from app.database import get_db
from app import models, schemas, rbac
from app.cache import get_cached_session, set_cached_session, invalidate_cached_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions", tags=["Sessions"])

def serialize_session_to_dict(session: models.Session) -> dict:
    """Helper to convert SQLAlchemy Session model to a dict for Redis caching."""
    evaluation_data = None
    if session.evaluation:
        evaluation_data = {
            "id": session.evaluation.id,
            "session_id": session.evaluation.session_id,
            "status": session.evaluation.status,
            "feedback": session.evaluation.feedback,
            "score": session.evaluation.score,
            "created_at": session.evaluation.created_at.isoformat(),
            "updated_at": session.evaluation.updated_at.isoformat()
        }
    return {
        "id": session.id,
        "title": session.title,
        "description": session.description,
        "start_time": session.start_time.isoformat(),
        "end_time": session.end_time.isoformat(),
        "teacher_id": session.teacher_id,
        "student_id": session.student_id,
        "parent_id": session.student.parent_id,  # Include for fast cached RBAC checks
        "evaluation": evaluation_data
    }

@router.get("", response_model=List[schemas.SessionResponse])
def read_sessions(
    current_user: models.User = Depends(rbac.require_any_role),
    db: Session = Depends(get_db)
):
    """
    Lists all sessions accessible to the logged in user based on role constraints:
    - Admin: All sessions.
    - Teacher: Only their own sessions.
    - Parent: Only sessions for their children.
    """
    query = db.query(models.Session)
    
    if current_user.role == models.UserRole.ADMIN.value:
        pass  # Admin has no filters
    elif current_user.role == models.UserRole.TEACHER.value:
        query = query.filter(models.Session.teacher_id == current_user.id)
    elif current_user.role == models.UserRole.PARENT.value:
        query = query.join(models.Student).filter(models.Student.parent_id == current_user.id)
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not authorized to access sessions."
        )
        
    return query.all()

@router.get("/{session_id}", response_model=schemas.SessionResponse)
def read_session_by_id(
    session_id: int,
    current_user: models.User = Depends(rbac.require_any_role),
    db: Session = Depends(get_db)
):
    """
    Retrieves a single session.
    First attempts to read from Redis cache, verifies RBAC on cached data, 
    and falls back to database on cache miss.
    """
    # 1. Attempt to hit cache
    cached_session = get_cached_session(session_id)
    if cached_session:
        # Check permissions on cached data
        if current_user.role == models.UserRole.ADMIN.value:
            return cached_session
        elif current_user.role == models.UserRole.TEACHER.value:
            if cached_session["teacher_id"] == current_user.id:
                return cached_session
        elif current_user.role == models.UserRole.PARENT.value:
            if cached_session["parent_id"] == current_user.id:
                return cached_session
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not have permission to view this session."
        )

    # 2. Cache miss: read from DB
    session = db.query(models.Session).filter(models.Session.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with ID {session_id} not found."
        )

    # 3. Enforce DB/Object-level RBAC check
    rbac.check_session_access(session, current_user)

    # 4. Save to Redis Cache for future reads
    try:
        session_dict = serialize_session_to_dict(session)
        set_cached_session(session_id, session_dict)
    except Exception as e:
        logger.warning(f"Failed to cache session {session_id}: {e}")

    return session

@router.post("", response_model=schemas.SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    session_in: schemas.SessionCreate,
    current_user: models.User = Depends(rbac.require_staff),
    db: Session = Depends(get_db)
):
    """
    Creates a new session.
    - Admins can assign sessions to any teacher.
    - Teachers can only create sessions where they are the teacher.
    """
    # Validate student existence
    student = db.query(models.Student).filter(models.Student.id == session_in.student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID {session_in.student_id} not found."
        )

    # Set and validate teacher
    assigned_teacher_id = current_user.id
    if current_user.role == models.UserRole.ADMIN.value:
        if session_in.teacher_id:
            # Verify the assigned teacher actually exists and has teacher role
            teacher = db.query(models.User).filter(
                models.User.id == session_in.teacher_id, 
                models.User.role == models.UserRole.TEACHER.value
            ).first()
            if not teacher:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"User with ID {session_in.teacher_id} is not a valid teacher."
                )
            assigned_teacher_id = session_in.teacher_id
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin must specify a teacher_id to create a session."
            )
    else:
        # Teacher role
        if session_in.teacher_id and session_in.teacher_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Teachers can only create sessions for themselves."
            )

    new_session = models.Session(
        title=session_in.title,
        description=session_in.description,
        start_time=session_in.start_time,
        end_time=session_in.end_time,
        teacher_id=assigned_teacher_id,
        student_id=session_in.student_id
    )
    
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session

@router.put("/{session_id}", response_model=schemas.SessionResponse)
def update_session(
    session_id: int,
    session_in: schemas.SessionUpdate,
    current_user: models.User = Depends(rbac.require_staff),
    db: Session = Depends(get_db)
):
    """
    Updates an existing session.
    - Admins can edit any session.
    - Teachers can only edit their own sessions.
    """
    session = db.query(models.Session).filter(models.Session.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with ID {session_id} not found."
        )

    # Check update permission
    rbac.check_session_access(session, current_user)

    # Perform updates
    update_data = session_in.model_dump(exclude_unset=True)
    
    # Validation if fields are updated
    if "student_id" in update_data:
        student = db.query(models.Student).filter(models.Student.id == update_data["student_id"]).first()
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Student with ID {update_data['student_id']} not found."
            )
            
    if "teacher_id" in update_data and current_user.role != models.UserRole.ADMIN.value:
        if update_data["teacher_id"] != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Teachers cannot reassign their sessions to other teachers."
            )

    for field, value in update_data.items():
        setattr(session, field, value)

    db.commit()
    db.refresh(session)

    # Invalidate cache to maintain consistency
    invalidate_cached_session(session_id)

    return session

@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: int,
    current_user: models.User = Depends(rbac.require_staff),
    db: Session = Depends(get_db)
):
    """
    Deletes a session.
    - Admins can delete any session.
    - Teachers can only delete their own sessions.
    """
    session = db.query(models.Session).filter(models.Session.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with ID {session_id} not found."
        )

    # Check delete permission
    rbac.check_session_access(session, current_user)

    db.delete(session)
    db.commit()

    # Invalidate cache
    invalidate_cached_session(session_id)

    return None
