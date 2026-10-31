import uuid

from pydantic import BaseModel, EmailStr, Field


class RegistroEntrada(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    nombre: str = Field(min_length=1, max_length=120)


class LoginEntrada(BaseModel):
    email: EmailStr
    password: str


class UsuarioSalida(BaseModel):
    id: uuid.UUID
    email: EmailStr
    rol: str


class TokenSalida(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expira_en: int
