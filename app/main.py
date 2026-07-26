import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routes import auth, evaluations, sessions

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize database schema via metadata creation for local/dev environments.
# For production, this should be replaced with Alembic migrations.
if settings.ENVIRONMENT != "production":
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
    allow_origins=settings.allowed_origins,
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
