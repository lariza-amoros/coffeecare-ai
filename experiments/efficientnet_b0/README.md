# Experimento EfficientNet-B0

Este experimento usa la receta auditada de CoffeeCare en una copia temporal. Compara EfficientNet-B0 con el MobileNet A publicado sobre la misma validación de 202 fotos. La rama conserva el código de la app y de la API tal como está en `main`.

## Ejecutar en Colab

1. Selecciona un entorno con GPU en el cuaderno de entrenamiento y monta Google Drive.
2. Coloca `run_efficientnet_b0.py` y el checkpoint `model/model_a_calibrated.pt` del repositorio en `/content`. Si ya tienes una copia de la rama en Colab, puedes indicar las rutas de esa copia.
3. Ejecuta:

   ```bash
   !python /content/run_efficientnet_b0.py --baseline /content/model_a_calibrated.pt
   ```

Por defecto, el script lee los insumos auditados del proyecto en `/content/drive/MyDrive/CoffeeCare AI`. Usa `--project` si montaste esa carpeta con otra ruta. Deben estar disponibles `reinforce_train.py`, `load_verified_reinforcement.py`, `coffeecare_ab.py`, los dos archivos ZIP auditados y el manifiesto original que verifica el cargador. El script comprueba los hashes antes de entrenar.

## Configuración y resultados

- **Entrada y clases.** RGB a 224 × 224, con el mismo redimensionamiento, normalización, orden de ocho clases y manifiesto del modelo A.
- **Entrenamiento.** Pesos iniciales de ImageNet. Cuatro épocas con la base congelada y una tasa de `1e-3` para la cabeza. Después se ajustan los últimos dos bloques de características con `1e-5` y la cabeza con `1e-4`. Usa Focal Loss con `gamma=2` y lotes balanceados por clase y familia.
- **Comparación.** Genera métricas, predicciones y matrices de confusión de validación para A y B0 en `runs/efficientnet-b0-…` dentro de Drive. Para Minador, compara falsos positivos, precisión y sensibilidad además de F1 macro.
- **Candidato.** Guarda el mejor checkpoint de validación sin calibrar. Los conjuntos de calibración y prueba se reservan para una fase posterior. Antes de considerar el despliegue, evalúa también fotos etiquetadas de celular.
