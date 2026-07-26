from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

# If DATABASE_URL starts with "postgres://", rewrite it to "postgresql://"
# because SQLAlchemy removed support for the deprecated "postgres://" prefix
# which is still default in Supabase/Heroku URI generation.
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    db_url,
    # pool_pre_ping=True helps reconnect when connections drop (e.g. Supabase cold-starts)
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
