import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app

cliente = TestClient(app)
PASSWORD = "ClaveSegura123"


@pytest.fixture
def usuario():
    email = f"prueba-{uuid.uuid4().hex[:10]}@example.com"
    r = cliente.post("/api/usuarios/registro", json={"email": email, "password": PASSWORD, "nombre": "Prueba"})
    assert r.status_code == 201, r.text
    return email


def test_registro_devuelve_201(usuario):
    r = cliente.post("/api/usuarios/login", json={"email": usuario, "password": PASSWORD})
    assert r.status_code == 200


def test_registro_email_duplicado_devuelve_409(usuario):
    r = cliente.post("/api/usuarios/registro", json={"email": usuario, "password": PASSWORD, "nombre": "Otra"})
    assert r.status_code == 409
    assert r.json()["error"] == "email_existe"


def test_registro_invalido_devuelve_422():
    r = cliente.post("/api/usuarios/registro", json={"email": "no-es-email", "password": "corta", "nombre": ""})
    assert r.status_code == 422
    assert r.json()["error"] == "validacion"


def test_login_devuelve_token(usuario):
    r = cliente.post("/api/usuarios/login", json={"email": usuario, "password": PASSWORD})
    cuerpo = r.json()
    assert r.status_code == 200
    assert cuerpo["token_type"] == "bearer"
    assert cuerpo["expira_en"] == 15 * 60
    assert cuerpo["access_token"]


def test_login_invalido_devuelve_401(usuario):
    r = cliente.post("/api/usuarios/login", json={"email": usuario, "password": "incorrecta"})
    assert r.status_code == 401


def test_bloqueo_tras_5_intentos_devuelve_423(usuario):
    codigos = [
        cliente.post("/api/usuarios/login", json={"email": usuario, "password": "incorrecta"}).status_code
        for _ in range(5)
    ]
    assert codigos == [401] * 5
    r = cliente.post("/api/usuarios/login", json={"email": usuario, "password": PASSWORD})
    assert r.status_code == 423


def test_me_con_token_devuelve_200(usuario):
    token = cliente.post("/api/usuarios/login", json={"email": usuario, "password": PASSWORD}).json()["access_token"]
    r = cliente.get("/api/usuarios/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == usuario
    assert r.json()["rol"] == "cliente"


def test_me_sin_token_devuelve_401():
    assert cliente.get("/api/usuarios/me").status_code == 401
