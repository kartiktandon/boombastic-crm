import asyncio

import pytest
from bson import ObjectId
from fastapi import HTTPException

from auth import get_current_user, hash_password, require_admin, verify_password, workspace_id
from models import PasswordChange
from routes import auth as auth_routes, leads


def test_admin_can_edit_any_lead():
    leads.ensure_can_edit({"assigned_to_id": "someone-else"}, {"_id": "admin-1", "role": "admin"})


def test_member_can_edit_assigned_lead():
    leads.ensure_can_edit({"assigned_to_id": "person-1"}, {"_id": "user-1", "person_id": "person-1", "role": "member"})


def test_member_cannot_edit_another_persons_lead():
    with pytest.raises(HTTPException) as error:
        leads.ensure_can_edit({"assigned_to_id": "person-2"}, {"_id": "user-1", "person_id": "person-1", "role": "member"})
    assert error.value.status_code == 403


def test_only_admin_passes_admin_guard():
    require_admin({"role": "admin"})
    with pytest.raises(HTTPException) as error:
        require_admin({"role": "member"})
    assert error.value.status_code == 403


def test_member_uses_admin_workspace_id():
    assert workspace_id({"_id": "user-1", "workspace_id": "admin-1"}) == "admin-1"
    assert workspace_id({"_id": "admin-1"}) == "admin-1"


def test_missing_token_is_not_an_admin_session():
    with pytest.raises(HTTPException) as error:
        asyncio.run(get_current_user(None))
    assert error.value.status_code == 401


class FakeLeadCollection:
    def __init__(self, lead):
        self.lead = lead

    async def find_one(self, query):
        assert query["_id"] == self.lead["_id"]
        return self.lead


def test_editable_lead_checks_assignment(monkeypatch):
    lead_id = ObjectId()
    monkeypatch.setattr(leads, "leads_collection", FakeLeadCollection({"_id": lead_id, "assigned_to_id": "person-2"}))
    with pytest.raises(HTTPException) as error:
        asyncio.run(leads.editable_lead(str(lead_id), {"_id": "user-1", "person_id": "person-1", "role": "member"}))
    assert error.value.status_code == 403


class FakeUsersCollection:
    def __init__(self, user):
        self.user = user

    async def find_one(self, query):
        return self.user if query.get("_id") == self.user["_id"] else None

    async def update_one(self, query, update):
        assert query["_id"] == self.user["_id"]
        self.user.update(update["$set"])


def test_user_can_change_own_password(monkeypatch):
    user_id = ObjectId()
    users = FakeUsersCollection({"_id": user_id, "hashed_password": hash_password("old-password")})
    monkeypatch.setattr(auth_routes, "users_collection", users)
    result = asyncio.run(auth_routes.change_password(
        PasswordChange(current_password="old-password", new_password="new-password"),
        {"_id": str(user_id), "role": "member"},
    ))
    assert result["message"] == "Password changed successfully"
    assert verify_password("new-password", users.user["hashed_password"])


def test_password_change_requires_current_password(monkeypatch):
    user_id = ObjectId()
    users = FakeUsersCollection({"_id": user_id, "hashed_password": hash_password("old-password")})
    monkeypatch.setattr(auth_routes, "users_collection", users)
    with pytest.raises(HTTPException) as error:
        asyncio.run(auth_routes.change_password(
            PasswordChange(current_password="wrong-password", new_password="new-password"),
            {"_id": str(user_id), "role": "admin"},
        ))
    assert error.value.status_code == 400
