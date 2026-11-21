"""Staff roles and permissions, enforced in code (never by prompts).

Users come from MIRA_STAFF_USERS as "name:role:key" entries separated by commas. The defaults
are demo-only accounts for local use; set your own in .env for anything shared.

Permissions:            staff   approver
  view/edit enquiries     ✓        ✓
  create content drafts   ✓        ✓
  publish/reject drafts   ✗        ✓
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from enum import Enum

from fastapi import Header, HTTPException

from mira.config import get_settings


class Role(str, Enum):
    STAFF = "staff"
    APPROVER = "approver"


class Permission(str, Enum):
    VIEW_ENQUIRIES = "view_enquiries"
    EDIT_ENQUIRIES = "edit_enquiries"
    CREATE_DRAFT = "create_draft"
    PUBLISH_CONTENT = "publish_content"


GRANTS: dict[Role, frozenset[Permission]] = {
    Role.STAFF: frozenset({Permission.VIEW_ENQUIRIES, Permission.EDIT_ENQUIRIES, Permission.CREATE_DRAFT}),
    Role.APPROVER: frozenset(Permission),
}


@dataclass(frozen=True)
class User:
    name: str
    role: Role

    def can(self, permission: Permission) -> bool:
        return permission in GRANTS[self.role]


def load_users(spec: str) -> dict[str, User]:
    users: dict[str, User] = {}
    for entry in filter(None, (e.strip() for e in spec.split(","))):
        name, role, key = (part.strip() for part in entry.split(":", 2))
        users[key] = User(name=name, role=Role(role))
    return users


def authenticate(key: str | None) -> User | None:
    if not key:
        return None
    for known, user in load_users(get_settings().mira_staff_users).items():
        if hmac.compare_digest(known, key):
            return user
    return None


def require(permission: Permission):
    """FastAPI dependency: 401 without a valid staff key, 403 without the permission."""

    def dependency(x_staff_key: str | None = Header(default=None)) -> User:
        user = authenticate(x_staff_key)
        if user is None:
            raise HTTPException(status_code=401, detail="Staff key required.")
        if not user.can(permission):
            raise HTTPException(status_code=403, detail=f"The {user.role.value} role cannot {permission.value}.")
        return user

    return dependency
