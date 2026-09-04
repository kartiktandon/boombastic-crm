import hashlib
import hmac
import json
import os
from datetime import datetime
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from db import leads_collection

router = APIRouter(prefix="/webhooks/meta", tags=["meta-webhook"])


def require_setting(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise HTTPException(status_code=503, detail=f"{name} is not configured")
    return value


def valid_signature(body: bytes, signature_header: str | None, app_secret: str) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature_header.removeprefix("sha256="), expected)


def field_values(field_data: list[dict[str, Any]]) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    for field in field_data:
        name = str(field.get("name", "")).strip().lower()
        if not name:
            continue
        raw_values = field.get("values", [])
        if not isinstance(raw_values, list):
            raw_values = [raw_values]
        values[name] = [str(value).strip() for value in raw_values if value is not None]
    return values


def first_value(fields: dict[str, list[str]], *names: str) -> str | None:
    for name in names:
        values = fields.get(name)
        if values and values[0]:
            return values[0]
    return None


def normalize_meta_lead(payload: dict[str, Any], notification: dict[str, Any]) -> dict[str, Any]:
    fields = field_values(payload.get("field_data", []))
    first_name = first_value(fields, "first_name")
    last_name = first_value(fields, "last_name")
    name = first_value(fields, "full_name", "name")
    if not name:
        name = " ".join(part for part in (first_name, last_name) if part).strip()
    lead_id = str(payload.get("id") or notification.get("leadgen_id") or "").strip()
    if not lead_id:
        raise ValueError("Meta lead payload does not include an id")
    if not name:
        name = f"Meta Lead {lead_id[-6:]}"

    email = first_value(fields, "email")
    phone = first_value(fields, "phone_number", "phone", "mobile_number")
    if not email and not phone:
        raise ValueError("Meta lead does not include an email or phone number")

    standard_fields = {
        "full_name", "name", "first_name", "last_name", "email", "phone_number",
        "phone", "mobile_number", "city", "company_name", "company",
    }
    custom_fields = {key: value for key, value in fields.items() if key not in standard_fields}
    form_id = str(payload.get("form_id") or notification.get("form_id") or "").strip()
    now = datetime.utcnow()

    return {
        "name": name,
        "company": first_value(fields, "company_name", "company"),
        "email": email,
        "phone": phone,
        "city": first_value(fields, "city"),
        "source": "meta",
        "campaign": f"Meta form {form_id}" if form_id else "Meta Lead Ad",
        "status": "new",
        "temperature": "warm",
        "tags": ["meta-lead-ad"],
        "meta_lead_id": lead_id,
        "meta_form_id": form_id or None,
        "meta_ad_id": str(payload.get("ad_id") or notification.get("ad_id") or "") or None,
        "meta_created_time": payload.get("created_time"),
        "meta_fields": custom_fields,
        "created_at": now,
        "updated_at": now,
        "created_by": "meta",
        "notes": [],
        "activities": [{
            "type": "created",
            "message": "Lead imported from Meta Lead Ads",
            "created_by": "Meta Lead Ads",
            "created_at": now,
        }],
    }


async def fetch_meta_lead(lead_id: str, notification: dict[str, Any]) -> dict[str, Any]:
    access_token = require_setting("META_PAGE_ACCESS_TOKEN")
    graph_version = os.getenv("META_GRAPH_VERSION", "v26.0")
    url = f"https://graph.facebook.com/{graph_version}/{lead_id}"
    params = {
        "access_token": access_token,
        "fields": "id,created_time,ad_id,form_id,field_data",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Could not retrieve lead from Meta") from exc
    return normalize_meta_lead(payload, notification)


async def store_meta_lead(lead: dict[str, Any]) -> bool:
    result = await leads_collection.update_one(
        {"meta_lead_id": lead["meta_lead_id"]},
        {"$setOnInsert": lead},
        upsert=True,
    )
    return result.upserted_id is not None


@router.get("")
async def verify_webhook(
    mode: str | None = Query(default=None, alias="hub.mode"),
    verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    challenge: str | None = Query(default=None, alias="hub.challenge"),
):
    expected_token = require_setting("META_VERIFY_TOKEN")
    if mode != "subscribe" or not challenge or not hmac.compare_digest(verify_token or "", expected_token):
        raise HTTPException(status_code=403, detail="Webhook verification failed")
    return PlainTextResponse(challenge)


@router.post("")
async def receive_webhook(request: Request):
    body = await request.body()
    app_secret = require_setting("META_APP_SECRET")
    if not valid_signature(body, request.headers.get("X-Hub-Signature-256"), app_secret):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    if payload.get("object") != "page":
        return {"received": True, "inserted": 0, "duplicates": 0}

    inserted = 0
    duplicates = 0
    processed_ids: set[str] = set()
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "leadgen":
                continue
            notification = change.get("value") or {}
            lead_id = str(notification.get("leadgen_id") or "").strip()
            if not lead_id or lead_id in processed_ids:
                continue
            processed_ids.add(lead_id)
            try:
                lead = await fetch_meta_lead(lead_id, notification)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            if await store_meta_lead(lead):
                inserted += 1
            else:
                duplicates += 1

    return {"received": True, "inserted": inserted, "duplicates": duplicates}
