# InvenioRDM — Docker autocontenido

## Estructura

```
inveniordm/
├── Dockerfile.dev           # Dev — build autocontenido (Flask run, HTTP)
├── Dockerfile               # Prod — build autocontenido (uWSGI, sin Nginx)
├── docker-compose.dev.yml   # Dev — orquestación (app + servicios)
├── docker-compose.yml       # Prod — orquestación (web-ui + web-api + worker + scheduler + servicios)
├── .env.example             # Plantilla de variables
├── AGENTS.md                # Esta documentación
├── hello-world/             # Código fuente de la app InvenioRDM
│   ├── Dockerfile           # Dockerfile original (se mantiene como referencia)
│   ├── Pipfile / Pipfile.lock
│   ├── invenio.cfg
│   ├── site/
│   ├── assets/ / static/
│   ├── docker/uwsgi/
│   └── ...
```

## Concepto

Las imágenes son **autocontenidas**: todo el código de la app se copia dentro de la imagen en el build. No se montan volúmenes de código fuente. Para ver cambios, reconstruir la imagen.

## Entorno Dev — HTTP (puerto 5000)

**Dockerfile.dev:** `CMD ["invenio", "run", "--host", "0.0.0.0", "--port", "5000"]`

```bash
cp .env.example .env
docker compose -f docker-compose.dev.yml --env-file .env build --no-cache app
docker compose -f docker-compose.dev.yml --env-file .env up -d

# Inicializar (solo primera vez)
docker compose -f docker-compose.dev.yml exec app invenio db create
docker compose -f docker-compose.dev.yml exec app invenio db init
docker compose -f docker-compose.dev.yml exec app invenio index init
docker compose -f docker-compose.dev.yml exec app invenio files location create --default default-location /opt/invenio/var/instance/data

# Crear admin
docker compose -f docker-compose.dev.yml exec app invenio users create admin@example.com --password <PASSWORD> --active
docker compose -f docker-compose.dev.yml exec app invenio roles add admin@example.com admin
```

**Acceso:** http://localhost:5000

## Entorno Prod — uWSGI, sin Nginx (puerto 5000 / 5001)

**Dockerfile:** `CMD ["uwsgi", "/opt/invenio/var/instance/uwsgi_ui.ini"]`

| Servicio   | Entrypoint                        | Puerto expuesto |
|------------|-----------------------------------|-----------------|
| web-ui     | uwsgi uwsgi_ui.ini (CMD por defecto) | 5000 → 5000   |
| web-api    | uwsgi uwsgi_rest.ini              | 5001 → 5000    |
| worker     | celery worker                     | —               |
| scheduler  | celery beat                       | —               |

```bash
cp .env.example .env
# (Opcional) Configurar hostname para produccion:
# cp .env.prop .env.prod  # y editar INVENIO_HOSTNAME
docker compose -f docker-compose.yml --env-file .env build --no-cache
docker compose -f docker-compose.yml --env-file .env up -d

# Inicializar (solo primera vez)
docker compose -f docker-compose.yml exec web-api invenio db create
docker compose -f docker-compose.yml exec web-api invenio db init
docker compose -f docker-compose.yml exec web-api invenio index init
docker compose -f docker-compose.yml exec web-api invenio files location create --default default-location /opt/invenio/var/instance/data
```

**Acceso directo (sin proxy):**
- UI: http://localhost:5000  (o http://<IP>:5000 si usas 0.0.0.0)
- API: http://localhost:5001  (o http://<IP>:5001 si usas 0.0.0.0)

**Con proxy reverso (Apache, Caddy, etc.):** El proxy termina SSL y redirige a web-ui:5000 (UI) y web-api:5001 (API). Las rutas están configuradas en `/invenio`.

> **Configurar hostname:** Define `INVENIO_HOSTNAME` en `.env.prod` (ver `.env.prop`) y pásalo con `--env-file .env.prod` al levantar.

## Puertos

| Servicio   | Dev       | Prod              |
|------------|-----------|-------------------|
| App UI     | 5000      | 5000 (web-ui)     |
| App API    | —         | 5001 (web-api)    |
| PostgreSQL | 5432      | 5432              |
| Redis      | 6379      | 6379              |
| RabbitMQ   | 5672/15672| 5672/15672        |
| OpenSearch | 9200/9600 | 9200/9600         |

## Apache del servidor (proxy inverso)

### Estructura de archivos

```
/etc/apache2/
├── sites-available/
│   └── default-ssl.conf    # Unico archivo activo con todos los vhosts
├── ssl/
│   ├── discourse.test.pem
│   ├── discourse.test-key.pem
│   ├── localhost+2.pem
│   └── localhost+2-key.pem
└── ...
```

### default-ssl.conf — VirtualHosts definidos

El archivo tiene 3 VirtualHosts en este orden:

1. **`discourse.test`** — ProxyPass `/` → `127.0.0.1:8080` (Discourse). Atrapa TODAS las rutas.
2. **`localhost`** — ProxyPass `/invenio` → `127.0.0.1:5000`, `/invenio/api` → `127.0.0.1:5001`
3. **Catch-all (sin ServerName)** — ProxyPass `/biblioteca`, `/dspace`

### Problema conocido (resuelto)

Al acceder por IP (`https://172.24.0.98/invenio`), Apache siempre caía en el **primer** VirtualHost (`discourse.test`) porque el `Host` header no coincidía con ningún `ServerName`. Como ese vhost tenía un `ProxyPass /` genérico, las rutas `/invenio` nunca llegaban al vhost correcto.

**Solución:** El VirtualHost de Invenio (`localhost`) debe ser el **primero** en `default-ssl.conf`. Al no tener `ProxyPass /`, Apache solo responde rutas conocidas (`/invenio`, `/invenio/api`). Cuando se accede por hostname (`discourse.test`), Apache hace match por ServerName y usa el vhost correcto.

```
# ORDEN CORRECTO en default-ssl.conf:

# 1. Invenio (primero = default para accesos por IP)
<VirtualHost *:443>
    ServerName localhost
    # Sin ProxyPass / — solo rutas explicitas
    ProxyPass /invenio/api http://127.0.0.1:5001/invenio/api
    ProxyPassReverse /invenio/api http://127.0.0.1:5001/invenio/api
    ProxyPass /invenio http://127.0.0.1:5000/invenio
    ProxyPassReverse /invenio http://127.0.0.1:5000/invenio
</VirtualHost>

# 2. Discourse
<VirtualHost *:443>
    ServerName discourse.test
    ProxyPass / http://127.0.0.1:8080/
    ProxyPassReverse / http://127.0.0.1:8080/
</VirtualHost>

# 3. Catch-all (otros servicios)
<VirtualHost *:443>
    ProxyPass /biblioteca ...
    ProxyPass /dspace ...
</VirtualHost>
```

**Además**, se actualizó `invenio.prod.cfg` para incluir `INVENIO_HOSTNAME` en `TRUSTED_HOSTS`, y se agregó `INVENIO_HOSTNAME` como variable de entorno en los servicios Docker. Define la IP en `.env.prop`:

```ini
INVENIO_HOSTNAME=172.24.0.98
```

## Notas

- Las imágenes son autocontenidas: no necesitas montar el código fuente
- Para cambios en el código, reconstruye la imagen con `build --no-cache`
- Los datos persistentes (DB, uploads) se guardan en volúmenes Docker
- El `hello-world/Dockerfile` original se mantiene como referencia
