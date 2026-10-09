from conftest import upload, xlsx

# como el Excel de la captura: artista y título en una sola columna, precio con "AGOTADO", columnas sin encabezado
SHEET = [
    ("ARTISTA / TITULO", "$ EFECTIVO / TRANSFER", "TARJETA 3 CUOTAS SIN INTERÉS", "STOCK", None, None, None),
    ("2 Minutos 20 Años No Es Nada (2LP)", 75000, 82500, "P0", None, "NACIONAL", "PINHEAD"),
    ("2 Minutos De Advertencia", "AGOTADO", "#¡VALOR!", 0, None, "NACIONAL", "DBN"),
]


def test_artist_and_title_in_one_column(shop):
    slug, admin = shop
    r = admin.post(f"/api/t/{slug}/admin/upload/preview", files={"file": ("lista.xlsx", xlsx(*SHEET))})
    cols = {c["header"]: c["field"] for c in r.json()["columns"]}
    assert cols["ARTISTA / TITULO"] == "artist_title" and cols["$ EFECTIVO / TRANSFER"] == "price"
    mapping = {"0": "artist_title", "1": "price", "2": "custom", "3": "custom", "5": "origin", "6": "label"}
    assert upload(admin, slug, xlsx(*SHEET), mapping)["total"] == 2
    [d] = admin.get(f"/api/t/{slug}/discos", params={"q": "advertencia"}).json()["items"]
    assert (d["artist"], d["title"], d["price"], d["label"]) == ("", "2 Minutos De Advertencia", "AGOTADO", "DBN")
    assert d["extra"]["STOCK"] == "0"
    assert admin.get(f"/api/t/{slug}/discos", params={"q": "2 minutos"}).json()["total"] == 2  # se busca igual


def test_cannot_mix_together_and_separate_columns(shop):
    slug, admin = shop
    admin.post(f"/api/t/{slug}/admin/upload/preview", files={"file": ("lista.xlsx", xlsx(*SHEET))})
    r = admin.post(f"/api/t/{slug}/admin/upload/confirm", json={"header_row": 1, "mapping": {"0": "artist_title", "6": "artist"}})
    assert r.status_code == 400
