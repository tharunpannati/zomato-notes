"""
schemas.py — Pydantic request/response schemas for User and Note.
Part 1A — Task 2
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# User schemas
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    name:     str       = Field(..., description="Display name of the user")
    email:    EmailStr
    password: str       = Field(..., min_length=8)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("name must not be empty or whitespace-only")
        return v.strip()


class UserResponse(BaseModel):
    id:         int
    name:       str
    email:      EmailStr
    created_at: datetime

    # password is intentionally omitted from this response schema

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Note schemas
# ---------------------------------------------------------------------------

class NoteCreate(BaseModel):
    title:    str = Field(..., min_length=1, max_length=120)
    content:  str = Field(..., min_length=1)
    tag:      Optional[str] = None
    owner_id: int


class NoteUpdate(BaseModel):
    title:   Optional[str] = Field(None, min_length=1, max_length=120)
    content: Optional[str] = Field(None, min_length=1)
    tag:     Optional[str] = None


class NoteResponse(BaseModel):
    id:         int
    title:      str
    content:    str
    tag:        Optional[str]
    owner_id:   int
    created_at: datetime

    model_config = {"from_attributes": True}


class NoteResponseWithAI(NoteResponse):
    """Extended response returned by POST /notes — includes the AI suggestion field."""
    ai_suggestion: Optional[dict] = None
