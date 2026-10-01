"""Admin de cada disquería: acceso y configuración de la tienda."""
from fastapi import APIRouter, Depends, HTTPException, Response

from .. import validators
from ..config import MESSAGE, MESSAGE_LINE
from ..db import get_setting, set_settings
from ..dependencies import require_admin, tenant
from ..schemas import Message, Secret, Toggle
from ..security import admin_token, check_password, clear_tenant_cookie, set_tenant_cookie
from ..services import catalog, tenants

router = APIRouter(prefix="/api/t/{slug}/admin", tags=["admin"])


@router.post("/login")
def login(body: Secret, response: Response, t: dict = Depends(tenant)):
    if not check_password(body.value, t["admin_hash"]):
        raise HTTPException(401, "Contraseña incorrecta.")
    set_tenant_cookie(response, t, "admin", admin_token(t), "strict")
    return {"ok": True}


@router.post("/logout")
def logout(response: Response, slug: str):
    clear_tenant_cookie(response, slug, "admin")
    return {"ok": True}


@router.get("/status")
def status(t: dict = Depends(require_admin)):
    return {"client_code": tenants.client_code(t), "code_required": tenants.code_required(t), "whatsapp": tenants.whatsapp(t),
            **tenants.messages(t), "custom_columns": tenants.custom_columns(t),
            "filename": get_setting(t, "filename"), "uploaded_at": get_setting(t, "uploaded_at"),
            "closes_at": tenants.closes_at(t), "closed": tenants.is_closed(t), **catalog.stats(t)}


@router.put("/code")
def change_code(body: Secret, t: dict = Depends(require_admin)):
    code = validators.client_code(body.value)
    set_settings(t, client_code=code)
    return {"ok": True, "client_code": code}


@router.put("/code_required")
def change_code_required(body: Toggle, t: dict = Depends(require_admin)):
    set_settings(t, code_required="1" if body.value else "0")
    return {"ok": True, "code_required": body.value}


@router.put("/whatsapp")
def change_whatsapp(body: Secret, t: dict = Depends(require_admin)):
    number = validators.whatsapp(body.value)
    set_settings(t, whatsapp=number)
    return {"ok": True, "whatsapp": number}


@router.put("/message")
def change_message(body: Message, t: dict = Depends(require_admin)):
    template, line = validators.message(body.template, body.line)
    set_settings(t, message=template, message_line=line)
    return {"ok": True, **tenants.messages(t)}


@router.delete("/message")
def reset_message(t: dict = Depends(require_admin)):
    set_settings(t, message=MESSAGE, message_line=MESSAGE_LINE)
    return {"ok": True, **tenants.messages(t)}


@router.put("/closes_at")
def change_closes_at(body: Secret, t: dict = Depends(require_admin)):
    value = validators.closing_date(body.value)
    set_settings(t, closes_at=value)
    return {"ok": True, "closes_at": value or None, "closed": tenants.is_closed(t)}
