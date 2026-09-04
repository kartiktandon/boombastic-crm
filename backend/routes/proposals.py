from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from auth import get_current_user
from db import proposals_collection
from models import Proposal, ProposalUpdate
from utils import serialize, serialize_list, to_object_id

router = APIRouter(prefix="/proposals", tags=["proposals"])

def totals(data):
    subtotal = sum(item["qty"] * item["price"] for item in data.get("line_items", []))
    taxable = max(subtotal - data.get("discount", 0), 0)
    data.update({"subtotal": subtotal, "amount": taxable, "tax_amount": taxable * data.get("tax_rate", 0) / 100, "grand_total": taxable * (1 + data.get("tax_rate", 0) / 100)})
    return data

@router.post("/", status_code=201)
async def create(proposal: Proposal, user: dict = Depends(get_current_user)):
    data = totals(proposal.model_dump()); data.update({"created_at": datetime.utcnow(), "updated_at": datetime.utcnow(), "created_by": user["_id"]})
    result = await proposals_collection.insert_one(data)
    return serialize(await proposals_collection.find_one({"_id": result.inserted_id}))

@router.get("/")
async def list_items(lead_id: str | None = None, status: str | None = None, _: dict = Depends(get_current_user)):
    query = {k: v for k, v in {"lead_id": lead_id, "status": status}.items() if v}
    return serialize_list(await proposals_collection.find(query).sort("created_at", -1).to_list(500))

@router.patch("/{proposal_id}")
async def update(proposal_id: str, update: ProposalUpdate, _: dict = Depends(get_current_user)):
    current = await proposals_collection.find_one({"_id": to_object_id(proposal_id)})
    if not current: raise HTTPException(404, "Proposal not found")
    data = update.model_dump(exclude_unset=True)
    if any(key in data for key in ("line_items", "tax_rate", "discount")): data = totals({**current, **data})
    data["updated_at"] = datetime.utcnow()
    await proposals_collection.update_one({"_id": current["_id"]}, {"$set": data})
    return serialize(await proposals_collection.find_one({"_id": current["_id"]}))

@router.delete("/{proposal_id}", status_code=204)
async def remove(proposal_id: str, _: dict = Depends(get_current_user)):
    if not (await proposals_collection.delete_one({"_id": to_object_id(proposal_id)})).deleted_count: raise HTTPException(404, "Proposal not found")
