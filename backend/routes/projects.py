from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from auth import get_current_user
from db import projects_collection
from models import Project, ProjectUpdate
from utils import serialize, serialize_list, to_object_id

router = APIRouter(prefix="/projects", tags=["projects"])

@router.post("/", status_code=201)
async def create(project: Project, user: dict = Depends(get_current_user)):
    data = project.model_dump(); data.update({"created_at": datetime.utcnow(), "created_by": user["_id"]})
    result = await projects_collection.insert_one(data)
    return serialize(await projects_collection.find_one({"_id": result.inserted_id}))

@router.get("/")
async def list_items(lead_id: str | None = None, status: str | None = None, _: dict = Depends(get_current_user)):
    query = {k: v for k, v in {"lead_id": lead_id, "status": status}.items() if v}
    return serialize_list(await projects_collection.find(query).sort("created_at", -1).to_list(500))

@router.patch("/{project_id}")
async def update(project_id: str, update: ProjectUpdate, _: dict = Depends(get_current_user)):
    result = await projects_collection.update_one({"_id": to_object_id(project_id)}, {"$set": update.model_dump(exclude_unset=True)})
    if not result.matched_count: raise HTTPException(404, "Project not found")
    return serialize(await projects_collection.find_one({"_id": to_object_id(project_id)}))

@router.delete("/{project_id}", status_code=204)
async def remove(project_id: str, _: dict = Depends(get_current_user)):
    if not (await projects_collection.delete_one({"_id": to_object_id(project_id)})).deleted_count: raise HTTPException(404, "Project not found")
