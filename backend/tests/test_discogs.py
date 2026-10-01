import json

from app.db import set_settings
from app.services import discogs, tenants

LISTING = {"condition": "Near Mint (NM or M-)", "sleeve_condition": "Very Good Plus (VG+)", "comments": "Sellado",
           "price": {"value": 45000.0, "currency": "ARS"},
           "release": {"id": 249504, "artist": "Soda Stereo", "title": "Canción Animal", "label": "Sony",
                       "format": "Vinyl, LP, Album, RE", "catalog_number": "88985", "year": 1990}}


def test_listing_row_maps_like_an_excel_row():
    row = discogs.listing_row(1, LISTING)
    d = dict(zip(["id", "artist", "title", "label", "media", "description", "genre", "price", "origin", "barcode", "extra", "k"], row))
    assert (d["id"], d["artist"], d["media"], d["price"]) == (1, "Soda Stereo", "Vinyl", "45000")
    assert d["description"] == "LP, Album, RE · 88985 · Sellado"
    assert json.loads(d["extra"]) == {"Año": "1990", "Estado": "Near Mint (NM or M-)", "Tapa": "Very Good Plus (VG+)"}
    assert d["k"].startswith("v2:discogs:249504|")  # "v2:" = la migración de secciones no la recalcula
    usd = discogs.listing_row(2, {**LISTING, "price": {"value": 30.5, "currency": "USD"}})
    assert usd[7] == "USD 30.5"


def test_connect_needs_server_keys(shop):
    slug, admin = shop
    assert admin.get(f"/api/t/{slug}/admin/status").json()["discogs"] == {"enabled": False, "user": "", "job": {}, "running": False}
    assert admin.post(f"/api/t/{slug}/admin/discogs/connect").status_code == 400
    assert admin.post(f"/api/t/{slug}/admin/discogs/import").status_code == 400  # sin cuenta conectada


def test_callback_rejects_unknown_token(shop, client):
    slug, _ = shop
    r = client.get("/api/discogs/callback", params={"slug": slug, "oauth_token": "falso", "oauth_verifier": "x"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith(f"/{slug}/admin?discogs=error")
    r = client.get("/api/discogs/callback", params={"slug": slug, "denied": "abc"}, follow_redirects=False)
    assert r.headers["location"] == f"/{slug}/admin?discogs=denied"


def test_import_replaces_catalog(shop, monkeypatch):
    slug, admin = shop
    set_settings(tenants.find(slug), discogs_user="surco", discogs_token="tok", discogs_secret="sec")
    pages = {1: [LISTING, {**LISTING, "release": {**LISTING["release"], "id": 1, "artist": "Spinetta"}}], 2: [LISTING]}
    def fake(method, url, token_secret="", **oauth):
        assert "/users/surco/inventory" in url and token_secret == "sec" and oauth["oauth_token"] == "tok"
        page = int(url.rsplit("page=", 1)[1])
        return json.dumps({"pagination": {"pages": 2, "items": 3}, "listings": pages[page]})
    monkeypatch.setattr(discogs, "_call", fake)
    monkeypatch.setattr(discogs.time, "sleep", lambda s: None)
    assert admin.post(f"/api/t/{slug}/admin/discogs/import").status_code == 200  # la tarea corre al terminar el pedido
    s = admin.get(f"/api/t/{slug}/admin/status").json()
    assert s["total"] == 3 and s["filename"] == "Discogs · @surco" and s["discogs"]["job"]["state"] == "done"
    assert [c["key"] for c in s["custom_columns"]] == ["ano", "estado", "tapa"]
    assert admin.get(f"/api/t/{slug}/discos", params={"q": "spinetta"}).json()["total"] == 1
    assert admin.delete(f"/api/t/{slug}/admin/discogs").json()["user"] == ""
    assert admin.get(f"/api/t/{slug}/admin/status").json()["total"] == 3  # desconectar no borra el catálogo
