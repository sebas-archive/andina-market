import logging
import os
import uuid
from datetime import datetime

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Integer, String, create_engine, func, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

SERVICE_TOKEN = os.environ["SERVICE_TOKEN"]
engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
Sesion = sessionmaker(engine, expire_on_commit=False)
log = logging.getLogger("uvicorn.error")


class Base(DeclarativeBase):
    pass


class Stock(Base):
    __tablename__ = "stock"
    __table_args__ = {"schema": "inventario"}

    producto_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    disponible: Mapped[int] = mapped_column(Integer)
    reservado: Mapped[int] = mapped_column(Integer, default=0)
    umbral: Mapped[int] = mapped_column(Integer, default=10)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Movimiento(Base):
    __tablename__ = "movimiento"
    __table_args__ = {"schema": "inventario"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    producto_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    tipo: Mapped[str] = mapped_column(String)
    cantidad: Mapped[int] = mapped_column(Integer)
    referencia: Mapped[str | None] = mapped_column(String)


class CantidadEntrada(BaseModel):
    cantidad: int = Field(gt=0)
    referencia: str | None = None


class ErrorApi(HTTPException):
    def __init__(self, status_code: int, error: str, detalle: str):
        super().__init__(status_code=status_code, detail=detalle)
        self.error = error


app = FastAPI(title="Servicio Inventario")


@app.exception_handler(ErrorApi)
def manejar_error_api(_: Request, exc: ErrorApi):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.error, "detalle": exc.detail})


@app.exception_handler(RequestValidationError)
def manejar_validacion(_: Request, exc: RequestValidationError):
    detalle = "; ".join(f"{'.'.join(map(str, e['loc'][1:]))}: {e['msg']}" for e in exc.errors())
    return JSONResponse(status_code=422, content={"error": "validacion", "detalle": detalle})


def obtener_sesion():
    with Sesion() as sesion:
        yield sesion


def exigir_token_servicio(x_service_token: str | None = Header(default=None)):
    if x_service_token != SERVICE_TOKEN:
        raise ErrorApi(401, "token_servicio_invalido", "Se requiere X-Service-Token válido.")


def bloquear_stock(sesion: Session, producto_id: uuid.UUID) -> Stock:
    stock = sesion.scalar(select(Stock).where(Stock.producto_id == producto_id).with_for_update())
    if stock is None:
        raise ErrorApi(404, "producto_no_encontrado", "No hay inventario para ese producto.")
    return stock


@app.get("/health")
def health():
    return {"status": "ok", "servicio": "inventario"}


@app.get("/api/inventario/{producto_id}")
def consultar(producto_id: uuid.UUID, sesion: Session = Depends(obtener_sesion)):
    stock = sesion.get(Stock, producto_id)
    if stock is None:
        raise ErrorApi(404, "producto_no_encontrado", "No hay inventario para ese producto.")
    return {"producto_id": stock.producto_id, "disponible": stock.disponible, "reservado": stock.reservado}


@app.post("/api/inventario/{producto_id}/reservar", dependencies=[Depends(exigir_token_servicio)])
def reservar(producto_id: uuid.UUID, datos: CantidadEntrada, sesion: Session = Depends(obtener_sesion)):
    stock = bloquear_stock(sesion, producto_id)
    if stock.disponible < datos.cantidad:
        raise ErrorApi(409, "stock_insuficiente", f"Disponible: {stock.disponible}, solicitado: {datos.cantidad}.")
    stock.disponible -= datos.cantidad
    stock.reservado += datos.cantidad
    sesion.add(Movimiento(producto_id=producto_id, tipo="reserva", cantidad=datos.cantidad, referencia=datos.referencia))
    sesion.commit()
    if stock.disponible < stock.umbral:
        log.warning("alerta=stock_bajo producto_id=%s disponible=%s umbral=%s", producto_id, stock.disponible, stock.umbral)
    return {"reservado": datos.cantidad}


@app.post("/api/inventario/{producto_id}/liberar", dependencies=[Depends(exigir_token_servicio)])
def liberar(producto_id: uuid.UUID, datos: CantidadEntrada, sesion: Session = Depends(obtener_sesion)):
    stock = bloquear_stock(sesion, producto_id)
    cantidad = min(datos.cantidad, stock.reservado)
    stock.disponible += cantidad
    stock.reservado -= cantidad
    if cantidad:
        sesion.add(Movimiento(producto_id=producto_id, tipo="liberacion", cantidad=cantidad, referencia=datos.referencia))
    sesion.commit()
    return {"liberado": cantidad}
