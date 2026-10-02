"""Validaciones reutilizables: devuelven el valor limpio o cortan con un 400 y un mensaje para la persona."""
import re
from datetime import datetime, timezone

from fastapi import HTTPException

from .config import COLOR, PLANS, RESERVED, SLUG


def fail(message):
    raise HTTPException(400, message)


def digits(value):
    return "".join(c for c in value if c.isdigit())


def text(value, low, high, message):
    clean = value.strip()
    if not low <= len(clean) <= high:
        fail(message)
    return clean


def tenant_name(value):
    return text(value, 2, 80, "El nombre tiene que tener entre 2 y 80 caracteres.")


def slug(value):
    clean = value.strip().lower()
    if not SLUG.fullmatch(clean) or clean in RESERVED:
        fail("La dirección solo puede tener letras minúsculas, números y guiones (2 a 40), sin guion al principio ni al final.")
    return clean


def client_code(value):
    return text(value, 4, 64, "El código tiene que tener entre 4 y 64 caracteres.")


def admin_password(value):
    if len(value) < 6:
        fail("La contraseña del admin tiene que tener al menos 6 caracteres.")
    return value


def whatsapp(value):
    # se guardan solo los dígitos: acepta "+54 9 11 1234-5678"
    number = digits(value)
    if not 8 <= len(number) <= 15:
        fail("El número tiene que tener código de país y área, por ejemplo 54 9 11 1234 5678.")
    return number


def color(value):
    if not COLOR.fullmatch(value):
        fail("Los colores tienen que ser hexadecimales, por ejemplo #03a0c4.")
    return value


def logo(value):
    clean = value.strip()
    local = clean.startswith("/") and not clean.startswith("//")  # "//host/x" es otro sitio, no una ruta
    if clean and not ((local or clean.startswith("https://")) and len(clean) <= 500):
        fail("El logo tiene que ser una ruta (/assets/img/logo.svg) o una URL https.")
    return clean or None  # vacío = logo por defecto


def closing_date(value):
    # fecha ISO con zona (el navegador manda UTC), o "" para quitar el cierre
    clean = value.strip()
    if not clean:
        return ""
    try:
        when = datetime.fromisoformat(clean)
    except ValueError:
        fail("La fecha no es válida.")
    if when.tzinfo is None:
        fail("La fecha tiene que incluir la zona horaria.")
    return when.astimezone(timezone.utc).isoformat(timespec="minutes")


EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
INSTAGRAM = re.compile(r"[A-Za-z0-9._]{1,30}")


def contact(c):
    # todo opcional: lo vacío no se muestra en la tienda
    out = {
        "address": text(c.address, 0, 150, "La dirección puede tener hasta 150 caracteres."),
        "city": text(c.city, 0, 80, "La localidad puede tener hasta 80 caracteres."),
        "phone": text(c.phone, 0, 40, "El teléfono puede tener hasta 40 caracteres."),
        "email": text(c.email, 0, 120, "El mail puede tener hasta 120 caracteres."),
        "hours": text(c.hours, 0, 150, "Los horarios pueden tener hasta 150 caracteres."),
        # acepta "@surco", "surco" o el link del perfil; se guarda solo el usuario
        "instagram": c.instagram.strip().rstrip("/").rsplit("/", 1)[-1].lstrip("@"),
    }
    if out["phone"] and not 6 <= len(digits(out["phone"])) <= 15:
        fail("El teléfono no parece válido. Escribilo con código de área, por ejemplo 11 4567-8901.")
    if out["email"] and not EMAIL.fullmatch(out["email"]):
        fail("El mail no parece válido, por ejemplo hola@tudisqueria.com.")
    if out["instagram"] and not INSTAGRAM.fullmatch(out["instagram"]):
        fail("El usuario de Instagram solo puede tener letras, números, puntos y guiones bajos.")
    return out


def message(template, line):
    template, line = template.strip(), line.strip()
    if "{discos}" not in template:
        fail("El mensaje tiene que incluir {discos}, que es donde va la lista.")
    if not line:
        fail("La línea por disco no puede quedar vacía.")
    if len(template) > 2000 or len(line) > 300:
        fail("El mensaje es demasiado largo.")
    return template, line


def plan(value):
    if value not in PLANS:
        fail("El plan tiene que ser Gratis o Premium.")
    return value


def premium_until(value):
    # vacío = Premium sin vencimiento; si no, fecha ISO con zona (el navegador manda UTC)
    return closing_date(value) or None
