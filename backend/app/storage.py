"""Dónde vive en disco cada cosa de una disquería. Un solo lugar para las rutas de archivos."""
import shutil

from .config import TENANTS


def db_path(slug):
    return TENANTS / f"{slug}.db"


def files_dir(slug):
    # imágenes de los banners
    return TENANTS / slug


def pending_path(slug):
    # el Excel queda acá entre la vista previa y la confirmación
    return TENANTS / f"{slug}.upload.xlsx"


def remove_tenant_storage(slug):
    db_path(slug).unlink(missing_ok=True)
    pending_path(slug).unlink(missing_ok=True)
    shutil.rmtree(files_dir(slug), ignore_errors=True)
