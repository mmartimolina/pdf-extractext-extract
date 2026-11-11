# Entrega — Ecosistema de microservicios de procesamiento de PDF

Documento de entrega del ecosistema **pdf-extractext**: auditoría, correcciones,
pruebas y matriz de requisitos. Los cuatro repositorios son:

| Repositorio               | Responsabilidad                              |
|---------------------------|----------------------------------------------|
| `pdf-extractext-extract`  | Extrae texto y páginas de un PDF (`POST /extract`) |
| `pdf-extractext-validation` | Valida estructura y checksum de un PDF (`POST /validate`) |
| `pdf-extractext-summarize` | Orquestador: valida → extrae → resume con LLM → persiste |
| `pdf-extractext-persistence` | Persistencia idempotente por checksum en MongoDB (`/documents`) |

## 1. Arquitectura

```text
                    ┌──────────────┐
  PDF binario ────▶ │ pdf-summarize│ (orquestador, red interna)
                    └──┬───┬───┬───┘
        ┌──────────────┘   │   └──────────────┐
        ▼                  ▼                  ▼
 ┌─────────────┐   ┌─────────────┐   ┌──────────────────┐
 │  validation │   │   nginx     │   │   persistence    │
 │ POST /vali- │   │  :8002 host │   │ POST /documents  │
 │ date :8001  │   │  ┌───┬───┐  │   │ :8003 host  ── MongoDB
 └─────────────┘   │  ▼   ▼   ▼  │   └──────────────────┘
                   │ extract ×3  │
                   │ (1 CPU/1GB) │
                   └──────┬──────┘
                          │ registro dinámico
                          ▼
                    ┌───────────┐
                    │   Consul  │  UI http://localhost:8500
                    │  (server) │  volumen consul-data
                    └───────────┘
     Red Docker externa compartida: pdf-ecosystem-net
```

- **Extract**: 3 réplicas stateless (configurable 1–5) detrás de **Nginx**
  (`least_conn` + Docker DNS). Cada réplica se registra **dinámicamente** en
  Consul con su IP de contenedor, ID `extract-<hostname>` y healthcheck HTTP
  contra `/health` (10 s, `DeregisterCriticalServiceAfter: 1m`).
- **Validation / Summarize / Persistence**: instancias únicas registradas de
  forma **estática** en Consul (`services.json` del repositorio summarize),
  con healthchecks `/health/ready`.
- **Consul**: agente servidor único con UI, ACL habilitadas
  (`default_policy = "allow"`), política `pdf-service-registration` y su token
  para el registro desde los servicios; datos en volumen `consul-data`.
- Comunicación inter-servicios: HTTP binario (`Content-Type: application/pdf`)
  con `X-Request-ID` propagado; resolución por DNS de la red compartida
  (`pdf-validation`, `nginx`, `pdf-persistence`).

## 2. Instalación y ejecución

Requisitos: Docker Desktop, [uv](https://docs.astral.sh/uv/) (opcional, para tests).

```powershell
# 1. Red y volumen compartidos (solo la primera vez)
docker network create pdf-ecosystem-net
docker volume create consul-data

# 2. Consul (repositorio pdf-extractext-summarize)
docker compose -f docker-compose.consul.yml up -d

# 3. Servicios (desde cada repositorio)
#    pdf-extractext-extract        → extract (3 réplicas) + nginx :8002
#    pdf-extractext-validation     → :8001
#    pdf-extractext-persistence    → :8003 (requiere MongoDB en la red)
#    pdf-extractext-summarize      → docker compose -f docker-compose.ecosystem.yml up -d
docker compose up -d --build
```

## 3. Variables de entorno

| Servicio    | Variable                | Default                       | Uso                              |
|-------------|-------------------------|-------------------------------|----------------------------------|
| extract     | `MAX_PDF_SIZE_BYTES`    | `20971520` (20 MB)            | Límite de tamaño del PDF         |
| extract     | `CONSUL_HTTP_ADDR`      | `http://consul:8500`          | Registro Consul (vacío = off)    |
| extract     | `CONSUL_SERVICE_ID`     | `extract-<hostname>`          | ID único de la réplica           |
| extract     | `SERVICE_ADDRESS`       | IP del contenedor             | Dirección registrada             |
| extract     | `CONSUL_ACL_TOKEN`      | (vacío)                       | Token ACL opcional de registro   |
| validation  | `MAX_FILE_SIZE_MIB`     | `20`                          | Límite de tamaño (MiB)           |
| persistence | `PORT` / `MONGO_URI` / `MONGO_DATABASE` / `MONGO_COLLECTION` / `MONGO_TIMEOUT_MS` / `LOG_LEVEL` | `8003` / `mongodb://mongo_db:27017` / `pdf_persistence` / `documents` / `5000` / `INFO` | Configuración de Mongo y logs |
| summarize   | `LLM_API_KEY`           | — (obligatoria para resumir)  | Proveedor IA OpenAI-compatible   |
| summarize   | `LLM_BASE_URL` / `LLM_MODEL` / `LLM_TIMEOUT_SECONDS` / `LLM_MAX_TOKENS` | `https://integrate.api.nvidia.com/v1` / `meta/llama-3.1-8b-instruct` / `60` / `1000` | Proveedor IA |
| summarize   | `VALIDATION_SERVICE_URL` / `EXTRACT_SERVICE_URL` / `PERSISTENCE_SERVICE_URL` | `http://pdf-validation:8000` / `http://nginx:8000` / `http://pdf-persistence:8003` | Dependencias del flujo |
| summarize   | `MAX_PDF_SIZE_MIB` / `UPSTREAM_TIMEOUT_SECONDS` / `LOG_LEVEL` | `20` / `30` / `INFO` | Límites y logs |

Los secretos (`LLM_API_KEY`) viven en `.env` local, nunca versionados ni en logs.

## 4. Consul: registro dinámico, diagnóstico y solución

**Problema original**: la réplica `extract-533865dd72da` quedaba `critical` en el
catálogo aunque su check local y sus tres endpoints `/health` respondían 200.

**Causa raíz (confirmada con logs y API)**: el agente tenía persistido un token
ACL de agente que ya no existía en el store del servidor
(`agent.anti_entropy: failed to sync remote state: error="ACL not found"`).
El anti-entropy no podía publicar las actualizaciones de los checks al catálogo,
que conservaba el último estado crítico conocido (con salida vacía).

**Solución aplicada (no destructiva, sin recrear datos)**:

1. Se verificó que el token de registro `pdf-service-registration` **sí existe**
   (se reutiliza; no se crearon tokens nuevos).
2. Se limpió únicamente el token de agente roto:
   `docker exec consul consul acl set-agent-token agent ""` (con
   `default_policy = "allow"` el agente no necesita token dedicado).
3. El anti-entropy volvió a sincronizar: el catálogo pasó a `passing` para las
   tres réplicas y `/v1/health/state/critical` devolvió `[]`.

**Robustez implementada** (`src/consul.py` en extract):

- Reintentos de registro (3 intentos, 2 s entre ellos) con fail-soft: si Consul
  no responde, el servicio sigue funcionando.
- Soporte opcional de ACL: `CONSUL_ACL_TOKEN` envía el header `X-Consul-Token`
  al registrar (reutiliza la política existente cuando se configure).
- Desregistro en el cierre (lifespan de FastAPI) y limpieza por
  `DeregisterCriticalServiceAfter: 1m` ante caídas abruptas.

## 5. Pruebas y resultados

### Suite automatizada (todas en verde)

| Repositorio  | Comando                          | Resultado                        |
|--------------|----------------------------------|----------------------------------|
| extract      | `uv run pytest`                  | **39 passed**, cobertura 100 %   |
| validation   | `uv run pytest`                  | **26 passed**, cobertura 96 %    |
| persistence  | `uv run pytest`                  | **97 passed**, 3 skipped, 100 %  |
| persistence  | `uv run pytest -m integration --no-cov` (Mongo real) | **3 passed** |
| summarize    | `uv run pytest`                  | **137 passed**, 100 %            |
| los 4        | `uv run ruff check .` + `ruff format --check .` | sin errores       |

Nuevos tests agregados en extract (`tests/test_consul.py`): reintentos de
registro, abandono tras máximos intentos, token ACL opcional en el header.

### Verificación en vivo del ecosistema (ejecutada)

| Verificación | Resultado |
|---|---|
| `/health` extract vía Nginx (:8002) | 200 `{"status":"ok"}` |
| `/health/ready` validation (:8001) y persistence (:8003) | 200 |
| `/health/ready` summarize (interno) | 200 `{"status":"ready"}` |
| 3 réplicas de extract en Consul | 3 × `passing`, `state/critical` = `[]` |
| Flujo completo `POST /summarize` (PDF con texto real) | 200 con resumen, checksum y `request_id`; verificado en `/documents/{checksum}` de persistence |
| Propagación Extract vía Nginx | log de acceso de Nginx muestra `POST /extract 200` desde summarize |
| Fallo y recuperación | `docker stop` de una réplica → desaparece de `passing`; `docker start` → se re-registra (3 × passing) |
| Casos de error | sample sin texto útil → 422 `NO_USEFUL_TEXT`; reintento del mismo PDF con resumen LLM distinto → 409 `PERSISTENCE_CONFLICT` (deduplicación por checksum, comportamiento documentado) |

## 6. Correcciones aplicadas en esta auditoría

| Problema | Corrección | Archivo |
|---|---|---|
| Réplica stuck en `critical` en el catálogo | Limpieza del token de agente ACL inválido (causa: anti-entropy `ACL not found`) | runtime Consul (verificado con `/v1/health/state/*`) |
| Registro sin reintentos ni soporte ACL | Reintentos (3×2 s) + `CONSUL_ACL_TOKEN` opcional | `pdf-extractext-extract/src/consul.py` |
| `CONSUL_HTTP_ADDR` deshabilitado por defecto en compose | Default `http://consul:8500`, sobrescribible | `pdf-extractext-extract/docker-compose.yml` |
| Summarize apuntando a una réplica fija de extract | `EXTRACT_SERVICE_URL=http://nginx:8000` (balanceo least_conn) | `.env` local de summarize |
| Colisión de puerto host (8002) al levantar summarize standalone | `PORT=8010` en `.env` local | `.env` de summarize |
| Lint BLE001 por excepciones ciegas | `except RuntimeError` (contrato de `_request`) | `src/consul.py` |
| README de persistence inexistente | README completo (API, env vars, tests) | `pdf-extractext-persistence/README.md` |
| READMEs sin documentar Consul/réplicas | Secciones de Consul y escalabilidad | READMEs de extract, validation y summarize |

## 7. Matriz de requisitos

| # | Requisito | Estado | Implementación | Prueba/verificación |
|---|-----------|--------|----------------|---------------------|
| 1 | Microservicio de extracción de texto de PDF | Cumplido | `pdf-extractext-extract/src/**` | `uv run pytest` (39), flujo real |
| 2 | `POST /extract` con body binario | Cumplido | `src/api/routes.py` | tests + curl/Nginx 200 |
| 3 | Respuesta JSON `content` + `page_count` | Cumplido | `src/domain/models.py` | tests |
| 4 | Validaciones: MIME, vacío, tamaño, PDF inválido/cifrado | Cumplido | `src/service/extraction.py`, `routes.py` | `test_extract.py`, `test_size_limits.py` |
| 5 | `MAX_PDF_SIZE_BYTES` (20 MB default) | Cumplido | `src/config.py` | `test_config.py` |
| 6 | Healthcheck `GET /health` | Cumplido | `src/api/routes.py` | curl + Consul check 200 |
| 7 | Servicio stateless | Cumplido | sin estado ni sesiones | réplica cualquiera responde |
| 8 | Contenerización Docker (Python 3.13-slim, uv, no-root) | Cumplido | `Dockerfile` | imagen construida y corriendo |
| 9 | Límites de recursos 1 CPU / 1 GB | Cumplido | `docker-compose.yml` | `docker inspect` |
| 10 | 3–5 réplicas detrás de balanceador | Cumplido | `deploy.replicas: 3` + `nginx.conf` | 3 instancias passing en Consul |
| 11 | Pruebas de carga k6 y Vegeta | Cumplido (ejecutadas con sample; oficial pendiente con PDFs de stress) | `tests/load/`, `results/` | informes en `docs/informe-tp.md` |
| 12 | Red compartida `pdf-ecosystem-net` | Cumplido | red externa en los 4 compose | contenedores en la red |
| 13 | Consul como service discovery | Cumplido | `infra/consul/*` (summarize) + `src/consul.py` (extract) | catálogo y checks verificados |
| 14 | Registro dinámico por réplica con healthcheck | Cumplido | `src/consul.py`, lifespan | 3 × passing; stop/start re-registra |
| 15 | Desregistro ante caída (deregister) | Cumplido | `DeregisterCriticalServiceAfter: 1m` + deregister en shutdown | stop → sale de `passing` |
| 16 | ACL: política y token de registro | Cumplido | `infra/service-registration-policy.hcl` (política `pdf-service-registration`) | token existente reutilizado; opcional vía `CONSUL_ACL_TOKEN` |
| 17 | Recuperación ante fallos / reintentos | Cumplido | reintentos en `consul.py` | test + stop/start verificado |
| 18 | Validación como servicio independiente | Cumplido | `pdf-extractext-validation` | 26 tests + `POST /validate` 200 |
| 19 | Orquestación validate→extract→LLM→persist | Cumplido | `pdf-extractext-summarize` | flujo real 200 end-to-end |
| 20 | Persistencia idempotente por checksum + soft-delete | Cumplido | `pdf-extractext-persistence` | 97 tests + 3 integración Mongo |
| 21 | Manejo de errores uniforme y request-id | Cumplido | handlers + middleware en los 4 | 422/409 verificados en vivo |
| 22 | Observabilidad (logs JSON, métricas) | Parcial | logs JSON y `/metrics` en summarize y persistence; validation sin `/metrics` (documentado como pendiente) | — |
| 23 | Documentación por repositorio | Cumplido | READMEs actualizados (persistence creado) | — |
| 24 | Secretos fuera del código y logs | Cumplido | `.env` no versionado; `LLM_API_KEY` solo presencia en readiness | revisión de logs |

## 8. Instrucciones de demostración

```powershell
# 1. Estado de los contenedores
docker ps --filter "network=pdf-ecosystem-net"

# 2. Catálogo de Consul con las 3 réplicas y el resto de servicios
#    UI: http://localhost:8500
curl.exe http://localhost:8500/v1/health/service/extract
curl.exe http://localhost:8500/v1/health/state/critical   # -> []

# 3. Extracción con balanceo (repetir: alterna réplicas least_conn)
curl.exe -X POST http://localhost:8002/extract -H "Content-Type: application/pdf" --data-binary "@tests/sample.pdf"

# 4. Validación
curl.exe -X POST http://localhost:8001/validate -H "Content-Type: application/pdf" --data-binary "@tests/sample.pdf"

# 5. Flujo completo (requiere LLM_API_KEY configurada en summarize)
#    usa un PDF con texto real (tests/sample.pdf solo tiene 2 palabras → 422 NO_USEFUL_TEXT)
docker cp big-sample.pdf pdf-extractext-summarize-pdf-summarize-1:/tmp/big.pdf
docker exec pdf-extractext-summarize-pdf-summarize-1 python -c "…POST /summarize…"
# ver el documento persistido:
curl.exe http://localhost:8003/documents

# 6. Recuperación ante fallos
docker stop pdf-extractext-extract-extract-2   # la réplica sale del catálogo (~1 min)
docker start pdf-extractext-extract-extract-2  # vuelve a registrarse (passing)
```

## 9. Pendientes conocidos

1. **Pruebas de carga con los PDFs oficiales de stress de la cátedra**: los
   resultados en `results/` usan el sample pequeño; reproducir k6/Vegeta con
   los PDFs oficiales y registrar los valores en el informe.
2. **`/metrics` en validation**: documentado como pendiente hasta cerrar el
   contrato común de métricas del ecosistema.
3. **Trazas distribuidas** (OpenTelemetry): fuera del alcance de la consigna;
   la correlación actual es por `X-Request-ID`.
4. **`pdf_api` (contenedor antiguo, exited)**: resto del monolito original, no
   forma parte del ecosistema; no se elimina sin autorización.
