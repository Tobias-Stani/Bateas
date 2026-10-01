"""Crea la tienda de demo (/demo) por la API: catálogo, secciones y banners.

Usa la sesión de super admin, que entra a cualquier admin. Corre en un contenedor del backend (usa openpyxl):

    local:      docker compose run --rm --no-deps -v ./demo:/demo backend python /demo/seed_demo.py
    producción: docker compose run --rm --no-deps -v ./demo:/demo -e SUPER_PASSWORD=... backend \
                    python /demo/seed_demo.py https://bateas-production.up.railway.app

Si /demo ya existe, no toca nada.
"""
import http.cookiejar
import io
import json
import os
import secrets
import struct
import sys
import urllib.error
import urllib.request
import zlib

from openpyxl import Workbook

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://backend:8000").rstrip("/")  # default: el backend local de compose
SLUG, NAME = "demo", "Disquería Demo"

HEADER = ("Artista", "Título", "Sello", "Formato", "Descripción", "Género", "Origen", "Precio")
DISCS = [
    ("Soda Stereo", "Canción Animal", "Sony Music", "Vinyl", "LP 180g, reedición", "Rock Nacional", "AR", 62000),
    ("Charly García", "Clics Modernos", "Sony Music", "Vinyl", "LP", "Rock Nacional", "AR", 58000),
    ("Luis Alberto Spinetta", "Artaud", "Sony Music", "Vinyl", "LP, tapa troquelada", "Rock Nacional", "AR", 69000),
    ("Sui Generis", "Vida", "Sony Music", "Vinyl", "LP", "Rock Nacional", "AR", 52000),
    ("Serú Girán", "La Grasa De Las Capitales", "Sony Music", "Vinyl", "LP", "Rock Nacional", "AR", 56000),
    ("Patricio Rey y sus Redonditos de Ricota", "Oktubre", "Del Cielito Records", "Vinyl", "LP", "Rock Nacional", "AR", 60000),
    ("Gustavo Cerati", "Bocanada", "Sony Music", "Vinyl", "2LP gatefold", "Rock Nacional", "AR", 84000),
    ("Babasónicos", "Jessico", "Pop Art", "Vinyl", "LP", "Rock Nacional", "AR", 55000),
    ("Los Fabulosos Cadillacs", "Vasos Vacíos", "Sony Music", "CD", "", "Rock Nacional", "AR", 19000),
    ("Mercedes Sosa", "Cantora 1", "Sony Music", "CD", "", "Folklore", "AR", 21000),
    ("Astor Piazzolla", "Tango: Zero Hour", "American Clavé", "CD", "", "Tango", "US", 26000),
    ("Radiohead", "OK Computer", "XL Recordings", "Vinyl", "2LP, OKNOTOK", "Rock", "UK", 89000),
    ("Radiohead", "In Rainbows", "XL Recordings", "Vinyl", "LP 180g", "Rock", "UK", 65000),
    ("Radiohead", "Kid A", "XL Recordings", "CD", "", "Rock", "UK", 24000),
    ("Pink Floyd", "The Dark Side Of The Moon", "Pink Floyd Records", "Vinyl", "LP 180g, remaster", "Rock", "EU", 72000),
    ("The Beatles", "Abbey Road", "Apple Records", "Vinyl", "LP, mezcla 2019", "Rock", "EU", 70000),
    ("Led Zeppelin", "Led Zeppelin IV", "Atlantic", "Vinyl", "LP 180g", "Rock", "EU", 68000),
    ("Fleetwood Mac", "Rumours", "Warner Records", "Vinyl", "LP", "Rock", "EU", 64000),
    ("Nirvana", "Nevermind", "DGC", "Vinyl", "LP", "Rock", "EU", 63000),
    ("Arctic Monkeys", "AM", "Domino", "Vinyl", "LP", "Rock", "UK", 61000),
    ("The Velvet Underground & Nico", "The Velvet Underground & Nico", "Verve", "Vinyl", "LP", "Rock", "EU", 66000),
    ("David Bowie", "The Rise And Fall Of Ziggy Stardust", "Parlophone", "Vinyl", "LP, remaster", "Rock", "EU", 67000),
    ("Joy Division", "Unknown Pleasures", "Factory", "Vinyl", "LP 180g", "Post Punk", "UK", 64000),
    ("The Cure", "Disintegration", "Fiction", "Vinyl", "2LP", "Post Punk", "EU", 82000),
    ("Tame Impala", "Currents", "Interscope", "Vinyl", "2LP", "Psicodelia", "EU", 79000),
    ("Miles Davis", "Kind Of Blue", "Columbia", "Vinyl", "LP 180g", "Jazz", "US", 59000),
    ("John Coltrane", "A Love Supreme", "Impulse!", "Vinyl", "LP", "Jazz", "US", 62000),
    ("Bill Evans Trio", "Waltz For Debby", "Riverside", "Vinyl", "LP", "Jazz", "US", 58000),
    ("Herbie Hancock", "Head Hunters", "Columbia", "Vinyl", "LP", "Jazz", "US", 60000),
    ("Marvin Gaye", "What's Going On", "Motown", "Vinyl", "LP", "Soul", "US", 61000),
    ("Amy Winehouse", "Back To Black", "Island", "Vinyl", "LP", "Soul", "EU", 63000),
    ("Bob Marley & The Wailers", "Exodus", "Island", "Vinyl", "LP", "Reggae", "EU", 59000),
    ("Caetano Veloso", "Transa", "Philips", "Vinyl", "LP", "MPB", "BR", 66000),
    ("Jorge Ben", "África Brasil", "Philips", "Vinyl", "LP", "MPB", "BR", 64000),
    ("Kraftwerk", "Autobahn", "Parlophone", "Vinyl", "LP, remaster", "Electrónica", "EU", 60000),
    ("Daft Punk", "Random Access Memories", "Columbia", "Vinyl", "2LP gatefold", "Electrónica", "EU", 88000),
    ("Massive Attack", "Mezzanine", "Virgin", "Vinyl", "2LP", "Electrónica", "EU", 78000),
    ("Aphex Twin", "Selected Ambient Works 85-92", "Apollo", "Vinyl", "2LP", "Electrónica", "UK", 76000),
    ("Björk", "Homogenic", "One Little Independent", "Vinyl", "LP", "Electrónica", "UK", 62000),
    ("Kendrick Lamar", "To Pimp A Butterfly", "Interscope", "Vinyl", "2LP", "Hip Hop", "EU", 80000),
    ("Michael Jackson", "Thriller", "Epic", "Vinyl", "LP", "Pop", "EU", 62000),
    ("Rosalía", "Motomami", "Columbia", "Vinyl", "LP color", "Pop", "EU", 70000),
    ("Bad Bunny", "Un Verano Sin Ti", "Rimas", "Vinyl", "2LP color", "Urbano", "US", 95000),
    ("Billie Eilish", "Happier Than Ever", "Interscope", "Vinyl", "2LP", "Pop", "EU", 83000),
]
# secciones de la portada: nombre -> artista/título de sus discos
SECTIONS = {
    "Rock nacional en vinilo": ["Canción Animal", "Clics Modernos", "Artaud", "Bocanada", "Oktubre", "Jessico", "Vida"],
    "Recomendados de la casa": ["Kind Of Blue", "Transa", "Unknown Pleasures", "Mezzanine", "A Love Supreme", "Currents", "África Brasil"],
}
BANNERS = [  # título, texto, botón, a dónde lleva, colores del degradé
    ("Preventa del mes", "Llegaron los importados. Reservá el tuyo antes del viernes.", "Ver el catálogo", "catalog", (0x1a, 0x1a, 0x20), (0xff, 0x5a, 0x1f)),
    ("Rock nacional en vinilo", "Reediciones de Soda, Charly, Spinetta y más.", "Ver la sección", "section:rock", (0x14, 0x14, 0x30), (0x3b, 0x5b, 0xdb)),
]


def session():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def call(op, method, path, body=None, files=None):
    headers, data = {}, None
    if files:  # multipart a mano: un archivo y campos de texto
        boundary = secrets.token_hex(12)
        parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in (body or {}).items()]
        for field, (name, content, kind) in files.items():
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{name}"\r\n'
                         f"Content-Type: {kind}\r\n\r\n".encode() + content + b"\r\n")
        data, headers["Content-Type"] = b"".join(parts) + f"--{boundary}--\r\n".encode(), f"multipart/form-data; boundary={boundary}"
    elif body is not None:
        data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
    try:
        with op.open(urllib.request.Request(BASE + path, data=data, method=method, headers=headers)) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {path}: {e.code} {e.read().decode()}")


def xlsx():
    wb = Workbook()
    ws = wb.active
    ws.append(HEADER)
    for row in DISCS:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def gradient_png(left, right, width=1920, height=640):
    # degradé horizontal: todas las filas iguales, comprime a casi nada
    row = b"\x00" + b"".join(bytes(round(a + (b - a) * (x / (width - 1)) ** 1.6) for a, b in zip(left, right)) for x in range(width))
    chunk = lambda kind, data: struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(row * height, 9)) + chunk(b"IEND", b""))


def main():
    boss = session()
    call(boss, "POST", "/api/super/login", {"value": os.environ["SUPER_PASSWORD"]})
    if any(t["slug"] == SLUG for t in call(boss, "GET", "/api/super/tenants")):
        sys.exit(f"/{SLUG} ya existe: no se tocó nada. Para rehacerla, cancelala y eliminala desde /super.")
    call(boss, "POST", "/api/super/tenants", {"name": NAME, "slug": SLUG, "admin_password": secrets.token_urlsafe(12), "client_code": "demo"})
    admin = f"/api/t/{SLUG}/admin"
    call(boss, "PUT", f"{admin}/code_required", {"value": False})  # pública: se entra directo desde la landing

    preview = call(boss, "POST", f"{admin}/upload/preview", files={"file": ("demo.xlsx", xlsx(), "application/octet-stream")})
    mapping = {str(c["index"]): c["field"] for c in preview["columns"]}
    total = call(boss, "POST", f"{admin}/upload/confirm", {"header_row": preview["header_row"], "mapping": mapping})["total"]

    ids = {title: n for n, (_, title, *_) in enumerate(DISCS, start=2)}  # id = fila del Excel (la 1 es el encabezado)
    section_ids = {}
    for name, titles in SECTIONS.items():
        sid = section_ids[name] = call(boss, "POST", f"{admin}/secciones", {"name": name})["id"]
        for title in titles:
            call(boss, "POST", f"{admin}/secciones/{sid}/discos", {"disc_id": ids[title]})

    group = call(boss, "POST", f"{admin}/banner-bloques", {"name": "Destacados"})["id"]
    for title, text, label, link, left, right in BANNERS:
        bid = call(boss, "POST", f"{admin}/banners", {"group_id": group}, files={"file": ("banner.png", gradient_png(left, right), "image/png")})["id"]
        link = f"section:{section_ids['Rock nacional en vinilo']}" if link == "section:rock" else link
        call(boss, "PATCH", f"{admin}/banners/{bid}", {"title": title, "text": text, "button_label": label, "button_link": link})

    print(f"Listo: {BASE}/{SLUG} con {total} discos, {len(SECTIONS)} secciones y {len(BANNERS)} banners.")
    print(f"El admin está en {BASE}/{SLUG}/admin (entrás como super admin desde /super).")


if __name__ == "__main__":
    main()
