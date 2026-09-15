from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm

from db import users_collection
from models import PasswordChange, UserRegister
from auth import hash_password, verify_password, create_access_token, get_current_user
from utils import to_object_id

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
async def register(user: UserRegister):
    if await users_collection.count_documents({}):
        raise HTTPException(status_code=403, detail="New accounts must be created by an admin")
    existing = await users_collection.find_one({"email": user.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    doc = {
        "name": user.name,
        "email": user.email,
        "hashed_password": hash_password(user.password),
        "role": "admin",
        "active": True,
        "created_at": datetime.utcnow(),
    }
    result = await users_collection.insert_one(doc)
    token = create_access_token(str(result.inserted_id), user.email)
    return {"access_token": token, "token_type": "bearer"}


@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # OAuth2PasswordRequestForm uses "username" as the field name — we treat it as email.
    user = await users_collection.find_one({"email": form_data.username})
    if not user or user.get("active") is False or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = create_access_token(str(user["_id"]), user["email"])
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    return current_user


@router.post("/change-password")
async def change_password(payload: PasswordChange, current_user: dict = Depends(get_current_user)):
    user_id = to_object_id(current_user["_id"])
    user = await users_collection.find_one({"_id": user_id})
    if not user or not verify_password(payload.current_password, user.get("hashed_password", "")):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if verify_password(payload.new_password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="New password must be different from the current password")
    await users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {"hashed_password": hash_password(payload.new_password), "password_changed_at": datetime.utcnow()}},
    )
    return {"message": "Password changed successfully"}
