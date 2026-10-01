"""Panel del super administrador: alta, marca, estado y baja de disquerías."""
from fastapi import APIRouter, Depends, HTTPException, Response

from .. import validators
from ..config import STATUSES, SUPER_PASSWORD
from ..db import now, set_settings
from ..dependencies import require_super
from ..schemas import NewTenant, Secret, TenantPatch
from ..security import clear_super_cookie, hash_password, same, set_super_cookie
from ..services import tenants
from ..storage import remove_tenant_storage

router = APIRouter(prefix="/api/super", tags=["super admin"])
protected = [Depends(require_super)]


@router.post("/login")
def login(body: Secret, response: Response):
    if not SUPER_PASSWORD:
        raise HTTPException(403, "El panel de super admin está deshabilitado. Configurá SUPER_PASSWORD.")
    if not same(body.value, SUPER_PASSWORD):
        raise HTTPException(401, "Contraseña incorrecta.")
    set_super_cookie(response)
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
    if tenants.find(slug):
        raise HTTPException(409, f"Ya existe una disquería en /{slug}.")
    code, password = validators.client_code(body.client_code), validators.admin_password(body.admin_password)
    number = validators.whatsapp(body.whatsapp) if body.whatsapp.strip() else ""
    remove_tenant_storage(slug)  # restos de una disquería eliminada con el mismo slug
    set_settings({"slug": slug}, client_code=code, whatsapp=number)
    tenants.update_registry("INSERT INTO tenants (slug, name, admin_hash, created_at, status_at) VALUES (?, ?, ?, ?, ?)",
                            (slug, name, hash_password(password), now(), now()))
    return tenants.super_view(tenants.find(slug))


@router.patch("/tenants/{slug}", dependencies=protected)
def update(slug: str, body: TenantPatch):
    tenants.existing(slug)
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
    if changes:
        tenants.update_registry(f"UPDATE tenants SET {', '.join(f'{k} = ?' for k in changes)} WHERE slug = ?", [*changes.values(), slug])
    return tenants.super_view(tenants.find(slug))


@router.put("/tenants/{slug}/status", dependencies=protected)
def change_status(slug: str, body: Secret):
    tenants.existing(slug)
    if body.value not in STATUSES:
        validators.fail("Estado desconocido.")
    tenants.update_registry("UPDATE tenants SET status = ?, status_at = ? WHERE slug = ?", (body.value, now(), slug))
    return tenants.super_view(tenants.find(slug))


@router.put("/tenants/{slug}/password", dependencies=protected)
def reset_password(slug: str, body: Secret):
    tenants.existing(slug)
    tenants.update_registry("UPDATE tenants SET admin_hash = ? WHERE slug = ?", (hash_password(validators.admin_password(body.value)), slug))
    return {"ok": True}


@router.delete("/tenants/{slug}", dependencies=protected)
def delete(slug: str):
    if tenants.existing(slug)["status"] != "cancelled":
        validators.fail("Primero cancelá la disquería. Solo se eliminan las canceladas.")
    tenants.update_registry("DELETE FROM tenants WHERE slug = ?", (slug,))
    remove_tenant_storage(slug)  # base, Excel pendiente e imágenes
    return {"ok": True}
