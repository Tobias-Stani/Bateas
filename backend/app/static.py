"""Producción (Railway): un solo contenedor sirve también el front. En local lo hace nginx con las mismas reglas."""
import re
from pathlib import Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

REVALIDATE = ("text/html", "text/javascript", "application/javascript", "text/css")


class Pages(StaticFiles):
    async def get_response(self, path, scope):
        response = await self.page(path, scope)
        # HTML, JS y CSS se revalidan siempre (304 si no cambiaron): sin esto el navegador
        # puede mezclar un index.html nuevo con un .js viejo después de cada deploy
        if response.media_type and response.media_type.split(";")[0] in REVALIDATE:
            response.headers["Cache-Control"] = "no-cache"
        return response

    async def page(self, path, scope):
        if path in ("", "."):
            return FileResponse(Path(self.directory) / "home.html")
        if path.rstrip("/") == "super":
            return FileResponse(Path(self.directory) / "super.html")
        if m := re.fullmatch(r"[a-z0-9-]+(/admin)?/?", path):
            return FileResponse(Path(self.directory) / ("admin.html" if m[1] else "index.html"))
        return await super().get_response(path, scope)
