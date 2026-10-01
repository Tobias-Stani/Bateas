"""Portada de la disquería: orden de los bloques y bloques de banners con sus imágenes."""
from fastapi import APIRouter, Depends, File, Form, UploadFile

from .. import validators
from ..dependencies import require_admin
from ..schemas import BannerIn, GroupIn, Layout, Order
from ..services import banners, home

router = APIRouter(prefix="/api/t/{slug}/admin", tags=["portada"])

GROUP_NAME = "El nombre del bloque tiene que tener entre 1 y 60 caracteres."
TEXT_LIMITS = {"title": 80, "text": 200, "button_label": 30}


@router.get("/portada")
def view(t: dict = Depends(require_admin)):
    return home.admin_view(t)


@router.put("/portada/orden")
def reorder(body: Layout, t: dict = Depends(require_admin)):
    home.save_order(t, body.tokens)
    return {"ok": True}


# --- bloques de banners ---

@router.post("/banner-bloques")
def create_group(body: GroupIn, t: dict = Depends(require_admin)):
    return {"ok": True, "id": banners.create_group(t, validators.text(body.name or "", 1, 60, GROUP_NAME))}


@router.patch("/banner-bloques/{group_id}")
def update_group(group_id: int, body: GroupIn, t: dict = Depends(require_admin)):
    name = validators.text(body.name, 1, 60, GROUP_NAME) if body.name is not None else None
    banners.update_group(t, group_id, name=name, visible=body.visible)
    return {"ok": True}


@router.delete("/banner-bloques/{group_id}")
def delete_group(group_id: int, t: dict = Depends(require_admin)):
    banners.delete_group(t, group_id)
    return {"ok": True}


# --- imágenes de un bloque ---

@router.post("/banners")
def create(file: UploadFile = File(...), group_id: int = Form(...), t: dict = Depends(require_admin)):
    return {"ok": True, "id": banners.create(t, group_id, file)}


@router.patch("/banners/{banner_id}")
def update(banner_id: int, body: BannerIn, t: dict = Depends(require_admin)):
    changes = body.model_dump(exclude_none=True)
    for key, top in TEXT_LIMITS.items():
        if key in changes:
            changes[key] = changes[key].strip()
            if len(changes[key]) > top:
                validators.fail(f"El texto es demasiado largo (máximo {top} caracteres).")
    if "button_link" in changes:
        changes["button_link"] = home.valid_link(t, changes["button_link"])
    if "visible" in changes:
        changes["visible"] = int(changes["visible"])
    banners.update(t, banner_id, changes)
    return {"ok": True}


@router.put("/banners/{banner_id}/imagen")
def replace_image(banner_id: int, file: UploadFile = File(...), t: dict = Depends(require_admin)):
    banners.replace_image(t, banner_id, file)
    return {"ok": True}


@router.delete("/banners/{banner_id}")
def delete(banner_id: int, t: dict = Depends(require_admin)):
    banners.delete(t, banner_id)
    return {"ok": True}


@router.put("/banners-orden")
def reorder_images(body: Order, t: dict = Depends(require_admin)):
    banners.reorder(t, body.ids)
    return {"ok": True}
