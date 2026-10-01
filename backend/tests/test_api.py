"""Comportamiento de la API vista desde afuera: lo que no tiene que cambiar cuando se reorganiza el código."""
from datetime import datetime, timedelta, timezone

from conftest import APP, CATALOG, CATALOG_MAP, png, upload, xlsx
from fastapi.testclient import TestClient


# --- páginas ---

def test_pages_are_routed(client):
    for path, marker in [("/", "Por melómanos, para melómanos"), ("/super", "Super admin"), ("/super/", "Super admin"),
                         ("/una-tienda", 'id="gate-title"'), ("/una-tienda/admin", "Administración")]:
        r = client.get(path)
        assert r.status_code == 200 and marker in r.text, path


def test_static_files_and_cache(client):
    assert ":root" in client.get("/style.css").text
    assert client.get("/logo.svg").text.startswith("<svg")
    for path in ["/", "/una-tienda", "/super", "/common.js", "/style.css"]:
        assert client.get(path).headers.get("cache-control") == "no-cache", path
    assert "cache-control" not in client.get("/logo.svg").headers


# --- super admin ---

def test_super_login(client):
    assert client.get("/api/super/tenants").status_code == 401
    assert client.post("/api/super/login", json={"value": "mala"}).status_code == 401
    assert client.post("/api/super/login", json={"value": "s3cret"}).status_code == 200
    assert client.get("/api/super/tenants").status_code == 200


def test_create_tenant_validations(boss):
    ok = {"name": "El Surco", "slug": "el-surco", "admin_password": "surco99", "client_code": "surco", "whatsapp": "+54 9 11 5555-0000"}
    r = boss.post("/api/super/tenants", json=ok)
    assert r.status_code == 200 and r.json()["whatsapp"] == "5491155550000" and "admin_hash" not in r.json()
    assert boss.post("/api/super/tenants", json=ok).status_code == 409
    for bad in [{"slug": "super"}, {"slug": "-mal"}, {"slug": "Con Espacios"}, {"admin_password": "123"}, {"client_code": "ab"}, {"name": "x"}]:
        assert boss.post("/api/super/tenants", json={**ok, "slug": "otra", **bad}).status_code == 400, bad


def test_update_tenant_brand(boss, shop, client):
    slug, _ = shop
    r = boss.patch(f"/api/super/tenants/{slug}", json={"name": "Chopp & Rock", "accent": "#ff0000", "notes": "cobra el 5"})
    assert r.status_code == 200 and r.json()["accent"] == "#ff0000" and "admin_hash" not in r.json()
    for bad in [{"accent": "red;}"}, {"logo": "javascript:alert(1)"}, {"logo": "//evil.tld/x.png"}, {"name": "x"}]:
        assert boss.patch(f"/api/super/tenants/{slug}", json=bad).status_code == 400, bad
    for good in ["/logo.svg", "https://x.com/a.png", ""]:
        assert boss.patch(f"/api/super/tenants/{slug}", json={"logo": good}).status_code == 200, good
    brand = client.get(f"/api/t/{slug}/brand").json()
    assert brand["name"] == "Chopp & Rock" and brand["logo"] == "/logo.svg" and brand["status"] == "active"


def test_tenant_status_lifecycle(boss, shop, client):
    slug, admin = shop
    boss.put(f"/api/super/tenants/{slug}/status", json={"value": "suspended"})
    assert client.get(f"/api/t/{slug}/brand").status_code == 423
    assert admin.get(f"/api/t/{slug}/admin/status").status_code == 423
    assert boss.get(f"/api/t/{slug}/admin/status").status_code == 200  # el super entra igual
    assert boss.get(f"/api/t/{slug}/brand").json()["status"] == "suspended"
    assert boss.delete(f"/api/super/tenants/{slug}").status_code == 400  # solo canceladas
    boss.put(f"/api/super/tenants/{slug}/status", json={"value": "cancelled"})
    assert client.get(f"/api/t/{slug}/brand").status_code == 410
    assert boss.put(f"/api/super/tenants/{slug}/status", json={"value": "otra"}).status_code == 400
    assert boss.delete(f"/api/super/tenants/{slug}").status_code == 200
    assert client.get(f"/api/t/{slug}/brand").status_code == 404


def test_password_reset_closes_admin_sessions(boss, shop):
    slug, admin = shop
    assert boss.put(f"/api/super/tenants/{slug}/password", json={"value": "123"}).status_code == 400
    assert boss.put(f"/api/super/tenants/{slug}/password", json={"value": "nueva456"}).status_code == 200
    assert admin.get(f"/api/t/{slug}/admin/status").status_code == 401
    assert TestClient(APP).post(f"/api/t/{slug}/admin/login", json={"value": "nueva456"}).status_code == 200


def test_super_lists_tenants_with_usage(boss, shop):
    slug, admin = shop
    upload(admin, slug, xlsx(*CATALOG), CATALOG_MAP)
    t = next(t for t in boss.get("/api/super/tenants").json() if t["slug"] == slug)
    assert t["total"] == 5 and t["client_code"] == "codigo" and t["code_required"] is True and "admin_hash" not in t


# --- aislamiento entre disquerías ---

def test_tenants_are_isolated(boss, shop):
    slug, admin = shop
    other = "aislada"
    boss.post("/api/super/tenants", json={"name": "Otra", "slug": other, "admin_password": "otra123", "client_code": "otracode"})
    r = TestClient(APP).post(f"/api/t/{slug}/admin/login", json={"value": "pass123"})
    assert f"Path=/api/t/{slug}" in r.headers["set-cookie"]
    stolen = TestClient(APP)
    stolen.cookies.set("admin", admin.cookies.get("admin"))
    assert stolen.get(f"/api/t/{other}/admin/status").status_code == 401
    assert TestClient(APP).post(f"/api/t/{other}/admin/login", json={"value": "pass123"}).status_code == 401
    assert TestClient(APP).post(f"/api/t/{other}/login", json={"value": "codigo"}).status_code == 401


# --- tienda ---

def test_client_access_with_code(shop, client):
    slug, admin = shop
    upload(admin, slug, xlsx(*CATALOG), CATALOG_MAP)
    assert client.get(f"/api/t/{slug}/discos").status_code == 401
    assert client.post(f"/api/t/{slug}/login", json={"value": "mal"}).status_code == 401
    assert client.post(f"/api/t/{slug}/login", json={"value": " codigo "}).status_code == 200
    assert client.get(f"/api/t/{slug}/discos").json()["total"] == 5
    client.post(f"/api/t/{slug}/logout")
    assert client.get(f"/api/t/{slug}/discos").status_code == 401


def test_public_store_toggle(shop, client):
    slug, admin = shop
    assert client.put(f"/api/t/{slug}/admin/code_required", json={"value": False}).status_code == 401
    assert admin.put(f"/api/t/{slug}/admin/code_required", json={"value": False}).json()["code_required"] is False
    assert client.get(f"/api/t/{slug}/discos").status_code == 200
    assert client.get(f"/api/t/{slug}/estado").json()["code_required"] is False
    admin.put(f"/api/t/{slug}/admin/code_required", json={"value": True})
    assert client.get(f"/api/t/{slug}/discos").status_code == 401


def test_closing_date(shop, client):
    slug, admin = shop
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    assert admin.put(f"/api/t/{slug}/admin/closes_at", json={"value": "mañana"}).status_code == 400
    assert admin.put(f"/api/t/{slug}/admin/closes_at", json={"value": "2030-01-01T10:00"}).status_code == 400  # sin zona
    assert admin.put(f"/api/t/{slug}/admin/closes_at", json={"value": past}).json()["closed"] is True
    assert client.post(f"/api/t/{slug}/login", json={"value": "codigo"}).status_code == 403
    assert client.get(f"/api/t/{slug}/estado").json()["closed"] is True
    assert admin.get(f"/api/t/{slug}/discos").status_code == 200  # el admin entra aunque esté cerrado
    admin.put(f"/api/t/{slug}/admin/closes_at", json={"value": ""})
    assert client.post(f"/api/t/{slug}/login", json={"value": "codigo"}).status_code == 200


def test_brand_has_store_settings(shop, client):
    slug, admin = shop
    admin.put(f"/api/t/{slug}/admin/whatsapp", json={"value": "+54 9 11 1234-5678"})
    b = client.get(f"/api/t/{slug}/brand").json()
    assert b["whatsapp"] == "5491112345678" and "{discos}" in b["message"] and b["custom_columns"] == []
    assert b["accent"].startswith("#") and b["highlight"].startswith("#")


def test_contact_info(shop, client):
    slug, admin = shop
    put = lambda **c: admin.put(f"/api/t/{slug}/admin/contact", json=c)
    assert put(email="no-es-mail").status_code == 400
    assert put(phone="12").status_code == 400
    assert put(instagram="con espacio").status_code == 400
    r = put(address=" Corrientes 1234 ", city="CABA", phone="11 4567-8901", email="hola@surco.com",
            instagram="https://instagram.com/el.surco/")
    assert r.json()["contact"] == {"address": "Corrientes 1234", "city": "CABA", "phone": "11 4567-8901",
                                   "email": "hola@surco.com", "instagram": "el.surco"}
    assert client.get(f"/api/t/{slug}/brand").json()["contact"]["instagram"] == "el.surco"
    assert admin.get(f"/api/t/{slug}/admin/status").json()["contact"]["city"] == "CABA"
    assert put().json()["contact"] == {}  # todo vacío: se borra


def test_search_filters_and_id(shop):
    slug, admin = shop
    upload(admin, slug, xlsx(*CATALOG), CATALOG_MAP)
    d = lambda q="", **kw: admin.get(f"/api/t/{slug}/discos", params={"q": q, **kw}).json()
    assert [i["artist"] for i in d("madonna confessions")["items"]] == ["MADONNA", "MADONNA"]
    assert [i["id"] for i in d("#3")["items"]] == [3] and [i["id"] for i in d("3")["items"]][0] == 3
    assert d(media="CD")["total"] == 3 and d(genre="Jazz")["total"] == 1
    assert d()["page_size"] == 50
    two = d(per_page=2, page=2)
    assert two["page_size"] == 2 and [i["id"] for i in two["items"]] == [4, 5] and two["total"] == 5
    assert d(per_page=500)["page_size"] == 50 and d(per_page=0)["page_size"] == 1
    f = admin.get(f"/api/t/{slug}/filtros").json()
    assert f["media"] == ["CD", "Vinyl"] and "Jazz" in f["genre"]
    item = d("radiohead")["items"][0]
    assert item["price"] == "68000" and item["barcode"] == "634904078164" and item["extra"] == {} and "k" not in item


def test_admin_settings_validation(shop):
    slug, admin = shop
    assert admin.put(f"/api/t/{slug}/admin/code", json={"value": "ab"}).status_code == 400
    assert admin.put(f"/api/t/{slug}/admin/code", json={"value": " nuevo "}).json()["client_code"] == "nuevo"
    assert admin.put(f"/api/t/{slug}/admin/whatsapp", json={"value": "12"}).status_code == 400
    assert admin.put(f"/api/t/{slug}/admin/message", json={"template": "Hola", "line": "{title}"}).status_code == 400
    assert admin.put(f"/api/t/{slug}/admin/message", json={"template": "{discos}", "line": " "}).status_code == 400
    r = admin.put(f"/api/t/{slug}/admin/message", json={"template": "Hola 👋\n{discos}", "line": "💿 {title}"})
    assert r.json()["message"] == "Hola 👋\n{discos}"
    assert "Quiero cotizar" in admin.delete(f"/api/t/{slug}/admin/message").json()["message"]
    s = admin.get(f"/api/t/{slug}/admin/status").json()
    assert s["client_code"] == "nuevo" and s["code_required"] is True and s["total"] == 0


# --- carga del Excel ---

def test_upload_detects_spanish_header_and_custom_columns(shop):
    slug, admin = shop
    data = xlsx(["CHOPP & ROCK RECORDS"], [], ["Artista", "Título / Álbum", "Origen", "Insert", "Precio (ARS)"],
                ["ABBA", "The Singles", "Reino Unido", "Sí", 75000.0])
    r = admin.post(f"/api/t/{slug}/admin/upload/preview", files={"file": ("l.xlsx", data)}).json()
    assert r["header_row"] == 3
    assert [c["field"] for c in r["columns"]] == ["artist", "title", "origin", "custom", "price"]
    bad = {"0": "artist", "1": "artist", "2": "origin", "3": "custom", "4": "price"}
    assert admin.post(f"/api/t/{slug}/admin/upload/confirm", json={"header_row": 3, "mapping": bad}).status_code == 400
    assert admin.post(f"/api/t/{slug}/admin/upload/confirm", json={"header_row": 3, "mapping": {"0": "artist"}}).status_code == 400
    assert admin.post(f"/api/t/{slug}/admin/upload/confirm", json={"header_row": 3, "mapping": {"0": "artist", "1": "title", "2": "hack"}}).status_code == 400
    upload(admin, slug, data, {"0": "artist", "1": "title", "2": "origin", "3": "custom", "4": "price"}, header_row=3)
    disc = admin.get(f"/api/t/{slug}/discos").json()["items"][0]
    assert disc["id"] == 4 and disc["extra"] == {"Insert": "Sí"} and disc["price"] == "75000" and disc["origin"] == "Reino Unido"
    assert admin.get(f"/api/t/{slug}/brand").json()["custom_columns"] == [{"key": "insert", "name": "Insert"}]
    again = admin.post(f"/api/t/{slug}/admin/upload/preview", files={"file": ("l.xlsx", data)}).json()
    assert [c["field"] for c in again["columns"]][3] == "custom"  # recuerda la asignación


def test_upload_extra_goes_to_description(shop):
    slug, admin = shop
    data = xlsx(["Artist", "Title", "Insert"], ["X", "Y", "Sí"])
    upload(admin, slug, data, {"0": "artist", "1": "title", "2": "extra"})
    assert admin.get(f"/api/t/{slug}/discos").json()["items"][0]["description"] == "Insert: Sí"


def test_upload_errors(shop):
    slug, admin = shop
    assert admin.post(f"/api/t/{slug}/admin/upload/preview", files={"file": ("l.csv", b"a,b")}).status_code == 400
    assert admin.post(f"/api/t/{slug}/admin/upload/preview", files={"file": ("l.xlsx", b"no es excel")}).status_code == 400
    assert admin.post(f"/api/t/{slug}/admin/upload/confirm", json={"header_row": 1, "mapping": {"0": "artist", "1": "title"}}).status_code == 400
    admin.post(f"/api/t/{slug}/admin/upload/preview", files={"file": ("l.xlsx", xlsx(["Artist", "Title"]))})
    assert admin.post(f"/api/t/{slug}/admin/upload/confirm", json={"header_row": 1, "mapping": {"0": "artist", "1": "title"}}).status_code == 400


def test_delete_catalog(shop):
    slug, admin = shop
    upload(admin, slug, xlsx(*CATALOG), CATALOG_MAP)
    admin.delete(f"/api/t/{slug}/admin/catalog")
    assert admin.get(f"/api/t/{slug}/admin/status").json()["total"] == 0
    assert admin.get(f"/api/t/{slug}/discos").json()["total"] == 0


# --- secciones ---

def test_sections_crud_and_public_view(shop, client):
    slug, admin = shop
    upload(admin, slug, xlsx(*CATALOG), CATALOG_MAP)
    admin.put(f"/api/t/{slug}/admin/code_required", json={"value": False})
    assert admin.post(f"/api/t/{slug}/admin/secciones", json={"name": " "}).status_code == 400
    sid = admin.post(f"/api/t/{slug}/admin/secciones", json={"name": "Más vendidos"}).json()["id"]
    hidden = admin.post(f"/api/t/{slug}/admin/secciones", json={"name": "Oculta"}).json()["id"]
    for disc_id in (2, 3, 4):
        assert admin.post(f"/api/t/{slug}/admin/secciones/{sid}/discos", json={"disc_id": disc_id}).status_code == 200
    assert admin.post(f"/api/t/{slug}/admin/secciones/{sid}/discos", json={"disc_id": 2}).status_code == 409
    assert admin.post(f"/api/t/{slug}/admin/secciones/{sid}/discos", json={"disc_id": 999}).status_code == 404
    assert admin.post(f"/api/t/{slug}/admin/secciones/999/discos", json={"disc_id": 2}).status_code == 404
    admin.post(f"/api/t/{slug}/admin/secciones/{hidden}/discos", json={"disc_id": 5})
    admin.patch(f"/api/t/{slug}/admin/secciones/{hidden}", json={"visible": False})
    admin.patch(f"/api/t/{slug}/admin/secciones/{sid}", json={"name": "Top"})
    public = client.get(f"/api/t/{slug}/secciones").json()
    assert [(s["name"], [i["id"] for i in s["items"]]) for s in public] == [("Top", [2, 3, 4])]
    items = admin.get(f"/api/t/{slug}/admin/secciones").json()[0]["items"]
    ids = [it["item_id"] for it in items]
    admin.put(f"/api/t/{slug}/admin/secciones/{sid}/orden", json={"ids": ids[::-1]})
    assert [i["id"] for i in client.get(f"/api/t/{slug}/secciones").json()[0]["items"]] == [4, 3, 2]
    admin.delete(f"/api/t/{slug}/admin/secciones/{sid}/discos/{ids[0]}")
    assert len(admin.get(f"/api/t/{slug}/admin/secciones").json()[0]["items"]) == 2
    admin.delete(f"/api/t/{slug}/admin/secciones/{hidden}")
    assert len(admin.get(f"/api/t/{slug}/admin/secciones").json()) == 1


def test_sections_survive_new_excel_and_keep_editions_apart(shop):
    slug, admin = shop
    upload(admin, slug, xlsx(*CATALOG), CATALOG_MAP)
    sid = admin.post(f"/api/t/{slug}/admin/secciones", json={"name": "S"}).json()["id"]
    for disc_id in (2, 3, 4, 5):  # 3 y 4: dos ediciones de Confessions II
        assert admin.post(f"/api/t/{slug}/admin/secciones/{sid}/discos", json={"disc_id": disc_id}).status_code == 200
    # mes siguiente: sin Soda Stereo y con las filas corridas
    r = upload(admin, slug, xlsx(CATALOG[0], ("Nuevo", "Disco", "", "", "", "", None, None), *[r for r in CATALOG[1:] if r[0] != "Soda Stereo"]), CATALOG_MAP)
    assert r["sections_missing"] == [{"name": "S", "missing": 1}]
    items = admin.get(f"/api/t/{slug}/admin/secciones").json()[0]["items"]
    assert [(it["artist"], it["disc"] and it["disc"]["id"]) for it in items] == [
        ("Radiohead", 3), ("MADONNA", 4), ("MADONNA", 5), ("Soda Stereo", None)]
    assert [it["disc"]["description"] for it in items[1:3]] == ["CD in stickered case", "CD + poster"]


# --- portada y banners ---

def test_home_layout_and_banner_blocks(shop, client):
    slug, admin = shop
    upload(admin, slug, xlsx(*CATALOG), CATALOG_MAP)
    admin.put(f"/api/t/{slug}/admin/code_required", json={"value": False})
    sid = admin.post(f"/api/t/{slug}/admin/secciones", json={"name": "Top"}).json()["id"]
    admin.post(f"/api/t/{slug}/admin/secciones/{sid}/discos", json={"disc_id": 2})
    assert [b["token"] for b in admin.get(f"/api/t/{slug}/admin/portada").json()["blocks"]] == [f"section:{sid}", "catalog"]

    gid = admin.post(f"/api/t/{slug}/admin/banner-bloques", json={"name": "Principal"}).json()["id"]
    assert [b["type"] for b in client.get(f"/api/t/{slug}/portada").json()["blocks"]] == ["section", "catalog"]  # bloque vacío no se ve
    assert admin.post(f"/api/t/{slug}/admin/banners", files={"file": ("x.png", b"<script>")}, data={"group_id": gid}).status_code == 400
    assert admin.post(f"/api/t/{slug}/admin/banners", files={"file": ("x.png", png())}, data={"group_id": 999}).status_code == 404
    bid = admin.post(f"/api/t/{slug}/admin/banners", files={"file": ("x.png", png())}, data={"group_id": gid}).json()["id"]
    assert admin.patch(f"/api/t/{slug}/admin/banners/{bid}", json={"button_link": "javascript:alert(1)"}).status_code == 400
    assert admin.patch(f"/api/t/{slug}/admin/banners/{bid}", json={"button_link": "section:999"}).status_code == 400
    assert admin.patch(f"/api/t/{slug}/admin/banners/{bid}", json={"title": "Preventa", "button_label": "Ver", "button_link": f"section:{sid}"}).status_code == 200

    blocks = client.get(f"/api/t/{slug}/portada").json()["blocks"]
    assert [b["type"] for b in blocks] == ["banners", "section", "catalog"]  # bloque nuevo: arriba
    banner = blocks[0]["banners"][0]
    assert banner["title"] == "Preventa" and banner["button_link"] == f"section:{sid}"
    img = client.get(banner["url"])
    assert img.status_code == 200 and img.headers["content-type"] == "image/png" and "immutable" in img.headers["cache-control"]
    assert client.get(f"/api/t/{slug}/files/..%2F..%2Fregistry.db").status_code == 404

    tokens = [b["token"] for b in admin.get(f"/api/t/{slug}/admin/portada").json()["blocks"]]
    assert admin.put(f"/api/t/{slug}/admin/portada/orden", json={"tokens": ["catalog"]}).status_code == 400
    admin.put(f"/api/t/{slug}/admin/portada/orden", json={"tokens": tokens[::-1]})
    assert [b["type"] for b in client.get(f"/api/t/{slug}/portada").json()["blocks"]] == ["catalog", "section", "banners"]

    admin.patch(f"/api/t/{slug}/admin/banner-bloques/{gid}", json={"visible": False})
    assert "banners" not in [b["type"] for b in client.get(f"/api/t/{slug}/portada").json()["blocks"]]
    admin.patch(f"/api/t/{slug}/admin/banner-bloques/{gid}", json={"visible": True})

    second = admin.post(f"/api/t/{slug}/admin/banner-bloques", json={"name": "Otro"}).json()["id"]
    admin.post(f"/api/t/{slug}/admin/banners", files={"file": ("y.png", png())}, data={"group_id": second})
    assert [b["type"] for b in client.get(f"/api/t/{slug}/portada").json()["blocks"]].count("banners") == 2

    admin.delete(f"/api/t/{slug}/admin/secciones/{sid}")  # el botón que llevaba ahí queda sin destino
    assert admin.get(f"/api/t/{slug}/admin/portada").json()["banners"][0]["button_link"] == ""
    admin.delete(f"/api/t/{slug}/admin/banner-bloques/{gid}")
    assert client.get(banner["url"]).status_code == 404  # la imagen se borró del disco
