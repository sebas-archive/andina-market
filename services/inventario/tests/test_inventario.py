import os
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import Sesion, Stock, app

cliente = TestClient(app)
TOKEN = {"X-Service-Token": os.environ["SERVICE_TOKEN"]}


@pytest.fixture
def producto():
    """Fila de stock propia de cada prueba, para no tocar los datos del seed."""
    producto_id = uuid.uuid4()
    with Sesion() as sesion:
        sesion.add(Stock(producto_id=producto_id, disponible=5, reservado=0))
        sesion.commit()
    return str(producto_id)


def test_consulta_devuelve_existencias(producto):
    r = cliente.get(f"/api/inventario/{producto}")
    assert r.status_code == 200
    assert r.json() == {"producto_id": producto, "disponible": 5, "reservado": 0}


def test_consulta_producto_inexistente_devuelve_404():
    assert cliente.get(f"/api/inventario/{uuid.uuid4()}").status_code == 404


def test_reserva_descuenta(producto):
    r = cliente.post(f"/api/inventario/{producto}/reservar", json={"cantidad": 3}, headers=TOKEN)
    assert r.status_code == 200
    assert cliente.get(f"/api/inventario/{producto}").json()["disponible"] == 2


def test_reserva_sin_stock_devuelve_409(producto):
    r = cliente.post(f"/api/inventario/{producto}/reservar", json={"cantidad": 6}, headers=TOKEN)
    assert r.status_code == 409
    assert r.json()["error"] == "stock_insuficiente"


def test_reserva_sin_token_devuelve_401(producto):
    r = cliente.post(f"/api/inventario/{producto}/reservar", json={"cantidad": 1})
    assert r.status_code == 401


def test_liberacion_repone(producto):
    cliente.post(f"/api/inventario/{producto}/reservar", json={"cantidad": 4}, headers=TOKEN)
    r = cliente.post(f"/api/inventario/{producto}/liberar", json={"cantidad": 4}, headers=TOKEN)
    assert r.status_code == 200
    assert cliente.get(f"/api/inventario/{producto}").json() == {"producto_id": producto, "disponible": 5, "reservado": 0}
