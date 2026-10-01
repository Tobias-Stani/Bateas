from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from conftest import CATALOG, CATALOG_MAP, upload, xlsx

from app.db import get_setting, set_settings
from app.services import mercadopago, tenants


@pytest.fixture
def mp(monkeypatch):
    """Mercado Pago configurado en el servidor, con 10% de comisión; las llamadas a la API quedan en `calls`."""
    monkeypatch.setattr(mercadopago, "MP_CLIENT_ID", "app-id")
    monkeypatch.setattr(mercadopago, "MP_CLIENT_SECRET", "app-secret")
    monkeypatch.setattr(mercadopago, "MP_FEE_PERCENT", 10.0)
    calls, replies = [], {}
    def fake(method, path, token="", body=None):
        calls.append((method, path, token, body))
        return replies[path](body) if callable(replies.get(path)) else replies.get(path, {})
    monkeypatch.setattr(mercadopago, "_call", fake)
    return calls, replies


def connect(slug, expires_in=timedelta(days=100)):
    when = (datetime.now(timezone.utc) + expires_in).isoformat(timespec="minutes")
    set_settings(tenants.find(slug), mp_token="seller-token", mp_refresh="refresh", mp_expires=when)


def test_without_server_app_nothing_is_offered(shop, client):
    slug, admin = shop
    assert client.get(f"/api/t/{slug}/brand").json()["payments"] is False
    assert admin.post(f"/api/t/{slug}/admin/mercadopago/connect").status_code == 400
    assert admin.post(f"/api/t/{slug}/pagar", json={"ids": [2]}).status_code == 400


def test_connect_uses_pkce_and_state(shop, mp):
    slug, admin = shop
    calls, replies = mp
    url = admin.post(f"/api/t/{slug}/admin/mercadopago/connect").json()["url"]
    q = parse_qs(urlparse(url).query)
    assert q["client_id"] == ["app-id"] and q["code_challenge_method"] == ["S256"] and q["state"][0].startswith(f"{slug}.")
    assert q["redirect_uri"] == ["http://testserver/api/mercadopago/callback"]
    bad = admin.get("/api/mercadopago/callback", params={"state": f"{slug}.otro", "code": "c"}, follow_redirects=False)
    assert bad.headers["location"].startswith(f"/{slug}/admin?mp=error")
    replies["/oauth/token"] = {"access_token": "seller-token", "refresh_token": "r", "user_id": 42, "expires_in": 15552000}
    ok = admin.get("/api/mercadopago/callback", params={"state": q["state"][0], "code": "c"}, follow_redirects=False)
    assert ok.headers["location"] == f"/{slug}/admin?mp=ok"
    body = calls[-1][3]
    assert body["grant_type"] == "authorization_code" and len(body["code_verifier"]) >= 43
    assert admin.get(f"/api/t/{slug}/admin/status").json()["mercadopago"]["connected"] is True


def test_checkout_uses_catalog_prices_and_fee(shop, client, mp):
    slug, admin = shop
    calls, replies = mp
    upload(admin, slug, xlsx(*CATALOG), CATALOG_MAP)
    assert admin.put(f"/api/t/{slug}/admin/mercadopago/payments", json={"value": True}).status_code == 400  # sin cuenta
    connect(slug)
    assert admin.put(f"/api/t/{slug}/admin/mercadopago/payments", json={"value": True}).json()["payments"] is True
    assert client.get(f"/api/t/{slug}/brand").json()["payments"] is True

    assert admin.post(f"/api/t/{slug}/pagar", json={"ids": [2, 3]}).status_code == 400  # #3 no tiene precio
    replies["/checkout/preferences"] = {"init_point": "https://mp/pagar", "sandbox_init_point": "https://sandbox"}
    r = admin.post(f"/api/t/{slug}/pagar", json={"ids": [2, 6, 2]}).json()
    assert r["url"] == "https://mp/pagar"
    method, path, token, pref = calls[-1]
    assert token == "seller-token" and [i["unit_price"] for i in pref["items"]] == [68000.0, 25000.0]
    assert pref["marketplace_fee"] == 9300.0 and pref["external_reference"] == str(r["order"])
    assert pref["back_urls"]["success"].endswith(f"/{slug}?pago=success&pedido={r['order']}")
    assert pref["notification_url"].endswith(f"/api/mercadopago/webhook?slug={slug}")
    assert admin.get(f"/api/t/{slug}/admin/pedidos").json() == []  # sin pago todavía: no se lista

    # aviso de Mercado Pago: se confirma consultando el pago con el token de la disquería
    replies["/v1/payments/555"] = {"id": 555, "status": "approved", "external_reference": str(r["order"]),
                                   "transaction_amount": 93000, "payer": {"email": "cliente@mail.com"}}
    assert client.post(f"/api/mercadopago/webhook?slug={slug}", json={"type": "payment", "data": {"id": "555"}}).status_code == 200
    [order] = admin.get(f"/api/t/{slug}/admin/pedidos").json()
    assert order["status"] == "approved" and order["payer"] == "cliente@mail.com" and order["total"] == 93000
    seen = admin.get(f"/api/t/{slug}/pedidos/{r['order']}", params={"payment_id": "555"}).json()
    assert seen["status"] == "approved" and "payer" not in seen

    # monto distinto al del pedido: no se da por pagado
    replies["/v1/payments/556"] = {**replies["/v1/payments/555"], "id": 556, "transaction_amount": 1}
    client.post(f"/api/mercadopago/webhook?slug={slug}", json={"type": "payment", "data": {"id": "556"}})
    assert admin.get(f"/api/t/{slug}/admin/pedidos").json()[0]["status"] == "amount_mismatch"
    assert client.post("/api/mercadopago/webhook?slug=no-existe", json={"type": "merchant_order"}).status_code == 200


def test_direct_token_mode_for_development(shop, mp, monkeypatch):
    slug, admin = shop
    calls, replies = mp
    monkeypatch.setattr(mercadopago, "MP_CLIENT_SECRET", "")  # sin la app OAuth
    monkeypatch.setattr(mercadopago, "MP_ACCESS_TOKEN", "TEST-token")
    upload(admin, slug, xlsx(*CATALOG), CATALOG_MAP)
    assert admin.post(f"/api/t/{slug}/admin/mercadopago/connect").json()["url"] == f"/{slug}/admin?mp=ok"
    assert admin.put(f"/api/t/{slug}/admin/mercadopago/payments", json={"value": True}).json()["fee_percent"] == 0
    replies["/checkout/preferences"] = {"init_point": "https://mp/pagar"}
    admin.post(f"/api/t/{slug}/pagar", json={"ids": [2]})
    _, _, token, pref = calls[-1]
    assert token == "TEST-token" and "marketplace_fee" not in pref  # la cuenta que cobra es la propia


def test_token_is_renewed_before_it_expires(shop, mp):
    slug, _ = shop
    calls, replies = mp
    connect(slug, expires_in=timedelta(days=2))
    replies["/oauth/token"] = {"access_token": "nuevo", "refresh_token": "r2", "expires_in": 15552000}
    t = tenants.find(slug)
    assert mercadopago.token(t) == "nuevo" and calls[-1][3]["grant_type"] == "refresh_token"
    assert get_setting(t, "mp_refresh") == "r2"
