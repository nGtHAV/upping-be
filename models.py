from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class SiteIn(BaseModel):
    name: str
    url: str

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(max_length=72)
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserUpdate(BaseModel):
    full_name: Optional[str] = None

class ChangePassword(BaseModel):
    current_password: str
    new_password: str = Field(max_length=72)

class TierUpdate(BaseModel):
    tier: str
