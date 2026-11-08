# CoffeeCare AI

Prototipo académico para orientar a agricultores sobre el estado de hojas y frutos de café. La versión web usa el modelo A calibrado. [Abrir CoffeeCare](https://coffeecare-ai.streamlit.app/)

## Usuarios y flujo

- **Farmer:** toma o sube una foto, autoriza guardarla y recibe una orientación. Puede consultar su historial y las revisiones de sus fotos.
- **Admin autorizado:** abre la bandeja **Inciertos pendientes**, consulta la foto privada y registra una clasificación revisada o pide más información.
- **Resultado incierto:** si la confianza queda por debajo del 61,03%, la app guarda el caso sin mostrar una clase y lo deja pendiente de revisión.

Streamlit valida la imagen y usa la API HTTP para inferencia cuando está configurada. La API verifica la sesión con Supabase Auth y ejecuta el modelo PyTorch. PostgreSQL guarda las observaciones y revisiones, y Storage guarda las fotos en un depósito privado. Las políticas de acceso limitan cada Farmer a sus registros y permiten la revisión al rol Admin.

## Ejecutar localmente

1. Clona este repositorio y entra en su carpeta. Usa Python 3.12 y un entorno virtual.
2. Instala las dependencias con `python -m pip install -r requirements.txt`.
3. Usa el proyecto CoffeeCare existente si ya tienes acceso. Para un proyecto **nuevo**, ejecuta [el SQL inicial](supabase/bootstrap.sql) una vez en SQL Editor. En Auth, configura el Site URL para que la confirmación de correo vuelva a la app. Crea una cuenta Farmer de prueba y asigna `app_metadata.role=admin` a la cuenta autorizada mediante administración de Supabase.
4. Crea `.streamlit/secrets.toml` con `SUPABASE_URL` y `SUPABASE_KEY` del proyecto. Usa la clave publicable o anon. Mantén el archivo de secretos fuera de Git.
5. Ejecuta `python -m streamlit run app.py`. La app carga `model/model_a_calibrated.pt`, incluido en el repositorio.

## Estructura

| Ruta | Responsabilidad |
| --- | --- |
| `app.py` | Entrada de Streamlit y flujo Farmer–Admin |
| `api.py` | Entrada ASGI de FastAPI, autenticación y contrato HTTP |
| `coffeecare/` | Procesamiento de imágenes, inferencia y componentes de la interfaz |
| `model/` | Modelo A calibrado para CPU |
| `supabase/` | SQL inicial para instalaciones nuevas |
| `tests/` | Pruebas del contrato HTTP y de inferencia con fotos auditadas |
| `docs/` | Guion de demostración, evidencias y matriz de confusión |

## API HTTP

Instala `requirements-api.txt` y configura `SUPABASE_URL` y `SUPABASE_KEY` como variables de entorno del servidor de la API. Ejecuta `python -m uvicorn api:app --host 127.0.0.1 --port 8000`. La documentación OpenAPI queda disponible en `/docs` y `GET /health` devuelve el estado y la versión del modelo.

`POST /predict` recibe los bytes de una foto JPEG, PNG o WebP de hasta 8 MB con el token de sesión en el encabezado `Authorization`. El servicio devuelve la clase, confianza, probabilidades, estado de abstención y versión del modelo. Para un caso incierto devuelve `label: "Uncertain"` y probabilidades vacías. El servicio de predicción procesa la imagen en memoria. Streamlit guarda las observaciones según el consentimiento.

```bash
curl --fail-with-body http://127.0.0.1:8000/predict \
  -H "Authorization: Bearer ${COFFEECARE_ACCESS_TOKEN}" \
  -H "Content-Type: image/jpeg" \
  --data-binary @foto.jpg
```

Añade `PREDICTION_API_URL = "http://127.0.0.1:8000"` a los secretos locales de Streamlit. Para producción usa la URL HTTPS del servicio. Si omites ese secreto, Streamlit ejecuta el modelo localmente.

Instala `requirements-api.txt` y ejecuta `python -m unittest discover -s tests -v` desde la raíz para comprobar el contrato HTTP con Auth simulado. Configura `COFFEECARE_VALIDATION_ZIP` con la ruta al ZIP auditado de CoffeeCare para ejecutar también las pruebas de inferencia con las dos fotos reales.

El archivo `render.yaml` configura un servicio web gratuito de Render. Proporciona la URL y la clave publicable del mismo proyecto Supabase al crear el servicio. Después de comprobar `/health`, configura la URL HTTPS de Render en los secretos de Streamlit. El servicio gratuito puede tardar en despertar tras un periodo sin uso.

## Modelo y evaluación

MobileNetV3-Small inicializado con pesos de ImageNet, elegido por su tamaño para inferencia en CPU. Distingue cinco estados de hoja (sana, roya, Cercospora, Phoma y Minador) y tres de fruto (sano, broca y daño visible). Los datos combinan BRACOL, una selección auditada de Project-AgML y fuentes de frutos. Se revisaron duplicados y grupos, y se reservaron validación, calibración y prueba. El entrenamiento usó lotes balanceados con cuatro ejemplos por clase.

| Configuración | Exactitud en validación | Macro-F1 en validación |
|---|---:|---:|
| Control reforzado | 88,12% | 83,16% |
| **A, Focal Loss** | **91,09%** | 84,58% |
| B, clasificador de 512 neuronas | 90,10% | **85,52%** |

Se eligió A de la época 17 por su exactitud en validación. Se probaron datos adicionales, EMA y tasas separadas. La variante B con tasas separadas se detuvo en la época 5 al quedar por debajo de B original en Macro-F1 a esa altura.

**Prueba interna reservada de A.** 174/199 aciertos (87,44%) y Macro-F1 de 79,32%. Broca acertó 38/38, Minador 7/11 y Cercospora 1/4. Con el umbral calibrado se clasificaron 180/199 fotos (90,45% de cobertura) y se acertaron 163/180 (90,56%). Los 19 casos restantes quedaron inciertos. Los tamaños por clase y las diferencias de iluminación, enfoque, fondo y procedencia limitan las conclusiones para fotos de finca en Puerto Rico. Las orientaciones tienen carácter provisional y el modelo cubre solo las ocho clases indicadas.

[Cuaderno de entrenamiento y evaluación](https://colab.research.google.com/drive/1Sz5M7k-PVridMZEGIxG9eCvAIcwcyUW6) · [Comparación A/B](https://drive.google.com/file/d/1DJiA5GNXDGugX144IsynybZ2GTYfFEuF/view) · [Modelo calibrado, métricas por clase y matriz final](https://drive.google.com/drive/folders/1FLFtL777bV7-6leB2OZk7sWA211-3DSU)

## Demostración y comprobaciones

Consulta el [guion de demostración y evidencias para la rúbrica](docs/DEMO.md). El flujo de revisión de un caso incierto ya se verificó en la versión publicada con el folio `409d68`. La validación de cámara en un celular real y las comprobaciones de esta revisión en producción se registran por separado de las pruebas locales.
