from conftest import CATALOG, CATALOG_MAP, upload, xlsx
from test_mercadopago import connect, mp  # noqa: F401  (fixture)

from app.services import tenants


def kinds(boss, slug):
    return [e["kind"] for e in boss.get("/api/super/events", params={"slug": slug}).json()]


def test_activity_is_logged_with_who_did_it(boss, shop, client):
    slug, admin = shop
    client.post(f"/api/t/{slug}/admin/login", json={"value": "mala"})
    admin.put(f"/api/t/{slug}/admin/whatsapp", json={"value": "54 9 11 1234 5678"})
    boss.put(f"/api/t/{slug}/admin/code_required", json={"value": False})  # el super admin entrando a un admin
    upload(admin, slug, xlsx(*CATALOG), CATALOG_MAP)
    events = boss.get("/api/super/events", params={"slug": slug}).json()
    by_kind = {e["kind"]: e for e in events}
    assert by_kind["admin_login_failed"]["actor"] == "admin"
    assert by_kind["catalog_uploaded"]["detail"] == {"source": "excel", "filename": "lista.xlsx", "discs": 5}
    changes = [(e["actor"], e["detail"]["field"]) for e in events if e["kind"] == "settings_changed"]
    assert changes == [("super", "code_required"), ("admin", "whatsapp")]  # del más nuevo al más viejo
    assert by_kind["tenant_created"]["actor"] == "super"
    assert "admin_password_hash" not in str(events)
    assert client.get("/api/super/events").status_code == 401  # solo el super admin


def test_payments_survive_tenant_deletion(boss, shop, client, mp):  # noqa: F811
    slug, admin = shop
    calls, replies = mp
    upload(admin, slug, xlsx(*CATALOG), CATALOG_MAP)
    connect(slug)
    boss.put(f"/api/t/{slug}/admin/mercadopago/payments", json={"value": True})
    replies["/checkout/preferences"] = {"init_point": "https://mp/pagar"}
    order = admin.post(f"/api/t/{slug}/pagar", json={"ids": [2]}).json()["order"]
    replies["/v1/payments/900"] = {"id": 900, "status": "approved", "external_reference": f"{slug}:{order}", "transaction_amount": 68000,
                                   "fee_details": [{"type": "mercadopago_fee", "amount": 4080}], "transaction_details": {"net_received_amount": 57120}}
    client.post(f"/api/mercadopago/webhook?slug={slug}", json={"type": "payment", "data": {"id": "900"}})
    client.post(f"/api/mercadopago/webhook?slug={slug}", json={"type": "payment", "data": {"id": "900"}})  # aviso repetido

    stats = boss.get("/api/super/stats").json()
    assert stats["by_slug"][slug] == {"slug": slug, "n": 1, "total": 68000, "fee": 6800, "mp_fee": 4080, "net": 57120}
    pay = [e for e in kinds(boss, slug) if e == "payment"]
    assert pay == ["payment"]  # el aviso repetido no duplica el evento

    boss.put(f"/api/super/tenants/{slug}/status", json={"value": "cancelled"})
    assert boss.delete(f"/api/super/tenants/{slug}").status_code == 200
    assert not tenants.find(slug)
    [ledger] = boss.get("/api/super/payments", params={"slug": slug}).json()
    assert ledger["payment_id"] == "900" and ledger["status"] == "approved" and ledger["items"][0]["id"] == 2
    assert {"tenant_deleted", "tenant_status", "payment", "checkout_started"} <= set(kinds(boss, slug))
