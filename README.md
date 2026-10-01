# Bateas

Catálogo online de discos, marca blanca y multitenant. Cada disquería tiene su tienda y su admin: sube el Excel mensual, sus clientes entran con un código, arman el pedido y lo mandan por WhatsApp. Un super admin crea y administra las disquerías.

## Rutas

| Ruta | Qué es |
|---|---|
| `/super` | Panel de super admin: alta, marca, contraseñas, suspender, cancelar y eliminar disquerías |
| `/{slug}` | Tienda de una disquería |
| `/{slug}/admin` | Admin de esa disquería: catálogo, código de acceso, fecha de cierre, WhatsApp y mensaje del pedido |

API: `/api/super/...` y `/api/t/{slug}/...`.

## Levantar en local

```
docker-compose up -d --build
```

Sin nada en `.env`, la contraseña de `/super` es `super`. Se cambia con `SUPER_PASSWORD` en `.env`. `PORT` define el puerto (default 8000).

## Railway

Se despliega con el `Dockerfile` de la raíz, en un solo servicio.

- Montar un **volumen en `/data`**: ahí viven las bases y la clave de firma.
- Definir **`SUPER_PASSWORD`**. Si falta, el panel `/super` queda deshabilitado.
- Opcional: `SECRET_KEY` para firmar cookies. Si falta, se genera una y se guarda en `/data/secret.key`.

## Datos

- `/data/registry.db`: las disquerías (nombre, estado, marca, notas y el hash de la contraseña del admin).
- `/data/tenants/{slug}.db`: una base por disquería, con su catálogo y su configuración. Ninguna disquería puede leer los datos de otra.

Estados: **activa** → **suspendida** (reversible; la tienda y el admin muestran "suspendida") → **cancelada** (la tienda deja de estar disponible y los datos se conservan). Solo una cancelada se puede eliminar definitivamente. El super admin entra a cualquier admin, en cualquier estado.

## Estructura

```
backend/
├── app/
│   ├── main.py            arma la app: rutas + front
│   ├── config.py          variables de entorno, límites y textos fijos
│   ├── db.py              conexiones SQLite (registro y base de cada disquería) y settings
│   ├── storage.py         rutas de los archivos de cada disquería en el disco
│   ├── security.py        contraseñas, firma de cookies, tokens
│   ├── dependencies.py    quién puede entrar a qué (super, admin, cliente)
│   ├── schemas.py         cuerpos de los pedidos a la API
│   ├── validators.py      validaciones reutilizables
│   ├── static.py          sirve el front en producción
│   ├── services/          lógica de negocio, sin HTTP
│   │   ├── tenants.py     disquerías y su configuración
│   │   ├── catalog.py     Excel: detectar columnas, leer, guardar, buscar
│   │   ├── sections.py    secciones y clave estable de cada edición
│   │   ├── banners.py     bloques de banners
│   │   ├── layout.py      orden de la portada
│   │   ├── home.py        armado de la portada
│   │   └── images.py      imágenes subidas
│   └── routers/           solo HTTP: reciben, validan y llaman a services
│       ├── store.py       tienda pública
│       ├── admin.py       admin de la disquería: acceso y configuración
│       ├── catalog.py     carga del Excel
│       ├── sections.py    secciones
│       ├── home.py        portada y banners
│       └── superadmin.py  panel /super
└── tests/                 la API vista desde afuera + el parser del Excel
frontend/
├── nginx.conf             mismas rutas que app/static.py, para desarrollo
└── public/                páginas, estilos y scripts del navegador
```

Dependencias en una sola dirección: `routers → services → db/storage/config`. Los services no saben de HTTP salvo para cortar con un error claro.

## Tests

```
cd backend
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest tests
```

Las tapas se buscan en Deezer desde el navegador del cliente; no se guardan en el servidor.
