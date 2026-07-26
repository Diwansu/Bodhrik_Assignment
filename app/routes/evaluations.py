from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from app.database import get_db
from app import models, schemas, rbac
from app.worker import run_evaluation_job

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/evaluations", tags=["Evaluations"])

@router.post("/trigger", response_model=schemas.EvaluationResponse, status_code=status.HTTP_202_ACCEPTED)
def trigger_evaluation(
    payload: schemas.EvaluationTrigger,
    current_user: models.User = Depends(rbac.require_staff),
    db: Session = Depends(get_db)
):
    """
    Triggers an evaluation job for a specific session.
    - Validates session existence and access control.
    - Creates/resets an Evaluation record.
    - Enqueues the processing job in Celery via Redis.
    """
    session_id = payload.session_id
    
    # 1. Verify session exists
    session = db.query(models.Session).filter(models.Session.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with ID {session_id} not found."
        )

    # 2. Check that the teacher/admin has permission to access this session
    rbac.check_session_access(session, current_user)

    # 3. Check if an evaluation already exists for this session
    evaluation = db.query(models.Evaluation).filter(models.Evaluation.session_id == session_id).first()
    
    if evaluation:
        # If it's already processing, return 400
        if evaluation.status == models.EvaluationStatus.PROCESSING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An evaluation job is already running for this session."
            )
        # Reset evaluation fields for a fresh run
        evaluation.status = models.EvaluationStatus.PENDING.value
        evaluation.feedback = None
        evaluation.score = None
    else:
        # Create new evaluation record
        evaluation = models.Evaluation(
            session_id=session_id,
            status=models.EvaluationStatus.PENDING.value
        )
        db.add(evaluation)
        
    db.commit()
    db.refresh(evaluation)

    # 4. Enqueue the task in Celery
    try:
        run_evaluation_job.delay(evaluation.id)
        logger.info(f"Enqueued evaluation job {evaluation.id} in Celery")
    except Exception as e:
        logger.error(f"Failed to enqueue Celery task for evaluation {evaluation.id}: {e}")
        # Rollback evaluation status in database if we can't enqueue
        evaluation.status = models.EvaluationStatus.FAILED.value
        evaluation.feedback = "Failed to queue evaluation task. Worker may be offline."
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not enqueue evaluation job. Message broker might be offline."
        )

    # Invalidate cache for this session since evaluation status has changed
    try:
        from app.cache import invalidate_cached_session
        invalidate_cached_session(session_id)
    except Exception as cache_err:
        logger.warning(f"Failed to invalidate cache for session {session_id}: {cache_err}")

    return evaluation

@router.get("/{evaluation_id}", response_model=schemas.EvaluationResponse)
def read_evaluation(
    evaluation_id: int,
    current_user: models.User = Depends(rbac.require_any_role),
    db: Session = Depends(get_db)
):
    """
    Fetches evaluation status and details.
    Access constraints are inherited from the linked session.
    """
    evaluation = db.query(models.Evaluation).filter(models.Evaluation.id == evaluation_id).first()
    if not evaluation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation with ID {evaluation_id} not found."
        )

    # Enforce RBAC access on the session associated with the evaluation
    rbac.check_session_access(evaluation.session, current_user)
    
    return evaluation
