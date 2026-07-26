import time
import random
import logging
from celery import Celery
from app.config import settings
from app.database import SessionLocal
from app import models

logger = logging.getLogger(__name__)

# Initialize Celery app
celery = Celery(
    "bodhrik_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

# Optional configuration overrides
celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

@celery.task(name="app.worker.run_evaluation_job")
def run_evaluation_job(evaluation_id: int) -> dict:
    """
    Asynchronous Celery task that simulates evaluation processing.
    Updates DB status: pending -> processing -> completed/failed.
    """
    logger.info(f"Starting evaluation job for Evaluation ID: {evaluation_id}")
    db = SessionLocal()
    try:
        # 1. Fetch evaluation record
        evaluation = db.query(models.Evaluation).filter(models.Evaluation.id == evaluation_id).first()
        if not evaluation:
            logger.error(f"Evaluation with ID {evaluation_id} not found.")
            return {"status": "error", "message": "Evaluation not found"}

        # 2. Update status to PROCESSING
        evaluation.status = models.EvaluationStatus.PROCESSING.value
        db.commit()
        logger.info(f"Evaluation {evaluation_id} set to PROCESSING")

        # 3. Simulate processing time (e.g., LLM analysis latency)
        time.sleep(5)

        # 4. Generate mock evaluation outcome
        mock_feedbacks = [
            "Great engagement! The student was active and answered questions correctly.",
            "Good progress. Need to focus more on core math concepts next session.",
            "Excellent understanding of the material. Ready for the next topic.",
            "The student struggled slightly with concentration, but completed all exercises."
        ]
        
        evaluation.status = models.EvaluationStatus.COMPLETED.value
        evaluation.feedback = random.choice(mock_feedbacks)
        evaluation.score = random.randint(70, 100)
        db.commit()
        
        logger.info(f"Evaluation {evaluation_id} completed successfully with score: {evaluation.score}")
        
        # 5. Invalidate the session cache since evaluation data is now linked
        try:
            from app.cache import invalidate_cached_session
            invalidate_cached_session(evaluation.session_id)
        except Exception as cache_err:
            logger.warning(f"Failed to invalidate cache for session {evaluation.session_id}: {cache_err}")

        return {
            "status": "success",
            "evaluation_id": evaluation_id,
            "score": evaluation.score,
            "feedback": evaluation.feedback
        }

    except Exception as e:
        logger.exception(f"Error processing evaluation job {evaluation_id}: {e}")
        try:
            # Attempt to set status to FAILED in case of exception
            db.rollback()
            evaluation = db.query(models.Evaluation).filter(models.Evaluation.id == evaluation_id).first()
            if evaluation:
                evaluation.status = models.EvaluationStatus.FAILED.value
                db.commit()
        except Exception as rollback_err:
            logger.error(f"Failed to rollback and save error status for evaluation {evaluation_id}: {rollback_err}")
        return {"status": "failed", "error": str(e)}
        
    finally:
        db.close()
