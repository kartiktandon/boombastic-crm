import os
from datetime import datetime

from fastapi import APIRouter, Depends

from auth import get_current_user
from db import settings_collection
from models import BusinessSettings

router = APIRouter(prefix="/settings", tags=["settings"])


def defaults(user: dict) -> dict:
    return BusinessSettings(
        business_email=user.get("email"),
        default_lead_owner=user.get("name"),
    ).model_dump()


@router.get("/me")
async def get_settings(user: dict = Depends(get_current_user)):
    saved = await settings_collection.find_one({"user_id": user["_id"]})
    values = defaults(user)
    if saved:
        values.update({key: value for key, value in saved.items() if key in values})
    values["channels"] = {
        "meta_leads": bool(os.getenv("META_PAGE_ACCESS_TOKEN")),
        "instagram": False,
        "whatsapp": False,
        "website_forms": True,
    }
    return values


@router.put("/me")
async def save_settings(payload: BusinessSettings, user: dict = Depends(get_current_user)):
    values = payload.model_dump()
    values["updated_at"] = datetime.utcnow()
    await settings_collection.update_one(
        {"user_id": user["_id"]},
        {"$set": values, "$setOnInsert": {"user_id": user["_id"], "created_at": datetime.utcnow()}},
        upsert=True,
    )
    return {"message": "Settings saved", **payload.model_dump()}
