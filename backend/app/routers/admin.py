"""Admin de cada disquería: acceso y configuración de la tienda. Cada cambio queda en el registro de actividad."""
from fastapi import APIRouter, Depends, HTTPException, Response

from .. import validators
from ..config import MESSAGE, MESSAGE_LINE
from ..db import get_setting, set_settings
from ..dependencies import actor, require_admin, tenant
from ..schemas import Contact, Message, Secret, Toggle
from ..security import admin_token, check_password, clear_tenant_cookie, set_tenant_cookie
from ..services import audit, catalog, discogs, mercadopago, tenants

router = APIRouter(prefix="/api/t/{slug}/admin", tags=["admin"])


@router.post("/login")
def login(body: Secret, response: Response, t: dict = Depends(tenant)):
    if not check_password(body.value, t["admin_hash"]):
        audit.log(t["slug"], "admin", "admin_login_failed")
        raise HTTPException(401, "Contraseña incorrecta.")
    set_tenant_cookie(response, t, "admin", admin_token(t), "strict")
    audit.log(t["slug"], "admin", "admin_login")
    return {"ok": True}


@router.post("/logout")
def logout(response: Response, slug: str):
    clear_tenant_cookie(response, slug, "admin")
    return {"ok": True}


@router.get("/status")
def status(t: dict = Depends(require_admin)):
    return {"client_code": tenants.client_code(t), "code_required": tenants.code_required(t), "whatsapp": tenants.whatsapp(t),
            **tenants.messages(t), "custom_columns": tenants.custom_columns(t), "contact": tenants.contact(t),
            "filename": get_setting(t, "filename"), "uploaded_at": get_setting(t, "uploaded_at"),
            "closes_at": tenants.closes_at(t), "closed": tenants.is_closed(t), "discogs": discogs.status(t),
            "mercadopago": mercadopago.status(t), **catalog.stats(t)}


@router.put("/code")
def change_code(body: Secret, t: dict = Depends(require_admin), who: str = Depends(actor)):
    code = validators.client_code(body.value)
    set_settings(t, client_code=code)
    audit.log(t["slug"], who, "settings_changed", field="client_code")
    return {"ok": True, "client_code": code}


@router.put("/code_required")
def change_code_required(body: Toggle, t: dict = Depends(require_admin), who: str = Depends(actor)):
    set_settings(t, code_required="1" if body.value else "0")
    audit.log(t["slug"], who, "settings_changed", field="code_required", value=body.value)
    return {"ok": True, "code_required": body.value}


@router.put("/whatsapp")
def change_whatsapp(body: Secret, t: dict = Depends(require_admin), who: str = Depends(actor)):
    number = validators.whatsapp(body.value)
    before = tenants.whatsapp(t)
    set_settings(t, whatsapp=number)
    audit.log(t["slug"], who, "settings_changed", field="whatsapp", before=before, after=number)
    return {"ok": True, "whatsapp": number}


@router.put("/contact")
def change_contact(body: Contact, t: dict = Depends(require_admin), who: str = Depends(actor)):
    contact = tenants.set_contact(t, validators.contact(body))
    audit.log(t["slug"], who, "settings_changed", field="contact", value=contact)
    return {"ok": True, "contact": contact}


@router.put("/message")
def change_message(body: Message, t: dict = Depends(require_admin), who: str = Depends(actor)):
    template, line = validators.message(body.template, body.line)
    set_settings(t, message=template, message_line=line)
    audit.log(t["slug"], who, "settings_changed", field="message")
    return {"ok": True, **tenants.messages(t)}


@router.delete("/message")
def reset_message(t: dict = Depends(require_admin), who: str = Depends(actor)):
    set_settings(t, message=MESSAGE, message_line=MESSAGE_LINE)
    audit.log(t["slug"], who, "settings_changed", field="message", value="original")
    return {"ok": True, **tenants.messages(t)}


@router.put("/closes_at")
def change_closes_at(body: Secret, t: dict = Depends(require_admin), who: str = Depends(actor)):
    value = validators.closing_date(body.value)
    set_settings(t, closes_at=value)
    audit.log(t["slug"], who, "settings_changed", field="closes_at", value=value or None)
    return {"ok": True, "closes_at": value or None, "closed": tenants.is_closed(t)}
