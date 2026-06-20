"""
Models package — tüm SQLAlchemy modelleri burada export edilir.

Bu dosyanın import edilmesi Alembic'in tüm tabloları tespit etmesi için şarttır.
alembic/env.py bu modülü import eder → Base.metadata tüm tabloları içerir.
"""
from app.models.user import User
from app.models.organization import Organization, OrganizationMember
from app.models.auth import (
    RefreshToken,
    EmailVerification,
    PasswordReset,
    OrganizationInvitation,
    OAuthAccount,
)
from app.models.provider import ProviderCredential
from app.models.agent import Agent
from app.models.test_suite import TestSuite, TestCase, TestRun, TestCaseResult
from app.models.conversation import Conversation, ConversationMessage
from app.models.agent_file import AgentFile
from app.models.agent_knowledge import AgentKnowledge

__all__ = [
    "User",
    "Organization",
    "OrganizationMember",
    "RefreshToken",
    "EmailVerification",
    "PasswordReset",
    "OrganizationInvitation",
    "OAuthAccount",
    "ProviderCredential",
    "Agent",
    "TestSuite",
    "TestCase",
    "TestRun",
    "TestCaseResult",
    "Conversation",
    "ConversationMessage",
    "AgentFile",
    "AgentKnowledge",
]
