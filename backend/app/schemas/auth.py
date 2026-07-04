import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict

class OrganizationBase(BaseModel):
    name: str = Field(..., max_length=255)

class OrganizationResponse(OrganizationBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime

class UserBase(BaseModel):
    email: EmailStr

class UserRegister(UserBase):
    password: str = Field(..., min_length=6)
    organization_name: str = Field(..., min_length=1, max_length=255)

class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    role: str
    created_at: datetime

class RegisterResponse(BaseModel):
    user: UserResponse
    organization: OrganizationResponse

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenPayload(BaseModel):
    sub: str | None = None
