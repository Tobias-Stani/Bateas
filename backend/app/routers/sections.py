"""Secciones de la disquería (curaduría): crear, nombrar, ocultar y elegir sus discos."""
from fastapi import APIRouter, Depends

from .. import validators
from ..dependencies import require_admin
from ..schemas import ItemIn, Order, SectionIn
from ..services import sections

router = APIRouter(prefix="/api/t/{slug}/admin", tags=["secciones"])

NAME = "El nombre de la sección tiene que tener entre 1 y 60 caracteres."


@router.get("/secciones")
def list_sections(t: dict = Depends(require_admin)):
    return sections.list_all(t, public=False)


@router.post("/secciones")
def create(body: SectionIn, t: dict = Depends(require_admin)):
    return {"ok": True, "id": sections.create(t, validators.text(body.name or "", 1, 60, NAME))}


@router.patch("/secciones/{section_id}")
def update(section_id: int, body: SectionIn, t: dict = Depends(require_admin)):
    name = validators.text(body.name, 1, 60, NAME) if body.name is not None else None
    sections.update(t, section_id, name=name, visible=body.visible)
    return {"ok": True}


@router.delete("/secciones/{section_id}")
def delete(section_id: int, t: dict = Depends(require_admin)):
    sections.delete(t, section_id)
    return {"ok": True}


@router.put("/secciones-orden")
def reorder(body: Order, t: dict = Depends(require_admin)):
    sections.reorder(t, body.ids)
    return {"ok": True}


@router.post("/secciones/{section_id}/discos")
def add_disc(section_id: int, body: ItemIn, t: dict = Depends(require_admin)):
    sections.add_disc(t, section_id, body.disc_id)
    return {"ok": True}


@router.delete("/secciones/{section_id}/discos/{item_id}")
def remove_disc(section_id: int, item_id: int, t: dict = Depends(require_admin)):
    sections.remove_disc(t, section_id, item_id)
    return {"ok": True}


@router.put("/secciones/{section_id}/orden")
def reorder_discs(section_id: int, body: Order, t: dict = Depends(require_admin)):
    sections.reorder_discs(t, section_id, body.ids)
    return {"ok": True}
