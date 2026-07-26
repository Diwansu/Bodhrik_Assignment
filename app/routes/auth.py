from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from app.database import get_db
from app import models, schemas, rbac

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=schemas.UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    """Registers a new user in the platform."""
    existing_user = (
        db.query(models.User).filter(models.User.email == user_in.email).first()
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    hashed_pwd = rbac.get_password_hash(user_in.password)
    user = models.User(
        email=user_in.email,
        name=user_in.name,
        hashed_password=hashed_pwd,
        role=user_in.role.value,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/token", response_model=schemas.Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    """OAuth2 password flow token endpoint."""
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not rbac.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=rbac.settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = rbac.create_access_token(
        data={"sub": user.email, "role": user.role, "user_id": user.id},
        expires_delta=access_token_expires,
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/seed", status_code=status.HTTP_200_OK)
def seed_database(db: Session = Depends(get_db)):
    """Seeds the database with test users, students, and sessions for demonstration/testing."""
    # 1. Clean existing records to avoid conflicts and start fresh
    db.query(models.Evaluation).delete()
    db.query(models.Session).delete()
    db.query(models.Student).delete()
    db.query(models.User).delete()
    db.commit()

    # 2. Create Users
    password_hash = rbac.get_password_hash("password123")

    admin = models.User(
        email="admin@bodhrik.com",
        name="Admin User",
        hashed_password=password_hash,
        role="admin",
    )
    teacher1 = models.User(
        email="teacher1@bodhrik.com",
        name="Teacher One",
        hashed_password=password_hash,
        role="teacher",
    )
    teacher2 = models.User(
        email="teacher2@bodhrik.com",
        name="Teacher Two",
        hashed_password=password_hash,
        role="teacher",
    )
    parent1 = models.User(
        email="parent1@bodhrik.com",
        name="Parent One (John & Jane)",
        hashed_password=password_hash,
        role="parent",
    )
    parent2 = models.User(
        email="parent2@bodhrik.com",
        name="Parent Two (Bob)",
        hashed_password=password_hash,
        role="parent",
    )

    db.add_all([admin, teacher1, teacher2, parent1, parent2])
    db.commit()
    db.refresh(teacher1)
    db.refresh(teacher2)
    db.refresh(parent1)
    db.refresh(parent2)

    # 3. Create Students (linked to parents)
    student_john = models.Student(name="John Doe", parent_id=parent1.id)
    student_jane = models.Student(name="Jane Doe", parent_id=parent1.id)
    student_bob = models.Student(name="Bob Smith", parent_id=parent2.id)

    db.add_all([student_john, student_jane, student_bob])
    db.commit()
    db.refresh(student_john)
    db.refresh(student_jane)
    db.refresh(student_bob)

    # 4. Create Sessions
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)

    # Session 1: Teacher 1 teaching John Doe (Parent 1 child)
    session1 = models.Session(
        title="Math Session - Algebra",
        description="Covering quadratic equations.",
        start_time=now - timedelta(hours=2),
        end_time=now - timedelta(hours=1),
        teacher_id=teacher1.id,
        student_id=student_john.id,
    )

    # Session 2: Teacher 1 teaching Jane Doe (Parent 1 child)
    session2 = models.Session(
        title="Science Session - Physics",
        description="Introduction to gravity.",
        start_time=now - timedelta(days=1),
        end_time=now - timedelta(days=1, hours=-1),
        teacher_id=teacher1.id,
        student_id=student_jane.id,
    )

    # Session 3: Teacher 2 teaching Bob Smith (Parent 2 child)
    session3 = models.Session(
        title="History Session - Rome",
        description="Discussing the Roman Empire.",
        start_time=now - timedelta(hours=5),
        end_time=now - timedelta(hours=4),
        teacher_id=teacher2.id,
        student_id=student_bob.id,
    )

    db.add_all([session1, session2, session3])
    db.commit()

    return {
        "message": "Database successfully seeded with 1 Admin, 2 Teachers, 2 Parents, 3 Students, and 3 Sessions."
    }
