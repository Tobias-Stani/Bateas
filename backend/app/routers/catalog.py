"""Carga del catálogo: vista previa de columnas -> confirmación. El Excel queda en disco entre los dos pasos."""
import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ..config import FIELDS
from ..db import get_setting, now, set_settings
from ..dependencies import actor, require_admin
from ..schemas import ImportPlan
from ..services import audit, catalog, plans, sections
from ..storage import pending_path

router = APIRouter(prefix="/api/t/{slug}/admin", tags=["catálogo"])


@router.post("/upload/preview")
def preview(file: UploadFile = File(...), t: dict = Depends(require_admin)):
    if not (file.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(400, "El archivo tiene que ser .xlsx.")
    path = pending_path(t["slug"])
    with path.open("wb") as out:
        while chunk := file.file.read(1 << 20):
            out.write(chunk)
    plan = catalog.detect(path, json.loads(get_setting(t, "column_map") or "{}"))
    set_settings(t, pending_filename=file.filename)
    return {**plan, "filename": file.filename, "fields": list(FIELDS)}


@router.post("/upload/confirm")
def confirm(body: ImportPlan, t: dict = Depends(require_admin), who: str = Depends(actor)):
    path = pending_path(t["slug"])
    if not path.exists():
        raise HTTPException(400, "Volvé a elegir el Excel: la vista previa venció.")
    catalog.validate_plan(body.header_row, body.mapping)
    rows, columns = catalog.read_discs(path, body.header_row, body.mapping)
    if len({c["name"] for c in columns}) != len(columns):
        raise HTTPException(400, "Hay dos columnas propias con el mismo nombre. Renombralas en el Excel o dejá una sola.")
    if not rows:
        raise HTTPException(400, "El Excel no tiene discos debajo de los encabezados. Revisá que sea la lista correcta.")
    plans.check(t, "discs", 0, len(rows))  # reemplaza el catálogo entero: cuenta la lista nueva
    catalog.save(t, rows)
    # se recuerda por nombre de encabezado: el Excel del mes que viene sale directo
    names = {c["index"]: catalog.norm(c["header"]) for c in catalog.detect(path, {})["columns"]}
    remembered = json.loads(get_setting(t, "column_map") or "{}")
    remembered.update({names[i]: f for i, f in body.mapping.items() if names.get(i)})
    set_settings(t, filename=get_setting(t, "pending_filename", "catalogo.xlsx"), uploaded_at=now(),
                 column_map=json.dumps(remembered), custom_columns=json.dumps(columns, ensure_ascii=False))
    path.unlink(missing_ok=True)
    audit.log(t["slug"], who, "catalog_uploaded", source="excel", filename=get_setting(t, "filename"), discs=len(rows))
    return {"ok": True, "total": len(rows), "sections_missing": sections.missing_after_upload(t)}


@router.delete("/catalog")
def delete(t: dict = Depends(require_admin), who: str = Depends(actor)):
    discs = catalog.total(t)
    catalog.drop(t)
    set_settings(t, filename="", uploaded_at="", custom_columns="[]")
    audit.log(t["slug"], who, "catalog_deleted", discs=discs)
    return {"ok": True}
