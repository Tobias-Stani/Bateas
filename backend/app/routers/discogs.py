"""Conexión con Discogs: el admin conecta su cuenta e importa su inventario."""
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from ..dependencies import actor, require_admin
from ..services import audit, discogs, tenants

router = APIRouter(tags=["discogs"])
ADMIN = "/api/t/{slug}/admin/discogs"


@router.post(f"{ADMIN}/connect")
def connect(request: Request, t: dict = Depends(require_admin)):
    if not discogs.enabled():
        raise HTTPException(400, "La conexión con Discogs no está configurada en el servidor.")
    # Discogs vuelve a esta dirección; base_url respeta el dominio y el https del proxy
    callback = f"{request.base_url}api/discogs/callback?slug={t['slug']}"
    return {"url": discogs.start(t, callback)}


@router.get("/api/discogs/callback")
def callback(slug: str, oauth_token: str = "", oauth_verifier: str = "", denied: str = ""):
    t = tenants.existing(slug)
    back = lambda result, msg="": RedirectResponse(f"/{slug}/admin?discogs={result}" + (f"&msg={quote(msg)}" if msg else ""), 303)
    if denied or not oauth_verifier:
        return back("denied")
    try:
        user = discogs.finish(t, oauth_token, oauth_verifier)
    except HTTPException as e:
        audit.log(slug, "admin", "discogs_connect_failed", error=e.detail)
        return back("error", e.detail)
    audit.log(slug, "admin", "discogs_connected", user=user)
    return back("ok")


@router.post(f"{ADMIN}/import")
def start_import(tasks: BackgroundTasks, t: dict = Depends(require_admin), who: str = Depends(actor)):
    discogs.begin(t)
    audit.log(t["slug"], who, "discogs_import_started", user=discogs.user(t))
    tasks.add_task(discogs.import_inventory, t)
    return discogs.status(t)


@router.delete(ADMIN)
def disconnect(t: dict = Depends(require_admin), who: str = Depends(actor)):
    if discogs.running(t):
        raise HTTPException(409, "Esperá a que termine la importación para desconectar.")
    user = discogs.user(t)
    discogs.disconnect(t)
    audit.log(t["slug"], who, "discogs_disconnected", user=user)
    return discogs.status(t)
