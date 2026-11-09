"""Render the archived Model A evaluation separately from live observations."""

from pathlib import Path

import pandas as pd
import streamlit as st


EVALUATION = Path(__file__).resolve().parents[1] / "docs" / "evaluation"
CLASS_NAMES = (
    "Hoja sin síntomas", "Roya", "Cercospora", "Phoma", "Minador",
    "Fruto sin daño", "Broca", "Fruto dañado",
)


@st.cache_data
def load_test_evidence():
    matrix = pd.read_csv(EVALUATION / "test-confusion-matrix.csv", index_col=0)
    correct = pd.Series(matrix.to_numpy().diagonal(), index=matrix.index)
    support = matrix.sum(axis=1)
    predicted = matrix.sum(axis=0)
    precision = correct.div(predicted.where(predicted > 0)).fillna(0)
    recall = correct.div(support.where(support > 0)).fillna(0)
    f1 = (2 * precision * recall).div((precision + recall).where(precision + recall > 0)).fillna(0)
    table = pd.DataFrame({"Fotos": support, "Precisión": precision, "Recall": recall, "F1": f1})
    table.index = pd.Index(CLASS_NAMES, name="Clase")
    return table, int(correct.sum()), int(support.sum()), int(support.max())


def render_model_evidence():
    st.subheader("Evaluación del modelo A")
    st.caption("MobileNetV3-Small · a-final-20261108-045022 · evaluación archivada")
    table, correct, total, majority = load_test_evidence()
    validation, test, macro_f1 = st.columns(3)
    validation.metric("Exactitud en validación", "91,09%", "184 de 202", delta_color="off")
    test.metric("Exactitud en prueba", f"{correct / total:.2%}", f"{correct} de {total}", delta_color="off")
    macro_f1.metric("F1 macro en prueba", f"{table['F1'].mean():.2%}")
    st.write(f"En la prueba, predecir siempre Phoma (clase mayoritaria) daría "
             f"{majority}/{total} aciertos ({majority / total:.2%}).")
    st.write("Con el umbral calibrado, el modelo acertó en 163 de las 180 fotos que clasificó "
             "(90,56% de exactitud con 90,45% de cobertura). Quedaron 19 sin clasificación automática.")

    st.markdown("#### Matriz de confusión y métricas por clase")
    st.image(str(EVALUATION / "test-confusion-matrix.svg"), width="stretch")
    st.caption("Filas: clase real. Columnas: clase predicha. Se muestra la clase de mayor puntuación antes de aplicar el umbral.")
    st.dataframe(table.assign(**{name: table[name].map("{:.1%}".format) for name in ("Precisión", "Recall", "F1")}),
                 width="stretch")
    st.download_button("Descargar matriz de prueba CSV", (EVALUATION / "test-confusion-matrix.csv").read_bytes(),
                       "coffeecare-test-confusion-matrix.csv", "text/csv")
    st.warning("En la prueba, 3 de 4 fotos de Cercospora se confundieron con Phoma y 7 de 55 fotos de "
               "Phoma se clasificaron como minador. Queda por validar el desempeño con fotos de fincas de Puerto Rico.")

    with st.expander("Más gráficas y comparación de configuraciones"):
        st.image(str(EVALUATION / "test-per-class-performance.svg"), width="stretch",
                 caption="Precisión y recall por clase en la prueba interna.")
        st.image(str(EVALUATION / "validation-confusion-matrix.svg"), width="stretch",
                 caption="Matriz de confusión de validación.")
        st.image(str(EVALUATION / "model-comparison.svg"), width="stretch",
                 caption="Comparación de configuraciones en validación.")
