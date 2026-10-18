"""0001_initial - full schema, enums, indexes, audit trigger, seed rows.

Revision ID: 0001_initial
Revises: c8cb86a7cf62
Create Date: 2026-10-18

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = "c8cb86a7cf62"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

USER_ROLE = postgresql.ENUM("requester", "agent", "admin", name="user_role")
TICKET_STATUS = postgresql.ENUM(
    "OPEN", "IN_PROGRESS", "ON_HOLD", "RESOLVED", "CLOSED", "REOPENED", name="ticket_status"
)
TICKET_PRIORITY = postgresql.ENUM("LOW", "MEDIUM", "HIGH", "CRITICAL", name="ticket_priority")
NOTIFICATION_TYPE = postgresql.ENUM(
    "TICKET_ASSIGNED",
    "COMMENT_ADDED",
    "STATUS_CHANGED",
    "SLA_AT_RISK",
    "SLA_BREACHED",
    name="notification_type",
)

USER_ROLE_COL = postgresql.ENUM("requester", "agent", "admin", name="user_role", create_type=False)
TICKET_STATUS_COL = postgresql.ENUM(
    "OPEN", "IN_PROGRESS", "ON_HOLD", "RESOLVED", "CLOSED", "REOPENED",
    name="ticket_status",
    create_type=False,
)
TICKET_PRIORITY_COL = postgresql.ENUM(
    "LOW", "MEDIUM", "HIGH", "CRITICAL", name="ticket_priority", create_type=False
)
NOTIFICATION_TYPE_COL = postgresql.ENUM(
    "TICKET_ASSIGNED",
    "COMMENT_ADDED",
    "STATUS_CHANGED",
    "SLA_AT_RISK",
    "SLA_BREACHED",
    name="notification_type",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    USER_ROLE.create(bind, checkfirst=True)
    TICKET_STATUS.create(bind, checkfirst=True)
    TICKET_PRIORITY.create(bind, checkfirst=True)
    NOTIFICATION_TYPE.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            USER_ROLE_COL,
            server_default=sa.text("'requester'"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role", "users", ["role"], unique=False)

    op.create_table(
        "categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_categories_name", "categories", ["name"], unique=True)

    op.create_table(
        "sla_policies",
        sa.Column("priority", TICKET_PRIORITY_COL, nullable=False),
        sa.Column("first_response_minutes", sa.Integer(), nullable=False),
        sa.Column("resolution_minutes", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("priority"),
    )
    op.execute(
        """
        INSERT INTO sla_policies (priority, first_response_minutes, resolution_minutes) VALUES
            ('CRITICAL', 60, 240),
            ('HIGH', 240, 1440),
            ('MEDIUM', 480, 2880),
            ('LOW', 1440, 4320)
        ON CONFLICT (priority) DO NOTHING
        """
    )

    op.create_table(
        "counters",
        sa.Column("name", sa.String(length=30), nullable=False),
        sa.Column("value", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("name"),
    )
    op.execute("INSERT INTO counters (name, value) VALUES ('ticket', 1040) ON CONFLICT (name) DO NOTHING")

    op.create_table(
        "tickets",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("ticket_number", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", TICKET_STATUS_COL, server_default=sa.text("'OPEN'"), nullable=False),
        sa.Column("priority", TICKET_PRIORITY_COL, server_default=sa.text("'MEDIUM'"), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requester_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assignee_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("auto_assigned", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("first_response_due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolution_due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_paused_seconds", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("sla_breached", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"], name="fk_tickets_assignee", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], name="fk_tickets_category", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requester_id"], ["users.id"], name="fk_tickets_requester", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_tickets_ticket_number", "tickets", ["ticket_number"], unique=True)
    op.create_index("ix_tickets_status", "tickets", ["status"], unique=False)
    op.create_index("ix_tickets_priority", "tickets", ["priority"], unique=False)
    op.create_index("ix_tickets_assignee", "tickets", ["assignee_id"], unique=False)
    op.create_index("ix_tickets_requester", "tickets", ["requester_id"], unique=False)
    op.create_index("ix_tickets_category", "tickets", ["category_id"], unique=False)
    op.create_index("ix_tickets_created_at", "tickets", [sa.text("created_at DESC")], unique=False)
    op.create_index(
        "ix_tickets_sla_breached",
        "tickets",
        ["sla_breached"],
        unique=False,
        postgresql_where=sa.text("sla_breached = true"),
    )
    op.create_index(
        "ix_tickets_status_created",
        "tickets",
        ["status", sa.text("created_at DESC")],
        unique=False,
    )

    op.create_table(
        "ticket_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_role", USER_ROLE_COL, nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_public", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], name="fk_comments_author", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], name="fk_comments_ticket", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_comments_ticket_created", "ticket_comments", ["ticket_id", "created_at"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_role", USER_ROLE_COL, nullable=True),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("entity_type", sa.String(length=30), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("old_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], name="fk_audit_actor", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], name="fk_audit_ticket", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_ticket", "audit_logs", ["ticket_id", "created_at"], unique=False)
    op.create_index("ix_audit_actor", "audit_logs", ["actor_id"], unique=False)
    op.create_index("ix_audit_action", "audit_logs", ["action"], unique=False)
    op.create_index("ix_audit_created", "audit_logs", [sa.text("created_at DESC")], unique=False)

    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_audit_logs_immutable() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is append-only: UPDATE/DELETE are not allowed';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_logs_immutable
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION trg_audit_logs_immutable()
        """
    )

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", NOTIFICATION_TYPE_COL, nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_read", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], name="fk_notifications_ticket", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_notifications_user", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notifications_user_created",
        "notifications",
        ["user_id", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_notifications_unread",
        "notifications",
        ["user_id"],
        unique=False,
        postgresql_where=sa.text("is_read = false"),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_refresh_user", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_refresh_tokens_hash", "refresh_tokens", ["token_hash"], unique=True)
    op.create_index("ix_refresh_user", "refresh_tokens", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_table("refresh_tokens")
    op.drop_table("notifications")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_logs_immutable ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS audit_logs_immutable()")
    op.drop_table("audit_logs")
    op.drop_table("ticket_comments")
    op.drop_table("tickets")
    op.drop_table("counters")
    op.drop_table("sla_policies")
    op.drop_table("categories")
    op.drop_table("users")
    for enum in (NOTIFICATION_TYPE, TICKET_STATUS, TICKET_PRIORITY, USER_ROLE):
        enum.drop(op.get_bind(), checkfirst=True)
