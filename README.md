# CoffeeCare AI

Prototipo académico para orientar a agricultores sobre el estado de hojas y frutos de café. La versión web usa el modelo A calibrado. [Abrir CoffeeCare](https://coffeecare-ai.streamlit.app/)

## Usuarios y flujo

- **Farmer:** toma o sube una foto, autoriza guardarla y recibe una orientación. Puede consultar su historial y las revisiones de sus fotos.
- **Admin autorizado:** abre la bandeja **Inciertos pendientes**, consulta la foto privada y registra una clasificación revisada o pide más información.
- **Resultado incierto:** si la confianza queda por debajo del 61,03%, la app guarda el caso sin mostrar una clase y lo deja pendiente de revisión.

Streamlit valida la imagen y ejecuta el modelo PyTorch en el servidor. Supabase Auth valida la sesión. PostgreSQL guarda las observaciones y revisiones, y Storage guarda las fotos en un depósito privado. Las políticas de acceso limitan cada Farmer a sus registros y permiten la revisión al rol Admin. La interfaz de inferencia actual es la función Python `predict` llamada por Streamlit.

## Ejecutar localmente

1. Clona este repositorio y entra en su carpeta. Usa Python 3.12 y un entorno virtual.
2. Instala las dependencias con `python -m pip install -r requirements.txt`.
3. Configura un proyecto Supabase con las tablas `observations` y `reviews`, el depósito privado `coffee-photos`, las políticas de acceso y las restricciones de las ocho clases más el estado `Uncertain`. Usa el proyecto de CoffeeCare si ya tienes acceso.
4. Crea `.streamlit/secrets.toml` con `SUPABASE_URL` y `SUPABASE_KEY` del proyecto. Usa la clave publicable o anon. Mantén el archivo de secretos fuera de Git.
5. Ejecuta `python -m streamlit run app.py`. La app carga `model_a_calibrated.pt`, incluido en el repositorio.

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

1. Entra como Farmer desde un celular y sube una foto. Comprueba la orientación, la confianza y la entrada en el historial.
2. Sube un caso de baja confianza. Verifica que se muestre **Resultado incierto** y se guarde como pendiente. Entra como Admin, abre la bandeja, registra una revisión y vuelve a Farmer para comprobar que aparece.
3. Prueba un archivo de imagen inválido y comprueba que se muestre un mensaje comprensible.
4. Presenta la arquitectura, la comparación A/B y la matriz final. Usa fotos nuevas de celular para explorar el efecto de luz y encuadre, y registra los resultados como una prueba exploratoria.

Se verificaron localmente dos fotos con el modelo real (una aceptada y una incierta), la respuesta a una imagen inválida y la presentación en Streamlit. Se verificaron en Supabase la escritura del caso incierto, el aislamiento Farmer y la revisión Admin mediante una transacción de prueba. El recorrido autenticado completo en la web y la cámara de un celular quedan pendientes.
