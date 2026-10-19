"""DeskFlow demo-data seed (idempotent).

Usage (from the ``backend`` directory)::

    python -m app.db.seed

Reads ``DATABASE_URL`` from the environment (via ``app.core.config``). If the
demo admin account already exists the script prints ``already seeded`` and
exits ``0``. Every seeded ticket, comment and audit entry is created through
the same services the API uses, so behaviour and audit trails stay consistent.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.category import Category
from app.models.enums import AuditAction, TicketPriority, TicketStatus, UserRole
from app.models.notification import Notification
from app.models.sla_policy import SlaPolicy
from app.models.ticket import Ticket
from app.models.ticket_comment import TicketComment
from app.models.user import User
from app.repositories import (
    category_repository,
    sla_policy_repository,
    user_repository,
)
from app.schemas.category import CategoryCreate
from app.schemas.ticket import TicketCreate, TicketStatusUpdate
from app.schemas.user import UserCreate
from app.services import (
    assignment_service,
    audit_service,
    category_service,
    comment_service,
    sla_service,
    ticket_service,
    user_service,
)

ADMIN_EMAIL = "admin@deskflow.dev"
ADMIN_PASSWORD = "Admin@1234"
ADMIN_NAME = "Carla Mendes"
AGENT_PASSWORD = "Agent@1234"
REQUESTER_PASSWORD = "Requester@1234"

AGENT_NAMES = ["Bruno Costa", "Diogo Ferreira", "Elena Rocha"]
REQUESTER_NAMES = ["Ana Silva", "Rui Martins", "Sofia Almeida", "Tiago Costa", "Helena Ferreira"]

CATEGORIES: list[tuple[str, str]] = [
    ("Hardware", "Laptops, desktops, monitors and peripherals"),
    ("Software", "Installed applications, licences and updates"),
    ("Network", "Wired and wireless connectivity, VPN and DNS"),
    ("Access & Accounts", "Accounts, roles and access requests"),
    ("Email", "Mailboxes, distribution lists and deliverability"),
    ("Other", "Anything that does not fit the categories above"),
]

SLA_POLICIES: dict[TicketPriority, tuple[int, int]] = {
    TicketPriority.CRITICAL: (60, 240),
    TicketPriority.HIGH: (240, 1440),
    TicketPriority.MEDIUM: (480, 2880),
    TicketPriority.LOW: (1440, 4320),
}

REQUESTER_NOTES = [
    "Any update on this? It is blocking my work.",
    "This is still happening again this morning.",
    "I have attached a screenshot of the exact error.",
    "Happy to jump on a quick call if that is easier.",
    "Thanks, it looks a bit better after the last change.",
]

AGENT_NOTES = [
    "Thanks for reporting - I am taking a look now.",
    "I can reproduce this on my machine, investigating the root cause.",
    "Escalating to the second-line team, will keep you posted.",
    "Could you try again after clearing your local cache?",
]

INTERNAL_NOTES = [
    "Checked the asset records - this device is now out of warranty.",
    "Root cause looks like the last group policy update.",
    "Waiting on the vendor ticket before we can close this one.",
    "Reset already performed, monitoring for recurrence.",
]

P = TicketPriority
S = TicketStatus


@dataclass(frozen=True)
class Scenario:
    title: str
    description: str
    category: str
    priority: TicketPriority
    status: TicketStatus
    created_minutes: int
    response_minutes: int | None
    resolve_minutes: int | None
    paused_minutes: int | None
    assigned: bool
    comments: int
    paused_seconds: int = 0


CONTENT: list[tuple[str, str, str]] = [
    (
        "Laptop will not power on after update",
        "Since the firmware update yesterday the laptop shows no signs of life; "
        "a different charger and dock made no difference.",
        "Hardware",
    ),
    (
        "Monitor flickering on external display",
        "The second monitor flickers constantly on the dock; dropping to 60Hz "
        "reduces the flicker but does not remove it.",
        "Hardware",
    ),
    (
        "Docking station not detecting keyboard",
        "The new USB-C dock drives the monitor but the keyboard and mouse are "
        "completely ignored on every port.",
        "Hardware",
    ),
    (
        "Printer jams on every duplex job",
        "The department printer jams whenever double-sided printing is enabled.",
        "Hardware",
    ),
    (
        "Battery drains within an hour",
        "The laptop drops from full to twenty percent in under an hour of light browsing.",
        "Hardware",
    ),
    (
        "VPN drops every few minutes",
        "The corporate VPN disconnects roughly every five minutes and reconnects on its own.",
        "Network",
    ),
    (
        "WiFi keeps dropping in meeting room 4",
        "Calls cut out whenever I sit at the far end of meeting room 4.",
        "Network",
    ),
    (
        "Cannot reach the finance file share",
        "Mapping the finance file share fails with a network path not found error "
        "since this morning.",
        "Network",
    ),
    (
        "Slow internet on the second floor",
        "Pages take more than ten seconds to load; a speed test shows three Mbps.",
        "Network",
    ),
    (
        "DNS resolution fails intermittently",
        "Some internal hostnames fail to resolve until I flush the DNS cache.",
        "Network",
    ),
    (
        "Outlook keeps asking for password",
        "Outlook prompts for credentials repeatedly even though the password is correct.",
        "Email",
    ),
    (
        "Mailbox over quota warning",
        "I keep getting storage warnings and can no longer send new mail.",
        "Email",
    ),
    (
        "Mails to external domains bounce back",
        "External recipients get a relay error while internal mail is delivered.",
        "Email",
    ),
    (
        "Distribution list not receiving mail",
        "Mail sent to the IT support alias is not reaching any member of the list.",
        "Email",
    ),
    (
        "Cannot add shared mailbox in Outlook",
        "The shared calendar mailbox returns a cannot expand the folder error.",
        "Email",
    ),
    (
        "Excel crashes when opening large file",
        "The quarterly model crashes Excel on open since the latest update.",
        "Software",
    ),
    (
        "Browser fails to launch after update",
        "The browser opens then immediately closes with no error message shown.",
        "Software",
    ),
    (
        "Slack cannot join any calls",
        "Audio and video never connect; the call stays stuck on connecting.",
        "Software",
    ),
    (
        "License activation error for design suite",
        "The creative suite reports an expired licence despite an active plan.",
        "Software",
    ),
    (
        "Screen share shows only a black screen",
        "Screen sharing is black for participants while audio still works.",
        "Software",
    ),
    (
        "Password reset for the finance system",
        "Locked out after too many attempts; need a reset to the registered email.",
        "Access & Accounts",
    ),
    (
        "Access request for the reporting dashboard",
        "I need read access to the sales reporting dashboard for my new role.",
        "Access & Accounts",
    ),
    (
        "MFA device lost - cannot log in",
        "My phone with the authenticator app was replaced; I need MFA reset.",
        "Access & Accounts",
    ),
    (
        "New starter account provisioning",
        "A new hire starts on Monday; please create the account and standard groups.",
        "Access & Accounts",
    ),
    (
        "Shared drive permissions missing",
        "After the role change I lost access to the marketing shared drive.",
        "Access & Accounts",
    ),
    (
        "Second monitor request",
        "Requesting a larger monitor to match the new desk layout.",
        "Other",
    ),
    (
        "Meeting room AV not working",
        "The projector shows no signal from the HDMI cable in room 2.",
        "Other",
    ),
    (
        "Printer toner replacement needed",
        "The colour printer is showing low toner on cyan.",
        "Other",
    ),
    (
        "Software licence invoice query",
        "Finance needs the invoice reference for the security tool renewal.",
        "Other",
    ),
    (
        "Standing desk stopped adjusting",
        "The height adjustment does nothing after a brief power dip.",
        "Other",
    ),
    (
        "Laptop running very hot and loud",
        "The fans spin at full speed during simple tasks and the base gets hot.",
        "Hardware",
    ),
    (
        "Webcam not detected in meetings",
        "The camera is missing from the device list after the dock was swapped.",
        "Hardware",
    ),
    (
        "File server extremely slow at month end",
        "Reads to the shared drive take minutes during month-end close.",
        "Network",
    ),
    (
        "Outgoing mail flagged as spam",
        "Messages from our sales alias land in customer spam folders.",
        "Email",
    ),
    (
        "Cannot install approved software",
        "The installer is blocked by policy even though the app is on the allow list.",
        "Software",
    ),
    (
        "Account locked after password change",
        "I changed my password and now every service rejects it.",
        "Access & Accounts",
    ),
    (
        "Access to source control repository",
        "I need write access to the release repository for my team.",
        "Access & Accounts",
    ),
    (
        "Screen goes black when docking",
        "The external screen goes black whenever the laptop is docked.",
        "Hardware",
    ),
    (
        "Report export times out",
        "CSV export from the portal times out for date ranges over one month.",
        "Software",
    ),
    (
        "WiFi certificate warning",
        "The corporate network prompts an invalid certificate warning on connect.",
        "Network",
    ),
]

TIMING: list[tuple] = [
    (P.CRITICAL, S.OPEN, 1440, None, None, None, False, 4),
    (P.HIGH, S.OPEN, 2880, None, None, None, False, 0),
    (P.MEDIUM, S.OPEN, 4320, None, None, None, True, 4),
    (P.LOW, S.OPEN, 5760, None, None, None, False, 0),
    (P.CRITICAL, S.OPEN, 50, None, None, None, False, 0),
    (P.HIGH, S.OPEN, 200, None, None, None, False, 4),
    (P.MEDIUM, S.OPEN, 400, None, None, None, True, 0),
    (P.LOW, S.OPEN, 120, None, None, None, False, 0),
    (P.MEDIUM, S.OPEN, 120, None, None, None, True, 4),
    (P.HIGH, S.OPEN, 60, None, None, None, True, 0),
    (P.CRITICAL, S.OPEN, 20, None, None, None, True, 0),
    (P.HIGH, S.IN_PROGRESS, 2880, 120, None, None, True, 6),
    (P.MEDIUM, S.IN_PROGRESS, 4320, 240, None, None, True, 0),
    (P.MEDIUM, S.IN_PROGRESS, 2400, 240, None, None, True, 0),
    (P.LOW, S.IN_PROGRESS, 3600, 600, None, None, True, 4),
    (P.HIGH, S.IN_PROGRESS, 600, 120, None, None, True, 0, 3600),
    (P.MEDIUM, S.IN_PROGRESS, 600, 240, None, None, True, 0),
    (P.CRITICAL, S.IN_PROGRESS, 90, 30, None, None, True, 0),
    (P.LOW, S.IN_PROGRESS, 1440, 480, None, None, True, 4),
    (P.MEDIUM, S.ON_HOLD, 2880, 120, None, 2820, True, 0),
    (P.HIGH, S.ON_HOLD, 2880, 60, None, 2850, True, 0),
    (P.CRITICAL, S.ON_HOLD, 1440, 30, None, 1410, True, 0),
    (P.LOW, S.ON_HOLD, 4320, 240, None, 4300, True, 0),
    (P.MEDIUM, S.RESOLVED, 7200, 120, 1440, None, True, 6),
    (P.HIGH, S.RESOLVED, 5760, 120, 600, None, True, 0),
    (P.LOW, S.RESOLVED, 8640, 480, 2880, None, True, 4),
    (P.CRITICAL, S.RESOLVED, 4320, 30, 120, None, True, 0),
    (P.HIGH, S.RESOLVED, 10080, 120, 2880, None, True, 0),
    (P.MEDIUM, S.RESOLVED, 8640, 240, 4320, None, True, 4),
    (P.MEDIUM, S.CLOSED, 7200, 120, 1440, None, True, 0),
    (P.HIGH, S.CLOSED, 5760, 120, 600, None, True, 4),
    (P.CRITICAL, S.CLOSED, 4320, 30, 120, None, True, 0),
    (P.LOW, S.CLOSED, 8640, 480, 2880, None, True, 4),
    (P.MEDIUM, S.CLOSED, 64800, 240, 2880, None, True, 0),
    (P.HIGH, S.CLOSED, 56160, 120, 1440, None, True, 0),
    (P.HIGH, S.REOPENED, 10080, 120, 2880, None, True, 4),
    (P.MEDIUM, S.REOPENED, 8640, 240, 2880, None, True, 0),
    (P.LOW, S.REOPENED, 10080, 480, 2880, None, True, 6),
    (P.CRITICAL, S.RESOLVED, 2160, 20, 90, None, True, 0),
    (P.HIGH, S.ON_HOLD, 10080, 100, None, 10060, True, 0),
]

_TRANSITION_PATHS: dict[TicketStatus, list[TicketStatus]] = {
    S.OPEN: [],
    S.IN_PROGRESS: [S.IN_PROGRESS],
    S.ON_HOLD: [S.IN_PROGRESS, S.ON_HOLD],
    S.RESOLVED: [S.IN_PROGRESS, S.RESOLVED],
    S.CLOSED: [S.IN_PROGRESS, S.RESOLVED, S.CLOSED],
    S.REOPENED: [S.IN_PROGRESS, S.RESOLVED, S.REOPENED],
}

_REQUESTER_TRANSITIONS = {S.CLOSED, S.REOPENED}


def _scenarios() -> list[Scenario]:
    return [Scenario(*content, *timing) for content, timing in zip(CONTENT, TIMING, strict=True)]


def _seed_users(db: Session) -> dict[str, User | list[User]]:
    admin = user_repository.create(
        db,
        email=ADMIN_EMAIL,
        full_name=ADMIN_NAME,
        hashed_password=hash_password(ADMIN_PASSWORD),
        role=UserRole.ADMIN,
    )
    audit_service.record(
        db,
        actor=None,
        action=AuditAction.USER_CREATED,
        entity_type="user",
        entity_id=admin.id,
        new_value={"email": admin.email, "role": admin.role.value},
    )

    agents = [
        user_service.create_user(
            db,
            actor=admin,
            payload=UserCreate(
                email=f"agent{index + 1}@deskflow.dev",
                full_name=name,
                password=AGENT_PASSWORD,
                role=UserRole.AGENT,
            ),
        )
        for index, name in enumerate(AGENT_NAMES)
    ]
    requesters = [
        user_service.create_user(
            db,
            actor=admin,
            payload=UserCreate(
                email=f"requester{index + 1}@deskflow.dev",
                full_name=name,
                password=REQUESTER_PASSWORD,
                role=UserRole.REQUESTER,
            ),
        )
        for index, name in enumerate(REQUESTER_NAMES)
    ]
    return {"admin": admin, "agents": agents, "requesters": requesters}


def _seed_categories(db: Session, *, admin: User) -> dict[str, Category]:
    categories: dict[str, Category] = {}
    for name, description in CATEGORIES:
        existing = category_repository.get_by_name(db, name)
        if existing is None:
            existing = category_service.create_category(
                db, actor=admin, payload=CategoryCreate(name=name, description=description)
            )
        categories[name] = existing
    return categories


def _ensure_sla_policies(db: Session) -> None:
    existing = {policy.priority for policy in sla_policy_repository.list_all(db)}
    for priority, (first_response, resolution) in SLA_POLICIES.items():
        if priority not in existing:
            db.add(
                SlaPolicy(
                    priority=priority,
                    first_response_minutes=first_response,
                    resolution_minutes=resolution,
                )
            )
    db.flush()


def _add_comments(db: Session, *, ticket: Ticket, requester: User, agent: User, count: int) -> None:
    for position in range(count):
        if position % 2 == 1:
            internal = (position // 2) % 2 == 1
            comment_service.add_comment(
                db,
                ticket=ticket,
                author=agent,
                body=INTERNAL_NOTES[position % len(INTERNAL_NOTES)]
                if internal
                else AGENT_NOTES[position % len(AGENT_NOTES)],
                is_public=not internal,
            )
        else:
            comment_service.add_comment(
                db,
                ticket=ticket,
                author=requester,
                body=REQUESTER_NOTES[position % len(REQUESTER_NOTES)],
                is_public=True,
            )


def _build_ticket(
    db: Session,
    *,
    scenario: Scenario,
    index: int,
    users: dict[str, User | list[User]],
    categories: dict[str, Category],
) -> Ticket:
    admin = users["admin"]
    agents = users["agents"]
    requesters = users["requesters"]
    assert isinstance(admin, User)
    assert isinstance(agents, list) and isinstance(requesters, list)

    requester = requesters[index % len(requesters)]
    now = datetime.now(UTC)
    created_at = now - timedelta(minutes=scenario.created_minutes)

    ticket = ticket_service.create(
        db,
        actor=requester,
        payload=TicketCreate(
            title=scenario.title,
            description=scenario.description,
            category_id=categories[scenario.category].id,
            priority=scenario.priority,
            auto_assign=False,
        ),
    )
    ticket.created_at = created_at
    policy = sla_policy_repository.get(db, scenario.priority)
    assert policy is not None
    first_response_due_at, resolution_due_at = sla_service.compute_due_dates(created_at, policy)
    if scenario.paused_seconds:
        shift = timedelta(seconds=scenario.paused_seconds)
        first_response_due_at += shift
        resolution_due_at += shift
    ticket.first_response_due_at = first_response_due_at
    ticket.resolution_due_at = resolution_due_at
    db.flush()

    if scenario.assigned:
        if index % 2 == 0:
            assignment_service.auto_assign(db, ticket=ticket)
        else:
            assignment_service.admin_assign(
                db,
                ticket=ticket,
                assignee_id=agents[index % len(agents)].id,
                actor=admin,
            )

    agent_actor = ticket.assignee or agents[index % len(agents)]
    for status in _TRANSITION_PATHS[scenario.status]:
        actor = requester if status in _REQUESTER_TRANSITIONS else agent_actor
        ticket_service.transition(
            db,
            actor=actor,
            ticket_id=ticket.id,
            payload=TicketStatusUpdate(status=status),
        )

    if scenario.comments:
        _add_comments(
            db,
            ticket=ticket,
            requester=requester,
            agent=agent_actor,
            count=scenario.comments,
        )

    ticket.first_responded_at = (
        created_at + timedelta(minutes=scenario.response_minutes)
        if scenario.response_minutes is not None
        else None
    )
    ticket.resolved_at = (
        created_at + timedelta(minutes=scenario.resolve_minutes)
        if scenario.resolve_minutes is not None
        else None
    )
    ticket.paused_at = (
        now - timedelta(minutes=scenario.paused_minutes)
        if scenario.paused_minutes is not None
        else None
    )
    ticket.total_paused_seconds = scenario.paused_seconds
    db.flush()

    sla_service.evaluate_and_persist(db, ticket, now)
    return ticket


def seed_database(db: Session) -> dict[str, int]:
    users = _seed_users(db)
    categories = _seed_categories(db, admin=users["admin"])
    _ensure_sla_policies(db)

    for index, scenario in enumerate(_scenarios()):
        _build_ticket(db, scenario=scenario, index=index, users=users, categories=categories)
    db.flush()

    return {
        "users": len(users["agents"]) + len(users["requesters"]) + 1,
        "categories": len(CATEGORIES),
        "sla_policies": len(SLA_POLICIES),
        "tickets": _count(db, Ticket),
        "comments": _count(db, TicketComment),
        "audit_entries": _count(db, AuditLog),
        "notifications": _count(db, Notification),
    }


def _count(db: Session, model: type) -> int:
    return db.scalar(select(func.count()).select_from(model))


def main() -> int:
    with SessionLocal() as db:
        if user_repository.get_by_email(db, ADMIN_EMAIL) is not None:
            print("already seeded")
            return 0

        summary = seed_database(db)
        db.commit()

    print("DeskFlow demo data seeded.")
    print(f"  users ............ {summary['users']} (1 admin, 3 agents, 5 requesters)")
    print(f"  categories ....... {summary['categories']}")
    print(f"  SLA policies ..... {summary['sla_policies']}")
    print(f"  tickets .......... {summary['tickets']}")
    print(f"  comments ......... {summary['comments']}")
    print(f"  audit entries .... {summary['audit_entries']}")
    print(f"  notifications .... {summary['notifications']}")
    print("Credentials:")
    print(f"  admin      {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    print("  agents     agent1@deskflow.dev .. agent3@deskflow.dev / Agent@1234")
    print("  requesters requester1@deskflow.dev .. requester5@deskflow.dev / Requester@1234")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
