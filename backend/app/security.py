"""Contraseñas y sesiones.

Cada firma incluye el slug: una cookie de una disquería no abre otra.
La del admin incluye el hash de su contraseña: resetearla cierra las sesiones abiertas.
"""
import hashlib
import hmac
import secrets

from .config import DATA, MONTH, SECRET_KEY, SUPER_PASSWORD


def _secret_key():
    # firma de cookies; en Railway se genera una vez y queda en el volumen
    if SECRET_KEY:
        return SECRET_KEY
    f = DATA / "secret.key"
    if not f.exists():
        f.write_text(secrets.token_hex(32))
    return f.read_text().strip()


KEY = _secret_key()


def hash_password(password):
    salt = secrets.token_bytes(16)
    return salt.hex() + "$" + hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000).hex()


def check_password(password, stored):
    salt, digest = stored.split("$")
    return hmac.compare_digest(hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000).hex(), digest)


def sign(value):
    # la cookie guarda la firma, no el secreto
    return hmac.new(KEY.encode(), value.encode(), hashlib.sha256).hexdigest()


def same(a, b):
    return bool(a) and hmac.compare_digest(a, b)


def super_token():
    return sign("super:" + SUPER_PASSWORD)


def admin_token(t):
    return sign(f"admin:{t['slug']}:{t['admin_hash']}")


def client_token(t, code):
    return sign(f"client:{t['slug']}:{code}")


def account_token(account):
    # incluye el id de Google: si se borra y recrea la cuenta, la cookie vieja no sirve
    signature = sign(f"account:{account['id']}:{account['google_sub']}")
    return f"{account['id']}.{signature}"


def set_account_cookie(response, account):
    # path /api: el dueño entra al admin de su disquería con esta cookie, sin contraseña
    response.set_cookie("account", account_token(account), httponly=True, samesite="lax", max_age=MONTH, path="/api")


def clear_account_cookie(response):
    response.delete_cookie("account", path="/api")


def set_tenant_cookie(response, t, name, value, samesite):
    # path de la disquería: el navegador no la manda a las APIs de otras
    response.set_cookie(name, value, httponly=True, samesite=samesite, max_age=MONTH, path=f"/api/t/{t['slug']}")


def clear_tenant_cookie(response, slug, name):
    response.delete_cookie(name, path=f"/api/t/{slug}")


def set_super_cookie(response):
    # path /api: el super admin también opera las APIs de cada disquería
    response.set_cookie("super", super_token(), httponly=True, samesite="strict", max_age=MONTH, path="/api")


def clear_super_cookie(response):
    response.delete_cookie("super", path="/api")
