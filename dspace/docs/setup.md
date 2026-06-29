# DSpace 8.0 Production Deployment

## Architecture

```
Machine  192.168.0.236          Machine  172.24.0.95 (este host)
┌──────────────────────┐       ┌─────────────────────────────────────┐
│   Apache (HTTPS)     │──────▶│  Docker                             │
│   ProxyPass a        │       │  ┌──────────┐  ┌─────────────────┐  │
│   puerto 443         │       │  │ dspacedb │  │ dspace-solr     │  │
│                      │       │  │ :5432    │  │ :8983           │  │
│                      │       │  └──────────┘  └─────────────────┘  │
│                      │       │  ┌────────────────────────────────┐  │
│                      │       │  │ dspace-backend (tomcat)        │  │
│                      │       │  │ :8080 (interno) → host :8090   │  │
│                      │       │  │ context-path: /dspace/server    │  │
│                      │       │  └────────────────────────────────┘  │
│                      │       │  ┌────────────────────────────────┐  │
│                      │       │  │ dspace-angular (SSR Node)       │  │
│                      │       │  │ :4000 (interno) → host :4000    │  │
│                      │       │  │ namespace: /dspace              │  │
│                      │       │  └────────────────────────────────┘  │
│                      │       └─────────────────────────────────────┘
└──────────────────────┘
```

## Archivos de Configuración

### `docker-compose.prod.yml`

- `docker-compose.prod.yml` en la raíz del proyecto
- Variables de entorno para el frontend se definen inline en `environment:`
- Backend expone puerto `8090` (host) → `8080` (container)
- Frontend expone puerto `4000` (host) → `4000` (container)

### `dspace-angular/docker/dspace-ui.json`

Configuración de PM2 para el servidor SSR. Modificado:

```json
{
  "instances": 2,
  "exec_mode": "cluster",
  "script": "dist/server/main.js",
  "name": "dspace-ui",
  ...
}
```

**Cambio**: `instances: "max"` → `instances: 2` (original spawn 16 procesos en CPU de 16 núcleos).

### `dspace-angular/config/config.prod.yml`

- Se carga automáticamente en producción (log: "Overriding app config with /app/config/config.prod.yml")
- Contiene overrides de cache, UI, REST, etc.
- Ubicación: dentro del container en `/app/config/config.prod.yml`

## Conexión al Backend

### Opción A: Vía Apache HTTPS (configuración actual en compose)

```yaml
DSPACE_REST_HOST=192.168.0.236
DSPACE_REST_PORT=443
DSPACE_REST_NAMESPACE=/dspace/server
DSPACE_REST_SSL=true
NODE_TLS_REJECT_UNAUTHORIZED=0    # necesario para cert autofirmado
```

- SSR → Apache (`.236:443`) → ProxyPass → Backend Docker (`.124:8090`)
- Requiere `NODE_TLS_REJECT_UNAUTHORIZED=0` para certificado SSL autofirmado
- **Problema actual**: Apache devuelve HTTP 503. Revisar configuración en `.236`.

### Opción B: Conexión directa por Docker (alternativa)

```yaml
DSPACE_REST_HOST=dspace-backend
DSPACE_REST_PORT=8080
DSPACE_REST_NAMESPACE=/dspace/server
DSPACE_REST_SSL=false
# Sin NODE_TLS_REJECT_UNAUTHORIZED
```

- SSR → Backend directamente por red interna Docker (`dspacenet`)
- Sin overhead TLS, sin necesidad de certificados
- **Problema**: Causa `Maximum call stack size exceeded` en `DspaceRestResponseParsingService.process()` al parsear respuestas HAL con `_embedded`. Ocurre porque el parser recursivo no detecta ciclos en las referencias embebidas.

## Variables de Entorno Importantes

### Prefijo `DSPACE_*`

El sistema usa `overrideWithEnvironment()` que transforma propiedades con puntos a mayúsculas con underscore:

| Propiedad | Env var | Ejemplo |
|-----------|---------|---------|
| `rest.ssl` | `DSPACE_REST_SSL` | `true`/`false` |
| `rest.host` | `DSPACE_REST_HOST` | `192.168.0.236` |
| `rest.port` | `DSPACE_REST_PORT` | `443` |
| `rest.namespace` | `DSPACE_REST_NAMESPACE` | `/dspace/server` |
| `cache.serverSide.botCache.timeToLive` | `DSPACE_CACHE_SERVERSIDE_BOTCACHE_TIMETOLIVE` | `300000` |

**Nota**: Las propiedades se concatenan sin separadores: `timeToLive` → `TIMETOLIVE` (NO `TIME_TO_LIVE`).

### Otras Variables

| Env var | Propósito |
|---------|-----------|
| `NODE_ENV=production` | Modo producción |
| `NODE_TLS_REJECT_UNAUTHORIZED=0` | Deshabilita verificación SSL (solo para cert autofirmado) |
| `DSPACE_CACHE_SERVERSIDE_BOTCACHE_TIMETOLIVE=300000` | TTL de bot cache: 5 min (default: 1 día) |

## Cache y Rendimiento

### Bot Cache (server-side)

- **Propósito**: Cachea respuestas SSR para user-agents detectados como bots (via librería `isbot`)
- **Default**: `max: 1000`, `timeToLive: 86400000` (1 día), `allowStale: true`
- **Problema**: Si un bot (ej: `curl`) recibe una respuesta de error (SSR falla temporalmente), esa respuesta se cachea por 1 día
- **Fix**: Reducir `timeToLive` a 5 minutos (300000ms)

### PM2 Cluster Mode

- **Problema original**: `instances: "max"` spawn 16 worker processes en CPU de 16 núcleos, causando contención de recursos
- **Fix**: Reducir a `instances: 2` — suficiente para redundancia sin desperdicio
- **Importante**: `docker/dspace-ui.json` se copia en el build de la imagen Docker (`Dockerfile.dist`). Cambios requieren rebuild de la imagen.

## SSL y Certificados

- Backend usa certificado SSL autofirmado en Apache (`.236`)
- Node.js por defecto rechaza certificados autofirmados → requiere `NODE_TLS_REJECT_UNAUTHORIZED=0`
- Alternativa: conectar directamente por HTTP interno de Docker (Opción B)

## Problemas Conocidos

### 1. Apache devuelve 503

```
GET https://192.168.0.236/dspace/server/api → HTTP 503
```

Backend accesible desde el host en `http://127.0.0.1:8090/dspace/server/api`. Apache necesita proxy:

```apache
ProxyPass /dspace/server http://172.24.0.95:8090/dspace/server
ProxyPassReverse /dspace/server http://172.24.0.95:8090/dspace/server

RequestHeader set X-Forwarded-Proto "https"
RequestHeader set X-Forwarded-Port "443"
```

### 2. Infinite recursion en response parser (Opción B)

```
RangeError: Maximum call stack size exceeded
  at getEmbedSizeParams (/app/dist/server/main.js:1:518806)
  at DspaceRestResponseParsingService2.process (...)
```

Ocurre al conectar SSR directo por HTTP Docker. El método `DspaceRestResponseParsingService.process()` (en `src/app/core/data/dspace-rest-response-parsing.service.ts`) recorre recursivamente todas las propiedades de `_embedded` en respuestas HAL sin detección de ciclos ni límite de profundidad.

Posibles causas:
- Respuestas HAL con referencias circulares (ej: comunidad → subcomunidades → comunidad padre)
- `getEmbedSizeParams()` se llama en cada invocación recursiva sin memoización
- No hay `Set` de objetos ya visitados ni contador de profundidad

**Workaround**: Usar Opción A (Apache) que evita el problema porque:
- Apache devuelve HTML/error en lugar de HAL+JSON real
- El parser falla gracefulmente ("No _links section found")

### 3. Cache de errores para bots

- Bot cache con TTL de 1 día cachea respuestas de error para user-agents detectados como bots
- Fix aplicado: TTL reducido a 5 min

## Comandos Útiles

```bash
# Rebuild image (necesario tras cambios en dspace-ui.json)
docker compose -f docker-compose.prod.yml build dspace-angular

# Recrear container (necesario tras cambios en env vars)
docker compose -f docker-compose.prod.yml rm -fs dspace-angular
docker compose -f docker-compose.prod.yml up -d dspace-angular

# Ver logs del frontend
docker logs dspace-angular --tail 50

# Ver logs del backend
docker logs dspace --tail 50

# Test SSR local
Invoke-WebRequest -Uri "http://127.0.0.1:4000/dspace/" -TimeoutSec 30 -UseBasicParsing

# Test backend reachability
curl.exe -s -o /dev/null -w "HTTP %{http_code}" "http://127.0.0.1:8090/dspace/server/api"

# Test backend via Apache
curl.exe -k -s -o /dev/null -w "HTTP %{http_code}" "https://192.168.0.236/dspace/server/api"
```

## Archivos Relevantes

| Archivo | Propósito |
|---------|-----------|
| `docker-compose.prod.yml` | Orquestación de containers |
| `dspace-angular/docker/dspace-ui.json` | Config PM2 cluster mode |
| `dspace-angular/Dockerfile.dist` | Dockerfile oficial para producción |
| `dspace-angular/config/config.prod.yml` | Config de producción del frontend |
| `dspace-angular/config/config.yml` | Config base del frontend |
| `dspace-angular/package.json` | Script build:ssr con --base-href /dspace/ |
| `dspace-angular/server.ts` | Lógica SSR y bot cache |
| `dspace-angular/src/app/core/data/dspace-rest-response-parsing.service.ts` | Response parser con bug de recursión |
| `.env.prod` | Variables de entorno comunes |
