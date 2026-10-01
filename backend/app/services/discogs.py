"""Discogs: cada disquería conecta su cuenta (OAuth 1.0a) e importa su inventario a la venta como catálogo."""
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from ..config import DISCOGS_AGENT, DISCOGS_API, DISCOGS_AUTHORIZE, DISCOGS_KEY, DISCOGS_PAGE, DISCOGS_SECRET, FIELDS
from ..db import get_setting, now, set_settings
from ..security import same
from . import catalog, sections

# lo que trae Discogs y no tiene campo fijo: columnas propias, usables en el mensaje como {ano}, {estado}, {tapa}
COLUMNS = [{"key": catalog.custom_key(n), "name": n} for n in ("Año", "Estado", "Tapa")]
STALE = timedelta(minutes=30)  # una importación sin avances en este tiempo se dio por muerta (ej. reinicio)


def enabled():
    return bool(DISCOGS_KEY and DISCOGS_SECRET)


def quote(value):
    return urllib.parse.quote(str(value), safe="")


def _call(method, url, token_secret="", **oauth):
    """Pedido firmado a Discogs. Firma PLAINTEXT: válida sobre HTTPS y sin dependencias."""
    for attempt in range(4):
        params = {"oauth_consumer_key": DISCOGS_KEY, "oauth_nonce": secrets.token_hex(16),
                  "oauth_signature": f"{quote(DISCOGS_SECRET)}&{quote(token_secret)}", "oauth_signature_method": "PLAINTEXT",
                  "oauth_timestamp": str(int(time.time())), "oauth_version": "1.0", **oauth}
        headers = {"Authorization": "OAuth " + ", ".join(f'{k}="{quote(v)}"' for k, v in params.items()),
                   "User-Agent": DISCOGS_AGENT, "Content-Type": "application/x-www-form-urlencoded"}
        req = urllib.request.Request(url, method=method, headers=headers, data=b"" if method == "POST" else None)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode()
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:
                time.sleep(60)  # se pasó del límite por minuto: esperar a que se renueve
                continue
            if e.code == 401:
                raise HTTPException(400, "Discogs no aceptó la conexión. Desconectá y volvé a conectar tu cuenta.")
            raise HTTPException(502, f"Discogs respondió con un error ({e.code}). Probá de nuevo en un rato.")
        except urllib.error.URLError:
            raise HTTPException(502, "No se pudo conectar con Discogs. Probá de nuevo en un rato.")


# --- conexión ---

def start(t, callback):
    """Pide un token temporal y devuelve la página de Discogs donde la disquería autoriza a Bateas."""
    body = dict(urllib.parse.parse_qsl(_call("GET", f"{DISCOGS_API}/oauth/request_token", oauth_callback=callback)))
    set_settings(t, discogs_req_token=body["oauth_token"], discogs_req_secret=body["oauth_token_secret"])
    return f"{DISCOGS_AUTHORIZE}?oauth_token={quote(body['oauth_token'])}"


def finish(t, token, verifier):
    # el token tiene que ser el que pidió el admin de esta disquería: la vuelta no trae cookies
    if not same(get_setting(t, "discogs_req_token", "").encode(), token.encode()):
        raise HTTPException(400, "La conexión con Discogs venció. Volvé a intentarlo desde el admin.")
    body = dict(urllib.parse.parse_qsl(_call("POST", f"{DISCOGS_API}/oauth/access_token", get_setting(t, "discogs_req_secret", ""),
                                             oauth_token=token, oauth_verifier=verifier)))
    access, secret = body["oauth_token"], body["oauth_token_secret"]
    user = json.loads(_call("GET", f"{DISCOGS_API}/oauth/identity", secret, oauth_token=access))["username"]
    set_settings(t, discogs_token=access, discogs_secret=secret, discogs_user=user, discogs_req_token="", discogs_req_secret="")
    return user


def disconnect(t):
    # el catálogo importado queda; solo se olvida el acceso a la cuenta
    set_settings(t, discogs_token="", discogs_secret="", discogs_user="", discogs_job="")


def user(t):
    return get_setting(t, "discogs_user", "")


# --- importación ---

def job(t):
    return json.loads(get_setting(t, "discogs_job") or "{}")


def _set_job(t, **values):
    set_settings(t, discogs_job=json.dumps({**values, "at": now()}, ensure_ascii=False))


def running(t):
    j = job(t)
    return j.get("state") == "running" and datetime.fromisoformat(j["at"]) > datetime.now(timezone.utc) - STALE


def status(t):
    # lo que ve el admin; nunca los tokens
    return {"enabled": enabled(), "user": user(t), "job": job(t), "running": running(t)}


def listing_row(n, listing):
    """Un aviso del inventario -> fila del catálogo, igual que una fila del Excel."""
    rel = listing.get("release") or {}
    media, *more = [p.strip() for p in (rel.get("format") or "").split(",") if p.strip()] or [""]
    price, amount = listing.get("price") or {}, ""
    if price.get("value") is not None:
        value = float(price["value"])
        amount = str(int(value) if value.is_integer() else value)  # 25000.0 -> "25000": el front le pone el $
        if price.get("currency", "ARS") != "ARS":
            amount = f"{price['currency']} {amount}"
    rec = {"artist": rel.get("artist", ""), "title": rel.get("title", ""), "label": rel.get("label", ""), "media": media,
           "description": " · ".join(filter(None, [", ".join(more), rel.get("catalog_number", ""), listing.get("comments", "")])),
           "price": amount}
    own = {"Año": str(rel.get("year") or ""), "Estado": listing.get("condition", ""), "Tapa": listing.get("sleeve_condition", "")}
    own = {k: v for k, v in own.items() if v}
    # clave estable para las secciones: la edición (release) + el estado; "v2:" para que la migración no la toque
    key = "v2:discogs:" + "|".join(catalog.norm(x) for x in (rel.get("id"), listing.get("condition"), listing.get("sleeve_condition")))
    return (n, *(rec.get(f, "") for f in FIELDS), json.dumps(own, ensure_ascii=False) if own else "", key)


def begin(t):
    if not user(t):
        raise HTTPException(400, "Primero conectá tu cuenta de Discogs.")
    if running(t):
        raise HTTPException(409, "Ya hay una importación en curso. Esperá a que termine.")
    _set_job(t, state="running", done=0, total=None)


def import_inventory(t):
    """Corre en segundo plano: baja el inventario a la venta página por página y reemplaza el catálogo."""
    name, token, secret = user(t), get_setting(t, "discogs_token", ""), get_setting(t, "discogs_secret", "")
    rows, page, pages = [], 1, 1
    try:
        while page <= pages:
            data = json.loads(_call("GET", f"{DISCOGS_API}/users/{quote(name)}/inventory?status=For%20Sale"
                                           f"&sort=artist&per_page={DISCOGS_PAGE}&page={page}", secret, oauth_token=token))
            pages = data["pagination"]["pages"]
            rows += [listing_row(len(rows) + i + 1, item) for i, item in enumerate(data["listings"])]
            _set_job(t, state="running", done=len(rows), total=data["pagination"]["items"])
            page += 1
            if page <= pages:
                time.sleep(1)  # ponytail: 1 pedido por segundo queda bajo el límite de 60/min; un 429 igual se reintenta
        if not rows:
            raise HTTPException(400, "Tu inventario de Discogs no tiene discos a la venta.")
        catalog.save(t, rows)
        set_settings(t, filename=f"Discogs · @{name}", uploaded_at=now(), custom_columns=json.dumps(COLUMNS, ensure_ascii=False))
        _set_job(t, state="done", done=len(rows), total=len(rows), sections_missing=sections.missing_after_upload(t))
    except HTTPException as e:
        _set_job(t, state="error", message=e.detail)
    except Exception:
        _set_job(t, state="error", message="Algo falló al importar desde Discogs. Probá de nuevo.")
        raise  # queda en el log del servidor
