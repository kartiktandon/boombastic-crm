from datetime import datetime
from re import escape

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import get_current_user
from db import leads_collection, people_collection
from models import PersonCreate, PersonUpdate
from utils import serialize, serialize_list, to_object_id

router = APIRouter(prefix="/people", tags=["people"])


def owner_query(user: dict) -> dict:
    return {"owner_id": user["_id"]}


@router.get("/")
async def list_people(
    include_inactive: bool = Query(False),
    current_user: dict = Depends(get_current_user),
):
    query = owner_query(current_user)
    if not include_inactive:
        query["active"] = {"$ne": False}
    docs = await people_collection.find(query).sort("name", 1).to_list(500)
    return serialize_list(docs)


@router.post("/", status_code=201)
async def create_person(person: PersonCreate, current_user: dict = Depends(get_current_user)):
    data = person.model_dump()
    if data.get("email"):
        duplicate = await people_collection.find_one({
            **owner_query(current_user),
            "email": {"$regex": f"^{escape(data['email'])}$", "$options": "i"},
            "active": {"$ne": False},
        })
        if duplicate:
            raise HTTPException(status_code=400, detail="A person with this email already exists")
    now = datetime.utcnow()
    data.update({"owner_id": current_user["_id"], "active": True, "created_at": now, "updated_at": now})
    result = await people_collection.insert_one(data)
    return serialize(await people_collection.find_one({"_id": result.inserted_id}))


@router.patch("/{person_id}")
async def update_person(
    person_id: str,
    update: PersonUpdate,
    current_user: dict = Depends(get_current_user),
):
    person_oid = to_object_id(person_id)
    query = {"_id": person_oid, **owner_query(current_user)}
    existing = await people_collection.find_one(query)
    if not existing:
        raise HTTPException(status_code=404, detail="Person not found")
    payload = update.model_dump(exclude_unset=True)
    if not payload:
        raise HTTPException(status_code=400, detail="No changes supplied")
    if payload.get("email"):
        duplicate = await people_collection.find_one({
            **owner_query(current_user),
            "_id": {"$ne": person_oid},
            "email": {"$regex": f"^{escape(payload['email'])}$", "$options": "i"},
            "active": {"$ne": False},
        })
        if duplicate:
            raise HTTPException(status_code=400, detail="A person with this email already exists")
    payload["updated_at"] = datetime.utcnow()
    await people_collection.update_one(query, {"$set": payload})
    if "name" in payload and payload["name"] != existing.get("name"):
        await leads_collection.update_many(
            {"assigned_to_id": person_id},
            {"$set": {"assigned_to": payload["name"], "updated_at": datetime.utcnow()}},
        )
    return serialize(await people_collection.find_one(query))


@router.delete("/{person_id}", status_code=204)
async def remove_person(person_id: str, current_user: dict = Depends(get_current_user)):
    result = await people_collection.update_one(
        {"_id": to_object_id(person_id), **owner_query(current_user)},
        {"$set": {"active": False, "updated_at": datetime.utcnow()}},
    )
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Person not found")
