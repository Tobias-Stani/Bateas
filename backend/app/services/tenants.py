"""Disquerías: el registro y la configuración de cada una."""
import json
from datetime import datetime, timezone

from fastapi import HTTPException

from ..config import DEFAULT_ACCENT, DEFAULT_HIGHLIGHT, DEFAULT_LOGO, MESSAGE, MESSAGE_LINE
from ..db import get_setting, registry, set_settings
from . import catalog


def find(slug):
    con = registry()
    row = con.execute("SELECT * FROM tenants WHERE slug = ?", (slug,)).fetchone()
    con.close()
    return dict(row) if row else None


def existing(slug):
    t = find(slug)
    if not t:
        raise HTTPException(404, "Esa disquería no existe.")
    return t


def all_tenants():
    con = registry()
    rows = [dict(r) for r in con.execute("SELECT * FROM tenants ORDER BY created_at DESC")]
    con.close()
    return rows


def update_registry(sql, params):
    with registry() as con:
        con.execute(sql, params)
    con.close()


# --- configuración de la disquería (en su settings) ---

def client_code(t):
    return get_setting(t, "client_code", "")


def code_required(t):
    # apagado = tienda pública: se entra con el link, sin código
    return get_setting(t, "code_required", "1") == "1"


def whatsapp(t):
    return get_setting(t, "whatsapp", "")


def messages(t):
    return {"message": get_setting(t, "message", MESSAGE), "message_line": get_setting(t, "message_line", MESSAGE_LINE)}


def closes_at(t):
    return get_setting(t, "closes_at") or None  # ISO en UTC, o None si no hay cierre


def is_closed(t):
    c = closes_at(t)
    return bool(c) and datetime.fromisoformat(c) <= datetime.now(timezone.utc)


def contact(t):
    # {"address", "city", "phone", "email", "hours", "instagram"}; lo que no cargaron no viene
    return json.loads(get_setting(t, "contact") or "{}")


def set_contact(t, data):
    data = {k: v for k, v in data.items() if v}
    set_settings(t, contact=json.dumps(data, ensure_ascii=False))
    return data


def custom_columns(t):
    # las columnas propias del catálogo cargado: [{"key": "insert", "name": "Insert"}]
    return json.loads(get_setting(t, "custom_columns") or "[]")


# --- vistas ---

def brand(t):
    # status: solo le llega distinto de "active" al super admin (al resto ya le respondió 423/410)
    return {"name": t["name"], "status": t["status"], "logo": t["logo"] or DEFAULT_LOGO,
            "accent": t["accent"] or DEFAULT_ACCENT, "highlight": t["highlight"] or DEFAULT_HIGHLIGHT,
            "whatsapp": whatsapp(t), **messages(t), "custom_columns": custom_columns(t), "contact": contact(t)}


def super_view(t):
    # lo que ve el super admin de cada disquería; nunca el hash de la contraseña
    view = {k: v for k, v in t.items() if k != "admin_hash"}
    view.update(client_code=client_code(t), code_required=code_required(t), whatsapp=whatsapp(t), total=catalog.total(t),
                uploaded_at=get_setting(t, "uploaded_at") or None, closes_at=closes_at(t), closed=is_closed(t))
    return view
