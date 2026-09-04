from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException


def serialize(doc: dict) -> dict:
    """Convert a Mongo document's _id (and any *_id fields) to plain strings."""
    if doc is None:
        return None
    doc["_id"] = str(doc["_id"])
    return doc


def serialize_list(docs: list) -> list:
    return [serialize(d) for d in docs]


def to_object_id(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except InvalidId:
        raise HTTPException(status_code=400, detail=f"Invalid id: {id_str}")
