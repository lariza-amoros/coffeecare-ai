"""Shared visual components for the CoffeeCare app."""

import base64
from functools import lru_cache
from pathlib import Path

import streamlit as st

from .core import UNCERTAIN

LABELS = {
    'Healthy': 'Hoja sin síntomas visibles de las clases evaluadas',
    'Rust': 'Roya', 'Cercospora': 'Mancha de Cercospora', 'Phoma': 'Mancha por Phoma',
    'Miner': 'Daño por minador', 'Fruit_Healthy': 'Fruto sin daño visible',
    'Fruit_Borer': 'Posible daño por broca', 'Fruit_Damaged': 'Fruto con daño visible',
    UNCERTAIN: 'Resultado incierto',
}
CONDITION_INFO = {
    'Healthy': 'Observa otras hojas si la planta presenta cambios.',
    'Rust': 'Fotografía el envés de la hoja si observas manchas o polvillo anaranjado.',
    'Cercospora': 'Toma una segunda foto de las manchas con buena luz para facilitar la revisión.',
    'Phoma': 'Registra si las manchas avanzan y si aparecen en otras hojas.',
    'Miner': 'Fotografía de cerca las zonas dañadas para facilitar la revisión.',
    'Fruit_Healthy': 'Observa otros frutos del mismo racimo si tienes dudas.',
    'Fruit_Borer': 'Fotografía de cerca cualquier orificio visible en el fruto.',
    'Fruit_Damaged': 'Fotografía el daño desde otro ángulo para facilitar la revisión.',
}

ASSETS = Path(__file__).resolve().parents[1] / "assets"


@lru_cache(maxsize=2)
def asset_uri(name):
    data = base64.b64encode((ASSETS / name).read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{data}"


def page_header(*, signed_in=False):
    st.markdown("""<style>
    .stApp {background:#fffefb;color:#342317;}
    .block-container {max-width:1180px;padding-top:3rem;padding-bottom:3rem;}
    h1,h2,h3 {color:#342317;letter-spacing:-.025em;}
    a {color:#1b492e;text-underline-offset:3px;}
    button:focus-visible,input:focus-visible,textarea:focus-visible,[role="tab"]:focus-visible {
      outline:3px solid #947238!important;outline-offset:3px!important;}
    [data-testid="stButton"] button,[data-testid="stFormSubmitButton"] button,
    [data-testid="stDownloadButton"] button,[data-testid="stButtonGroup"] button {
      min-height:46px;border-radius:10px;font-weight:650;}
    [data-testid="stTabs"] [role="tab"] {min-height:46px;font-weight:650;}
    [data-testid="stTabs"] [data-baseweb="tab-list"] {gap:1.2rem;}
    [data-testid="stVerticalBlockBorderWrapper"] {border-color:#e6d9bf;}
    .cc-brand {border-bottom:1px solid #e6d9bf;padding:.2rem 0 .8rem;margin-bottom:.5rem;}
    .cc-brand--welcome {width:fit-content;max-width:100%;margin-inline:auto;}
    .cc-brand-trigger {display:flex;align-items:center;gap:.8rem;width:fit-content;max-width:100%;
      padding:.35rem .65rem .35rem .35rem;border-radius:14px;list-style:none;cursor:pointer;}
    .cc-brand-trigger::-webkit-details-marker {display:none;}
    .cc-brand-trigger:hover,.cc-brand[open] .cc-brand-trigger {background:#f8f3e7;}
    .cc-brand-trigger:focus-visible {outline:3px solid #947238;outline-offset:3px;}
    .cc-brand-copy {display:grid;gap:.2rem;line-height:1.2;}
    .cc-wordmark {font-weight:750;font-size:1.6rem;letter-spacing:-.035em;color:#342317;}
    .cc-tagline {color:#1b492e;font-size:.92rem;font-weight:650;}
    .cc-subtitle {color:#654c38;font-size:.84rem;}
    .cc-emblem {width:60px;height:60px;display:block;position:relative;overflow:hidden;
      border:1px solid #e6d9bf;border-radius:50%;background:#fffefb;flex-shrink:0;}
    .cc-emblem img {position:absolute;width:320%;max-width:none;left:-110%;top:-19%;}
    .cc-brand-chevron {width:.45rem;height:.45rem;border:solid #654c38;border-width:0 2px 2px 0;
      flex-shrink:0;transform:rotate(45deg);margin:.1rem .15rem .25rem .25rem;}
    .cc-brand[open] .cc-brand-chevron {transform:rotate(225deg);margin-block:.35rem .1rem;}
    .cc-brand-message {max-width:36ch;margin:.45rem .35rem 0;font-size:.9rem;color:#654c38;}
    .cc-photo-hero {background:#f8f3e7;border:1px solid #e6d9bf;border-radius:16px;
      overflow:hidden;margin:0 0 .4rem;}
    .cc-photo-hero img {display:block;width:100%;aspect-ratio:2.55;object-fit:cover;object-position:center;}
    .cc-photo-caption {padding:.45rem .9rem;color:#654c38;font-size:.82rem;}
    .cc-steps {display:grid;grid-template-columns:repeat(3,1fr);gap:10px;padding:0;list-style:none;}
    .cc-steps li {background:#f8f3e7;border:1px solid #e6d9bf;border-radius:12px;padding:12px;}
    .cc-steps strong {display:block;color:#1b492e;margin-bottom:4px;}
    .cc-steps span {font-size:.94rem;}
    @media(max-width:640px) {
      .block-container {padding:3.5rem 1rem 2rem;}
      .cc-brand {padding-bottom:.6rem;}
      .cc-emblem {width:48px;height:48px;}
      .cc-brand-trigger {gap:.6rem;}
      .cc-wordmark {font-size:1.4rem;}
      .cc-photo-hero img {aspect-ratio:1.8;}
      .cc-steps {grid-template-columns:1fr;}
      [data-testid="stTabs"] [data-baseweb="tab-list"] {gap:.65rem;}
    }
    @media(prefers-reduced-motion:reduce) {*{scroll-behavior:auto!important;}}
    </style>""", unsafe_allow_html=True)
    logo = asset_uri("coffeecare-logo.jpg")
    brand_class = "cc-brand" if signed_in else "cc-brand cc-brand--welcome"
    st.markdown(
        f'<details class="{brand_class}"><summary class="cc-brand-trigger">'
        f'<span class="cc-emblem"><img src="{logo}" alt=""></span>'
        '<span class="cc-brand-copy"><span class="cc-wordmark">CoffeeCare</span>'
        '<span class="cc-tagline">Cada hoja y cada fruto cuentan.</span>'
        '<span class="cc-subtitle">La salud de tu cafetal, a simple vista.</span></span>'
        '<span class="cc-brand-chevron" aria-hidden="true"></span></summary>'
        '<div class="cc-brand-message">Sube una foto de una hoja o un fruto de café para recibir '
        'orientación sobre lo que observas en tu cafetal.</div></details>',
        unsafe_allow_html=True,
    )


def capture_photo_example():
    photo = asset_uri("coffee-leaf-and-cherries.jpg")
    st.markdown(
        f'<figure class="cc-photo-hero"><img src="{photo}" alt="Hoja y cerezas en una misma rama de café">'
        '<figcaption class="cc-photo-caption">Imagen ilustrativa · Hoja y frutos del café</figcaption></figure>',
        unsafe_allow_html=True,
    )


def photo_steps():
    st.markdown('''<ol class="cc-steps" aria-label="Cómo analizar una foto de café">
    <li><strong>1. Encuadra una hoja o un fruto</strong><span>Acerca la cámara hasta que ocupe la mayor parte de la foto. Incluye la zona con síntomas.</span></li>
    <li><strong>2. Usa luz natural y enfoca</strong><span>Evita el contraluz y los reflejos. Para una segunda foto de una hoja, prueba con el envés.</span></li>
    <li><strong>3. Revisa la orientación</strong><span>Consulta el resultado y pide ayuda agrícola si hay dudas.</span></li>
    </ol>''',unsafe_allow_html=True)


def show_leaf(jpeg):
    """Render validated JPEG bytes without a lazy image component or a public URL."""
    encoded = base64.b64encode(jpeg).decode('ascii')
    st.markdown(f'<img src="data:image/jpeg;base64,{encoded}" alt="Foto de café de esta observación" style="display:block;max-width:100%;height:auto;border-radius:12px" />',unsafe_allow_html=True)


def model_scope():
    st.markdown("### Qué puedes revisar hoy")
    st.markdown("**Hojas:** sin síntomas visibles, roya, Cercospora, Phoma y daño por minador.")
    st.markdown("**Frutos:** sin daño visible, posible daño por broca y daño visible.")


def result_summary(result, folio):
    with st.container(border=True):
        st.subheader("Resultado de tu foto")
        if result["abstained"]:
            st.warning("Resultado incierto")
            st.write("La foto quedó pendiente de revisión. Puedes tomar otra con mejor luz y enfoque.")
        else:
            st.markdown("### " + LABELS[result["label"]])
            st.write("**Siguiente paso**")
            st.write(CONDITION_INFO[result["label"]])
        st.write(f"**Confianza del modelo** · {result['confidence']:.1%}")
        st.caption(f"Folio {folio} · Consulta la observación en Historial y revisión.")
