"""
Auth Pydantic Schemas — Request/Response modelleri.

Spec'teki API contract ile birebir uyumlu.
Her field'ın validasyonu spec'teki kurallara göre yapılır.
"""
import uuid

from pydantic import BaseModel, EmailStr, field_validator


# ─── Request Schemas ──────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Full name must be at least 2 characters.")
        if len(v) > 255:
            raise ValueError("Full name must be at most 255 characters.")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ─── Response Schemas ─────────────────────────────────────

class OrgSummary(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    role: str

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    is_verified: bool
    avatar_url: str | None = None

    model_config = {"from_attributes": True}


class RegisterResponse(BaseModel):
    message: str
    user_id: str


class LoginResponse(BaseModel):
    user: UserResponse
    organizations: list[OrgSummary]


class MessageResponse(BaseModel):
    message: str
