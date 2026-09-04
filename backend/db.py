import os
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "crm")

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]
attachments_bucket = AsyncIOMotorGridFSBucket(db, bucket_name="lead_attachments")

leads_collection = db["leads"]
meetings_collection = db["meetings"]
proposals_collection = db["proposals"]
agreements_collection = db["agreements"]
projects_collection = db["projects"]
users_collection = db["users"]
stages_collection = db["lead_stages"]
