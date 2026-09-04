import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from routes import leads, meetings, proposals, agreements, projects, dashboard, auth, meta
from db import leads_collection, meetings_collection, proposals_collection, agreements_collection, projects_collection, users_collection


@asynccontextmanager
async def lifespan(_: FastAPI):
    await users_collection.create_index("email", unique=True)
    await leads_collection.create_index([("status", 1), ("created_at", -1)])
    await leads_collection.create_index([("assigned_to", 1), ("next_follow_up", 1)])
    await leads_collection.create_index("meta_lead_id", unique=True, sparse=True)
    await meetings_collection.create_index([("scheduled_at", 1), ("lead_id", 1)])
    await proposals_collection.create_index([("lead_id", 1), ("status", 1)])
    await agreements_collection.create_index([("lead_id", 1), ("status", 1)])
    await projects_collection.create_index([("lead_id", 1), ("status", 1)])
    yield

app = FastAPI(title="Growth CRM API", version="2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(leads.router)
app.include_router(meetings.router)
app.include_router(proposals.router)
app.include_router(agreements.router)
app.include_router(projects.router)
app.include_router(dashboard.router)
app.include_router(meta.router)


@app.get("/")
async def root():
    return {"status": "CRM API running"}
