"""Cuenta del dueño: iniciar sesión con Google y crear su tienda."""
import secrets

from fastapi import APIRouter, Depends, HTTPException, Response

from .. import validators
from ..config import GOOGLE_CLIENT_ID
from ..dependencies import require_account
from ..schemas import NewStore, Secret
from ..security import clear_account_cookie, set_account_cookie
from ..services import accounts, audit, plans, tenants

router = APIRouter(prefix="/api/cuenta", tags=["cuenta"])


@router.get("/config")
def config():
    # el Client ID de Google no es secreto: el botón lo necesita en la página
    return {"google_client_id": GOOGLE_CLIENT_ID}


@router.post("/google")
def google(body: Secret, response: Response):
    if not accounts.enabled():
        raise HTTPException(400, "El inicio de sesión con Google no está configurado en el servidor.")
    account, new = accounts.sign_in(accounts.verify_google(body.value))
    set_account_cookie(response, account)
    audit.log("", "account", "account_created" if new else "account_login", account=account["id"], email=account["email"])
    return accounts.view(account)


@router.get("")
def me(account: dict = Depends(require_account)):
    return accounts.view(account)


@router.post("/logout")
def logout(response: Response):
    clear_account_cookie(response)
    return {"ok": True}


@router.post("/tiendas")
def create_store(body: NewStore, account: dict = Depends(require_account)):
    accounts.check_can_create(account)
    name, slug, plan = validators.tenant_name(body.name), validators.slug(body.slug), validators.plan(body.plan)
    # entra con Google: la contraseña del admin queda al azar (el super admin puede darle una si la pide)
    t = tenants.create(name, slug, secrets.token_urlsafe(16), secrets.token_urlsafe(6), owner_id=account["id"], public=True)
    audit.log(slug, "account", "tenant_created", name=name, account=account["id"], email=account["email"], source="registro", plan=plan)
    if plan == "premium":
        # ponytail: sin suscripción automática todavía, Premium arranca como pedido; con la suscripción, acá va el pago
        plans.request_premium(t)
        audit.log(slug, "account", "premium_requested", email=account["email"], source="registro")
    return {"slug": t["slug"], "name": t["name"], "plan_requested": plan}
