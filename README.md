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
└── main.py                 # create_app(): composition root
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

| Variable             | Default              | Descripción                     |
|----------------------|----------------------|---------------------------------|
| `MAX_PDF_SIZE_BYTES` | `20971520` (20 MB)   | Tamaño máximo de PDF aceptado   |

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

Incluye tests unitarios (servicio, adaptador pypdf, configuración) y de integración (endpoints HTTP con `TestClient`), con cobertura vía `pytest-cov`.
