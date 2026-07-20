from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    hospital: str | None = None
    department: str | None = None


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=8, max_length=128)
    role: str
    hospital: str | None = Field(default=None, max_length=128)
    department: str | None = Field(default=None, max_length=128)


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    hospital: str | None
    department: str | None
