"""Configuración: variables de entorno, límites y textos fijos. Nada de lógica."""
import os
import re
from pathlib import Path

# --- entorno ---
# multitenant por ruta: /{slug} es la tienda, /{slug}/admin su panel y /super el del super administrador
DATA = Path(os.environ.get("DATA_DIR", "data"))
TENANTS = DATA / "tenants"
REGISTRY = DATA / "registry.db"
SUPER_PASSWORD = os.environ.get("SUPER_PASSWORD", "")  # vacío = panel de super admin deshabilitado
SECRET_KEY = os.environ.get("SECRET_KEY", "")  # vacío = se genera una y queda en el volumen
STATIC_DIR = os.environ.get("STATIC_DIR", "")  # producción: el backend también sirve el front
# app registrada en discogs.com/settings/developers; vacías = sin conexión con Discogs
DISCOGS_KEY = os.environ.get("DISCOGS_KEY", "")
DISCOGS_SECRET = os.environ.get("DISCOGS_SECRET", "")
# app de Mercado Pago (Tus integraciones); vacías = sin pagos online
MP_CLIENT_ID = os.environ.get("MP_CLIENT_ID", "")
MP_CLIENT_SECRET = os.environ.get("MP_CLIENT_SECRET", "")
MP_FEE_PERCENT = float(os.environ.get("MP_FEE_PERCENT", "0"))  # comisión de Bateas sobre cada venta, en %
MP_TEST = os.environ.get("MP_TEST", "") == "1"  # 1 = cuentas de prueba de Mercado Pago
# solo desarrollo: un Access Token de prueba que usan todas las disquerías, sin OAuth (y sin comisión)
MP_ACCESS_TOKEN = os.environ.get("MP_ACCESS_TOKEN", "")
# "Continuar con Google" (Google Cloud → proyecto Bateas → Clientes); vacío = sin registro con Google
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")

TENANTS.mkdir(parents=True, exist_ok=True)

# --- sesiones ---
MONTH = 60 * 60 * 24 * 30

# --- disquerías ---
SLUG = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])")
RESERVED = {"api", "super", "admin", "static", "assets", "www", "t", "cuenta", "registro", "entrar", "login", "views"}
STATUSES = {"active", "suspended", "cancelled"}
COLOR = re.compile(r"#[0-9a-fA-F]{6}")

# marca por defecto de cada disquería nueva; el super admin la cambia
DEFAULT_LOGO, DEFAULT_ACCENT, DEFAULT_HIGHLIGHT = "/assets/img/logo.svg", "#03a0c4", "#f8b318"

# plantillas del mensaje de pedido; el admin de cada disquería las cambia
MESSAGE = "Hola! Quiero cotizar estos discos:\n\n{discos}"
MESSAGE_LINE = "#{id} - {artist} – {title} ({label}) [{media} {description}]"

# --- catálogo ---
PAGE_SIZE = 50

# campos de cada disco -> palabras con las que aparecen en los encabezados de los Excel (normalizadas)
FIELDS = {
    "artist": ["artista", "artist", "interprete", "banda", "grupo", "autor"],
    "title": ["titulo", "title", "album", "disco", "obra"],
    "label": ["sello", "label", "discografica"],
    "media": ["formato", "format", "medium", "media", "soporte"],
    "description": ["descripcion", "description", "detalle", "detalles", "notas", "observaciones"],
    "genre": ["genero", "genre", "estilo", "style"],
    "price": ["precio", "price", "valor", "importe", "pvp"],
    "origin": ["origen", "origin", "pais", "country", "procedencia"],
    "barcode": ["barcode", "codigo de barras", "cod barras", "ean", "upc"],
}
# columnas sin campo fijo: propia de la disquería (se guarda con su nombre), a la descripción, o se descarta
CUSTOM, EXTRA, IGNORE = "custom", "extra", "ignore"
KINDS = {CUSTOM, EXTRA, IGNORE}
HEADER_SCAN = 15  # el encabezado puede venir debajo de un logo o un título

# --- Discogs ---
DISCOGS_API = "https://api.discogs.com"
DISCOGS_AUTHORIZE = "https://www.discogs.com/oauth/authorize"
DISCOGS_AGENT = "Bateas/1.0 +https://bateas-production.up.railway.app"  # Discogs exige un User-Agent propio
DISCOGS_PAGE = 100  # el máximo que deja la API

# --- Mercado Pago ---
MP_API = "https://api.mercadopago.com"
MP_AUTHORIZE = "https://auth.mercadopago.com/authorization"
MP_CURRENCY = "ARS"  # solo se cobran online los discos con precio en pesos
MAX_ORDER = 100  # discos por pago

# --- cuentas ---
STORES_PER_ACCOUNT = 1  # tiendas que puede crear cada cuenta por su cuenta (el super admin no tiene límite)

# --- planes ---
PLANS = {"free", "premium"}
PREMIUM_PRICE = 11999  # por mes, en pesos: lo muestran la landing y el admin
FREE_LIMITS = {"discs": 50, "banners": 1, "sections": 1}  # Premium: los máximos generales de abajo

# --- portada ---
MAX_SECTIONS, MAX_SECTION_ITEMS = 20, 60
MAX_BANNER_GROUPS, MAX_BANNERS = 6, 8  # bloques de banners por disquería, imágenes por bloque
MAX_IMAGE_BYTES = 3 * 1024 * 1024  # el navegador la achica antes de subirla
IMAGE_TYPES = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
FILE_NAME = re.compile(r"[A-Za-z0-9_-]{16,40}\.(jpg|png|webp)")

# --- textos que ve el cliente ---
CLOSED = "La lista de este mes ya cerró. Esperá la próxima."
SUSPENDED = "Esta tienda está suspendida por el momento."
GONE = "Esta tienda ya no está disponible."
