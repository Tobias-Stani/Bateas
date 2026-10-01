"""Orden de la portada: una lista de bloques ("banners:N", "section:N", "catalog") que la disquería ordena."""
import json

from fastapi import HTTPException

from ..db import get_setting, set_settings
from . import banners


def tokens(t, con):
    """Siempre completo: suma lo que falte y saca lo que ya no existe."""
    banners.ensure_tables(t, con)
    sections = [f"section:{r[0]}" for r in con.execute("SELECT id FROM sections ORDER BY position, id")]
    groups = [f"banners:{r[0]}" for r in con.execute("SELECT id FROM banner_groups ORDER BY id")]
    saved = json.loads(get_setting(t, "home_layout") or "[]")
    order = [tok for tok in saved if tok == "catalog" or tok in sections or tok in groups]
    if "catalog" not in order:
        order.append("catalog")
    order = [g for g in groups if g not in order] + order  # bloque de banners nuevo: arriba de todo
    missing = [sec for sec in sections if sec not in order]
    at = order.index("catalog")  # secciones nuevas: arriba del catálogo
    return order[:at] + missing + order[at:]


def save(t, con, new_order):
    valid = set(tokens(t, con))
    if set(new_order) != valid or len(new_order) != len(valid):
        raise HTTPException(400, "El orden no coincide con los bloques de la portada. Recargá la página.")
    set_settings(t, home_layout=json.dumps(new_order))
