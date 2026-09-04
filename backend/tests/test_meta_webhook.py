import hashlib
import hmac
import json

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from routes import meta

APP_SECRET = "test-app-secret"
VERIFY_TOKEN = "test-verify-token"


def make_client() -> TestClient:
    app = FastAPI()
    app.include_router(meta.router)
    return TestClient(app)


def signed_body(payload: dict) -> tuple[bytes, dict[str, str]]:
    body = json.dumps(payload, separators=(",", ":")).encode()
    digest = hmac.new(APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return body, {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": f"sha256={digest}",
    }


def lead_notification(lead_id: str = "lead-123") -> dict:
    return {
        "object": "page",
        "entry": [{
            "changes": [{
                "field": "leadgen",
                "value": {"leadgen_id": lead_id, "form_id": "form-1"},
            }],
        }],
    }


def test_verification_handshake(monkeypatch):
    monkeypatch.setenv("META_VERIFY_TOKEN", VERIFY_TOKEN)
    client = make_client()

    response = client.get(
        "/webhooks/meta",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": VERIFY_TOKEN,
            "hub.challenge": "challenge-123",
        },
    )

    assert response.status_code == 200
    assert response.text == "challenge-123"


def test_verification_rejects_wrong_token(monkeypatch):
    monkeypatch.setenv("META_VERIFY_TOKEN", VERIFY_TOKEN)
    client = make_client()

    response = client.get(
        "/webhooks/meta",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong",
            "hub.challenge": "challenge-123",
        },
    )

    assert response.status_code == 403


def test_webhook_rejects_invalid_signature(monkeypatch):
    monkeypatch.setenv("META_APP_SECRET", APP_SECRET)
    client = make_client()

    response = client.post(
        "/webhooks/meta",
        content=b'{"object":"page"}',
        headers={"X-Hub-Signature-256": "sha256=invalid"},
    )

    assert response.status_code == 401


def test_normalizes_phone_only_lead_and_custom_fields():
    lead = meta.normalize_meta_lead(
        {
            "id": "lead-123",
            "form_id": "form-1",
            "ad_id": "ad-1",
            "field_data": [
                {"name": "full_name", "values": ["Asha Singh"]},
                {"name": "phone_number", "values": ["+91 90000 00000"]},
                {"name": "preferred_party_date", "values": ["Sunday"]},
            ],
        },
        {},
    )

    assert lead["name"] == "Asha Singh"
    assert lead["email"] is None
    assert lead["phone"] == "+91 90000 00000"
    assert lead["source"] == "meta"
    assert lead["meta_lead_id"] == "lead-123"
    assert lead["meta_fields"] == {"preferred_party_date": ["Sunday"]}


def test_valid_webhook_inserts_once_and_deduplicates(monkeypatch):
    monkeypatch.setenv("META_APP_SECRET", APP_SECRET)
    stored_ids: set[str] = set()

    async def fake_fetch(lead_id, notification):
        return {"meta_lead_id": lead_id, "name": "Test Lead"}

    async def fake_store(lead):
        lead_id = lead["meta_lead_id"]
        if lead_id in stored_ids:
            return False
        stored_ids.add(lead_id)
        return True

    monkeypatch.setattr(meta, "fetch_meta_lead", fake_fetch)
    monkeypatch.setattr(meta, "store_meta_lead", fake_store)
    client = make_client()
    body, headers = signed_body(lead_notification())

    first = client.post("/webhooks/meta", content=body, headers=headers)
    second = client.post("/webhooks/meta", content=body, headers=headers)

    assert first.status_code == 200
    assert first.json() == {"received": True, "inserted": 1, "duplicates": 0}
    assert second.status_code == 200
    assert second.json() == {"received": True, "inserted": 0, "duplicates": 1}


def test_graph_api_failure_is_retryable(monkeypatch):
    monkeypatch.setenv("META_APP_SECRET", APP_SECRET)

    async def failed_fetch(lead_id, notification):
        raise HTTPException(status_code=502, detail="Could not retrieve lead from Meta")

    monkeypatch.setattr(meta, "fetch_meta_lead", failed_fetch)
    client = make_client()
    body, headers = signed_body(lead_notification())

    response = client.post("/webhooks/meta", content=body, headers=headers)

    assert response.status_code == 502
