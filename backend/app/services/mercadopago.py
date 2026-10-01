"""Mercado Pago como marketplace: cada disquería conecta su cuenta (OAuth) y cobra; Bateas se queda con su comisión."""
import base64
import hashlib
import json
import logging
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from ..config import (MAX_ORDER, MP_ACCESS_TOKEN, MP_API, MP_AUTHORIZE, MP_CLIENT_ID, MP_CLIENT_SECRET, MP_CURRENCY,
                      MP_FEE_PERCENT, MP_TEST)
from ..db import db, get_setting, now, set_settings
from ..security import same
from . import catalog

log = logging.getLogger("uvicorn.error")  # el motivo de un rechazo de Mercado Pago queda en el log del servidor
PRICE = re.compile(r"\d+(\.\d+)?")  # mismo criterio que fmtPrice del front: sin moneda = pesos
RENEW_BEFORE = timedelta(days=7)  # el token dura 180 días; se renueva antes de que venza


def direct():
    # modo desarrollo: sin la app OAuth, con un Access Token de prueba fijo
    return bool(MP_ACCESS_TOKEN) and not (MP_CLIENT_ID and MP_CLIENT_SECRET)


def enabled():
    return bool(MP_CLIENT_ID and MP_CLIENT_SECRET) or direct()


def connect_direct(t):
    # la cuenta que cobra es la del token: no hay a quién descontarle comisión
    far = (datetime.now(timezone.utc) + timedelta(days=3650)).isoformat(timespec="minutes")
    set_settings(t, mp_token=MP_ACCESS_TOKEN, mp_refresh="", mp_user="", mp_expires=far)


def _call(method, path, token="", body=None):
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(MP_API + path, method=method, headers=headers,
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        log.warning("Mercado Pago %s %s -> %s %s", method, path, e.code, e.read().decode(errors="replace")[:500])
        if e.code in (400, 401, 403) and path == "/oauth/token":
            raise HTTPException(400, "Mercado Pago no aceptó la conexión. Volvé a conectar la cuenta.")
        raise HTTPException(502, f"Mercado Pago respondió con un error ({e.code}). Probá de nuevo en un rato.")
    except urllib.error.URLError:
        raise HTTPException(502, "No se pudo conectar con Mercado Pago. Probá de nuevo en un rato.")


# --- conexión de la cuenta de la disquería ---

def start(t, redirect_uri):
    # state = slug + azar: la vuelta llega a una URL fija (la registrada en la app) y así se sabe de qué disquería es
    nonce, verifier = secrets.token_urlsafe(16), secrets.token_urlsafe(64)
    set_settings(t, mp_state=nonce, mp_verifier=verifier)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return MP_AUTHORIZE + "?" + urllib.parse.urlencode({
        "client_id": MP_CLIENT_ID, "response_type": "code", "platform_id": "mp", "redirect_uri": redirect_uri,
        "state": f"{t['slug']}.{nonce}", "code_challenge": challenge, "code_challenge_method": "S256"})


def _save_token(t, data):
    expires = datetime.now(timezone.utc) + timedelta(seconds=int(data.get("expires_in", 15552000)))
    set_settings(t, mp_token=data["access_token"], mp_refresh=data.get("refresh_token", ""),
                 mp_user=str(data.get("user_id", "")), mp_expires=expires.isoformat(timespec="minutes"))


def finish(t, nonce, code, redirect_uri):
    if not same(get_setting(t, "mp_state", "").encode(), nonce.encode()):
        raise HTTPException(400, "La conexión con Mercado Pago venció. Volvé a intentarlo desde el admin.")
    data = _call("POST", "/oauth/token", body={
        "client_id": MP_CLIENT_ID, "client_secret": MP_CLIENT_SECRET, "grant_type": "authorization_code", "code": code,
        "redirect_uri": redirect_uri, "code_verifier": get_setting(t, "mp_verifier", ""), "test_token": "true" if MP_TEST else "false"})
    _save_token(t, data)
    set_settings(t, mp_state="", mp_verifier="")


def token(t):
    """El access_token de la disquería, renovado si está por vencer."""
    current, expires = get_setting(t, "mp_token", ""), get_setting(t, "mp_expires", "")
    if current and expires and datetime.fromisoformat(expires) - RENEW_BEFORE < datetime.now(timezone.utc):
        _save_token(t, _call("POST", "/oauth/token", body={"client_id": MP_CLIENT_ID, "client_secret": MP_CLIENT_SECRET,
                                                           "grant_type": "refresh_token", "refresh_token": get_setting(t, "mp_refresh", "")}))
        current = get_setting(t, "mp_token", "")
    return current


def connected(t):
    return bool(get_setting(t, "mp_token", ""))


def disconnect(t):
    set_settings(t, mp_token="", mp_refresh="", mp_user="", mp_expires="", payments="0")


def payments_on(t):
    # lo que mira la tienda: la disquería lo prendió, tiene la cuenta conectada y el servidor tiene la app
    return enabled() and connected(t) and get_setting(t, "payments", "0") == "1"


def set_payments(t, on):
    if on and not connected(t):
        raise HTTPException(400, "Primero conectá tu cuenta de Mercado Pago.")
    set_settings(t, payments="1" if on else "0")


def status(t):
    # lo que ve el admin; nunca los tokens
    return {"enabled": enabled(), "connected": connected(t), "payments": payments_on(t), "fee_percent": fee_percent(), "test": MP_TEST}


def fee_percent():
    return 0.0 if direct() else MP_FEE_PERCENT


# --- pedidos ---

def _orders(t):
    con = db(t)
    con.execute("""CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, items TEXT NOT NULL,
                   total REAL NOT NULL, fee REAL NOT NULL, status TEXT NOT NULL, payment_id TEXT, payer TEXT, updated_at TEXT)""")
    return con


def order_view(row):
    return {**dict(row), "items": json.loads(row["items"])}


def checkout(t, ids, base_url):
    """Arma el pedido con los precios del catálogo (nunca los del navegador) y devuelve el link de pago."""
    if not payments_on(t):
        raise HTTPException(400, "Esta disquería no cobra online. Consultá por WhatsApp.")
    ids = list(dict.fromkeys(ids))  # sin repetidos: un disco es una unidad
    if not 1 <= len(ids) <= MAX_ORDER:
        raise HTTPException(400, f"El pedido tiene que tener entre 1 y {MAX_ORDER} discos.")
    discs = {d["id"]: d for d in catalog.by_ids(t, ids)}
    if missing := [i for i in ids if i not in discs]:
        raise HTTPException(400, f"Hay discos que ya no están en la lista (#{', #'.join(map(str, missing))}). Quitalos del pedido.")
    if unpriced := [d for d in discs.values() if not PRICE.fullmatch(d["price"] or "")]:
        raise HTTPException(400, f"#{unpriced[0]['id']} {unpriced[0]['title']} no tiene precio en pesos: consultalo por WhatsApp.")
    items = [{"id": i, "artist": discs[i]["artist"], "title": discs[i]["title"], "media": discs[i]["media"],
              "description": discs[i]["description"], "price": float(discs[i]["price"])} for i in ids]
    total = round(sum(it["price"] for it in items), 2)
    fee = round(total * fee_percent() / 100, 2)
    con = _orders(t)
    with con:
        order = con.execute("INSERT INTO orders (created_at, items, total, fee, status) VALUES (?, ?, ?, ?, 'pending')",
                            (now(), json.dumps(items, ensure_ascii=False), total, fee)).lastrowid
    con.close()
    store = f"{base_url}{t['slug']}"
    pref = _call("POST", "/checkout/preferences", token(t), {
        "items": [{"id": str(it["id"]), "title": f"#{it['id']} {it['artist']} – {it['title']}"[:250], "quantity": 1,
                   "unit_price": it["price"], "currency_id": MP_CURRENCY} for it in items],
        "external_reference": str(order),
        **({"marketplace_fee": fee} if fee else {}),
        "back_urls": {k: f"{store}?pago={k}&pedido={order}" for k in ("success", "failure", "pending")},
        # Mercado Pago rechaza el regreso automático a localhost; en local se vuelve con "Volver al sitio"
        **({"auto_return": "approved"} if store.startswith("https://") else {}),
        "notification_url": f"{base_url}api/mercadopago/webhook?slug={t['slug']}",
        "statement_descriptor": t["name"][:22],
    })
    return {"order": order, "url": (MP_TEST and pref.get("sandbox_init_point")) or pref["init_point"]}


def sync_payment(t, payment_id):
    """Trae el pago de Mercado Pago (la única fuente confiable) y actualiza su pedido. Lo usan el webhook y la vuelta del cliente."""
    p = _call("GET", f"/v1/payments/{int(payment_id)}", token(t))
    con = _orders(t)
    row = con.execute("SELECT * FROM orders WHERE id = ?", (int(p.get("external_reference") or 0),)).fetchone()
    if not row:
        con.close()
        return None
    status = p.get("status", "pending")
    if status == "approved" and abs(float(p.get("transaction_amount", 0)) - row["total"]) > 0.01:
        status = "amount_mismatch"  # nunca debería pasar: el monto cobrado no es el del pedido
    with con:
        con.execute("UPDATE orders SET status = ?, payment_id = ?, payer = ?, updated_at = ? WHERE id = ?",
                    (status, str(p.get("id")), (p.get("payer") or {}).get("email", ""), now(), row["id"]))
    row = con.execute("SELECT * FROM orders WHERE id = ?", (row["id"],)).fetchone()
    con.close()
    return order_view(row)


def get_order(t, order_id):
    con = _orders(t)
    row = con.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    con.close()
    return order_view(row) if row else None


def list_orders(t, limit=100):
    # los pendientes sin pago son carritos abandonados: no le sirven a la disquería
    con = _orders(t)
    rows = [order_view(r) for r in con.execute("SELECT * FROM orders WHERE payment_id IS NOT NULL ORDER BY id DESC LIMIT ?", (limit,))]
    con.close()
    return rows
