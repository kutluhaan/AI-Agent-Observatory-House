"""
Organization Pydantic Schemas — Spec'e uygun request/response modelleri.
"""
import re
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator


# ─── Request Schemas ──────────────────────────────────────

class CreateOrgRequest(BaseModel):
    name: str
    slug: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Organization name must be at least 2 characters.")
        if len(v) > 255:
            raise ValueError("Organization name must be at most 255 characters.")
        return v

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Slug must be at least 2 characters.")
        if len(v) > 100:
            raise ValueError("Slug must be at most 100 characters.")
        if v != v.lower():
            raise ValueError("Slug must be lowercase.")
        if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', v) and len(v) > 1:
            raise ValueError("Slug must contain only lowercase letters, numbers, and hyphens.")
        return v


class UpdateOrgRequest(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Organization name must be at least 2 characters.")
        return v


class UpdateMemberRoleRequest(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ("admin", "member"):
            raise ValueError("Role must be 'admin' or 'member'. Owner role cannot be assigned via invitation.")
        return v


class CreateInvitationRequest(BaseModel):
    email: EmailStr
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v == "owner":
            raise ValueError("Cannot invite with owner role.")
        if v not in ("admin", "member"):
            raise ValueError("Role must be 'admin' or 'member'.")
        return v


# ─── Response Schemas ─────────────────────────────────────

class OrgResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    plan: str
    member_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class OrgCreatedResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MemberResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    full_name: str | None
    role: str
    joined_at: datetime

    model_config = {"from_attributes": True}


class InvitationResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    expires_at: datetime

    model_config = {"from_attributes": True}


class AcceptInvitationResponse(BaseModel):
    organization: dict
    role: str
