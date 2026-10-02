# Bateas

**Por melómanos, para melómanos.** Bateas le da a cada disquería su propia tienda online de preventa: sube el Excel que le manda el distribuidor, sus clientes recorren el catálogo (con tapas, fragmentos para escuchar, secciones y banners) y el pedido le llega ordenado por WhatsApp. Es marca blanca y multitenant: una sola instalación, muchas disquerías, cada una con su marca y su link.

- **Producción:** https://bateas-production.up.railway.app
- **Stack:** FastAPI + SQLite (backend) · HTML/CSS/JS sin build (frontend) · Docker · Railway

---

## Arrancar en otra máquina

> Lo único que necesitás instalado es **Docker**. Python solo hace falta para correr los tests.

1. **Traé el código** a la máquina nueva (clonando el repo o copiando la carpeta).
2. **Creá un `.env`** en la raíz:
   ```
   PORT=8011
   SUPER_PASSWORD=una-clave-para-desarrollo
   ```
3. **Levantá todo:**
   ```
   docker compose up -d --build      # o docker-compose, según cómo esté instalado
   ```
4. **Abrí** http://localhost:8011 (la landing) y http://localhost:8011/super (entrás con tu `SUPER_PASSWORD`).
5. **Creá una disquería** desde `/super` y entrá a su admin para subir un Excel.

✅ Funciona si la landing carga, `/super` te deja entrar y la disquería nueva muestra su tienda en `/{slug}`.

> ⚠️ **Los datos no viajan con el código.** En local viven en el volumen de Docker `bateas_data`, no en la carpeta. Una máquina nueva arranca sin disquerías. Los datos reales están en el volumen de Railway.

---

## Qué es cada cosa

### Quién usa qué

| Quién | Dónde | Qué hace |
|---|---|---|
| **Vos (super admin)** | `/super` | Crea disquerías, define su marca, las suspende, cancela o elimina. Entra a cualquier admin sin contraseña. |
| **La disquería (admin)** | `/{slug}/admin` | Sube el Excel, arma la portada (banners y secciones), configura código de acceso, fecha de cierre, WhatsApp y el mensaje del pedido. |
| **El cliente** | `/{slug}` | Busca, filtra, escucha, arma el pedido y lo manda por WhatsApp. |
| **Cualquiera** | `/` | La landing de Bateas. |

### Vocabulario del proyecto

| Término | Qué significa |
|---|---|
| **Disquería / tenant** | Cada tienda. Se identifica por su `slug` (la dirección: `/chopp-and-rock`). |
| **Catálogo** | Los discos del Excel. El `id` de cada disco es **el número de fila del Excel**, así la disquería lo encuentra directo. |
| **Columna propia** | Una columna del Excel que no es un campo conocido (ej. "Insert"). Se guarda con su nombre y se puede usar en el mensaje como `{insert}`. |
| **Clave estable** | Identifica una **edición** entre un Excel y el siguiente (artista + título + formato + sello + descripción + código de barras). Sin esto, las secciones se romperían cada mes porque las filas cambian. |
| **Sección** | Un carrusel armado a mano por la disquería ("Más vendidos"). |
| **Bloque de banners** | Un slider de imágenes. Puede haber varios en distintos lugares de la portada. |
| **Portada** | El orden de los bloques (banners, secciones y catálogo) que elige la disquería. |
| **Estados** | `active` → `suspended` (reversible) → `cancelled` (la tienda deja de verse; solo una cancelada se puede eliminar). |

---

## Mapa del proyecto

```
bateas/
├── Dockerfile               imagen de producción (Railway): backend + front en un solo servicio
├── docker-compose.yml       desarrollo: backend con --reload + nginx
├── .dockerignore            qué no entra a la imagen (.env, tests…)
├── backend/
│   ├── app/                 la aplicación (ver "Backend")
│   ├── tests/               tests de la API y del lector de Excel
│   ├── requirements.txt     dependencias con versión fija
│   └── requirements-dev.txt pytest y httpx, solo para desarrollo
└── frontend/
    ├── nginx.conf           desarrollo: mismas rutas que backend/app/static.py
    └── public/              lo que ve el navegador (ver "Frontend")
        ├── assets/          lo compartido: css/base.css, js/ (common, brand, covers, player), img/
        └── views/           una carpeta por pantalla, con su index.html, su CSS y su JS
```

---

## Backend

### Estructura

```
backend/app/
├── main.py            arma la app: incluye las rutas y monta el front
├── config.py          variables de entorno, límites y textos fijos
├── db.py              conexiones SQLite (registro + una base por disquería) y settings
├── storage.py         rutas de los archivos de cada disquería en el disco
├── security.py        contraseñas, firma de cookies, tokens
├── dependencies.py    quién entra a qué: is_super, tenant, require_admin, require_client
├── schemas.py         cuerpos de los pedidos (Pydantic)
├── validators.py      validaciones reutilizables, con mensajes para la persona
├── static.py          sirve el front en producción, con las reglas de caché
├── services/          lógica de negocio, sin HTTP
│   ├── tenants.py     disquerías y su configuración
│   ├── catalog.py     Excel: detectar columnas, leer, guardar, buscar
│   ├── sections.py    secciones y migración de claves
│   ├── banners.py     bloques de banners y sus imágenes
│   ├── layout.py      el orden de la portada
│   ├── home.py        arma la portada (pública y del admin)
│   └── images.py      guardar, servir y borrar imágenes
└── routers/           solo HTTP: reciben, validan y llaman a services
    ├── store.py       tienda pública          /api/t/{slug}/...
    ├── admin.py       admin: acceso y config  /api/t/{slug}/admin/...
    ├── catalog.py     carga del Excel
    ├── sections.py    secciones
    ├── home.py        portada y banners
    └── superadmin.py  panel /super            /api/super/...
```

### Pautas

1. **Respetá las capas.** `routers → services → db / storage / config`. Un router no escribe SQL; un service no lee cookies ni arma respuestas HTTP (solo corta con `HTTPException` cuando algo no se puede hacer).
2. **Cada disquería tiene su propia base** (`/data/tenants/{slug}.db`). Nunca mezcles datos de dos disquerías en una consulta. Las cookies están firmadas con el slug y tienen `path=/api/t/{slug}`: no lo cambies.
3. **Los cambios de esquema se migran solos.** El patrón es `ensure_tables()` / `connect()` al abrir la base: crea lo que falta y migra lo viejo (ver `banners.py` y `sections.py`). No hay comandos de migración aparte; las bases de producción tienen que seguir andando.
4. **Los mensajes de error son para la persona, en castellano y con voseo**, diciendo qué pasó y cómo arreglarlo: `"El número tiene que tener código de país y área, por ejemplo 54 9 11 1234 5678."`
5. **Validá en `validators.py`** si la regla se usa en más de un lugar.
6. **Las dependencias van con versión fija** en `requirements.txt`. Si actualizás una, corré los tests antes de subir.
7. **Todo cambio de comportamiento lleva su test** en `backend/tests/`.

### Agregar un endpoint (receta)

1. La lógica va en el service que corresponda (o en uno nuevo en `services/`).
2. El cuerpo del pedido, si hace falta, en `schemas.py`.
3. La ruta en el router de su área, con la dependencia correcta: `require_super`, `require_admin`, `require_client` o `tenant`.
4. Si es un router nuevo, se agrega en la lista de `main.py`.
5. Un test en `tests/test_api.py` que lo use desde afuera.

---

## Frontend

### Pantallas

Cada pantalla vive en `frontend/public/views/<pantalla>/`: su `index.html`, su `<pantalla>.css` y su JS. Las URLs no cambian; `static.py` (producción) y `nginx.conf` (local) las mapean.

| Carpeta | Ruta | Qué es |
|---|---|---|
| `views/landing/` | `/` | Landing de Bateas: planes, demo, preguntas |
| `views/cuenta/` | `/cuenta` | Registro e ingreso con Google; crear la tienda |
| `views/super/` | `/super` | Panel del super admin: disquerías, cuentas, pagos, actividad |
| `views/tienda/` | `/{slug}` | Tienda de una disquería |
| `views/admin/` | `/{slug}/admin` | Admin de una disquería. El JS está en `views/admin/js/`, un archivo por bloque |

**Admin (`views/admin/js/`)**: se cargan en este orden y comparten variables globales (scripts clásicos, sin build). `panel.js` va primero (estado y apertura) e `inicio.js` último (arranque). En el medio, un archivo por bloque del panel: `ingreso`, `catalogo`, `configuracion`, `discogs`, `plan`, `mercadopago`, `contacto`, `mensaje`, `secciones`, `portada`. Para un bloque nuevo: su archivo en esa carpeta y su `<script>` en `views/admin/index.html`, antes de `inicio.js`.

| Compartido (`assets/`) | Para qué |
|---|---|
| `css/base.css` | Tokens de color y componentes compartidos (botones, campos, barra, paneles) |
| `js/common.js` | `api()` (fetch con errores), `esc()`, formatos de fecha y precio, armado del mensaje de WhatsApp |
| `js/brand.js` | Pide la marca de la disquería y la aplica (nombre, logo, colores, contacto). Si la tienda no existe o está suspendida, bloquea la página |
| `js/covers.js` | Busca las tapas en Deezer desde el navegador del cliente |
| `js/player.js` | Reproductor de fragmentos de 30 s de Deezer |
| `img/` | Logos de Bateas (`bateas.svg`) y de las tiendas sin logo propio (`logo.svg`) |

### Pautas

1. **Sin build ni frameworks.** HTML, CSS y JS directo: se edita y se ve con F5 (en local, `frontend/public` está montado en nginx).
2. **Toda llamada a la API pasa por `api()`.** Escribís `api("/api/discos")` y `common.js` la convierte en `/api/t/{slug}/discos` según la URL de la página. Así una misma página sirve para todas las disquerías.
3. **Todo texto que venga de datos va con `esc()`** antes de meterlo en `innerHTML`. Los Excels y los nombres los escribe gente; sin escapar, cualquiera puede inyectar HTML.
4. **Colores desde los tokens** (`var(--accent)`, `var(--highlight)`…). `brand.js` pisa `--accent` y `--highlight` con los de cada disquería: si escribís un color fijo, esa parte no se adapta a la marca.
5. **Pensá primero en el celular.** La mayoría de los clientes entra desde ahí. Probá a 390 px de ancho y que la página no se desplace hacia el costado.
6. **Textos en castellano rioplatense, con voseo** ("Subí el Excel", "Elegí"), igual que en el resto de la app.
7. **Las imágenes se achican en el navegador** antes de subirlas (`shrink()` en `views/admin/js/portada.js`): el servidor solo valida y guarda.
8. **No sumes dependencias externas** salvo que hagan un trabajo grande. Hoy solo se usa SweetAlert2 (CDN) y la fuente Archivo (Google Fonts).


---

## Tests

```
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest tests
```

Los tests prueban la API desde afuera, con una base temporal: no tocan tus datos. Si pasan, el comportamiento no cambió.

---

## Variables de entorno

| Variable | Dónde | Para qué |
|---|---|---|
| `SUPER_PASSWORD` | local y Railway | Contraseña de `/super`. Si falta, el panel queda deshabilitado (en local, compose usa `super` por defecto). |
| `PORT` | local (`.env`) y Railway (la pone sola) | Puerto donde escucha la app. |
| `DATA_DIR` | ya configurada | Dónde viven las bases e imágenes (`/data`). |
| `STATIC_DIR` | ya configurada en el `Dockerfile` | Producción: el backend también sirve el front. |
| `SECRET_KEY` | opcional | Firma de cookies. Si falta, se genera una y queda en `/data/secret.key`. |
| `GOOGLE_CLIENT_ID` | local (`.env`) y Railway | "Continuar con Google" en `/cuenta` (Google Cloud → proyecto Bateas → Clientes). No es secreto. Orígenes autorizados: `http://localhost:8011` y la URL de Railway. Sin ella, no hay registro. |
| `MP_CLIENT_ID` / `MP_CLIENT_SECRET` | local (`.env`) y Railway, opcionales | La app de Bateas en Mercado Pago (Tus integraciones). Sin ellas, no hay pagos online. URL de redirección a registrar: `https://bateas-production.up.railway.app/api/mercadopago/callback`. |
| `MP_FEE_PERCENT` | local y Railway | Comisión de Bateas sobre cada venta, en % (ej. `5`). Por defecto `0`. |
| `MP_TEST` | solo para probar | `1` = usa las cuentas de prueba de Mercado Pago (sandbox). |
| `MP_ACCESS_TOKEN` | solo desarrollo | Access Token de prueba de la app. Si no hay Client ID + Client Secret, todas las disquerías cobran con este token, sin OAuth y sin comisión. Nunca en producción. |
| `DISCOGS_KEY` / `DISCOGS_SECRET` | local (`.env`) y Railway, opcionales | La app de Bateas en discogs.com/settings/developers. Sin ellas, el admin no muestra la conexión con Discogs. |

---

## Tienda de demo

La landing enlaza a `/demo`: una disquería pública con 44 discos, dos secciones y banners. Como los datos viven en el volumen, se crea con un script que usa la API (si `/demo` ya existe, no toca nada):

```
# local
docker compose run --rm --no-deps -v ./demo:/demo backend python /demo/seed_demo.py

# producción (con la SUPER_PASSWORD de Railway)
docker compose run --rm --no-deps -v ./demo:/demo -e SUPER_PASSWORD=... backend python /demo/seed_demo.py https://bateas-production.up.railway.app
```

Para rehacerla: cancelarla y eliminarla desde `/super`, y volver a correr el script.

---

## Deploy en Railway

| Recurso | Valor |
|---|---|
| Proyecto | `bateas` |
| Servicio | `bateas` (se construye con el `Dockerfile` de la raíz) |
| Volumen | `bateas-volume`, montado en **`/data`** |
| Variables | `SUPER_PASSWORD` |
| Dirección | https://bateas-production.up.railway.app |

**Para publicar cambios:**

```
railway up --service bateas -m "qué cambió"
```

Antes de subir: tests en verde. Después: abrí la landing y `/super` para confirmar que arrancó.

> ⚠️ **El volumen es obligatorio.** En cada deploy Railway reemplaza el contenedor; todo lo que no esté en `/data` se pierde. **Borrar el volumen borra todas las disquerías**, sin vuelta atrás.

> ⚠️ **Una sola instancia.** Los datos están en SQLite y en archivos del volumen: no subas las réplicas. Para escalar habría que pasar a Postgres y guardar las imágenes en un bucket.

---

## Cosas que conviene saber

| Situación | Qué pasa / qué hacer |
|---|---|
| Después de actualizar, el navegador muestra errores raros | El HTML, el JS y el CSS se sirven con `Cache-Control: no-cache`, pero un navegador que tenía una versión anterior al arreglo puede necesitar **Ctrl + Shift + R** una vez. |
| Renombrar la carpeta del proyecto | No rompe nada: el `docker-compose.yml` fija `name: bateas`, así que contenedores y volumen no dependen del nombre de la carpeta. |
| `docker compose` no existe | Algunas máquinas tienen el binario suelto: usá `docker-compose`. |
| La CLI de Railway falla al crear un volumen | Pasale los IDs: `railway volume -s <service-id> -e <env-id> add --mount-path /data`. |
| Un disco aparece repetido en la búsqueda | Suele ser una edición distinta (otra descripción u otro código de barras). Son discos distintos a propósito. |
| Tapas o fragmentos que no aparecen | Dependen de que Deezer tenga el disco. Los vinilos raros a veces no están; para eso queda el link a YouTube. |

---

## Pendientes

- [ ] Poner el WhatsApp y el mail reales en la landing (`views/landing/index.html`, marcados con `TODO`).
- [ ] Inicializar git y subir el repo (hoy el proyecto no tiene historial de versiones).
- [x] Separar el JavaScript del admin en módulos (`views/admin/js/`).
- [ ] Backups periódicos del volumen de Railway.
- [x] Cobro con Mercado Pago, con comisión por venta (falta crear la app y probarlo con cuentas de prueba).
