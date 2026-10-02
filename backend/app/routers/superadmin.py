"""Panel del super administrador: alta, marca, estado y baja de disquerías; estadísticas y registro de actividad."""
from fastapi import APIRouter, Depends, HTTPException, Response

from .. import validators
from ..config import STATUSES, SUPER_PASSWORD
from ..db import now
from ..dependencies import require_super
from ..schemas import NewTenant, Secret, TenantPatch
from ..security import clear_super_cookie, hash_password, same, set_super_cookie
from ..services import accounts, audit, catalog, mercadopago, tenants
from ..storage import remove_tenant_storage

router = APIRouter(prefix="/api/super", tags=["super admin"])
protected = [Depends(require_super)]


@router.post("/login")
def login(body: Secret, response: Response):
    if not SUPER_PASSWORD:
        raise HTTPException(403, "El panel de super admin está deshabilitado. Configurá SUPER_PASSWORD.")
    if not same(body.value, SUPER_PASSWORD):
        audit.log("", "super", "super_login_failed")
        raise HTTPException(401, "Contraseña incorrecta.")
    set_super_cookie(response)
    audit.log("", "super", "super_login")
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    clear_super_cookie(response)
    return {"ok": True}


@router.get("/tenants", dependencies=protected)
def list_tenants():
    return [tenants.super_view(t) for t in tenants.all_tenants()]


@router.post("/tenants", dependencies=protected)
def create(body: NewTenant):
    name, slug = validators.tenant_name(body.name), validators.slug(body.slug)
    code, password = validators.client_code(body.client_code), validators.admin_password(body.admin_password)
    number = validators.whatsapp(body.whatsapp) if body.whatsapp.strip() else ""
    t = tenants.create(name, slug, password, code, number)
    audit.log(slug, "super", "tenant_created", name=name)
    return tenants.super_view(t)


@router.patch("/tenants/{slug}", dependencies=protected)
def update(slug: str, body: TenantPatch):
    before = tenants.existing(slug)
    changes = body.model_dump(exclude_none=True)
    if "name" in changes:
        changes["name"] = validators.tenant_name(changes["name"])
    for key in ("accent", "highlight"):
        if key in changes:
            validators.color(changes[key])
    if "logo" in changes:
        changes["logo"] = validators.logo(changes["logo"])
    if "notes" in changes and len(changes["notes"]) > 2000:
        validators.fail("Las notas son demasiado largas.")
    if "plan" in changes:
        changes["plan"] = validators.plan(changes["plan"])
    if "premium_until" in changes:
        changes["premium_until"] = validators.premium_until(changes["premium_until"])
    if changes:
        tenants.update_registry(f"UPDATE tenants SET {', '.join(f'{k} = ?' for k in changes)} WHERE slug = ?", [*changes.values(), slug])
        changed = {k: [before[k], v] for k, v in changes.items() if before[k] != v}  # [antes, después]
        if "notes" in changed:
            changed["notes"] = "editadas"  # las notas pueden ser largas: alcanza con saber que cambiaron
        if changed:
            audit.log(slug, "super", "tenant_updated", **changed)
    return tenants.super_view(tenants.find(slug))


@router.put("/tenants/{slug}/status", dependencies=protected)
def change_status(slug: str, body: Secret):
    before = tenants.existing(slug)["status"]
    if body.value not in STATUSES:
        validators.fail("Estado desconocido.")
    tenants.update_registry("UPDATE tenants SET status = ?, status_at = ? WHERE slug = ?", (body.value, now(), slug))
    if before != body.value:
        audit.log(slug, "super", "tenant_status", before=before, after=body.value)
    return tenants.super_view(tenants.find(slug))


@router.put("/tenants/{slug}/password", dependencies=protected)
def reset_password(slug: str, body: Secret):
    tenants.existing(slug)
    tenants.update_registry("UPDATE tenants SET admin_hash = ? WHERE slug = ?", (hash_password(validators.admin_password(body.value)), slug))
    audit.log(slug, "super", "admin_password_reset")
    return {"ok": True}


@router.delete("/tenants/{slug}", dependencies=protected)
def delete(slug: str):
    t = tenants.existing(slug)
    if t["status"] != "cancelled":
        validators.fail("Primero cancelá la disquería. Solo se eliminan las canceladas.")
    # foto de lo que se borra: los pagos ya están en el libro central, esto deja constancia del resto
    audit.log(slug, "super", "tenant_deleted", name=t["name"], discs=catalog.total(t), created_at=t["created_at"])
    tenants.update_registry("DELETE FROM tenants WHERE slug = ?", (slug,))
    remove_tenant_storage(slug)  # base, Excel pendiente e imágenes
    return {"ok": True}


# --- estadísticas y registro ---

@router.get("/stats", dependencies=protected)
def stats():
    return {**audit.stats(), "fee_percent": mercadopago.fee_percent(), "mp_enabled": mercadopago.enabled(), "mp_test": mercadopago.MP_TEST}


@router.get("/events", dependencies=protected)
def events(slug: str = "", kind: str = "", before: int = 0, limit: int = 100):
    return audit.events(slug, kind, before, limit)


@router.get("/payments", dependencies=protected)
def payments(slug: str = ""):
    return audit.payments(slug)


@router.get("/accounts", dependencies=protected)
def list_accounts():
    return accounts.all_accounts()


@router.post("/reconcile", dependencies=protected)
def reconcile():
    """Pregunta a Mercado Pago por los pedidos sin confirmar de todas las disquerías conectadas."""
    changed, failed = 0, []
    for t in tenants.all_tenants():
        try:
            changed += mercadopago.reconcile(t)
        except HTTPException:
            failed.append(t["slug"])
    audit.log("", "super", "mp_reconcile", changed=changed, failed=failed)
    return {"changed": changed, "failed": failed}
