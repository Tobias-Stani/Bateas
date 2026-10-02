from datetime import datetime, timedelta, timezone

from conftest import CATALOG_MAP, png, upload, xlsx

FREE = {"plan": "free"}


def test_free_plan_limits(shop, boss):
    slug, admin = shop
    boss.patch(f"/api/super/tenants/{slug}", json=FREE)
    head = ("Artist", "Title", "Label", "Medium", "Description", "Genre", "Barcode", "Price")
    rows = [(f"Artista {i}", f"Disco {i}", "Sello", "CD", "", "Rock", "", 1000) for i in range(51)]
    admin.post(f"/api/t/{slug}/admin/upload/preview", files={"file": ("lista.xlsx", xlsx(head, *rows))})
    r = admin.post(f"/api/t/{slug}/admin/upload/confirm", json={"header_row": 1, "mapping": CATALOG_MAP})
    assert r.status_code == 403 and "hasta 50 discos" in r.json()["detail"] and "51" in r.json()["detail"]
    upload(admin, slug, xlsx(head, *rows[:50]), CATALOG_MAP)  # 50 justos: entra

    assert admin.post(f"/api/t/{slug}/admin/secciones", json={"name": "Una"}).status_code == 200
    assert admin.post(f"/api/t/{slug}/admin/secciones", json={"name": "Dos"}).status_code == 403
    group = admin.post(f"/api/t/{slug}/admin/banner-bloques", json={"name": "B"}).json()["id"]
    banner = lambda: admin.post(f"/api/t/{slug}/admin/banners", data={"group_id": group}, files={"file": ("b.png", png(), "image/png")})
    assert banner().status_code == 200 and banner().status_code == 403

    plan = admin.get(f"/api/t/{slug}/admin/status").json()["plan"]
    assert plan["plan"] == "free" and plan["limits"]["discs"] == 50 and plan["usage"] == {"discs": 50, "banners": 1, "sections": 1}

    # pasa a Premium: sin límites
    boss.patch(f"/api/super/tenants/{slug}", json={"plan": "premium"})
    assert admin.post(f"/api/t/{slug}/admin/secciones", json={"name": "Dos"}).status_code == 200


def test_premium_expires_by_itself(shop, boss):
    slug, admin = shop
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    t = boss.patch(f"/api/super/tenants/{slug}", json={"plan": "premium", "premium_until": past}).json()
    assert t["plan"] == "premium" and t["plan_now"] == "free"  # asignado Premium, pero vencido
    assert boss.patch(f"/api/super/tenants/{slug}", json={"premium_until": future}).json()["plan_now"] == "premium"
    assert boss.patch(f"/api/super/tenants/{slug}", json={"premium_until": ""}).json()["premium_until"] is None  # sin vencimiento
    assert boss.patch(f"/api/super/tenants/{slug}", json={"plan": "oro"}).status_code == 400


def test_new_stores_start_free(boss):
    r = boss.post("/api/super/tenants", json={"name": "Nueva", "slug": "nueva-gratis", "admin_password": "pass123", "client_code": "codigo"})
    assert r.json()["plan"] == "free" and r.json()["plan_now"] == "free"


def test_discogs_is_premium(shop, boss):
    slug, admin = shop
    boss.patch(f"/api/super/tenants/{slug}", json=FREE)
    r = admin.post(f"/api/t/{slug}/admin/discogs/import")
    assert r.status_code == 403 and "plan Premium" in r.json()["detail"]


def test_only_super_admin_turns_on_online_payments(shop, boss):
    slug, admin = shop
    assert admin.post(f"/api/t/{slug}/admin/mercadopago/connect").status_code == 403
    assert admin.put(f"/api/t/{slug}/admin/mercadopago/payments", json={"value": True}).status_code == 403
    assert admin.get(f"/api/t/{slug}/admin/status").json()["mercadopago"]["allowed"] is False
    assert boss.get(f"/api/t/{slug}/admin/status").json()["mercadopago"]["allowed"] is True


def test_free_store_asks_for_premium_and_super_admin_sees_it(shop, boss):
    slug, admin = shop
    boss.patch(f"/api/super/tenants/{slug}", json=FREE)
    assert admin.get(f"/api/t/{slug}/admin/status").json()["plan"]["requested_at"] is None
    assert admin.post(f"/api/t/{slug}/admin/premium").json()["requested_at"]
    assert any(r["slug"] == slug for r in boss.get("/api/super/stats").json()["premium_requests"])
    boss.patch(f"/api/super/tenants/{slug}", json={"plan": "premium"})
    assert admin.post(f"/api/t/{slug}/admin/premium").status_code == 409  # ya es Premium
