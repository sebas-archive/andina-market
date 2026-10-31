import os
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_EXPIRA_MIN = int(os.environ.get("JWT_EXPIRA_MIN", "15"))
ALGORITMO = "HS256"

MAX_INTENTOS = 5
VENTANA_BLOQUEO = timedelta(minutes=15)

_contexto = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hashear(password: str) -> str:
    return _contexto.hash(password)


def verificar(password: str, password_hash: str) -> bool:
    return _contexto.verify(password, password_hash)


def emitir_token(usuario_id: str, rol: str) -> tuple[str, int]:
    expira_en = JWT_EXPIRA_MIN * 60
    exp = datetime.now(timezone.utc) + timedelta(seconds=expira_en)
    token = jwt.encode({"sub": usuario_id, "rol": rol, "exp": exp}, JWT_SECRET, algorithm=ALGORITMO)
    return token, expira_en


def decodificar_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[ALGORITMO])
    except JWTError:
        return None
