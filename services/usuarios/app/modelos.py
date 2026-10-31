import os
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Boolean, create_engine, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
Sesion = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Usuario(Base):
    __tablename__ = "usuario"
    __table_args__ = {"schema": "usuarios"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True)
    nombre: Mapped[str] = mapped_column(String)
    password_hash: Mapped[str] = mapped_column(String)
    rol: Mapped[str] = mapped_column(String, default="cliente")
    email_verificado: Mapped[bool] = mapped_column(Boolean, default=False)
    intentos_fallidos: Mapped[int] = mapped_column(Integer, default=0)
    primer_fallo: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


def obtener_sesion():
    with Sesion() as sesion:
        yield sesion
