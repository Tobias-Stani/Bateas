"""Quién puede entrar a qué. Se usan como Depends() en las rutas."""
from fastapi import Cookie, Depends, HTTPException

from .config import CLOSED, GONE, SUPER_PASSWORD, SUSPENDED
from .security import admin_token, client_token, same, super_token
from .services import accounts, tenants


def is_super(super_: str | None = Cookie(None, alias="super")):
    return bool(SUPER_PASSWORD) and same(super_, super_token())


def require_super(ok: bool = Depends(is_super)):
    if not ok:
        raise HTTPException(401, "Iniciá sesión como super administrador.")


def tenant(slug: str, sup: bool = Depends(is_super)):
    """La disquería de la URL, si está activa. El super admin entra a cualquiera, esté como esté."""
    t = tenants.find(slug)
    if not t:
        raise HTTPException(404, "Esta tienda no existe.")
    if sup:
        return t
    if t["status"] == "cancelled":
        raise HTTPException(410, GONE)
    if t["status"] == "suspended":
        raise HTTPException(423, SUSPENDED)
    return t


def current_account(account: str | None = Cookie(None)):
    """La cuenta con la que inició sesión con Google, o None."""
    return accounts.from_cookie(account)


def require_account(acc: dict | None = Depends(current_account)):
    if not acc:
        raise HTTPException(401, "Iniciá sesión con Google.")
    return acc


def is_admin(t, admin_cookie, sup, acc=None):
    # super admin, la contraseña del admin, o el dueño con su cuenta de Google
    return sup or same(admin_cookie, admin_token(t)) or bool(acc and t.get("owner_id") == acc["id"])


def require_admin(t: dict = Depends(tenant), admin: str | None = Cookie(None), sup: bool = Depends(is_super),
                  acc: dict | None = Depends(current_account)):
    if not is_admin(t, admin, sup, acc):
        raise HTTPException(401, "Iniciá sesión como administrador.")
    return t


def actor(sup: bool = Depends(is_super)):
    # para el registro de actividad: el super admin también entra a los admins
    return "super" if sup else "admin"


def require_client(t: dict = Depends(tenant), session: str | None = Cookie(None),
                   admin: str | None = Cookie(None), sup: bool = Depends(is_super), acc: dict | None = Depends(current_account)):
    if is_admin(t, admin, sup, acc):
        return t  # el admin entra aunque esté cerrado
    if tenants.code_required(t) and not same(session, client_token(t, tenants.client_code(t))):
        raise HTTPException(401, "Ingresá el código de acceso.")
    if tenants.is_closed(t):
        raise HTTPException(403, CLOSED)
    return t
