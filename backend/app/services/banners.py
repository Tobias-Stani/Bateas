"""Bloques de banners: cada bloque es un slider con sus imágenes y ocupa su lugar en la portada."""
import json

from fastapi import HTTPException

from ..config import MAX_BANNER_GROUPS, MAX_BANNERS
from ..db import db, get_setting, set_settings
from . import images, plans


def ensure_tables(t, con):
    con.execute("CREATE TABLE IF NOT EXISTS banner_groups (id INTEGER PRIMARY KEY, name TEXT NOT NULL, visible INTEGER NOT NULL DEFAULT 1)")
    con.execute("""CREATE TABLE IF NOT EXISTS banners (id INTEGER PRIMARY KEY, position INTEGER NOT NULL, image TEXT NOT NULL,
                   title TEXT NOT NULL DEFAULT '', text TEXT NOT NULL DEFAULT '', button_label TEXT NOT NULL DEFAULT '',
                   button_link TEXT NOT NULL DEFAULT '', visible INTEGER NOT NULL DEFAULT 1, group_id INTEGER)""")
    if "group_id" not in [c[1] for c in con.execute("PRAGMA table_info(banners)")]:
        con.execute("ALTER TABLE banners ADD COLUMN group_id INTEGER")
    _migrate_single_block(t, con)


def _migrate_single_block(t, con):
    # banners de cuando había un solo bloque: pasan a ser el primero, en el mismo lugar de la portada
    if not con.execute("SELECT 1 FROM banners WHERE group_id IS NULL LIMIT 1").fetchone():
        return
    with con:
        cur = con.execute("INSERT INTO banner_groups (name, visible) VALUES (?, ?)",
                          ("Banners principales", int(get_setting(t, "banners_visible", "1") == "1")))
        con.execute("UPDATE banners SET group_id = ? WHERE group_id IS NULL", (cur.lastrowid,))
    saved = json.loads(get_setting(t, "home_layout") or "[]")
    set_settings(t, home_layout=json.dumps([f"banners:{cur.lastrowid}" if tok == "banners" else tok for tok in saved]))


def connect(t):
    con = db(t)
    ensure_tables(t, con)
    return con


def groups(t):
    con = connect(t)
    rows = {r["id"]: dict(r) for r in con.execute("SELECT * FROM banner_groups")}
    con.close()
    return rows


def all_banners(t, public):
    """Todas las imágenes; las públicas son solo las visibles de bloques visibles."""
    con = connect(t)
    rows = [dict(r) for r in con.execute("SELECT * FROM banners ORDER BY position, id")]
    hidden = {r[0] for r in con.execute("SELECT id FROM banner_groups WHERE visible = 0")}
    con.close()
    for b in rows:
        b["visible"] = bool(b["visible"])
        b["url"] = images.url(t, b["image"])
    return [b for b in rows if b["visible"] and b["group_id"] not in hidden] if public else rows


def _group_or_404(con, group_id):
    row = con.execute("SELECT * FROM banner_groups WHERE id = ?", (group_id,)).fetchone()
    if not row:
        con.close()
        raise HTTPException(404, "Ese bloque de banners no existe.")
    return row


def _banner_or_404(con, banner_id):
    row = con.execute("SELECT * FROM banners WHERE id = ?", (banner_id,)).fetchone()
    if not row:
        con.close()
        raise HTTPException(404, "Ese banner no existe.")
    return row


# --- bloques ---

def create_group(t, name):
    con = connect(t)
    if con.execute("SELECT COUNT(*) FROM banner_groups").fetchone()[0] >= MAX_BANNER_GROUPS:
        con.close()
        raise HTTPException(400, f"Podés tener hasta {MAX_BANNER_GROUPS} bloques de banners.")
    with con:
        cur = con.execute("INSERT INTO banner_groups (name) VALUES (?)", (name,))
    con.close()
    return cur.lastrowid


def update_group(t, group_id, name=None, visible=None):
    con = connect(t)
    _group_or_404(con, group_id)
    with con:
        if name is not None:
            con.execute("UPDATE banner_groups SET name = ? WHERE id = ?", (name, group_id))
        if visible is not None:
            con.execute("UPDATE banner_groups SET visible = ? WHERE id = ?", (int(visible), group_id))
    con.close()


def delete_group(t, group_id):
    con = connect(t)
    _group_or_404(con, group_id)
    names = [r[0] for r in con.execute("SELECT image FROM banners WHERE group_id = ?", (group_id,))]
    with con:
        con.execute("DELETE FROM banners WHERE group_id = ?", (group_id,))
        con.execute("DELETE FROM banner_groups WHERE id = ?", (group_id,))
    con.close()
    for name in names:
        images.remove(t, name)


# --- imágenes de un bloque ---

def create(t, group_id, upload):
    con = connect(t)
    _group_or_404(con, group_id)
    if con.execute("SELECT COUNT(*) FROM banners WHERE group_id = ?", (group_id,)).fetchone()[0] >= MAX_BANNERS:
        con.close()
        raise HTTPException(400, f"Un bloque puede tener hasta {MAX_BANNERS} imágenes.")
    try:
        plans.check(t, "banners", con.execute("SELECT COUNT(*) FROM banners").fetchone()[0])
    except HTTPException:
        con.close()
        raise
    name = images.save(t, upload)
    with con:
        cur = con.execute("""INSERT INTO banners (position, image, group_id)
                             VALUES ((SELECT COALESCE(MAX(position), 0) + 1 FROM banners WHERE group_id = ?), ?, ?)""",
                          (group_id, name, group_id))
    con.close()
    return cur.lastrowid


def update(t, banner_id, changes):
    con = connect(t)
    _banner_or_404(con, banner_id)
    if changes:
        with con:
            con.execute(f"UPDATE banners SET {', '.join(f'{k} = ?' for k in changes)} WHERE id = ?", [*changes.values(), banner_id])
    con.close()


def replace_image(t, banner_id, upload):
    con = connect(t)
    old = _banner_or_404(con, banner_id)["image"]
    name = images.save(t, upload)
    with con:
        con.execute("UPDATE banners SET image = ? WHERE id = ?", (name, banner_id))
    con.close()
    images.remove(t, old)


def delete(t, banner_id):
    con = connect(t)
    name = _banner_or_404(con, banner_id)["image"]
    with con:
        con.execute("DELETE FROM banners WHERE id = ?", (banner_id,))
    con.close()
    images.remove(t, name)


def reorder(t, ids):
    con = connect(t)
    with con:
        con.executemany("UPDATE banners SET position = ? WHERE id = ?", [(i, bid) for i, bid in enumerate(ids)])
    con.close()


def unlink_section(con, section_id):
    # una sección borrada: el botón que llevaba ahí queda sin destino
    if con.execute("SELECT 1 FROM sqlite_master WHERE name = 'banners'").fetchone():
        con.execute("UPDATE banners SET button_link = '' WHERE button_link = ?", (f"section:{section_id}",))
