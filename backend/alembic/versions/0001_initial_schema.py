"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-01

8 tablo oluşturur:
- users
- organizations
- organization_members
- refresh_tokens
- email_verifications
- password_resets
- organization_invitations
- oauth_accounts (Faz 4 için hazır)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def install_updated_at_triggers() -> None:
    op.execute(text("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """))
    for table in ("users", "organizations", "oauth_accounts"):
        op.execute(text(f"""
            CREATE TRIGGER tr_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION set_updated_at();
        """))


def remove_updated_at_triggers() -> None:
    for table in ("oauth_accounts", "organizations", "users"):
        op.execute(text(f"DROP TRIGGER IF EXISTS tr_{table}_updated_at ON {table};"))
    op.execute(text("DROP FUNCTION IF EXISTS set_updated_at();"))


def upgrade() -> None:
    # ─── users ───────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    # ─── organizations ────────────────────────────────────
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("plan", sa.String(50), nullable=False, server_default=sa.text("'free'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_organizations_created_by"),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )
    op.create_index("idx_organizations_slug", "organizations", ["slug"])

    # ─── organization_members ─────────────────────────────
    op.create_table(
        "organization_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name="fk_org_members_org_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_org_members_user_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_member"),
        sa.CheckConstraint("role IN ('owner', 'admin', 'member')", name="ck_org_member_role"),
    )
    op.create_index("idx_org_members_org_id", "organization_members", ["organization_id"])
    op.create_index("idx_org_members_user_id", "organization_members", ["user_id"])

    # ─── refresh_tokens ───────────────────────────────────
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("device_info", sa.String(500), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_refresh_tokens_user_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("idx_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("idx_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"])

    # ─── email_verifications ──────────────────────────────
    op.create_table(
        "email_verifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_email_verifications_user_id",
            ondelete="CASCADE",
        ),
    )

    # ─── password_resets ──────────────────────────────────
    op.create_table(
        "password_resets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_password_resets_user_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("idx_password_resets_user_id", "password_resets", ["user_id"])
    op.create_index("idx_password_resets_token_hash", "password_resets", ["token_hash"])

    # ─── organization_invitations ─────────────────────────
    op.create_table(
        "organization_invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invited_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name="fk_invitations_org_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["invited_by"], ["users.id"],
            name="fk_invitations_invited_by",
        ),
        sa.CheckConstraint("role IN ('admin', 'member')", name="ck_invitation_role"),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'expired', 'cancelled')",
            name="ck_invitation_status",
        ),
    )
    op.create_index("idx_invitations_token_hash", "organization_invitations", ["token_hash"])
    op.create_index("idx_invitations_email", "organization_invitations", ["email"])

    # Aynı org'a aynı email'e iki pending davet gönderilemez — INVITATION_ALREADY_PENDING
    op.create_index("uq_org_invitation_pending_email", "organization_invitations", ["organization_id", "email"], unique=True, postgresql_where=sa.text("status = 'pending'"))

    # ─── oauth_accounts (Faz 4 için hazır) ───────────────
    op.create_table(
        "oauth_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_id", sa.String(255), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_oauth_accounts_user_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("provider", "provider_id", name="uq_oauth_provider_id"),
        sa.CheckConstraint("provider IN ('google', 'github')", name="ck_oauth_provider"),
    )

    install_updated_at_triggers()


def downgrade() -> None:
    # Ters sırada drop et — foreign key bağımlılıkları nedeniyle
    remove_updated_at_triggers()
    op.drop_table("oauth_accounts")
    op.drop_table("organization_invitations")
    op.drop_table("password_resets")
    op.drop_table("email_verifications")
    op.drop_table("refresh_tokens")
    op.drop_table("organization_members")
    op.drop_table("organizations")
    op.drop_table("users")
