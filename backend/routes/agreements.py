from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from auth import get_current_user
from db import agreements_collection
from models import Agreement, AgreementUpdate
from utils import serialize, serialize_list, to_object_id

router = APIRouter(prefix="/agreements", tags=["agreements"])

@router.post("/", status_code=201)
async def create(agreement: Agreement, user: dict = Depends(get_current_user)):
    data = agreement.model_dump(); data.update({"created_at": datetime.utcnow(), "created_by": user["_id"]})
    result = await agreements_collection.insert_one(data)
    return serialize(await agreements_collection.find_one({"_id": result.inserted_id}))

@router.get("/")
async def list_items(lead_id: str | None = None, status: str | None = None, _: dict = Depends(get_current_user)):
    query = {k: v for k, v in {"lead_id": lead_id, "status": status}.items() if v}
    return serialize_list(await agreements_collection.find(query).sort("created_at", -1).to_list(500))

@router.patch("/{agreement_id}")
async def update(agreement_id: str, update: AgreementUpdate, _: dict = Depends(get_current_user)):
    data = update.model_dump(exclude_unset=True)
    if data.get("status") == "signed": data["signed_at"] = datetime.utcnow()
    result = await agreements_collection.update_one({"_id": to_object_id(agreement_id)}, {"$set": data})
    if not result.matched_count: raise HTTPException(404, "Agreement not found")
    return serialize(await agreements_collection.find_one({"_id": to_object_id(agreement_id)}))

@router.delete("/{agreement_id}", status_code=204)
async def remove(agreement_id: str, _: dict = Depends(get_current_user)):
    if not (await agreements_collection.delete_one({"_id": to_object_id(agreement_id)})).deleted_count: raise HTTPException(404, "Agreement not found")
