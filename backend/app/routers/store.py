"""Tienda pública de cada disquería: lo que usa el cliente."""
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse

from ..config import CLOSED, IMAGE_TYPES
from ..dependencies import require_client, tenant
from ..schemas import Secret
from ..security import clear_tenant_cookie, client_token, same, set_tenant_cookie
from ..services import catalog, home, images, sections, tenants

router = APIRouter(prefix="/api/t/{slug}", tags=["tienda"])


@router.get("/brand")
def brand(t: dict = Depends(tenant)):
    return tenants.brand(t)


@router.get("/estado")
def estado(t: dict = Depends(tenant)):
    # público: la pantalla de ingreso muestra hasta cuándo está abierta la lista
    return {"closes_at": tenants.closes_at(t), "closed": tenants.is_closed(t), "code_required": tenants.code_required(t)}


@router.post("/login")
def login(body: Secret, response: Response, t: dict = Depends(tenant)):
    if tenants.is_closed(t):
        raise HTTPException(403, CLOSED)
    code = tenants.client_code(t)
    if not same(body.value.strip(), code):
        raise HTTPException(401, "Ese código no es correcto. Pedíselo a la disquería.")
    set_tenant_cookie(response, t, "session", client_token(t, code), "lax")
    return {"ok": True}


@router.post("/logout")
def logout(response: Response, slug: str):
    clear_tenant_cookie(response, slug, "session")
    return {"ok": True}


@router.get("/filtros")
def filtros(t: dict = Depends(require_client)):
    return catalog.filters(t)


@router.get("/discos")
def discos(q: str = "", media: str = "", genre: str = "", page: int = 1, t: dict = Depends(require_client)):
    return catalog.search(t, q, media, genre, page)


@router.get("/secciones")
def secciones(t: dict = Depends(require_client)):
    return sections.list_all(t, public=True)


@router.get("/portada")
def portada(t: dict = Depends(require_client)):
    return {"blocks": home.public_blocks(t)}


@router.get("/files/{name}")
def file(name: str, t: dict = Depends(tenant)):
    path = images.path(t, name)
    if not path:
        raise HTTPException(404, "No existe.")
    # nombre al azar y nunca se reescribe: se puede guardar para siempre
    return FileResponse(path, media_type=IMAGE_TYPES[name.rsplit(".", 1)[1]],
                        headers={"Cache-Control": "public, max-age=31536000, immutable"})
