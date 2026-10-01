import io
import os
import struct
import sys
import tempfile
import zlib
from pathlib import Path

import pytest

# la app lee la configuración al importarse: el entorno va antes que cualquier import de la app
BACKEND = Path(__file__).resolve().parents[1]
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="vinyl-tests-")
os.environ["SUPER_PASSWORD"] = "s3cret"
os.environ["STATIC_DIR"] = str(BACKEND.parent / "frontend" / "public")
os.environ["DISCOGS_KEY"] = os.environ["DISCOGS_SECRET"] = ""  # los tests nunca hablan con Discogs
for var in ("MP_CLIENT_ID", "MP_CLIENT_SECRET", "MP_ACCESS_TOKEN", "MP_TEST"):
    os.environ[var] = ""  # ni con Mercado Pago
sys.path.insert(0, str(BACKEND))

from app.main import app as APP  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from openpyxl import Workbook  # noqa: E402


@pytest.fixture
def client():
    """Un navegador nuevo, sin cookies."""
    return TestClient(APP)


@pytest.fixture
def boss():
    """Sesión de super admin."""
    c = TestClient(APP)
    assert c.post("/api/super/login", json={"value": "s3cret"}).status_code == 200
    return c


_counter = iter(range(10_000))


@pytest.fixture
def shop(boss):
    """Una disquería nueva con su admin logueado: (slug, cliente admin)."""
    slug = f"tienda-{next(_counter)}"
    r = boss.post("/api/super/tenants", json={"name": "Tienda Test", "slug": slug, "admin_password": "pass123", "client_code": "codigo"})
    assert r.status_code == 200, r.text
    admin = TestClient(APP)
    assert admin.post(f"/api/t/{slug}/admin/login", json={"value": "pass123"}).status_code == 200
    return slug, admin


def xlsx(*rows):
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(list(row))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def upload(admin, slug, data, mapping, header_row=1):
    r = admin.post(f"/api/t/{slug}/admin/upload/preview", files={"file": ("lista.xlsx", data)})
    assert r.status_code == 200, r.text
    r = admin.post(f"/api/t/{slug}/admin/upload/confirm", json={"header_row": header_row, "mapping": mapping})
    assert r.status_code == 200, r.text
    return r.json()


def png(width=40, height=20):
    raw = b"".join(b"\x00" + b"\xd6\x28\x28" * width for _ in range(height))
    chunk = lambda kind, data: struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


CATALOG = [
    ("Artist", "Title", "Label", "Medium", "Description", "Genre", "Barcode", "Price"),
    ("Radiohead", "OK Computer", "Parlophone", "Vinyl", "2LP", "Rock", "634904078164", 68000),
    ("MADONNA", "Confessions II", "Warner", "CD", "CD in stickered case", "Pop", "93624821304", None),
    ("MADONNA", "Confessions II", "Warner", "CD", "CD + poster", "Pop", "93624822356", None),
    ("Soda Stereo", "Canción Animal", "Sony", "Vinyl", "LP", "Rock", None, 59000),
    ("Miles Davis", "Kind Of Blue", "Columbia", "CD", "", "Jazz", None, 25000),
]
CATALOG_MAP = {"0": "artist", "1": "title", "2": "label", "3": "media", "4": "description", "5": "genre", "6": "barcode", "7": "price"}
