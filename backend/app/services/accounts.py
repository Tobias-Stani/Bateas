"""Cuentas de los dueños de disquerías: inician sesión con Google y se crean su tienda."""
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from fastapi import HTTPException

from ..config import GOOGLE_CLIENT_ID, STORES_PER_ACCOUNT
from ..db import now, registry
from ..security import same, sign

GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


def enabled():
    return bool(GOOGLE_CLIENT_ID)


def verify_google(credential):
    """Valida con Google el comprobante que devolvió el botón: que sea de Google, para Bateas, vigente y con el mail verificado.
    ponytail: tokeninfo es un pedido a Google por cada ingreso; verificar la firma localmente (con sus claves públicas) si crece mucho."""
    try:
        with urllib.request.urlopen("https://oauth2.googleapis.com/tokeninfo?" + urllib.parse.urlencode({"id_token": credential}), timeout=10) as r:
            claims = json.load(r)
    except urllib.error.HTTPError:
        raise HTTPException(401, "Google no validó el inicio de sesión. Probá de nuevo.")
    except urllib.error.URLError:
        raise HTTPException(502, "No se pudo conectar con Google. Probá de nuevo en un rato.")
    if (claims.get("aud") != GOOGLE_CLIENT_ID or claims.get("iss") not in GOOGLE_ISSUERS
            or int(claims.get("exp", 0)) < datetime.now(timezone.utc).timestamp()):
        raise HTTPException(401, "Google no validó el inicio de sesión. Probá de nuevo.")
    if claims.get("email_verified") not in ("true", True):
        raise HTTPException(403, "Tu mail de Google no está verificado. Verificalo en Google y volvé a intentar.")
    return claims


def sign_in(claims):
    """Crea la cuenta la primera vez; las siguientes actualiza nombre, foto y último ingreso. Devuelve (cuenta, es_nueva)."""
    con = registry()
    with con:
        row = con.execute("SELECT * FROM accounts WHERE google_sub = ?", (claims["sub"],)).fetchone()
        if row and row["status"] != "active":
            con.close()
            raise HTTPException(403, "Esta cuenta está bloqueada. Escribinos si creés que es un error.")
        if row:
            con.execute("UPDATE accounts SET email = ?, name = ?, picture = ?, last_login_at = ? WHERE id = ?",
                        (claims["email"], claims.get("name", ""), claims.get("picture", ""), now(), row["id"]))
        else:
            con.execute("INSERT INTO accounts (google_sub, email, name, picture, created_at, last_login_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (claims["sub"], claims["email"], claims.get("name", ""), claims.get("picture", ""), now(), now()))
    account = dict(con.execute("SELECT * FROM accounts WHERE google_sub = ?", (claims["sub"],)).fetchone())
    con.close()
    return account, row is None


def find(account_id):
    con = registry()
    row = con.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
    con.close()
    return dict(row) if row else None


def from_cookie(value):
    """La cuenta de la cookie, si la firma es válida y la cuenta sigue activa."""
    account_id, _, signature = (value or "").partition(".")
    account = find(int(account_id)) if account_id.isdigit() else None
    if not account or account["status"] != "active":
        return None
    return account if same(signature, sign(f"account:{account['id']}:{account['google_sub']}")) else None


def stores(account_id):
    con = registry()
    rows = [dict(r) for r in con.execute("SELECT * FROM tenants WHERE owner_id = ? ORDER BY created_at", (account_id,))]
    con.close()
    return rows


def check_can_create(account):
    if len(stores(account["id"])) >= STORES_PER_ACCOUNT:
        raise HTTPException(409, "Ya tenés tu tienda. Si necesitás otra, escribinos." if STORES_PER_ACCOUNT == 1
                            else f"Podés tener hasta {STORES_PER_ACCOUNT} tiendas. Si necesitás más, escribinos.")


def view(account):
    # lo que ve el dueño de su cuenta: sin el id de Google
    return {"id": account["id"], "email": account["email"], "name": account["name"], "picture": account["picture"],
            "stores": [{"slug": t["slug"], "name": t["name"], "status": t["status"]} for t in stores(account["id"])]}


def all_accounts():
    con = registry()
    rows = [dict(r) for r in con.execute("""SELECT a.id, a.email, a.name, a.status, a.created_at, a.last_login_at,
                                            GROUP_CONCAT(t.slug) stores FROM accounts a LEFT JOIN tenants t ON t.owner_id = a.id
                                            GROUP BY a.id ORDER BY a.id DESC""")]
    con.close()
    return rows
