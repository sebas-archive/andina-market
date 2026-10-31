"""Pruebas contra los servicios reales de productos e inventario en la red de Docker."""
import os
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app import main
from app.main import app

cliente = TestClient(app)


def cabecera(usuario_id: str | None = None) -> dict:
    exp = datetime.now(timezone.utc) + timedelta(minutes=5)
    claims = {"sub": usuario_id or str(uuid.uuid4()), "rol": "cliente", "exp": exp}
    return {"Authorization": f"Bearer {jwt.encode(claims, os.environ['JWT_SECRET'], algorithm='HS256')}"}


@pytest.fixture(scope="module")
def catalogo():
    r = httpx.get(f"{main.PRODUCTOS_URL}/api/productos", params={"q": "HOG", "tamano": 5})
    return {p["sku"]: p for p in r.json()["items"]}


def disponible(producto_id: str) -> int:
    return httpx.get(f"{main.INVENTARIO_URL}/api/inventario/{producto_id}").json()["disponible"]


def crear(items: list[tuple[str, int]], headers: dict, **extra) -> httpx.Response:
    cuerpo = {"items": [{"producto_id": pid, "cantidad": c} for pid, c in items]}
    return cliente.post("/api/pedidos", json=cuerpo, headers={**headers, **extra})


def test_crear_pedido_devuelve_201(catalogo):
    r = crear([(catalogo["HOG-001"]["id"], 1)], cabecera())
    assert r.status_code == 201, r.text
    assert r.json()["estado"] == "creado"


def test_sin_token_devuelve_401(catalogo):
    assert crear([(catalogo["HOG-001"]["id"], 1)], {}).status_code == 401


def test_sin_stock_devuelve_409_y_compensa_la_reserva(catalogo):
    a, b = catalogo["HOG-002"]["id"], catalogo["HOG-003"]["id"]
    antes = disponible(a)
    r = crear([(a, 1), (b, 1000)], cabecera())
    assert r.status_code == 409
    assert r.json()["error"] == "stock_insuficiente"
    assert disponible(a) == antes  # la reserva de `a` se liberó


def test_total_correcto_con_dos_items(catalogo):
    a, b = catalogo["HOG-004"], catalogo["HOG-005"]
    r = crear([(a["id"], 2), (b["id"], 3)], cabecera())
    assert r.status_code == 201
    assert r.json()["total"] == a["precio"] * 2 + b["precio"] * 3


def test_reintento_con_misma_idempotency_key_devuelve_el_mismo_pedido(catalogo):
    usuario, clave = cabecera(), {"Idempotency-Key": str(uuid.uuid4())}
    producto = catalogo["HOG-001"]["id"]
    primero = crear([(producto, 1)], usuario, **clave)
    antes = disponible(producto)
    segundo = crear([(producto, 1)], usuario, **clave)
    assert primero.json()["id"] == segundo.json()["id"]
    assert disponible(producto) == antes  # el reintento no reservó otra vez


def test_pago_exitoso_y_consulta(catalogo, monkeypatch):
    monkeypatch.setattr(main, "PAGO_FALLA_PCT", 0)
    usuario = cabecera()
    pedido = crear([(catalogo["HOG-001"]["id"], 1)], usuario).json()
    r = cliente.post(f"/api/pedidos/{pedido['id']}/pago", headers=usuario)
    assert r.status_code == 200 and r.json()["estado"] == "pagado"
    consulta = cliente.get(f"/api/pedidos/{pedido['id']}", headers=usuario).json()
    assert consulta["estado"] == "pagado" and len(consulta["items"]) == 1
    assert [p["id"] for p in cliente.get("/api/pedidos", headers=usuario).json()] == [pedido["id"]]


def test_pago_rechazado_devuelve_402_y_libera_stock(catalogo, monkeypatch):
    monkeypatch.setattr(main, "PAGO_FALLA_PCT", 100)
    usuario, producto = cabecera(), catalogo["HOG-002"]["id"]
    antes = disponible(producto)
    pedido = crear([(producto, 2)], usuario).json()
    assert disponible(producto) == antes - 2
    r = cliente.post(f"/api/pedidos/{pedido['id']}/pago", headers=usuario)
    assert r.status_code == 402
    assert disponible(producto) == antes


def test_pedido_de_otro_usuario_devuelve_404(catalogo):
    pedido = crear([(catalogo["HOG-001"]["id"], 1)], cabecera()).json()
    assert cliente.get(f"/api/pedidos/{pedido['id']}", headers=cabecera()).status_code == 404
