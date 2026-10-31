import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app.main import app


@pytest.fixture(scope="module")
def cliente():
    with TestClient(app) as c:  # ejecuta el ciclo de vida (bucket y cliente HTTP)
        yield c


def token(rol: str) -> dict:
    exp = datetime.now(timezone.utc) + timedelta(minutes=5)
    valor = jwt.encode({"sub": str(uuid.uuid4()), "rol": rol, "exp": exp}, os.environ["JWT_SECRET"], algorithm="HS256")
    return {"Authorization": f"Bearer {valor}"}


def test_paginacion_correcta(cliente):
    pagina1 = cliente.get("/api/productos", params={"pagina": 1, "tamano": 5}).json()
    pagina2 = cliente.get("/api/productos", params={"pagina": 2, "tamano": 5}).json()
    assert pagina1["total"] >= 20
    assert len(pagina1["items"]) == 5 and len(pagina2["items"]) == 5
    assert not {p["id"] for p in pagina1["items"]} & {p["id"] for p in pagina2["items"]}


def test_busqueda_por_nombre(cliente):
    items = cliente.get("/api/productos", params={"q": "teclado"}).json()["items"]
    assert [p["sku"] for p in items] == ["TEC-002"]


def test_listado_incluye_stock_e_imagen(cliente):
    items = cliente.get("/api/productos", params={"q": "TEC-001"}).json()["items"]
    assert items[0]["stock"] is not None
    assert items[0]["imagen_url"]


def test_producto_inexistente_devuelve_404(cliente):
    r = cliente.get(f"/api/productos/{uuid.uuid4()}")
    assert r.status_code == 404
    assert r.json()["error"] == "producto_no_encontrado"


def test_crear_sin_token_devuelve_401(cliente):
    assert cliente.post("/api/productos", data={"nombre": "X", "precio": "1000", "sku": "X-1"}).status_code == 401


def test_crear_con_rol_cliente_devuelve_403(cliente):
    r = cliente.post("/api/productos", data={"nombre": "X", "precio": "1000", "sku": "X-1"}, headers=token("cliente"))
    assert r.status_code == 403


def test_crear_con_admin_e_imagen_devuelve_201(cliente):
    sku = f"PRB-{uuid.uuid4().hex[:8]}"
    r = cliente.post(
        "/api/productos",
        data={"nombre": "Producto de prueba", "precio": "15000", "sku": sku},
        files={"imagen": ("prueba.png", b"\x89PNG\r\n\x1a\nprueba", "image/png")},
        headers=token("admin"),
    )
    assert r.status_code == 201, r.text
    assert r.json()["sku"] == sku
    assert r.json()["imagen_url"]


def test_url_firmada_sirve_la_imagen_y_rechaza_firma_alterada(cliente):
    url = cliente.get("/api/productos", params={"q": "TEC-001"}).json()["items"][0]["imagen_url"]
    ruta = url.split("localhost:8080", 1)[1]
    assert cliente.get(ruta).status_code == 200
    assert cliente.get(ruta[:-1] + ("0" if ruta[-1] != "0" else "1")).status_code == 403
