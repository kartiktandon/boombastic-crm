from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from gridfs.errors import NoFile

from auth import get_current_user
from db import attachments_bucket, leads_collection
from models import LeadCreate, LeadStatusUpdate, LeadUpdate, Note
from utils import serialize, serialize_list, to_object_id

router = APIRouter(prefix="/leads", tags=["leads"])

STAGES = ["new", "contacted", "interested", "call_back", "meeting_done", "proposal_sent", "on_hold", "not_interested", "won", "lost", "ringing"]
MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024
ALLOWED_ATTACHMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv", ".jpg", ".jpeg", ".png", ".webp"}

def activity(kind: str, message: str, user: dict):
    return {"type": kind, "message": message, "created_by": user.get("name"), "created_at": datetime.utcnow()}

@router.get("/stages")
async def list_stages(_: dict = Depends(get_current_user)):
    return [{"id": stage, "label": stage.replace("_", " ").title()} for stage in STAGES]

@router.get("/analytics")
async def analytics(business_unit: str | None = None, _: dict = Depends(get_current_user)):
    match = {"business_unit": {"$in": ["superfun", "uperfun", None]}} if business_unit == "superfun" else ({"business_unit": business_unit} if business_unit else {})
    pipeline = ([{"$match": match}] if match else []) + [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
    by_stage = {row["_id"]: row["count"] for row in await leads_collection.aggregate(pipeline).to_list(50)}
    platform_pipeline = ([{"$match": match}] if match else []) + [{"$group": {"_id": "$source", "count": {"$sum": 1}}}]
    by_platform = {row["_id"]: row["count"] for row in await leads_collection.aggregate(platform_pipeline).to_list(50)}
    total = sum(by_stage.values())
    won = by_stage.get("won", 0)
    return {"total": total, "won": won, "conversion": round((won / total * 100) if total else 0, 1), "by_stage": by_stage, "by_platform": by_platform}

@router.post("/", status_code=201)
async def create_lead(lead: LeadCreate, current_user: dict = Depends(get_current_user)):
    data = lead.model_dump()
    now = datetime.utcnow()
    data.update({"created_at": now, "updated_at": now, "created_by": current_user["_id"], "notes": [], "activities": [activity("created", "Lead created", current_user)]})
    result = await leads_collection.insert_one(data)
    return serialize(await leads_collection.find_one({"_id": result.inserted_id}))

@router.get("/")
async def list_leads(
    status: str | None = None, source: str | None = None, assigned_to: str | None = None, business_unit: str | None = None,
    q: str | None = None, follow_up: str | None = None, page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100), sort: str = "newest", _: dict = Depends(get_current_user),
):
    query = {}
    if business_unit:
        query["business_unit"] = {"$in": ["superfun", "uperfun", None]} if business_unit == "superfun" else business_unit
    for field, value in (("status", status), ("source", source), ("assigned_to", assigned_to)):
        if value: query[field] = value
    if q:
        query["$or"] = [{field: {"$regex": q, "$options": "i"}} for field in ["name", "company", "email", "phone", "city", "campaign"]]
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    if follow_up == "overdue": query["next_follow_up"] = {"$lt": today}
    elif follow_up == "today": query["next_follow_up"] = {"$gte": today, "$lt": today + timedelta(days=1)}
    elif follow_up == "upcoming": query["next_follow_up"] = {"$gte": today, "$lt": today + timedelta(days=8)}
    elif follow_up == "none": query["next_follow_up"] = None
    sort_field, direction = ("created_at", -1) if sort == "newest" else ("name", 1)
    total = await leads_collection.count_documents(query)
    docs = await leads_collection.find(query).sort(sort_field, direction).skip((page - 1) * limit).limit(limit).to_list(limit)
    return {"items": serialize_list(docs), "total": total, "page": page, "limit": limit}

@router.get("/{lead_id}")
async def get_lead(lead_id: str, _: dict = Depends(get_current_user)):
    doc = await leads_collection.find_one({"_id": to_object_id(lead_id)})
    if not doc: raise HTTPException(status_code=404, detail="Lead not found")
    return serialize(doc)

@router.patch("/{lead_id}")
async def update_lead(lead_id: str, update: LeadUpdate, current_user: dict = Depends(get_current_user)):
    payload = update.model_dump(exclude_unset=True)
    if not payload: raise HTTPException(status_code=400, detail="No changes supplied")
    payload["updated_at"] = datetime.utcnow()
    payload["activities"] = activity("updated", "Lead details updated", current_user)
    result = await leads_collection.update_one({"_id": to_object_id(lead_id)}, {"$set": {k: v for k, v in payload.items() if k != "activities"}, "$push": {"activities": payload["activities"]}})
    if not result.matched_count: raise HTTPException(status_code=404, detail="Lead not found")
    return serialize(await leads_collection.find_one({"_id": to_object_id(lead_id)}))

@router.patch("/{lead_id}/status")
async def update_lead_status(lead_id: str, update: LeadStatusUpdate, current_user: dict = Depends(get_current_user)):
    result = await leads_collection.update_one({"_id": to_object_id(lead_id)}, {"$set": {"status": update.status, "updated_at": datetime.utcnow()}, "$push": {"activities": activity("stage", f"Stage changed to {update.status.replace('_', ' ')}", current_user)}})
    if not result.matched_count: raise HTTPException(status_code=404, detail="Lead not found")
    return {"ok": True}

@router.post("/{lead_id}/notes")
async def add_note(lead_id: str, note: Note, current_user: dict = Depends(get_current_user)):
    data = note.model_dump()
    data["created_by"] = current_user.get("name")
    result = await leads_collection.update_one({"_id": to_object_id(lead_id)}, {"$push": {"notes": data, "activities": activity("note", "Added a note", current_user)}, "$set": {"updated_at": datetime.utcnow()}})
    if not result.matched_count: raise HTTPException(status_code=404, detail="Lead not found")
    return {"ok": True}

@router.get("/{lead_id}/attachments")
async def list_attachments(lead_id: str, _: dict = Depends(get_current_user)):
    lead_oid = to_object_id(lead_id)
    if not await leads_collection.find_one({"_id": lead_oid}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Lead not found")
    files = []
    async for item in attachments_bucket.find({"metadata.lead_id": lead_oid}).sort("uploadDate", -1):
        files.append({
            "_id": str(item._id),
            "filename": item.filename,
            "content_type": (item.metadata or {}).get("content_type", "application/octet-stream"),
            "size": item.length,
            "uploaded_at": item.upload_date,
            "uploaded_by": (item.metadata or {}).get("uploaded_by"),
        })
    return files

@router.post("/{lead_id}/attachments", status_code=201)
async def upload_attachment(
    lead_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    lead_oid = to_object_id(lead_id)
    if not await leads_collection.find_one({"_id": lead_oid}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Lead not found")
    filename = Path(file.filename or "attachment").name
    if Path(filename).suffix.lower() not in ALLOWED_ATTACHMENT_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file type")
    content = await file.read(MAX_ATTACHMENT_SIZE + 1)
    await file.close()
    if len(content) > MAX_ATTACHMENT_SIZE:
        raise HTTPException(status_code=413, detail="Attachments must be 10 MB or smaller")
    file_id = await attachments_bucket.upload_from_stream(
        filename,
        content,
        metadata={
            "lead_id": lead_oid,
            "content_type": file.content_type or "application/octet-stream",
            "uploaded_by": current_user.get("name"),
        },
    )
    await leads_collection.update_one(
        {"_id": lead_oid},
        {"$push": {"activities": activity("attachment", f"Attached {filename}", current_user)}, "$set": {"updated_at": datetime.utcnow()}},
    )
    return {"_id": str(file_id), "filename": filename, "size": len(content)}

@router.get("/{lead_id}/attachments/{attachment_id}")
async def download_attachment(lead_id: str, attachment_id: str, _: dict = Depends(get_current_user)):
    lead_oid, attachment_oid = to_object_id(lead_id), to_object_id(attachment_id)
    try:
        stream = await attachments_bucket.open_download_stream(attachment_oid)
    except NoFile:
        raise HTTPException(status_code=404, detail="Attachment not found")
    if (stream.metadata or {}).get("lead_id") != lead_oid:
        raise HTTPException(status_code=404, detail="Attachment not found")

    async def chunks():
        while True:
            chunk = await stream.readchunk()
            if not chunk:
                break
            yield chunk

    safe_name = stream.filename.replace('"', "")
    return StreamingResponse(
        chunks(),
        media_type=(stream.metadata or {}).get("content_type", "application/octet-stream"),
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )

@router.delete("/{lead_id}/attachments/{attachment_id}", status_code=204)
async def delete_attachment(lead_id: str, attachment_id: str, current_user: dict = Depends(get_current_user)):
    lead_oid, attachment_oid = to_object_id(lead_id), to_object_id(attachment_id)
    try:
        stream = await attachments_bucket.open_download_stream(attachment_oid)
    except NoFile:
        raise HTTPException(status_code=404, detail="Attachment not found")
    if (stream.metadata or {}).get("lead_id") != lead_oid:
        raise HTTPException(status_code=404, detail="Attachment not found")
    filename = stream.filename
    await attachments_bucket.delete(attachment_oid)
    await leads_collection.update_one(
        {"_id": lead_oid},
        {"$push": {"activities": activity("attachment", f"Removed attachment {filename}", current_user)}, "$set": {"updated_at": datetime.utcnow()}},
    )

@router.delete("/{lead_id}", status_code=204)
async def delete_lead(lead_id: str, _: dict = Depends(get_current_user)):
    lead_oid = to_object_id(lead_id)
    result = await leads_collection.delete_one({"_id": lead_oid})
    if not result.deleted_count: raise HTTPException(status_code=404, detail="Lead not found")
    async for item in attachments_bucket.find({"metadata.lead_id": lead_oid}):
        await attachments_bucket.delete(item._id)
