import uuid
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import seguridad
from .esquemas import LoginEntrada, RegistroEntrada, TokenSalida, UsuarioSalida
from .modelos import Usuario, obtener_sesion

app = FastAPI(title="Servicio Usuarios")
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


@app.get("/health")
def health():
    return {"status": "ok", "servicio": "usuarios"}


@app.post("/api/usuarios/registro", status_code=201, response_model=UsuarioSalida)
def registrar(datos: RegistroEntrada, sesion: Session = Depends(obtener_sesion)):
    email = datos.email.lower()
    if sesion.scalar(select(Usuario.id).where(Usuario.email == email)):
        raise ErrorApi(409, "email_existe", "Ya existe una cuenta con ese email.")
    usuario = Usuario(email=email, nombre=datos.nombre, password_hash=seguridad.hashear(datos.password))
    sesion.add(usuario)
    sesion.commit()
    return usuario


@app.post("/api/usuarios/login", response_model=TokenSalida)
def login(datos: LoginEntrada, sesion: Session = Depends(obtener_sesion)):
    ahora = datetime.now(timezone.utc)
    usuario = sesion.scalar(select(Usuario).where(Usuario.email == datos.email.lower()).with_for_update())
    if usuario is None:
        raise ErrorApi(401, "credenciales_invalidas", "Email o contraseña incorrectos.")
    if usuario.bloqueado_hasta and usuario.bloqueado_hasta > ahora:
        raise ErrorApi(423, "cuenta_bloqueada", "Cuenta bloqueada por intentos fallidos; intente más tarde.")

    if not seguridad.verificar(datos.password, usuario.password_hash):
        if usuario.primer_fallo is None or ahora - usuario.primer_fallo > seguridad.VENTANA_BLOQUEO:
            usuario.primer_fallo, usuario.intentos_fallidos = ahora, 1
        else:
            usuario.intentos_fallidos += 1
        if usuario.intentos_fallidos >= seguridad.MAX_INTENTOS:
            usuario.bloqueado_hasta = ahora + seguridad.VENTANA_BLOQUEO
        sesion.commit()
        raise ErrorApi(401, "credenciales_invalidas", "Email o contraseña incorrectos.")

    usuario.intentos_fallidos, usuario.primer_fallo, usuario.bloqueado_hasta = 0, None, None
    sesion.commit()
    token, expira_en = seguridad.emitir_token(str(usuario.id), usuario.rol)
    return TokenSalida(access_token=token, expira_en=expira_en)


@app.get("/api/usuarios/me", response_model=UsuarioSalida)
def me(cred: HTTPAuthorizationCredentials | None = Depends(bearer), sesion: Session = Depends(obtener_sesion)):
    claims = seguridad.decodificar_token(cred.credentials) if cred else None
    if not claims:
        raise ErrorApi(401, "no_autenticado", "Token ausente, inválido o vencido.")
    usuario = sesion.get(Usuario, uuid.UUID(claims["sub"]))
    if usuario is None:
        raise ErrorApi(401, "no_autenticado", "El usuario del token no existe.")
    return usuario
