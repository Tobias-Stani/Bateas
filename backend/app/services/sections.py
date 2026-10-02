"""Secciones: carruseles que arma la disquería eligiendo discos.

Cada disco se guarda por su clave estable (catalog.disc_key), no por la fila: así sobrevive al Excel del mes siguiente.
"""
from fastapi import HTTPException

from ..config import MAX_SECTION_ITEMS, MAX_SECTIONS
from ..db import db
from . import banners, catalog, layout, plans


def connect(t):
    con = db(t)
    con.execute("CREATE TABLE IF NOT EXISTS sections (id INTEGER PRIMARY KEY, name TEXT NOT NULL, position INTEGER NOT NULL, visible INTEGER NOT NULL DEFAULT 1)")
    # artist/title/media: copia para mostrar en el admin los que ya no están en la lista
    con.execute("""CREATE TABLE IF NOT EXISTS section_items (id INTEGER PRIMARY KEY, section_id INTEGER NOT NULL,
                   position INTEGER NOT NULL, k TEXT NOT NULL, artist, title, media)""")
    _migrate_keys(con, catalog.exists(t))
    return con


def _migrate_keys(con, has_catalog):
    # catálogos cargados antes de las secciones o con la clave vieja: se recalcula una sola vez
    if has_catalog:
        if "k" not in [c[1] for c in con.execute("PRAGMA table_info(discos)")]:
            con.execute("ALTER TABLE discos ADD COLUMN k")
        if con.execute("SELECT 1 FROM discos WHERE k IS NULL OR k NOT LIKE 'v2:%' LIMIT 1").fetchone():
            rows = [dict(r) for r in con.execute("SELECT * FROM discos")]
            with con:
                con.executemany("UPDATE discos SET k = ? WHERE id = ?", [(catalog.disc_key(r), r["id"]) for r in rows])
                con.execute("CREATE INDEX IF NOT EXISTS discos_k ON discos (k)")
    old = con.execute("SELECT id, k, artist, title, media FROM section_items WHERE k NOT LIKE 'v2:%'").fetchall()
    if not old:
        return
    # cada disco viejo pasa a la edición que se mostraba hasta ahora: la primera fila con esa clave
    first = {}
    if has_catalog:
        for r in con.execute("SELECT * FROM discos ORDER BY id DESC"):
            first[catalog.legacy_key(dict(r))] = r["k"]
    with con:
        con.executemany("UPDATE section_items SET k = ? WHERE id = ?",
                        [(first.get(it["k"]) or catalog.disc_key(dict(it)), it["id"]) for it in old])


def _section_or_404(con, section_id):
    sec = con.execute("SELECT * FROM sections WHERE id = ?", (section_id,)).fetchone()
    if not sec:
        con.close()
        raise HTTPException(404, "Esa sección no existe.")
    return sec


def exists(t, section_id):
    con = connect(t)
    ok = con.execute("SELECT 1 FROM sections WHERE id = ?", (section_id,)).fetchone()
    con.close()
    return bool(ok)


def list_all(t, public):
    """En el orden de la portada. Públicas: solo visibles y con discos de la lista actual."""
    con = connect(t)
    has_catalog = catalog.exists(t)
    order = {tok: i for i, tok in enumerate(layout.tokens(t, con))}
    rows = sorted(con.execute("SELECT * FROM sections").fetchall(), key=lambda r: order.get(f"section:{r['id']}", 1e9))
    out = []
    for sec in rows:
        if public and not sec["visible"]:
            continue
        items = []
        for it in con.execute("SELECT * FROM section_items WHERE section_id = ? ORDER BY position, id", (sec["id"],)):
            row = con.execute("SELECT * FROM discos WHERE k = ? ORDER BY id LIMIT 1", (it["k"],)).fetchone() if has_catalog else None
            if public:
                if row:
                    items.append(catalog.disc(row))
            else:
                items.append({"item_id": it["id"], "artist": it["artist"], "title": it["title"], "media": it["media"],
                              "disc": catalog.disc(row) if row else None})
        if public and not items:
            continue
        out.append({"id": sec["id"], "name": sec["name"], "visible": bool(sec["visible"]), "items": items})
    con.close()
    return out


def missing_after_upload(t):
    # después de cargar un Excel: cuántos discos de cada sección no están en la lista nueva
    return [{"name": s["name"], "missing": sum(1 for i in s["items"] if not i["disc"])}
            for s in list_all(t, public=False) if any(not i["disc"] for i in s["items"])]


# --- cambios ---

def create(t, name):
    con = connect(t)
    if con.execute("SELECT COUNT(*) FROM sections").fetchone()[0] >= MAX_SECTIONS:
        con.close()
        raise HTTPException(400, f"Llegaste al máximo de {MAX_SECTIONS} secciones.")
    try:
        plans.check(t, "sections", con.execute("SELECT COUNT(*) FROM sections").fetchone()[0])
    except HTTPException:
        con.close()
        raise
    with con:
        cur = con.execute("INSERT INTO sections (name, position) VALUES (?, (SELECT COALESCE(MAX(position), 0) + 1 FROM sections))", (name,))
    con.close()
    return cur.lastrowid


def update(t, section_id, name=None, visible=None):
    con = connect(t)
    _section_or_404(con, section_id)
    with con:
        if name is not None:
            con.execute("UPDATE sections SET name = ? WHERE id = ?", (name, section_id))
        if visible is not None:
            con.execute("UPDATE sections SET visible = ? WHERE id = ?", (int(visible), section_id))
    con.close()


def delete(t, section_id):
    con = connect(t)
    _section_or_404(con, section_id)
    with con:
        con.execute("DELETE FROM section_items WHERE section_id = ?", (section_id,))
        con.execute("DELETE FROM sections WHERE id = ?", (section_id,))
        banners.unlink_section(con, section_id)
    con.close()


def reorder(t, ids):
    con = connect(t)
    with con:
        con.executemany("UPDATE sections SET position = ? WHERE id = ?", [(i, sid) for i, sid in enumerate(ids)])
    con.close()


def add_disc(t, section_id, disc_id):
    con = connect(t)
    _section_or_404(con, section_id)
    row = con.execute("SELECT * FROM discos WHERE id = ?", (disc_id,)).fetchone() if catalog.exists(t) else None
    if not row:
        con.close()
        raise HTTPException(404, "Ese disco no está en la lista cargada.")
    k = row["k"] or catalog.disc_key(dict(row))
    if con.execute("SELECT 1 FROM section_items WHERE section_id = ? AND k = ?", (section_id, k)).fetchone():
        con.close()
        raise HTTPException(409, "Ese disco ya está en la sección.")
    if con.execute("SELECT COUNT(*) FROM section_items WHERE section_id = ?", (section_id,)).fetchone()[0] >= MAX_SECTION_ITEMS:
        con.close()
        raise HTTPException(400, f"Una sección puede tener hasta {MAX_SECTION_ITEMS} discos.")
    with con:
        con.execute("""INSERT INTO section_items (section_id, position, k, artist, title, media)
                       VALUES (?, (SELECT COALESCE(MAX(position), 0) + 1 FROM section_items WHERE section_id = ?), ?, ?, ?, ?)""",
                    (section_id, section_id, k, row["artist"], row["title"], row["media"]))
    con.close()


def remove_disc(t, section_id, item_id):
    con = connect(t)
    with con:
        con.execute("DELETE FROM section_items WHERE id = ? AND section_id = ?", (item_id, section_id))
    con.close()


def reorder_discs(t, section_id, ids):
    con = connect(t)
    with con:
        con.executemany("UPDATE section_items SET position = ? WHERE id = ? AND section_id = ?",
                        [(i, iid, section_id) for i, iid in enumerate(ids)])
    con.close()
