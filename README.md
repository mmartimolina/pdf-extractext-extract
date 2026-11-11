# pdf-extractext-extract

Microservicio de extracción de texto desde archivos PDF, desarrollado con Python y FastAPI.

## Responsabilidad

Recibir archivos PDF (body binario) y devolver su contenido textual junto con el número de páginas.

## Arquitectura

Tres capas con dependencias hacia adentro:

```
src/
├── api/                    # Capa de presentación (FastAPI)
│   └── routes.py           #   GET /health, POST /extract, mapeo de errores HTTP
├── service/                # Capa de aplicación
│   └── extraction.py       #   ExtractionService: valida tamaño y magic bytes,
│                           #   delega en un TextExtractor (Protocol)
├── infrastructure/         # Capa de infraestructura
│   └── pypdf_extractor.py  #   PypdfTextExtractor: adaptador sobre pypdf
├── domain/                 # Modelos y errores de dominio
│   ├── models.py           #   ExtractedText
│   └── errors.py           #   InvalidPdfError, PdfTooLargeError
├── config.py               # Settings (variables de entorno)
├── consul.py               # Registro dinámico en Consul (opcional)
└── main.py                 # create_app(): composition root + lifespan
```

## API

### GET /health

```json
200 {"status": "ok"}
```

### POST /extract

- Body: binario del PDF, `Content-Type: application/pdf`.
- Respuesta exitosa:

```json
200 {"content": "...", "page_count": 2}
```

- Errores:

| Código | Caso                                          |
|--------|-----------------------------------------------|
| 400    | Body vacío, PDF corrupto o inválido           |
| 413    | PDF supera `MAX_PDF_SIZE_BYTES`               |
| 415    | Content-Type distinto de `application/pdf`    |
| 500    | Error inesperado                              |

## Configuración

| Variable             | Default                     | Descripción                                              |
|----------------------|-----------------------------|----------------------------------------------------------|
| `MAX_PDF_SIZE_BYTES` | `20971520` (20 MB)          | Tamaño máximo de PDF aceptado                            |
| `CONSUL_HTTP_ADDR`   | `http://consul:8500`        | Dirección del agente Consul (vacío deshabilita registro) |
| `CONSUL_SERVICE_ID`  | `extract-<hostname>`        | ID único de la instancia en Consul                       |
| `SERVICE_ADDRESS`    | IP del contenedor           | Dirección con la que se registra la instancia            |
| `CONSUL_ACL_TOKEN`   | (vacío)                     | Token ACL opcional para registrar el servicio            |

## Escalabilidad: réplicas, balanceo y Consul

- `docker-compose.yml` define **3 réplicas** con límites de 1 CPU y 1 GB por instancia
  (configurables hasta 5 según la consigna).
- El servicio es **stateless**: cualquier réplica puede atender cualquier request.
- **Nginx** actúa como reverse proxy y balanceador en el puerto `8002:8000`,
  resolviendo las réplicas vía Docker DNS (`server extract:8000 resolve`) con `least_conn`.
- Cada réplica se **registra dinámicamente en Consul** al iniciar (lifespan de FastAPI)
  con su IP de contenedor y un healthcheck HTTP contra `/health` cada 10 s.
  Al detenerse se desregistra. Si Consul no responde, el servicio sigue funcionando
  (registro fail-soft con 3 reintentos).
- Los servicios estáticos (`pdf-validation`, `pdf-summarize`, `pdf-persistence`,
  `pdf-extract`) se registran por configuración del servidor Consul
  (`services.json` en el repositorio de summarize).

## Uso

Requiere [UV](https://docs.astral.sh/uv/).

```bash
uv sync
uv run uvicorn src.main:app --reload
```

Ejemplo:

```bash
curl -X POST http://localhost:8000/extract \
  -H "Content-Type: application/pdf" \
  --data-binary @documento.pdf
```

## Tests

```bash
uv run pytest
```

Incluye tests unitarios (servicio, adaptador pypdf, configuración, registro Consul) y de integración (endpoints HTTP con `TestClient`), con cobertura vía `pytest-cov`.

## Red compartida del ecosistema

El compose usa la red externa compartida `pdf-ecosystem-net` (variable `PDF_ECOSYSTEM_NETWORK`), donde también viven Consul, `pdf-validation`, `pdf-summarize`, `pdf-persistence` y MongoDB:

```bash
docker network create pdf-ecosystem-net   # solo la primera vez
docker compose up -d --build
```
