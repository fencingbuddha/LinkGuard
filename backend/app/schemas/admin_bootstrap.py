from pydantic import BaseModel, EmailStr, Field


class AdminBootstrapIn(BaseModel):
    org_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class AdminBootstrapOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    admin_id: int
    org_id: int