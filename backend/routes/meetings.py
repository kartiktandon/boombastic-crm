from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from auth import get_current_user
from db import meetings_collection
from models import Meeting, MeetingUpdate
from utils import serialize, serialize_list, to_object_id

router = APIRouter(prefix="/meetings", tags=["meetings"])

@router.post("/", status_code=201)
async def create(meeting: Meeting, user: dict = Depends(get_current_user)):
    data = meeting.model_dump(); data.update({"created_at": datetime.utcnow(), "created_by": user["_id"]})
    result = await meetings_collection.insert_one(data)
    return serialize(await meetings_collection.find_one({"_id": result.inserted_id}))

@router.get("/")
async def list_items(lead_id: str | None = None, status: str | None = None, _: dict = Depends(get_current_user)):
    query = {k: v for k, v in {"lead_id": lead_id, "status": status}.items() if v}
    return serialize_list(await meetings_collection.find(query).sort("scheduled_at", 1).to_list(500))

@router.patch("/{meeting_id}")
async def update(meeting_id: str, update: MeetingUpdate, _: dict = Depends(get_current_user)):
    data = update.model_dump(exclude_unset=True)
    result = await meetings_collection.update_one({"_id": to_object_id(meeting_id)}, {"$set": data})
    if not result.matched_count: raise HTTPException(404, "Meeting not found")
    return serialize(await meetings_collection.find_one({"_id": to_object_id(meeting_id)}))

@router.delete("/{meeting_id}", status_code=204)
async def remove(meeting_id: str, _: dict = Depends(get_current_user)):
    if not (await meetings_collection.delete_one({"_id": to_object_id(meeting_id)})).deleted_count: raise HTTPException(404, "Meeting not found")
