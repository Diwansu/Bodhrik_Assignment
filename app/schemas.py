from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from app.models import UserRole, EvaluationStatus

# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None
    user_id: Optional[int] = None

# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    name: str
    role: UserRole

class UserCreate(UserBase):
    password: str = Field(..., min_length=6)

class UserResponse(UserBase):
    id: int

    class Config:
        from_attributes = True

# Student Schemas
class StudentBase(BaseModel):
    name: str
    parent_id: int

class StudentCreate(StudentBase):
    pass

class StudentResponse(StudentBase):
    id: int

    class Config:
        from_attributes = True

# Evaluation Schemas
class EvaluationBase(BaseModel):
    session_id: int

class EvaluationResponse(EvaluationBase):
    id: int
    status: EvaluationStatus
    feedback: Optional[str] = None
    score: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class EvaluationTrigger(BaseModel):
    session_id: int

# Session Schemas
class SessionBase(BaseModel):
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    student_id: int

class SessionCreate(SessionBase):
    # Optional teacher_id for Admin to assign. For Teachers, it defaults to their own ID.
    teacher_id: Optional[int] = None

class SessionUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    student_id: Optional[int] = None
    teacher_id: Optional[int] = None

class SessionResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    teacher_id: int
    student_id: int
    evaluation: Optional[EvaluationResponse] = None

    class Config:
        from_attributes = True
