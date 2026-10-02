"""Producción (Railway): un solo contenedor sirve también el front. En local lo hace nginx con las mismas reglas (frontend/nginx.conf).

El front vive en frontend/public: assets/ (lo compartido) y views/<pantalla>/ (HTML, CSS y JS de cada una).
"""
import re
from pathlib import Path

from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

REVALIDATE = ("text/html", "text/javascript", "application/javascript", "text/css")
# rutas de la app -> pantalla
VIEWS = {"": "landing", "super": "super", "cuenta": "cuenta"}
# ponytail: logos que pueden haber quedado guardados con la ruta de antes de assets/; borrar cuando ninguna disquería los use
LEGACY = {"logo.svg": "/assets/img/logo.svg", "bateas.svg": "/assets/img/bateas.svg"}


class Pages(StaticFiles):
    async def get_response(self, path, scope):
        response = await self.page(path, scope)
        # HTML, JS y CSS se revalidan siempre (304 si no cambiaron): sin esto el navegador
        # puede mezclar un index.html nuevo con un .js viejo después de cada deploy
        if response.media_type and response.media_type.split(";")[0] in REVALIDATE:
            response.headers["Cache-Control"] = "no-cache"
        return response

    def view(self, name):
        return FileResponse(Path(self.directory) / "views" / name / "index.html")

    async def page(self, path, scope):
        clean = "" if path in ("", ".") else path.rstrip("/")
        if clean in VIEWS:
            return self.view(VIEWS[clean])
        if clean in LEGACY:
            return RedirectResponse(LEGACY[clean], 301)
        if m := re.fullmatch(r"[a-z0-9-]+(/admin)?", clean):
            return self.view("admin" if m[1] else "tienda")
        return await super().get_response(path, scope)
