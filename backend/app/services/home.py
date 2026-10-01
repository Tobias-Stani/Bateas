"""Portada: junta bloques de banners, secciones y catálogo en el orden que eligió la disquería."""
import re

from fastapi import HTTPException

from . import banners, layout, sections


def public_blocks(t):
    """Como la ve el cliente: solo bloques visibles y con contenido."""
    con = sections.connect(t)
    order = layout.tokens(t, con)
    con.close()
    shelves = {f"section:{sec['id']}": sec for sec in sections.list_all(t, public=True)}
    visible = banners.all_banners(t, public=True)
    blocks = []
    for tok in order:
        if tok.startswith("banners:"):
            group = int(tok.split(":")[1])
            if mine := [b for b in visible if b["group_id"] == group]:
                blocks.append({"type": "banners", "id": group, "banners": mine})
        elif tok == "catalog":
            blocks.append({"type": "catalog"})
        elif tok in shelves:
            blocks.append({"type": "section", **shelves[tok]})
    return blocks


def admin_view(t):
    """Todos los bloques (también los ocultos) con lo que hace falta para editarlos."""
    con = sections.connect(t)
    order = layout.tokens(t, con)
    shelves = {f"section:{r['id']}": r for r in con.execute(
        "SELECT s.id, s.name, s.visible, (SELECT COUNT(*) FROM section_items WHERE section_id = s.id) n FROM sections s")}
    con.close()
    groups = {f"banners:{g['id']}": g for g in banners.groups(t).values()}
    images = banners.all_banners(t, public=False)
    blocks = []
    for tok in order:
        if tok in groups:
            g = groups[tok]
            blocks.append({"token": tok, "type": "banners", "id": g["id"], "name": g["name"], "visible": bool(g["visible"]),
                           "count": sum(b["visible"] for b in images if b["group_id"] == g["id"])})
        elif tok == "catalog":
            blocks.append({"token": tok, "type": "catalog", "name": "Catálogo completo", "visible": True})
        else:
            sec = shelves[tok]
            blocks.append({"token": tok, "type": "section", "id": sec["id"], "name": sec["name"],
                           "visible": bool(sec["visible"]), "count": sec["n"]})
    return {"blocks": blocks, "banners": images,
            "groups": [{"id": g["id"], "name": g["name"], "visible": bool(g["visible"])} for g in
                       (groups[tok] for tok in order if tok in groups)]}


def save_order(t, new_order):
    con = sections.connect(t)
    try:
        layout.save(t, con, new_order)
    finally:
        con.close()


def valid_link(t, value):
    # a dónde lleva el botón del banner: una sección, el catálogo o un link https
    link = value.strip()
    if not link or link == "catalog" or link.startswith("https://") and len(link) <= 500:
        return link
    if (m := re.fullmatch(r"section:(\d+)", link)) and sections.exists(t, int(m[1])):
        return link
    raise HTTPException(400, "El botón tiene que llevar a una sección, al catálogo o a un link https.")
