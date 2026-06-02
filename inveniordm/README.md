# InvenioRDM - Despliegue con Docker

Documentación del proyecto **InvenioRDM v13** generado con `invenio-cli init` (cookiecutter `v13.0`, flavour RDM, PostgreSQL, OpenSearch 2, almacenamiento local) y orquestado mediante Docker Compose.

---

## 1. Estructura del repositorio

```
inveniordm/
├── hello-world/                 # Proyecto InvenioRDM generado por cookiecutter
│   ├── Dockerfile               # Imagen de la app (base: inveniosoftware/almalinux:1)
│   ├── docker-compose.yml       # (legacy) servicios de backend para dev
│   ├── docker-compose.full.yml  # (legacy) stack completo de prod
│   ├── docker-services.yml      # (legacy) servicios compartidos via extends
│   ├── docker/                  # nginx, pgadmin, uwsgi configs
│   ├── invenio.cfg              # Configuración de la app
│   ├── Pipfile / Pipfile.lock   # Dependencias Python
│   ├── site/                    # Paquete editable `hello-world`
│   ├── assets/, static/, templates/, translations/, app_data/
│   └── .invenio                 # Metadata del proyecto (versionado)
│
├── docker-compose.local.yml     # Dev: app + db + cache + mq + search (+ dashboards)
├── docker-compose.prod.yml      # Prod: nginx + web-ui + web-api + worker + scheduler + backend
├── .env.example                 # Plantilla de variables de entorno
└── README.md                    # Este archivo
```

> Los `docker-compose.*.yml` de la raíz **no usan `extends`**: son autocontenidos y apuntan a `./hello-world` como contexto de build, por lo que pueden copiarse o versionarse de forma independiente.

---

## 2. Por qué se descartó el intento original

El intento previo (Dockerfile de la raíz que instalaba `invenio-cli` globalmente y montaba `/var/run/docker.sock`) **no funciona** con InvenioRDM v13. Motivos:

| # | Problema | Consecuencia |
|---|----------|--------------|
| 1 | `Pipfile` vacío | Faltaban `invenio-app-rdm`, `uwsgi`, `hello-world` (editable), etc. |
| 2 | `invenio-cli` global | v13 requiere que `invenio-cli` corra **dentro** de un proyecto (con `.invenio`/`Pipfile`), no como binario suelto |
| 3 | Sin `invenio.cfg`/`site/`/`assets/`/`static/` | No había app real que arrancar |
| 4 | Montar `/var/run/docker.sock` | Patrón Docker-in-Docker innecesario y arriesgado |
| 5 | Sin servicios de backend | Faltaban postgres, redis, rabbitmq, opensearch |
| 6 | `CMD ["invenio-cli","run"]` | El entrypoint real es `uwsgi` o `flask --app invenio_app run` |
| 7 | Assets sin compilar | `invenio webpack buildall` debe correr en **build time** |

Esos archivos se eliminaron. El proyecto real vive en `hello-world/` y se orquesta desde la raíz.

---

## 3. Puesta en marcha rápida

### 3.1. Local (desarrollo)

```bash
cp .env.example .env

# Levantar todo (build la primera vez, ~5-10 min)
docker compose -f docker-compose.local.yml --env-file .env up -d --build

# Inicializar la base de datos, indices y storage (una sola vez)
docker compose -f docker-compose.local.yml exec app invenio db create
docker compose -f docker-compose.local.yml exec app invenio db init
docker compose -f docker-compose.local.yml exec app invenio index init
docker compose -f docker-compose.local.yml exec app invenio files location create default-location /opt/invenio/var/instance/data default
docker compose -f docker-compose.local.yml exec app invenio oai harvester init

# Acceder a la app
# UI/API:  http://127.0.0.1:5000
# Postgres: 127.0.0.1:5432  (user/pass: hello-world/hello-world)
# Redis:    127.0.0.1:6379
# RabbitMQ: 127.0.0.1:15672  (guest/guest)
# OpenSearch: http://127.0.0.1:9200
# OpenSearch Dashboards: http://127.0.0.1:5601
# pgAdmin:  http://127.0.0.1:5050  (info@hello-world.com / hello-world)

# Ver logs
docker compose -f docker-compose.local.yml logs -f app
```

### 3.2. Producción

```bash
cp .env.example .env
# $EDITOR .env  # cambiar TODOS los CHANGE_ME y passwords
# MUY IMPORTANTE: regenerar INVENIO_SECRET_KEY con:
#   python -c "import secrets; print(secrets.token_urlsafe(64))"

docker compose -f docker-compose.prod.yml --env-file .env build
docker compose -f docker-compose.prod.yml --env-file .env up -d

# Inicialización una sola vez (dentro de web-api)
docker compose -f docker-compose.prod.yml exec web-api invenio db create
docker compose -f docker-compose.prod.yml exec web-api invenio db init
docker compose -f docker-compose.prod.yml exec web-api invenio index init
docker compose -f docker-compose.prod.yml exec web-api invenio files location create default-location /opt/invenio/var/instance/data default
docker compose -f docker-compose.prod.yml exec web-api invenio oai harvester init
docker compose -f docker-compose.prod.yml exec web-api invenio roles create admin

# Accesos:
# HTTP  ->  http://<host>:80   (redirige a HTTPS si hay certs)
# HTTPS ->  https://<host>:443
```

---

## 4. Diferencias entre `local` y `prod`

| Aspecto | `docker-compose.local.yml` | `docker-compose.prod.yml` |
|---|---|---|
| **Servicios app** | `app` único (código montado en vivo) | `web-ui` + `web-api` (uwsgi) + `worker` (celery) + `scheduler` (celery beat) |
| **Servidor** | `invenio-cli run` (Flask dev server) | `uwsgi` con `uwsgi_ui.ini` y `uwsgi_rest.ini` |
| **Frontend** | No - lo sirve `app` | `frontend` con nginx (puertos 80/443) |
| **Bind frontend** | `127.0.0.1:5000` | `${FRONTEND_HTTP_BIND:-0.0.0.0}:80`, `:443` |
| **OpenSearch** | `DISABLE_SECURITY_PLUGIN=true` (sin auth) | `false` (HTTPS, requiere `OPENSEARCH_INITIAL_ADMIN_PASSWORD`) |
| **Redis** | sin password | `--requirepass ${REDIS_PASSWORD}` |
| **Tools de dev** | `pgadmin`, `opensearch-dashboards` | **eliminados** (no se exponen en prod) |
| **Restart policy** | `unless-stopped` | `always` |
| **Healthchecks** | Sí | Sí (más estrictos) |
| **Hot-reload** | Sí (volumen `./hello-world:/app`) | No (código baked en la imagen) |
| **Volúmenes** | 6 nombrados | 7 nombrados (incluye `static_data`) |

---

## 5. Variables de entorno (`.env`)

| Variable | Descripción | Default | ¿Requerida en prod? |
|---|---|---|---|
| `IMAGE_TAG` | Tag de la imagen de la app | `prod` | opcional |
| `APP_HOST_BIND` | Bind del puerto de la app en local | `127.0.0.1` | n/a |
| `DOCKER_SERVICES_IP_BIND` | Bind de los servicios backend en local | `127.0.0.1` | n/a |
| `FRONTEND_HTTP_BIND` | Bind puerto 80 de nginx | `0.0.0.0` | opcional |
| `FRONTEND_HTTPS_BIND` | Bind puerto 443 de nginx | `0.0.0.0` | opcional |
| `INVENIO_SECRET_KEY` | Secret key de Flask | `CHANGE_ME` | **obligatorio** |
| `POSTGRES_USER` / `_PASSWORD` / `_DB` | Credenciales Postgres | `hello-world` / `hello-world` / `hello-world` | sí, cambiar |
| `REDIS_PASSWORD` | Auth de Redis | `change-me-redis-password` | sí, cambiar |
| `RABBITMQ_USER` / `_PASSWORD` | Credenciales RabbitMQ | `hello-world` / `change-me-rabbitmq-password` | sí, cambiar |
| `OPENSEARCH_INITIAL_ADMIN_PASSWORD` | Password admin de OpenSearch | `MyStr0ng#Pass2026` | sí, cambiar |
| `OPENSEARCH_HEAP` | Heap JVM (`-Xms`/`-Xmx`) | `1g` | opcional |
| `OPENSEARCH_MEM_LIMIT` | Límite RAM del contenedor | `2g` | opcional |
| `PGADMIN_DEFAULT_EMAIL` / `_PASSWORD` | Creds pgAdmin (solo dev) | `info@hello-world.com` / `hello-world` | n/a (solo dev) |

> Genera un secret seguro:
> ```bash
> python -c "import secrets; print(secrets.token_urlsafe(64))"
> ```

---

## 6. Comandos útiles

### Inspeccionar / debug

```bash
# Ver estado de servicios
docker compose -f docker-compose.local.yml ps

# Logs en tiempo real
docker compose -f docker-compose.local.yml logs -f app

# Entrar a un contenedor
docker compose -f docker-compose.local.yml exec app bash
docker compose -f docker-compose.local.yml exec db psql -U hello-world hello-world

# Reiniciar un servicio
docker compose -f docker-compose.local.yml restart app

# Reconstruir solo la app tras cambiar Pipfile/assets
docker compose -f docker-compose.local.yml build app
docker compose -f docker-compose.local.yml up -d app
```

### Base de datos

```bash
# Crear/eliminar base de datos
docker compose -f docker-compose.local.yml exec app invenio db create
docker compose -f docker-compose.local.yml exec app invenio db drop

# Inicializar tablas
docker compose -f docker-compose.local.yml exec app invenio db init

# Reindexar (despues de cambios en mappings)
docker compose -f docker-compose.local.yml exec app invenio index reindex
```

### OpenSearch

```bash
# Estado del cluster
curl -u admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD http://127.0.0.1:9200/_cluster/health?pretty

# Listar indices
curl -u admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD http://127.0.0.1:9200/_cat/indices?v
```

### Reinicio limpio (⚠️ borra datos)

```bash
docker compose -f docker-compose.local.yml down -v
```

---

## 7. Volúmenes persistentes

| Volumen | Servicio | Contenido |
|---|---|---|
| `db_data` | postgres | Datos de PostgreSQL |
| `cache_data` | redis | Snapshots de Redis (AOF/RDB) |
| `mq_data` | rabbitmq | Mensajes y config de RabbitMQ |
| `search_data` | opensearch | Índices de OpenSearch |
| `static_data` | app/web-ui/frontend | Assets compilados servidos por nginx |
| `uploaded_data` | app/web-ui/web-api/worker | Archivos subidos por usuarios |
| `archived_data` | app/web-ui/web-api | Archivos archivados |

> Los nombres de volúmenes usan el prefijo del directorio del compose (ej. `inveniordm_db_data`). Verifica con `docker volume ls | grep inven`.

---

## 8. Despliegue en producción - checklist

- [ ] Regenerar `INVENIO_SECRET_KEY` con `secrets.token_urlsafe(64)`
- [ ] Cambiar `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `RABBITMQ_PASSWORD` a valores fuertes
- [ ] Cambiar `OPENSEARCH_INITIAL_ADMIN_PASSWORD` (mín. 12 chars, mayúsc/minúsc/núms/símbolos)
- [ ] Editar `invenio.cfg`:
  - `SECRET_KEY` (debe coincidir con `.env`)
  - `SITE_UI_URL` y `SITE_API_URL` apuntando al dominio real
  - `TRUSTED_HOSTS` con el dominio real
  - `DATACITE_*` si usas DOI
- [ ] Configurar certificados TLS reales en `hello-world/docker/nginx/`
- [ ] Configurar backups de los volúmenes `db_data`, `search_data`, `uploaded_data`
- [ ] Configurar `force_https=True` en `invenio.cfg` (ya está por defecto)
- [ ] Restringir bindings (`FRONTEND_HTTP_BIND`, `FRONTEND_HTTPS_BIND`) según la red
- [ ] Desactivar `pgadmin` y `opensearch-dashboards` (ya no aparecen en `prod`)
- [ ] Crear usuario admin tras la inicialización

---

## 9. Troubleshooting

### "Connection refused" a la base de datos al iniciar la app

Postgres aún no terminó de arrancar cuando la app intentó conectar. El `healthcheck` debería prevenirlo, pero si persiste:
```bash
docker compose -f docker-compose.local.yml logs db
docker compose -f docker-compose.local.yml restart app
```

### "OpenSearch: security_disabled" en producción

`DISABLE_SECURITY_PLUGIN` no debe estar en `true` para prod. Verifica que `docker-compose.prod.yml` tenga `false` y que `OPENSEARCH_INITIAL_ADMIN_PASSWORD` esté definido en `.env`.

### "invenio webpack buildall" falla por memoria

Aumenta el heap de Node o el límite de Docker Desktop (Settings → Resources → Memory ≥ 4 GB).

### "ALLOWED_HOSTS" / "Invalid Host" en navegador

Edita `invenio.cfg` → `TRUSTED_HOSTS` para incluir el host/dominio desde el que accedes.

### El frontend nginx devuelve 502

Los `web-ui`/`web-api` no están healthy:
```bash
docker compose -f docker-compose.prod.yml logs web-ui web-api
docker compose -f docker-compose.prod.yml ps
```

### Cambios en `Pipfile` o `assets/` no se reflejan

En local el código está montado como volumen, pero `node_modules` y los assets compilados **no**. Reconstruye la imagen:
```bash
docker compose -f docker-compose.local.yml build app
docker compose -f docker-compose.local.yml up -d app
```

---

## 10. Referencias

- Documentación oficial: https://inveniordm.docs.cern.ch/
- Configuración: https://inveniordm.docs.cern.ch/operate/customize/configuration/
- Autenticación: https://inveniordm.docs.cern.ch/operate/customize/authentication/
- DOIs / DataCite: https://inveniordm.docs.cern.ch/operate/customize/dois/
- Repositorio: https://github.com/inveniosoftware
