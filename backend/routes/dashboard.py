from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from auth import get_current_user
from db import (
    leads_collection,
    meetings_collection,
    proposals_collection,
    agreements_collection,
    projects_collection,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


async def count_by_status(collection):
    pipeline = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
    results = await collection.aggregate(pipeline).to_list(50)
    return {r["_id"]: r["count"] for r in results}


@router.get("/summary")
async def summary(_: dict = Depends(get_current_user)):
    """One call that powers the whole dashboard page: totals + status
    breakdown for every module, plus total pipeline value from proposals."""
    leads_by_status = await count_by_status(leads_collection)
    meetings_by_status = await count_by_status(meetings_collection)
    proposals_by_status = await count_by_status(proposals_collection)
    agreements_by_status = await count_by_status(agreements_collection)
    projects_by_status = await count_by_status(projects_collection)

    pipeline_value = await proposals_collection.aggregate(
        [
            {"$match": {"status": {"$in": ["sent", "accepted"]}}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
        ]
    ).to_list(1)

    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    overdue_followups = await leads_collection.count_documents({"next_follow_up": {"$lt": today}, "status": {"$nin": ["won", "lost"]}})
    today_followups = await leads_collection.count_documents({"next_follow_up": {"$gte": today, "$lt": today + timedelta(days=1)}})
    upcoming_meetings = await meetings_collection.count_documents({"scheduled_at": {"$gte": today}, "status": "scheduled"})
    total_leads = sum(leads_by_status.values())
    return {
        "leads": {
            "total": sum(leads_by_status.values()),
            "by_status": leads_by_status,
        },
        "meetings": {
            "total": sum(meetings_by_status.values()),
            "by_status": meetings_by_status,
        },
        "proposals": {
            "total": sum(proposals_by_status.values()),
            "by_status": proposals_by_status,
        },
        "agreements": {
            "total": sum(agreements_by_status.values()),
            "by_status": agreements_by_status,
        },
        "projects": {
            "total": sum(projects_by_status.values()),
            "by_status": projects_by_status,
        },
        "pipeline_value": pipeline_value[0]["total"] if pipeline_value else 0,
        "conversion_rate": round((leads_by_status.get("won", 0) / total_leads * 100) if total_leads else 0, 1),
        "overdue_followups": overdue_followups,
        "today_followups": today_followups,
        "upcoming_meetings": upcoming_meetings,
    }
