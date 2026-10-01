"""Pagos online con Mercado Pago: conexión de la cuenta (admin), pago (cliente) y avisos de Mercado Pago."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from urllib.parse import quote

from ..dependencies import require_admin, require_client
from ..schemas import Order, Toggle
from ..services import mercadopago, tenants

router = APIRouter(tags=["mercadopago"])
ADMIN = "/api/t/{slug}/admin"


def callback_url(request):
    # tiene que coincidir con la URL de redirección registrada en la app de Mercado Pago
    return f"{request.base_url}api/mercadopago/callback"


# --- admin ---

@router.post(f"{ADMIN}/mercadopago/connect")
def connect(request: Request, t: dict = Depends(require_admin)):
    if not mercadopago.enabled():
        raise HTTPException(400, "Los pagos con Mercado Pago no están configurados en el servidor.")
    if mercadopago.direct():
        mercadopago.connect_direct(t)
        return {"url": f"/{t['slug']}/admin?mp=ok"}
    return {"url": mercadopago.start(t, callback_url(request))}


@router.get("/api/mercadopago/callback")
def callback(request: Request, state: str = "", code: str = "", error: str = ""):
    slug, _, nonce = state.partition(".")
    t = tenants.existing(slug)
    back = lambda result, msg="": RedirectResponse(f"/{slug}/admin?mp={result}" + (f"&msg={quote(msg)}" if msg else ""), 303)
    if error or not code:
        return back("denied")
    try:
        mercadopago.finish(t, nonce, code, callback_url(request))
    except HTTPException as e:
        return back("error", e.detail)
    return back("ok")


@router.delete(f"{ADMIN}/mercadopago")
def disconnect(t: dict = Depends(require_admin)):
    mercadopago.disconnect(t)
    return mercadopago.status(t)


@router.put(f"{ADMIN}/mercadopago/payments")
def toggle_payments(body: Toggle, t: dict = Depends(require_admin)):
    mercadopago.set_payments(t, body.value)
    return mercadopago.status(t)


@router.get(f"{ADMIN}/pedidos")
def orders(t: dict = Depends(require_admin)):
    return mercadopago.list_orders(t)


# --- cliente ---

@router.post("/api/t/{slug}/pagar")
def pay(body: Order, request: Request, t: dict = Depends(require_client)):
    return mercadopago.checkout(t, body.ids, str(request.base_url))


@router.get("/api/t/{slug}/pedidos/{order_id}")
def order_status(order_id: int, payment_id: str = "", t: dict = Depends(require_client)):
    # vuelta del cliente desde Mercado Pago: se confirma con la API, no con lo que dice la URL
    order = mercadopago.sync_payment(t, payment_id) if payment_id.isdigit() else mercadopago.get_order(t, order_id)
    if not order or order["id"] != order_id:
        raise HTTPException(404, "No encontramos ese pedido.")
    return {k: order[k] for k in ("id", "status", "total", "items")}  # sin el mail de quien pagó


# --- avisos de Mercado Pago ---

@router.post("/api/mercadopago/webhook")
async def webhook(request: Request, slug: str = ""):
    # llega como {"type": "payment", "data": {"id": ...}} o, en el formato viejo, ?topic=payment&id=...
    body = await request.json() if (await request.body()) else {}
    kind = body.get("type") or request.query_params.get("topic") or request.query_params.get("type")
    payment = str((body.get("data") or {}).get("id") or request.query_params.get("data.id") or request.query_params.get("id") or "")
    t = tenants.find(slug)
    if t and kind == "payment" and payment.isdigit():
        try:
            mercadopago.sync_payment(t, payment)
        except HTTPException:
            raise HTTPException(502, "No se pudo consultar el pago.")  # Mercado Pago reintenta más tarde
    return {"ok": True}  # todo lo demás se ignora con 200, si no Mercado Pago reintenta para siempre
