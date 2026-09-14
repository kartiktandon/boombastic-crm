import asyncio

from bson import ObjectId
from fastapi import HTTPException

from routes import leads


class FakePeopleCollection:
    def __init__(self, person=None):
        self.person = person
        self.query = None

    async def find_one(self, query):
        self.query = query
        return self.person


def test_resolve_assignee_uses_directory_name(monkeypatch):
    person_id = str(ObjectId())
    collection = FakePeopleCollection({"_id": ObjectId(person_id), "name": "Rahul Mehta"})
    monkeypatch.setattr(leads, "people_collection", collection)
    payload = {"assigned_to_id": person_id, "assigned_to": "Outdated Name"}

    asyncio.run(leads.resolve_assignee(payload, {"_id": "owner-1"}))

    assert payload["assigned_to"] == "Rahul Mehta"
    assert collection.query["owner_id"] == "owner-1"


def test_resolve_assignee_preserves_legacy_name():
    payload = {"assigned_to_id": None, "assigned_to": "Existing Assignee"}

    asyncio.run(leads.resolve_assignee(payload, {"_id": "owner-1"}))

    assert payload == {"assigned_to_id": None, "assigned_to": "Existing Assignee"}


def test_resolve_assignee_rejects_unavailable_person(monkeypatch):
    monkeypatch.setattr(leads, "people_collection", FakePeopleCollection())
    payload = {"assigned_to_id": str(ObjectId())}

    try:
        asyncio.run(leads.resolve_assignee(payload, {"_id": "owner-1"}))
    except HTTPException as error:
        assert error.status_code == 400
        assert error.detail == "Selected person is not available"
    else:
        raise AssertionError("Unavailable people must not be assignable")
