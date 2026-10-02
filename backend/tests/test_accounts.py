import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from conftest import APP

from app.services import accounts


@pytest.fixture
def google(monkeypatch):
    """Google simulado: el comprobante "ok:<sub>" vale; cualquier otro, no."""
    monkeypatch.setattr(accounts, "GOOGLE_CLIENT_ID", "bateas.apps.googleusercontent.com")
    def verify(credential):
        if not credential.startswith("ok:"):
            raise HTTPException(401, "Google no validó el inicio de sesión. Probá de nuevo.")
        sub = credential[3:]
        return {"sub": sub, "email": f"{sub}@gmail.com", "name": sub.title(), "picture": ""}
    monkeypatch.setattr(accounts, "verify_google", verify)


def login(sub):
    c = TestClient(APP)
    r = c.post("/api/cuenta/google", json={"value": f"ok:{sub}"})
    assert r.status_code == 200, r.text
    return c, r.json()


def test_sign_up_creates_a_free_public_store_owned_by_the_account(google, boss):
    c, me = login("ana")
    assert me["email"] == "ana@gmail.com" and me["stores"] == []
    assert c.post("/api/cuenta/tiendas", json={"name": "Disquería Ana", "slug": "cuenta"}).status_code == 400  # reservada
    r = c.post("/api/cuenta/tiendas", json={"name": "Disquería Ana", "slug": "disqueria-ana"})
    assert r.status_code == 200 and c.get("/api/cuenta").json()["stores"][0]["slug"] == "disqueria-ana"
    # entra a su admin con Google, sin contraseña
    status = c.get("/api/t/disqueria-ana/admin/status").json()
    assert status["plan"]["plan"] == "free" and status["code_required"] is False
    assert c.post("/api/cuenta/tiendas", json={"name": "Otra", "slug": "otra-de-ana"}).status_code == 409  # 1 por cuenta
    # otra cuenta no entra a la tienda de Ana
    other, _ = login("beto")
    assert other.get("/api/t/disqueria-ana/admin/status").status_code == 401
    # el super admin ve de quién es y queda registrado
    t = next(t for t in boss.get("/api/super/tenants").json() if t["slug"] == "disqueria-ana")
    assert t["owner_email"] == "ana@gmail.com"
    kinds = [e["kind"] for e in boss.get("/api/super/events").json()]
    assert {"account_created", "tenant_created"} <= set(kinds)
    assert any(a["email"] == "ana@gmail.com" and a["stores"] == "disqueria-ana" for a in boss.get("/api/super/accounts").json())


def test_second_login_is_the_same_account(google):
    _, first = login("carla")
    _, again = login("carla")
    assert first["id"] == again["id"]


def test_bad_or_missing_credentials(google, client):
    assert client.post("/api/cuenta/google", json={"value": "trucho"}).status_code == 401
    assert client.get("/api/cuenta").status_code == 401
    forged = TestClient(APP, cookies={"account": "1.firmafalsa"})
    assert forged.get("/api/cuenta").status_code == 401


def test_logout(google):
    c, _ = login("dani")
    c.post("/api/cuenta/logout")
    assert c.get("/api/cuenta").status_code == 401
