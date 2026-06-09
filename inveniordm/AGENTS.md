# InvenioRDM v13 — Notas del proyecto

## Estructura

```
inveniordm/
├── docker-compose.local.yml      # Dev: app + db + cache + mq + search + dashboards + pgadmin
├── docker-compose.prod.yml       # Prod: nginx + web-ui + web-api + worker + scheduler
├── .env.example                   # Plantilla de variables de entorno
├── hello-world/                   # Proyecto InvenioRDM generado por cookiecutter
│   ├── Dockerfile                 # Imagen de la app
│   ├── Pipfile / Pipfile.lock    # Dependencias Python (generado con Python 3.12)
│   ├── invenio.cfg               # Configuración de la app
│   ├── site/                     # Paquete editable hello-world
│   ├── assets/, static/          # Frontend assets
│   └── docker/                   # Nginx, uwsgi, pgadmin configs
└── AGENTS.md                     # Este archivo
```

## Build

```bash
docker compose -f docker-compose.local.yml --env-file .env build --no-cache app
```

### Problemas conocidos del build

1. **Python 3.12 requerido**: La imagen base `registry.cern.ch/inveniosoftware/almalinux:1` viene con Python 3.9, pero el `Pipfile.lock` se generó para Python 3.12 y muchos paquetes tienen markers `python_version >= '3.10'`. Se instaló Python 3.12 en el Dockerfile.

2. **Directorio `assets/` faltante**: La imagen base crea `${INVENIO_INSTANCE_PATH}/static/` pero no `${INVENIO_INSTANCE_PATH}/assets/`. Se agregó `mkdir -p` antes del `cp`.

## Entrypoint

El Dockerfile tiene `ENTRYPOINT ["bash", "-c"]`. No usar `command:` en docker-compose con este entrypoint porque no se combina bien. En su lugar, usar `entrypoint:` como string:

```yaml
entrypoint: invenio run --host 0.0.0.0 --port 5000
```

## Inicialización (primera vez)

```bash
docker compose -f docker-compose.local.yml --env-file .env exec app invenio db create
docker compose -f docker-compose.local.yml --env-file .env exec app invenio db init
docker compose -f docker-compose.local.yml --env-file .env exec app invenio index init
docker compose -f docker-compose.local.yml --env-file .env exec app invenio files location create --default default-location /opt/invenio/var/instance/data
```

## Crear usuario admin

```bash
docker compose -f docker-compose.local.yml --env-file .env exec app invenio users create admin@hello-world.com --password <PASSWORD> --active
docker compose -f docker-compose.local.yml --env-file .env exec app invenio roles add admin@hello-world.com admin
```

## Puertos

| Servicio | Puerto |
|----------|--------|
| App InvenioRDM | 5000 |
| PostgreSQL | 5432 |
| Redis | 6379 |
| RabbitMQ | 5672 / 15672 |
| OpenSearch | 9200 / 9600 |
| OpenSearch Dashboards | 5601 |
| pgAdmin | 5050 |

## Troubleshooting

- **Puerto 5432 ocupado**: PostgreSQL local. Parar con `net stop postgresql-*` o mapear a 5433.
- **invenio-cli: command not found**: No usar `invenio-cli run`, usar `invenio run`.
- **Container restarting**: No usar `ENTRYPOINT ["bash", "-c"]` con `command:` en compose. Usar `entrypoint:` como string en su lugar.
