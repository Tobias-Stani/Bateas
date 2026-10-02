"""Planes: Gratis (con límites) y Premium (todo). Por ahora el Premium lo asigna el super admin; más adelante, la suscripción."""
from datetime import datetime, timezone

from fastapi import HTTPException

from ..config import FREE_LIMITS, PREMIUM_PRICE
from ..db import db, get_setting, now, set_settings


def plan(t):
    """El plan vigente: un Premium vencido vuelve a ser Gratis solo, sin que nadie tenga que tocar nada."""
    until = t.get("premium_until")
    if t.get("plan") == "premium" and (not until or datetime.fromisoformat(until) > datetime.now(timezone.utc)):
        return "premium"
    return "free"


def premium(t):
    return plan(t) == "premium"


def check(t, what, current, adding=1):
    """Corta con un mensaje para la persona si el plan Gratis no alcanza. Lo que ya existe no se toca: solo frena lo nuevo."""
    top = FREE_LIMITS[what]
    if premium(t) or current + adding <= top:
        return
    noun = {"discs": "discos", "banners": "banner" if top == 1 else "banners", "sections": "sección" if top == 1 else "secciones"}[what]
    detail = f" Tu lista tiene {current + adding:,}.".replace(",", ".") if what == "discs" else ""
    raise HTTPException(403, f"El plan Gratis permite hasta {top} {noun}.{detail} Con Premium ($ {PREMIUM_PRICE:,} por mes) no tenés límites.".replace(",", "."))


def require_premium(t, what):
    if not premium(t):
        raise HTTPException(403, f"{what} es parte del plan Premium ($ {PREMIUM_PRICE:,} por mes).".replace(",", "."))


def usage(t):
    con = db(t)
    count = lambda table: con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] \
        if con.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (table,)).fetchone() else 0
    used = {"discs": count("discos"), "banners": count("banners"), "sections": count("sections")}
    con.close()
    return used


def view(t):
    # lo que muestra el admin: plan, vencimiento, límites y cuánto usa
    return {"plan": plan(t), "premium_until": t.get("premium_until"), "price": PREMIUM_PRICE,
            "limits": None if premium(t) else FREE_LIMITS, "usage": usage(t),
            "requested_at": None if premium(t) else get_setting(t, "premium_requested_at") or None}


def request_premium(t):
    """Mientras no haya suscripción automática: la disquería avisa que quiere Premium y el super admin lo activa."""
    if premium(t):
        raise HTTPException(409, "Ya tenés Premium.")
    set_settings(t, premium_requested_at=now())
