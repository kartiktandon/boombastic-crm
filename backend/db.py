import os
import asyncio
from weakref import WeakKeyDictionary

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "crm")

_clients = WeakKeyDictionary()


def _database():
    """Return a Mongo database bound to the current asyncio event loop.

    Vercel can execute application startup and requests on different loops.
    Motor clients are loop-bound, so a module-level client causes requests to
    fail with "Future attached to a different loop" in that environment.
    """
    loop = asyncio.get_running_loop()
    client = _clients.get(loop)
    if client is None:
        client = AsyncIOMotorClient(MONGO_URI, io_loop=loop)
        _clients[loop] = client
    return client[DB_NAME]


class _CollectionProxy:
    def __init__(self, name):
        self.name = name

    def __getattr__(self, attribute):
        return getattr(_database()[self.name], attribute)


class _GridFSBucketProxy:
    def __getattr__(self, attribute):
        bucket = AsyncIOMotorGridFSBucket(
            _database(), bucket_name="lead_attachments"
        )
        return getattr(bucket, attribute)


attachments_bucket = _GridFSBucketProxy()
leads_collection = _CollectionProxy("leads")
meetings_collection = _CollectionProxy("meetings")
proposals_collection = _CollectionProxy("proposals")
agreements_collection = _CollectionProxy("agreements")
projects_collection = _CollectionProxy("projects")
users_collection = _CollectionProxy("users")
stages_collection = _CollectionProxy("lead_stages")
settings_collection = _CollectionProxy("settings")
