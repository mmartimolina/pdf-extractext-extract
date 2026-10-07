# Trabajo Pr�ctico � Test de Carga y Stress sobre Microservicio

## 1. Introducci�n

El presente trabajo pr�ctico aborda la transformaci�n de una funcionalidad de extracci�n de texto desde archivos PDF en un microservicio independiente, stateless y preparado para ser sometido a pruebas de carga y stress.

El microservicio desarrollado recibe un archivo PDF mediante `POST /extract`, extrae su contenido textual y devuelve una respuesta JSON con el texto obtenido y la cantidad de p�ginas procesadas.

La implementaci�n utiliza FastAPI y `pypdf`, se ejecuta mediante Docker y define l�mites expl�citos de recursos mediante Docker Compose.

## 2. Objetivo

Los objetivos principales son:

- Implementar un microservicio dedicado exclusivamente a la extracci�n de texto desde PDF.
- Mantener el servicio stateless.
- Exponer el endpoint obligatorio `POST /extract`.
- Validar entradas inv�lidas y archivos que superen el tama�o m�ximo permitido.
- Contenerizar la aplicaci�n mediante Docker.
- Definir l�mites de CPU y memoria.
- Ejecutar pruebas de carga mediante k6 y Vegeta.
- Analizar las m�tricas obtenidas.
- Dejar documentado el procedimiento de ejecuci�n y evaluaci�n.

## 3. Arquitectura

La soluci�n separa la responsabilidad de extracci�n en diferentes capas:

```text
src/
+-- api/
�   +-- routes.py
+-- service/
�   +-- extraction.py
+-- infrastructure/
�   +-- pypdf_extractor.py
+-- domain/
�   +-- models.py
�   +-- errors.py
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

Se implement� un endpoint de healthcheck:

GET /health

que permite verificar que el servicio se encuentra operativo.

5. Validaciones

El microservicio contempla:

Validaci�n del tipo MIME application/pdf.
Rechazo de requests con body vac�o.
L�mite configurable de tama�o mediante MAX_PDF_SIZE_BYTES.
Valor predeterminado de 20 MB.
Rechazo temprano cuando el Content-Length supera el l�mite.
Control del tama�o tambi�n durante la lectura del body.
Detecci�n de PDFs inv�lidos o corruptos.
Manejo de PDFs cifrados que no pueden procesarse.

Estas validaciones evitan procesar entradas que no cumplen el contrato del servicio y reducen el consumo innecesario de recursos.

6. Procesamiento

La extracci�n se realiza utilizando pypdf.

Debido a que la operaci�n de extracci�n es s�ncrona, se ejecuta fuera del event loop mediante un threadpool. De esta forma, una extracci�n PDF no bloquea directamente el event loop de FastAPI.

El servicio no persiste los archivos ni los resultados.

7. Tests

Se implementaron pruebas automatizadas para:

Healthcheck.
Extracci�n exitosa.
Validaci�n del content type.
Body vac�o.
PDF inv�lido.
PDF cifrado.
L�mite de tama�o.
Validaci�n mediante Content-Length.
Lectura del body excediendo el l�mite.
Servicio de extracci�n.
Adaptador pypdf.
Configuraci�n.

Los tests permiten verificar tanto la l�gica de negocio como el comportamiento HTTP del microservicio.

8. Docker

La aplicaci�n se contiene mediante un Dockerfile basado en Python 3.13 slim.

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

Docker Compose establece los siguientes l�mites por instancia:

deploy:
  resources:
    limits:
      cpus: "1.0"
      memory: 1G

Adem�s, se configura:

MAX_PDF_SIZE_BYTES=20971520

equivalente a 20 MB.

El servicio posee un healthcheck contra:

GET /health
10. Prueba funcional en Docker

Se verific� el funcionamiento real del contenedor utilizando un PDF de prueba.

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

Se configur� un escenario Spike Test con:

10 segundos hasta 100 VUs.
20 segundos manteniendo 100 VUs.
10 segundos de descenso hasta 0 VUs.
Duraci�n total: 40 segundos.

La configuraci�n se encuentra en:

tests/load/k6-spike.js
Resultado registrado

En una ejecuci�n de 40 segundos se obtuvieron:

M�trica    Resultado
Iteraciones    6.976
Requests aproximadas    6.976
Throughput    174,37 req/s
VUs m�ximos    100
p50    483,22 ms
p90    763,86 ms
p95    816,39 ms
M�ximo    1,06 s
Requests fallidas    0%
Checks exitosos    100%

Estos resultados fueron obtenidos utilizando tests/sample.pdf, un PDF peque�o de prueba de 852 bytes.

Por lo tanto, no deben interpretarse como equivalentes al benchmark realizado con los PDFs oficiales de stress del trabajo pr�ctico.

## 12. Prueba de carga con Vegeta

Se ejecutó una carga constante de:

- 50 requests por segundo
- durante 30 segundos
- total: 1500 requests

### Resultado obtenido

| Métrica | Resultado |
|---|---:|
| Requests | 1500 |
| Rate | 50,03 req/s |
| Throughput | 50,02 req/s |
| Duración | 29,985 s |
| Latencia mínima | 4,273 ms |
| Latencia media | 5,304 ms |
| p50 | 5,049 ms |
| p90 | 6,201 ms |
| p95 | 6,651 ms |
| p99 | 8,235 ms |
| Máxima | 25,652 ms |
| Éxito | 100% |
| HTTP 200 | 1500 |
| Errores | 0 |

El reporte completo se encuentra en:

`tests/load/vegeta-report.txt`

La prueba utilizó `tests/sample.pdf`, un archivo de 852 bytes.

13. An�lisis

Los resultados obtenidos muestran que, para el PDF peque�o utilizado durante estas pruebas, el servicio pudo sostener una carga constante de aproximadamente 50 requests por segundo durante 30 segundos sin registrar errores HTTP.

En la prueba Spike tambi�n se alcanzaron 100 usuarios virtuales sin errores, manteniendo el porcentaje de checks exitosos en 100%.

Sin embargo, el tama�o del PDF tiene una influencia importante sobre el costo de extracci�n. Por este motivo, estos resultados no permiten concluir por s� solos el comportamiento del sistema frente a los PDFs de mayor tama�o incluidos en el conjunto oficial de stress.

Para una evaluaci�n representativa del escenario final ser�a necesario ejecutar nuevamente las pruebas utilizando los archivos PDF oficiales proporcionados para el trabajo pr�ctico.

14. Consideraciones de escalabilidad

La arquitectura propuesta permite ejecutar m�ltiples instancias del microservicio debido a que no depende de estado local persistente.

El servicio no utiliza sesiones ni almacenamiento compartido para procesar una extracci�n.

Por lo tanto, puede ser colocado detr�s de un balanceador o reverse proxy y escalar horizontalmente mediante m�ltiples r�plicas.

Docker Compose permite definir la instancia y sus l�mites de recursos. La estrategia de escalamiento horizontal puede utilizar hasta cinco r�plicas seg�n los requisitos del trabajo pr�ctico.

15. Posibles optimizaciones

Como l�neas futuras de optimizaci�n se consideran:

Ejecutar m�ltiples r�plicas detr�s de un balanceador.
Controlar la concurrencia de extracci�n.
Incorporar backpressure.
Rechazar nuevas solicitudes cuando la cola alcance un l�mite.
Responder con 429 o 503 cuando no existan recursos disponibles.
Utilizar PDFs de stress reales durante la evaluaci�n.
Analizar consumo de CPU y memoria por instancia.
Comparar diferentes cantidades de r�plicas.
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
17. Conclusi�n

Se implement� un microservicio independiente para extracci�n de texto desde PDF, desacoplado del sistema monol�tico original.

La soluci�n cumple con el endpoint requerido, utiliza procesamiento stateless, incorpora validaciones, manejo de errores, pruebas automatizadas, contenerizaci�n y l�mites expl�citos de recursos.

Las pruebas realizadas con k6 y Vegeta permitieron verificar el comportamiento del servicio bajo carga utilizando un PDF peque�o de prueba. En ambos casos se obtuvo un 100% de �xito y no se registraron errores HTTP.

Los resultados constituyen una primera evaluaci�n del comportamiento del microservicio. Para completar una evaluaci�n de stress representativa del trabajo pr�ctico, deben utilizarse los PDFs oficiales de mayor tama�o proporcionados por la c�tedra y, posteriormente, comparar los resultados obtenidos con los valores de referencia.

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
