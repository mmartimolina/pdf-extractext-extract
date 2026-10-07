# Trabajo Práctico — Test de Carga y Stress sobre Microservicio

## 1. Introducción

El presente trabajo práctico aborda la transformación de una funcionalidad de extracción de texto desde archivos PDF en un microservicio independiente, stateless y preparado para ser sometido a pruebas de carga y stress.

El microservicio desarrollado recibe un archivo PDF mediante `POST /extract`, extrae su contenido textual y devuelve una respuesta JSON con el texto obtenido y la cantidad de páginas procesadas.

La implementación utiliza FastAPI y `pypdf`, se ejecuta mediante Docker y define límites explícitos de recursos mediante Docker Compose.

## 2. Objetivo

Los objetivos principales son:

- Implementar un microservicio dedicado exclusivamente a la extracción de texto desde PDF.
- Mantener el servicio stateless.
- Exponer el endpoint obligatorio `POST /extract`.
- Validar entradas inválidas y archivos que superen el tamaño máximo permitido.
- Contenerizar la aplicación mediante Docker.
- Definir límites de CPU y memoria.
- Ejecutar pruebas de carga mediante k6 y Vegeta.
- Analizar las métricas obtenidas.
- Dejar documentado el procedimiento de ejecución y evaluación.

## 3. Arquitectura

La solución separa la responsabilidad de extracción en diferentes capas:

```text
src/
+-- api/
¦   +-- routes.py
+-- service/
¦   +-- extraction.py
+-- infrastructure/
¦   +-- pypdf_extractor.py
+-- domain/
¦   +-- models.py
¦   +-- errors.py
+-- config.py
+-- main.py
4. Endpoint principal
POST /extract

El endpoint recibe el PDF mediante un body binario:

POST /extract
Content-Type: application/pdf

Respuesta exitosa:

{
  "content": "Hello World\nHello World",
  "page_count": 2
}
GET /health

Se implementó un endpoint de healthcheck:

GET /health

que permite verificar que el servicio se encuentra operativo.

5. Validaciones

El microservicio contempla:

Validación del tipo MIME application/pdf.
Rechazo de requests con body vacío.
Límite configurable de tamaño mediante MAX_PDF_SIZE_BYTES.
Valor predeterminado de 20 MB.
Rechazo temprano cuando el Content-Length supera el límite.
Control del tamaño también durante la lectura del body.
Detección de PDFs inválidos o corruptos.
Manejo de PDFs cifrados que no pueden procesarse.

Estas validaciones evitan procesar entradas que no cumplen el contrato del servicio y reducen el consumo innecesario de recursos.

6. Procesamiento

La extracción se realiza utilizando pypdf.

Debido a que la operación de extracción es síncrona, se ejecuta fuera del event loop mediante un threadpool. De esta forma, una extracción PDF no bloquea directamente el event loop de FastAPI.

El servicio no persiste los archivos ni los resultados.

7. Tests

Se implementaron pruebas automatizadas para:

Healthcheck.
Extracción exitosa.
Validación del content type.
Body vacío.
PDF inválido.
PDF cifrado.
Límite de tamaño.
Validación mediante Content-Length.
Lectura del body excediendo el límite.
Servicio de extracción.
Adaptador pypdf.
Configuración.

Los tests permiten verificar tanto la lógica de negocio como el comportamiento HTTP del microservicio.

8. Docker

La aplicación se contiene mediante un Dockerfile basado en Python 3.13 slim.

El contenedor:

Instala las dependencias mediante uv.
Ejecuta Uvicorn.
Expone el puerto 8000.
Utiliza un usuario no root.
Configura PYTHONDONTWRITEBYTECODE.
Configura PYTHONUNBUFFERED.

El servicio puede iniciarse mediante:

docker compose up --build
9. Recursos

Docker Compose establece los siguientes límites por instancia:

deploy:
  resources:
    limits:
      cpus: "1.0"
      memory: 1G

Además, se configura:

MAX_PDF_SIZE_BYTES=20971520

equivalente a 20 MB.

El servicio posee un healthcheck contra:

GET /health
10. Prueba funcional en Docker

Se verificó el funcionamiento real del contenedor utilizando un PDF de prueba.

Request:

curl.exe -X POST http://localhost:8000/extract \
  -H "Content-Type: application/pdf" \
  --data-binary "@tests/sample.pdf"

Respuesta obtenida:

{
  "content": "Hello World\nHello World",
  "page_count": 2
}

Esto confirma que el endpoint funciona correctamente dentro del contenedor.

11. Prueba de carga con k6

Se configuró un escenario Spike Test con:

10 segundos hasta 100 VUs.
20 segundos manteniendo 100 VUs.
10 segundos de descenso hasta 0 VUs.
Duración total: 40 segundos.

La configuración se encuentra en:

tests/load/k6-spike.js
Resultado registrado

En una ejecución de 40 segundos se obtuvieron:

Métrica    Resultado
Iteraciones    6.976
Requests aproximadas    6.976
Throughput    174,37 req/s
VUs máximos    100
p50    483,22 ms
p90    763,86 ms
p95    816,39 ms
Máximo    1,06 s
Requests fallidas    0%
Checks exitosos    100%

Estos resultados fueron obtenidos utilizando tests/sample.pdf, un PDF pequeño de prueba de 852 bytes.

Por lo tanto, no deben interpretarse como equivalentes al benchmark realizado con los PDFs oficiales de stress del trabajo práctico.

12. Prueba de carga con Vegeta

Se ejecutó una carga constante de:

50 requests/segundo
durante 30 segundos

Esto produjo un total esperado de aproximadamente:

50 × 30 = 1500 requests
Resultado obtenido
Métrica    Resultado
Requests    1500
Rate    50,03 req/s
Throughput    50,02 req/s
Duración    29,987 s
Latencia mínima    5,035 ms
Latencia media    15,133 ms
p50    9,696 ms
p90    17,776 ms
p95    45,446 ms
p99    135,9 ms
Máxima    240,785 ms
Éxito    100%
HTTP 200    1500
Errores    0

El reporte completo se encuentra en:

tests/load/vegeta-report.txt

Al igual que en la prueba de k6, esta ejecución utilizó un PDF pequeño de prueba de 852 bytes.

13. Análisis

Los resultados obtenidos muestran que, para el PDF pequeño utilizado durante estas pruebas, el servicio pudo sostener una carga constante de aproximadamente 50 requests por segundo durante 30 segundos sin registrar errores HTTP.

En la prueba Spike también se alcanzaron 100 usuarios virtuales sin errores, manteniendo el porcentaje de checks exitosos en 100%.

Sin embargo, el tamaño del PDF tiene una influencia importante sobre el costo de extracción. Por este motivo, estos resultados no permiten concluir por sí solos el comportamiento del sistema frente a los PDFs de mayor tamaño incluidos en el conjunto oficial de stress.

Para una evaluación representativa del escenario final sería necesario ejecutar nuevamente las pruebas utilizando los archivos PDF oficiales proporcionados para el trabajo práctico.

14. Consideraciones de escalabilidad

La arquitectura propuesta permite ejecutar múltiples instancias del microservicio debido a que no depende de estado local persistente.

El servicio no utiliza sesiones ni almacenamiento compartido para procesar una extracción.

Por lo tanto, puede ser colocado detrás de un balanceador o reverse proxy y escalar horizontalmente mediante múltiples réplicas.

Docker Compose permite definir la instancia y sus límites de recursos. La estrategia de escalamiento horizontal puede utilizar hasta cinco réplicas según los requisitos del trabajo práctico.

15. Posibles optimizaciones

Como líneas futuras de optimización se consideran:

Ejecutar múltiples réplicas detrás de un balanceador.
Controlar la concurrencia de extracción.
Incorporar backpressure.
Rechazar nuevas solicitudes cuando la cola alcance un límite.
Responder con 429 o 503 cuando no existan recursos disponibles.
Utilizar PDFs de stress reales durante la evaluación.
Analizar consumo de CPU y memoria por instancia.
Comparar diferentes cantidades de réplicas.
16. Reproducibilidad
Instalar dependencias
uv sync
Ejecutar tests
pytest
Ejecutar localmente
uv run uvicorn src.main:app --reload
Ejecutar Docker Compose
docker compose up --build
Ejecutar k6
k6 run tests/load/k6-spike.js
Ejecutar Vegeta

El proyecto incluye:

tests/load/vegeta-target.txt

y el reporte generado:

tests/load/vegeta-report.txt
17. Conclusión

Se implementó un microservicio independiente para extracción de texto desde PDF, desacoplado del sistema monolítico original.

La solución cumple con el endpoint requerido, utiliza procesamiento stateless, incorpora validaciones, manejo de errores, pruebas automatizadas, contenerización y límites explícitos de recursos.

Las pruebas realizadas con k6 y Vegeta permitieron verificar el comportamiento del servicio bajo carga utilizando un PDF pequeño de prueba. En ambos casos se obtuvo un 100% de éxito y no se registraron errores HTTP.

Los resultados constituyen una primera evaluación del comportamiento del microservicio. Para completar una evaluación de stress representativa del trabajo práctico, deben utilizarse los PDFs oficiales de mayor tamaño proporcionados por la cátedra y, posteriormente, comparar los resultados obtenidos con los valores de referencia.

18. Archivos relevantes
Dockerfile
docker-compose.yml
pyproject.toml
src/
tests/
tests/load/k6-spike.js
tests/load/vegeta-target.txt
tests/load/vegeta-report.txt

Repositorio:

https://github.com/mmartimolina/pdf-extractext-extract
