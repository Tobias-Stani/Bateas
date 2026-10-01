"""Arma la aplicación: rutas de la API y, en producción, el front."""
from fastapi import FastAPI

from .config import STATIC_DIR
from .db import init_registry
from .routers import admin, catalog, discogs, home, sections, store, superadmin
from .static import Pages

init_registry()

app = FastAPI(title="Catálogo de discos")

for module in (store, admin, catalog, discogs, sections, home, superadmin):
    app.include_router(module.router)

# va al final: es el comodín que atiende todo lo que no es /api
if STATIC_DIR:
    app.mount("/", Pages(directory=STATIC_DIR))
