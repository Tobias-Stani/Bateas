"""Imágenes de la disquería (banners): se valida el contenido, no la extensión."""
import secrets

from fastapi import HTTPException

from ..config import FILE_NAME, MAX_IMAGE_BYTES
from ..storage import files_dir


def _kind(data):
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def save(t, upload):
    data = upload.file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(400, "La imagen es demasiado pesada (máximo 3 MB).")
    ext = _kind(data)
    if not ext:
        raise HTTPException(400, "La imagen tiene que ser JPG, PNG o WebP.")
    folder = files_dir(t["slug"])
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{secrets.token_urlsafe(18)}.{ext}"  # nombre al azar: nunca se pisa, se puede cachear para siempre
    (folder / name).write_bytes(data)
    return name


def path(t, name):
    """Ruta de una imagen de la disquería, o None si el nombre no es válido o no existe."""
    if not FILE_NAME.fullmatch(name or ""):
        return None
    file = files_dir(t["slug"]) / name
    return file if file.exists() else None


def remove(t, name):
    if name and FILE_NAME.fullmatch(name):
        (files_dir(t["slug"]) / name).unlink(missing_ok=True)


def url(t, name):
    return f"/api/t/{t['slug']}/files/{name}"
