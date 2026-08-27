from fastapi import APIRouter, Depends, HTTPException, status
from database import users_col
from schemas import UserRegister, UserLogin, Token, ChangePassword
from security import hash_password, verify_password, create_access_token
from dependencies import get_current_user
from typing import Optional

router = APIRouter(prefix="/api/auth", tags=["Auth"])

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister):
    existing_user = await users_col.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_pwd = hash_password(user_data.password)
    user_doc = {"email": user_data.email, "password": hashed_pwd}
    result = await users_col.insert_one(user_doc)
    return {"id": str(result.inserted_id), "message": "User registered successfully"}

@router.post("/login", response_model=Token)
async def login(credentials: UserLogin):
    user = await users_col.find_one({"email": credentials.email})
    if not user or not verify_password(credentials.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    token = create_access_token(data={"sub": str(user["_id"])})
    return {"access_token": token, "token_type": "bearer"}

@router.post("/change-password")
async def change_password(data: ChangePassword, current_user: dict = Depends(get_current_user)):
    if not verify_password(data.current_password, current_user["password"]):
        raise HTTPException(status_code=400, detail="Incorrect current password")
    
    new_hashed_pwd = hash_password(data.new_password)
    await users_col.update_one(
        {"_id": current_user["_id"]},
        {"$set": {"password": new_hashed_pwd}}
    )
    return {"message": "Password updated successfully"}