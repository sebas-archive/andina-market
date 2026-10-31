import asyncio
import hashlib
import hmac
import os
import time
import struct
import uuid
import zlib
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from decimal import Decimal

import httpx
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import DateTime, Numeric, String, create_engine, func, or_, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from prometheus_fastapi_instrumentator import Instrumentator

JWT_SECRET = os.environ["JWT_SECRET"]
INVENTARIO_URL = os.environ.get("INVENTARIO_URL", "http://inventario:8000")
BUCKET = "productos"
URL_FIRMADA_VIGENCIA = timedelta(minutes=15)
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8080")
TIMEOUT_INVENTARIO = 0.5

engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
Sesion = sessionmaker(engine, expire_on_commit=False)

# Recorte de la Tarea 4.3: MinIO no se pudo descargar (docs/BLOQUEOS.md). Los objetos se guardan en un
# volumen local con la misma organización bucket/clave y se sirven con URL firmadas por HMAC, como S3.
ALMACEN = os.path.join(os.environ.get("ALMACEN_DIR", "/data/objetos"), BUCKET)
CLAVE_FIRMA = hashlib.sha256(b"imagenes:" + JWT_SECRET.encode()).digest()
# Fotos de muestra del catálogo (licencias libres, ver imagenes_seed/CREDITOS.md).
IMAGENES_SEED = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "imagenes_seed")


class Base(DeclarativeBase):
    pass


class Producto(Base):
    __tablename__ = "producto"
    __table_args__ = {"schema": "catalogo"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sku: Mapped[str] = mapped_column(String, unique=True)
    nombre: Mapped[str] = mapped_column(String)
    categoria: Mapped[str] = mapped_column(String)
    precio: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    imagen_key: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


def png_marcador(color=(46, 125, 50), lado=64) -> bytes:
    """PNG de un solo color para las imágenes del seed (sin archivos binarios en el repo)."""
    fila = b"\x00" + bytes(color) * lado
    datos = zlib.compress(fila * lado)

    def bloque(tipo, contenido):
        return struct.pack(">I", len(contenido)) + tipo + contenido + struct.pack(">I", zlib.crc32(tipo + contenido))

    cabecera = struct.pack(">IIBBBBB", lado, lado, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + bloque(b"IHDR", cabecera) + bloque(b"IDAT", datos) + bloque(b"IEND", b"")


def ruta_objeto(clave: str) -> str:
    ruta = os.path.realpath(os.path.join(ALMACEN, clave))
    if not ruta.startswith(os.path.realpath(ALMACEN) + os.sep):
        raise ErrorApi(404, "imagen_no_encontrada", "La imagen no existe.")
    return ruta


def guardar_objeto(clave: str, contenido: bytes):
    ruta = ruta_objeto(clave)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "wb") as f:
        f.write(contenido)


def preparar_almacenamiento():
    """Sube al almacén las imágenes del seed: la foto de imagenes_seed/ si existe; si no, un marcador PNG."""
    os.makedirs(ALMACEN, exist_ok=True)
    with Sesion() as sesion:
        claves = sesion.scalars(select(Producto.imagen_key).where(Producto.imagen_key.like("seed/%"))).all()
    for clave in claves:
        if os.path.exists(ruta_objeto(clave)):
            continue
        foto = os.path.join(IMAGENES_SEED, os.path.basename(clave))
        if os.path.exists(foto):
            with open(foto, "rb") as f:
                guardar_objeto(clave, f.read())
        else:
            guardar_objeto(clave, png_marcador())


@asynccontextmanager
async def ciclo_de_vida(app_: FastAPI):
    await run_in_threadpool(preparar_almacenamiento)
    app_.state.http = httpx.AsyncClient(timeout=TIMEOUT_INVENTARIO)
    yield
    await app_.state.http.aclose()


app = FastAPI(title="Servicio Productos", lifespan=ciclo_de_vida)
Instrumentator(should_instrument_requests_inprogress=True, inprogress_labels=True).instrument(app).expose(
    app, include_in_schema=False
)
bearer = HTTPBearer(auto_error=False)


class ErrorApi(HTTPException):
    def __init__(self, status_code: int, error: str, detalle: str):
        super().__init__(status_code=status_code, detail=detalle)
        self.error = error


@app.exception_handler(ErrorApi)
def manejar_error_api(_: Request, exc: ErrorApi):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.error, "detalle": exc.detail})


@app.exception_handler(RequestValidationError)
def manejar_validacion(_: Request, exc: RequestValidationError):
    detalle = "; ".join(f"{'.'.join(map(str, e['loc'][1:]))}: {e['msg']}" for e in exc.errors())
    return JSONResponse(status_code=422, content={"error": "validacion", "detalle": detalle})


def exigir_admin(cred: HTTPAuthorizationCredentials | None = Depends(bearer)):
    try:
        claims = jwt.decode(cred.credentials, JWT_SECRET, algorithms=["HS256"]) if cred else None
    except JWTError:
        claims = None
    if not claims:
        raise ErrorApi(401, "no_autenticado", "Token ausente, inválido o vencido.")
    if claims.get("rol") != "admin":
        raise ErrorApi(403, "prohibido", "Se requiere rol admin.")


def firma(clave: str, exp: int) -> str:
    return hmac.new(CLAVE_FIRMA, f"{clave}:{exp}".encode(), hashlib.sha256).hexdigest()


def url_imagen(clave: str | None) -> str | None:
    if not clave:
        return None
    exp = int(time.time() + URL_FIRMADA_VIGENCIA.total_seconds())
    return f"{PUBLIC_BASE_URL}/api/productos/imagenes/{clave}?exp={exp}&firma={firma(clave, exp)}"


async def stock_de(producto_id: uuid.UUID) -> int | None:
    """Stock leído de Inventario; si no responde en 500 ms se devuelve None (degradación controlada)."""
    try:
        r = await app.state.http.get(f"{INVENTARIO_URL}/api/inventario/{producto_id}")
        return r.json()["disponible"] if r.status_code == 200 else None
    except (httpx.HTTPError, KeyError, ValueError):
        return None


async def serializar(productos: list[Producto]) -> list[dict]:
    stocks = await asyncio.gather(*(stock_de(p.id) for p in productos))
    return [
        {
            "id": p.id,
            "sku": p.sku,
            "nombre": p.nombre,
            "categoria": p.categoria,
            "precio": float(p.precio),
            "stock": stock,
            "imagen_url": url_imagen(p.imagen_key),
        }
        for p, stock in zip(productos, stocks)
    ]


@app.get("/health")
def health():
    return {"status": "ok", "servicio": "productos"}


@app.get("/api/productos")
async def listar(
    pagina: int = Query(1, ge=1),
    tamano: int = Query(10, ge=1, le=100),
    q: str | None = Query(None, max_length=100),
):
    def consultar():
        filtro = select(Producto)
        if q:
            patron = f"%{q}%"
            filtro = filtro.where(or_(Producto.nombre.ilike(patron), Producto.sku.ilike(patron)))
        with Sesion() as sesion:
            total = sesion.scalar(select(func.count()).select_from(filtro.subquery()))
            items = sesion.scalars(filtro.order_by(Producto.sku).offset((pagina - 1) * tamano).limit(tamano)).all()
        return total, items

    total, items = await run_in_threadpool(consultar)
    return {"total": total, "items": await serializar(items)}


@app.get("/api/productos/imagenes/{clave:path}")
def imagen(clave: str, exp: int, firma_: str = Query(alias="firma")):
    if exp < time.time() or not hmac.compare_digest(firma_, firma(clave, exp)):
        raise ErrorApi(403, "url_invalida", "URL de imagen vencida o con firma inválida.")
    ruta = ruta_objeto(clave)
    if not os.path.exists(ruta):
        raise ErrorApi(404, "imagen_no_encontrada", "La imagen no existe.")
    return FileResponse(ruta)


@app.get("/api/productos/{producto_id}")
async def detalle(producto_id: uuid.UUID):
    def consultar():
        with Sesion() as sesion:
            return sesion.get(Producto, producto_id)

    producto = await run_in_threadpool(consultar)
    if producto is None:
        raise ErrorApi(404, "producto_no_encontrado", "El producto no existe.")
    return (await serializar([producto]))[0]


@app.post("/api/productos", status_code=201, dependencies=[Depends(exigir_admin)])
async def crear(
    nombre: str = Form(..., min_length=1, max_length=120),
    precio: Decimal = Form(..., gt=0),
    sku: str = Form(..., min_length=1, max_length=40),
    categoria: str = Form("general", max_length=40),
    imagen: UploadFile | None = File(None),
):
    contenido = await imagen.read() if imagen else None

    def guardar():
        clave = None
        if contenido:
            clave = f"productos/{uuid.uuid4()}-{os.path.basename(imagen.filename or 'imagen')}"
            guardar_objeto(clave, contenido)
        producto = Producto(sku=sku, nombre=nombre, categoria=categoria, precio=precio, imagen_key=clave)
        with Sesion() as sesion:
            sesion.add(producto)
            try:
                sesion.commit()
            except IntegrityError:
                raise ErrorApi(409, "sku_existe", "Ya existe un producto con ese SKU.")
        return producto

    producto = await run_in_threadpool(guardar)
    return (await serializar([producto]))[0]
