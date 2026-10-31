import os
import random
import uuid
from datetime import datetime
from decimal import Decimal

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, create_engine, func, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

JWT_SECRET = os.environ["JWT_SECRET"]
SERVICE_TOKEN = os.environ["SERVICE_TOKEN"]
PRODUCTOS_URL = os.environ.get("PRODUCTOS_URL", "http://productos:8000")
INVENTARIO_URL = os.environ.get("INVENTARIO_URL", "http://inventario:8000")
PAGO_FALLA_PCT = float(os.environ.get("PAGO_FALLA_PCT", "10"))

engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
Sesion = sessionmaker(engine, expire_on_commit=False)
http = httpx.Client(timeout=2.0)


class Base(DeclarativeBase):
    pass


class Pedido(Base):
    __tablename__ = "pedido"
    __table_args__ = {"schema": "pedidos"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    estado: Mapped[str] = mapped_column(String, default="creado")
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    items: Mapped[list["PedidoItem"]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class PedidoItem(Base):
    __tablename__ = "pedido_item"
    __table_args__ = {"schema": "pedidos"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pedidos.pedido.id"))
    producto_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    cantidad: Mapped[int] = mapped_column(Integer)
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2))


class Idempotencia(Base):
    __tablename__ = "idempotencia"
    __table_args__ = {"schema": "pedidos"}

    clave: Mapped[str] = mapped_column(String, primary_key=True)
    usuario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    pedido_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))


class ItemEntrada(BaseModel):
    producto_id: uuid.UUID
    cantidad: int = Field(gt=0, le=1000)


class PedidoEntrada(BaseModel):
    items: list[ItemEntrada] = Field(min_length=1, max_length=50)


class ErrorApi(HTTPException):
    def __init__(self, status_code: int, error: str, detalle: str):
        super().__init__(status_code=status_code, detail=detalle)
        self.error = error


app = FastAPI(title="Servicio Pedidos")
bearer = HTTPBearer(auto_error=False)


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


def usuario_actual(cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> uuid.UUID:
    try:
        claims = jwt.decode(cred.credentials, JWT_SECRET, algorithms=["HS256"]) if cred else None
    except JWTError:
        claims = None
    if not claims:
        raise ErrorApi(401, "no_autenticado", "Token ausente, inválido o vencido.")
    return uuid.UUID(claims["sub"])


def resumen(pedido: Pedido) -> dict:
    return {"id": pedido.id, "estado": pedido.estado, "total": float(pedido.total)}


def detalle(pedido: Pedido) -> dict:
    return {
        **resumen(pedido),
        "items": [
            {"producto_id": i.producto_id, "cantidad": i.cantidad, "precio_unitario": float(i.precio_unitario)}
            for i in pedido.items
        ],
        "created_at": pedido.created_at,
        "updated_at": pedido.updated_at,
    }


def precio_de(producto_id: uuid.UUID) -> Decimal:
    """El precio sale del catálogo, nunca del cliente."""
    try:
        r = http.get(f"{PRODUCTOS_URL}/api/productos/{producto_id}")
    except httpx.HTTPError:
        raise ErrorApi(503, "catalogo_no_disponible", "No se pudo consultar el catálogo.")
    if r.status_code == 404:
        raise ErrorApi(422, "producto_inexistente", f"El producto {producto_id} no existe.")
    if r.status_code != 200:
        raise ErrorApi(503, "catalogo_no_disponible", "No se pudo consultar el catálogo.")
    return Decimal(str(r.json()["precio"]))


def mover_stock(accion: str, producto_id: uuid.UUID, cantidad: int, referencia: str) -> httpx.Response:
    return http.post(
        f"{INVENTARIO_URL}/api/inventario/{producto_id}/{accion}",
        json={"cantidad": cantidad, "referencia": referencia},
        headers={"X-Service-Token": SERVICE_TOKEN},
    )


def liberar(items: list[tuple[uuid.UUID, int]], referencia: str):
    """Compensación: devuelve a inventario lo que se reservó para este pedido."""
    for producto_id, cantidad in items:
        try:
            mover_stock("liberar", producto_id, cantidad, referencia)
        except httpx.HTTPError:
            pass  # queda registrado en inventario.movimiento como reserva sin liberar


def pedido_existente(sesion: Session, clave: str | None, usuario_id: uuid.UUID) -> Pedido | None:
    if not clave:
        return None
    registro = sesion.get(Idempotencia, (clave, usuario_id))
    return sesion.get(Pedido, registro.pedido_id) if registro else None


@app.get("/health")
def health():
    return {"status": "ok", "servicio": "pedidos"}


@app.post("/api/pedidos", status_code=201)
def crear(
    datos: PedidoEntrada,
    usuario_id: uuid.UUID = Depends(usuario_actual),
    idempotency_key: str | None = Header(default=None, max_length=100),
    sesion: Session = Depends(obtener_sesion),
):
    if existente := pedido_existente(sesion, idempotency_key, usuario_id):
        return resumen(existente)

    cantidades: dict[uuid.UUID, int] = {}
    for item in datos.items:
        cantidades[item.producto_id] = cantidades.get(item.producto_id, 0) + item.cantidad
    precios = {pid: precio_de(pid) for pid in cantidades}

    pedido_id = uuid.uuid4()
    referencia = f"pedido:{pedido_id}"
    reservados: list[tuple[uuid.UUID, int]] = []
    for producto_id, cantidad in cantidades.items():
        try:
            r = mover_stock("reservar", producto_id, cantidad, referencia)
        except httpx.HTTPError:
            liberar(reservados, referencia)
            raise ErrorApi(503, "inventario_no_disponible", "No se pudo reservar el stock.")
        if r.status_code != 200:
            liberar(reservados, referencia)
            if r.status_code in (404, 409):
                raise ErrorApi(409, "stock_insuficiente", f"Sin stock suficiente para {producto_id}.")
            raise ErrorApi(503, "inventario_no_disponible", "No se pudo reservar el stock.")
        reservados.append((producto_id, cantidad))

    pedido = Pedido(
        id=pedido_id,
        usuario_id=usuario_id,
        estado="creado",
        total=sum(precios[pid] * c for pid, c in cantidades.items()),
        items=[PedidoItem(producto_id=pid, cantidad=c, precio_unitario=precios[pid]) for pid, c in cantidades.items()],
    )
    try:
        sesion.add(pedido)
        sesion.flush()  # el pedido debe existir antes que su registro de idempotencia (llave foránea)
        if idempotency_key:
            sesion.add(Idempotencia(clave=idempotency_key, usuario_id=usuario_id, pedido_id=pedido_id))
        sesion.commit()
    except IntegrityError:
        # Otro intento con la misma Idempotency-Key ganó la carrera: se compensa y se devuelve ese pedido.
        sesion.rollback()
        liberar(reservados, referencia)
        if existente := pedido_existente(sesion, idempotency_key, usuario_id):
            return resumen(existente)
        raise
    except Exception:
        sesion.rollback()
        liberar(reservados, referencia)
        raise
    return resumen(pedido)


@app.post("/api/pedidos/{pedido_id}/pago")
def pagar(pedido_id: uuid.UUID, usuario_id: uuid.UUID = Depends(usuario_actual), sesion: Session = Depends(obtener_sesion)):
    pedido = sesion.scalar(select(Pedido).where(Pedido.id == pedido_id, Pedido.usuario_id == usuario_id).with_for_update())
    if pedido is None:
        raise ErrorApi(404, "pedido_no_encontrado", "El pedido no existe.")
    if pedido.estado != "creado":
        raise ErrorApi(409, "estado_invalido", f"El pedido está en estado {pedido.estado}.")

    # Pasarela simulada: falla en PAGO_FALLA_PCT % de los intentos.
    if random.uniform(0, 100) < PAGO_FALLA_PCT:
        pedido.estado = "cancelado"
        sesion.commit()
        liberar([(i.producto_id, i.cantidad) for i in pedido.items], f"pedido:{pedido.id}")
        raise ErrorApi(402, "pago_rechazado", "La pasarela rechazó el pago; se liberó el stock reservado.")
    pedido.estado = "pagado"
    sesion.commit()
    return {"id": pedido.id, "estado": pedido.estado}


@app.get("/api/pedidos/{pedido_id}")
def consultar(pedido_id: uuid.UUID, usuario_id: uuid.UUID = Depends(usuario_actual), sesion: Session = Depends(obtener_sesion)):
    pedido = sesion.scalar(select(Pedido).where(Pedido.id == pedido_id, Pedido.usuario_id == usuario_id))
    if pedido is None:
        raise ErrorApi(404, "pedido_no_encontrado", "El pedido no existe.")
    return detalle(pedido)


@app.get("/api/pedidos")
def listar(usuario_id: uuid.UUID = Depends(usuario_actual), sesion: Session = Depends(obtener_sesion)):
    pedidos = sesion.scalars(select(Pedido).where(Pedido.usuario_id == usuario_id).order_by(Pedido.created_at.desc())).all()
    return [detalle(p) for p in pedidos]
