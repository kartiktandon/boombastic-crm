from datetime import datetime
from re import escape
from bson import ObjectId

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import get_current_user, hash_password, require_admin, workspace_id
from db import leads_collection, people_collection, users_collection
from models import PersonCreate, PersonUpdate
from utils import serialize, serialize_list, to_object_id

router = APIRouter(prefix="/people", tags=["people"])


def owner_query(user: dict) -> dict:
    return {"owner_id": workspace_id(user)}


@router.get("/")
async def list_people(
    include_inactive: bool = Query(False),
    current_user: dict = Depends(get_current_user),
):
    query = owner_query(current_user)
    if not include_inactive:
        query["active"] = {"$ne": False}
    docs = await people_collection.find(query).sort("name", 1).to_list(500)
    for person in docs:
        account = await users_collection.find_one({"person_id": str(person["_id"])}, {"role": 1, "active": 1})
        person["role"] = (account or {}).get("role", "member")
        person["login_enabled"] = bool(account and account.get("active", True))
    return serialize_list(docs)


@router.post("/", status_code=201)
async def create_person(person: PersonCreate, current_user: dict = Depends(get_current_user)):
    require_admin(current_user)
    data = person.model_dump()
    password, role = data.pop("password"), data.pop("role")
    if data.get("email"):
        duplicate = await people_collection.find_one({
            **owner_query(current_user),
            "email": {"$regex": f"^{escape(data['email'])}$", "$options": "i"},
            "active": {"$ne": False},
        })
        if duplicate:
            raise HTTPException(status_code=400, detail="A person with this email already exists")
    if await users_collection.find_one({"email": {"$regex": f"^{escape(data['email'])}$", "$options": "i"}}):
        raise HTTPException(status_code=400, detail="A login account with this email already exists")
    now = datetime.utcnow()
    person_id, user_id = ObjectId(), ObjectId()
    data.update({"_id": person_id, "owner_id": workspace_id(current_user), "user_id": str(user_id), "active": True, "created_at": now, "updated_at": now})
    account = {"_id": user_id, "person_id": str(person_id), "workspace_id": workspace_id(current_user), "name": data["name"], "email": data["email"], "hashed_password": hash_password(password), "role": role, "active": True, "created_at": now}
    await users_collection.insert_one(account)
    try:
        await people_collection.insert_one(data)
    except Exception:
        await users_collection.delete_one({"_id": user_id})
        raise
    result = serialize(await people_collection.find_one({"_id": person_id}))
    result.update({"role": role, "login_enabled": True})
    return result


@router.patch("/{person_id}")
async def update_person(
    person_id: str,
    update: PersonUpdate,
    current_user: dict = Depends(get_current_user),
):
    require_admin(current_user)
    person_oid = to_object_id(person_id)
    query = {"_id": person_oid, **owner_query(current_user)}
    existing = await people_collection.find_one(query)
    if not existing:
        raise HTTPException(status_code=404, detail="Person not found")
    payload = update.model_dump(exclude_unset=True)
    password, role = payload.pop("password", None), payload.pop("role", None)
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
    account = await users_collection.find_one({"person_id": person_id})
    account_values = {}
    if "name" in payload: account_values["name"] = payload["name"]
    if "email" in payload and payload["email"]: account_values["email"] = payload["email"]
    if role: account_values["role"] = role
    if password: account_values["hashed_password"] = hash_password(password)
    if account:
        if account_values: await users_collection.update_one({"_id": account["_id"]}, {"$set": account_values})
    elif password and (payload.get("email") or existing.get("email")):
        email = payload.get("email") or existing.get("email")
        await users_collection.insert_one({"person_id": person_id, "workspace_id": workspace_id(current_user), "name": payload.get("name") or existing["name"], "email": email, "hashed_password": hash_password(password), "role": role or "member", "active": True, "created_at": datetime.utcnow()})
    if "name" in payload and payload["name"] != existing.get("name"):
        await leads_collection.update_many(
            {"assigned_to_id": person_id},
            {"$set": {"assigned_to": payload["name"], "updated_at": datetime.utcnow()}},
        )
    result = serialize(await people_collection.find_one(query))
    result.update({"role": role or (account or {}).get("role", "member"), "login_enabled": True})
    return result


@router.delete("/{person_id}", status_code=204)
async def remove_person(person_id: str, current_user: dict = Depends(get_current_user)):
    require_admin(current_user)
    result = await people_collection.update_one(
        {"_id": to_object_id(person_id), **owner_query(current_user)},
        {"$set": {"active": False, "updated_at": datetime.utcnow()}},
    )
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Person not found")
    await users_collection.update_one({"person_id": person_id}, {"$set": {"active": False}})
