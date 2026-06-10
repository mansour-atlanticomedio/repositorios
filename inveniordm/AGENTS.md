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
docker compose -f docker-compose.yml --env-file .env build --no-cache
docker compose -f docker-compose.yml --env-file .env up -d

# Inicializar (solo primera vez)
docker compose -f docker-compose.yml exec web-api invenio db create
docker compose -f docker-compose.yml exec web-api invenio db init
docker compose -f docker-compose.yml exec web-api invenio index init
docker compose -f docker-compose.yml exec web-api invenio files location create --default default-location /opt/invenio/var/instance/data
```

**Acceso directo (sin proxy):**
- UI: http://localhost:5000
- API: http://localhost:5001

**Con proxy reverso (Apache, Caddy, etc.):** El proxy termina SSL y redirige a web-ui:5000 (UI) y web-api:5001 (API). Las rutas están configuradas en `/invenio`.

## Puertos

| Servicio   | Dev       | Prod              |
|------------|-----------|-------------------|
| App UI     | 5000      | 5000 (web-ui)     |
| App API    | —         | 5001 (web-api)    |
| PostgreSQL | 5432      | 5432              |
| Redis      | 6379      | 6379              |
| RabbitMQ   | 5672/15672| 5672/15672        |
| OpenSearch | 9200/9600 | 9200/9600         |

## Notas

- Las imágenes son autocontenidas: no necesitas montar el código fuente
- Para cambios en el código, reconstruye la imagen con `build --no-cache`
- Los datos persistentes (DB, uploads) se guardan en volúmenes Docker
- El `hello-world/Dockerfile` original se mantiene como referencia
