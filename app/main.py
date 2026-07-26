from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.database import engine, Base
from app.routes import auth, sessions, evaluations

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize database tables on startup
# Note: For production, we should use Alembic migrations instead of create_all
try:
    Base.metadata.create_all(bind=engine)
    logger.info("Successfully created database tables (if not already existing).")
except Exception as e:
    logger.exception(f"Error initializing database tables: {e}")

# Initialize FastAPI App
app = FastAPI(
    title="Bodhrik Core API",
    description="Backend service modeling users, sessions, evaluations, RBAC, and caching.",
    version="1.0.0",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(sessions.router)
app.include_router(evaluations.router)


@app.get("/")
def root():
    return {
        "app": "Bodhrik API",
        "version": "1.0.0",
        "docs_url": "/docs",
        "status": "healthy",
    }
