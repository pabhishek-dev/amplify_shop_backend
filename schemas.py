from pydantic import BaseModel, EmailStr, Field
from typing import Dict, List, Optional

# --- Product Schemas ---
class ProductSchema(BaseModel):
    id: int
    name: str
    price: float
    discountPrice: Optional[float] = None
    stock: int
    category: str
    rating: float
    reviewCount: int
    isFeatured: bool
    isNewArrival: bool
    imageUrl: str
    galleryImages: List[str]
    desc: str
    tags: List[str]
    specifications: Dict[str, str]

class ProductUpdateSchema(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    discountPrice: Optional[float] = None
    stock: Optional[int] = None
    category: Optional[str] = None
    rating: Optional[float] = None
    reviewCount: Optional[int] = None
    isFeatured: Optional[bool] = None
    isNewArrival: Optional[bool] = None
    imageUrl: Optional[str] = None
    galleryImages: Optional[List[str]] = None
    desc: Optional[str] = None
    tags: Optional[List[str]] = None
    specifications: Optional[Dict[str, str]] = None

class BulkDeleteSchema(BaseModel):
    product_ids: List[int]

# --- Auth Schemas ---
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)

class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(max_length=72)

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class ChangePassword(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=72)