"""Shared, lightweight farmer-facing presentation. Static HTML only."""
import streamlit as st

LABELS={'Healthy':'Sin síntomas de las clases entrenadas','Rust':'Roya','Cercospora':'Mancha de Cercospora'}

def page_header(demo=False):
    st.markdown('''<style>
    .stApp {background:#f6f8f3;color:#183329;}
    .block-container {max-width:1040px;padding-top:2rem;padding-bottom:3rem;}
    h1,h2,h3 {color:#153e2b;letter-spacing:-.025em;}
    p,li,label {font-size:1rem;line-height:1.6;}
    a {color:#175b3a;text-decoration:underline;text-underline-offset:3px;}
    button:focus-visible,input:focus-visible,textarea:focus-visible,[role="tab"]:focus-visible {
      outline:3px solid #a15c00!important;outline-offset:3px!important;}
    [data-testid="stButton"] button,[data-testid="stFormSubmitButton"] button,
    [data-testid="stDownloadButton"] button {min-height:48px;border-radius:12px;font-weight:650;}
    [data-testid="stTextInput"] input {min-height:48px;font-size:1rem;}
    [data-testid="stTabs"] [role="tab"] {min-height:48px;font-weight:650;padding:0 14px;}
    [data-testid="stFileUploader"] {border-radius:16px;}
    .cc-hero {display:flex;align-items:center;gap:22px;padding:24px 28px;border-radius:24px;
      background:#e6efdf;border:1px solid #ceddc5;margin:8px 0 24px;overflow:hidden;}
    .cc-hero-copy {flex:1;min-width:0;}
    .cc-hero h2 {font-size:clamp(1.6rem,4vw,2.2rem);line-height:1.15;margin:8px 0 12px;}
    .cc-hero p {color:#294a39;margin:0;max-width:540px;}
    .cc-tag {font-size:.8rem;font-weight:750;letter-spacing:.09em;text-transform:uppercase;}
    .cc-art {width:170px;flex-shrink:0;}
    .cc-steps {display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:12px 0 24px;padding:0;list-style:none;}
    .cc-steps li {background:white;border:1px solid #d7e1d1;border-radius:16px;padding:16px;}
    .cc-steps strong {display:block;color:#194b32;margin-bottom:5px;}
    .cc-steps span {display:block;color:#42594a;font-size:.94rem;}
    @media(max-width:600px) {
      .block-container {padding:1rem 1rem 2rem;}
      .cc-hero {padding:20px;gap:8px;}.cc-art {width:90px;}
      .cc-steps {grid-template-columns:1fr;gap:8px;}.cc-steps li {padding:12px 16px;}
    }
    @media(prefers-reduced-motion:reduce) {*{scroll-behavior:auto!important;}}
    </style>''',unsafe_allow_html=True)
    st.title('CoffeeCare AI')
    tag='Prueba el modelo' if demo else 'Tu cafetal, a mano'
    st.markdown(f'''<section class="cc-hero" aria-label="Bienvenida a CoffeeCare">
    <div class="cc-hero-copy"><div class="cc-tag">{tag}</div>
    <h2>Cuida tu cafetal,<br>hoja por hoja.</h2>
    <p>Toma una foto clara y recibe una orientación sobre roya y Cercospora. Conserva tus observaciones y pide una revisión cuando la necesites.</p></div>
    <svg class="cc-art" viewBox="0 0 180 180" aria-hidden="true" focusable="false" xmlns="http://www.w3.org/2000/svg">
    <circle cx="92" cy="89" r="77" fill="#d3e3c9"/>
    <path d="M72 156 Q82 103 125 31" fill="none" stroke="#806243" stroke-width="7" stroke-linecap="round"/>
    <path d="M90 113 C38 115 30 77 30 62 C69 63 91 79 90 113Z" fill="#346c43"/>
    <path d="M104 86 C142 96 164 74 168 54 C135 44 109 57 104 86Z" fill="#4b8051"/>
    <path d="M116 60 C82 55 77 27 81 10 C111 14 125 31 116 60Z" fill="#3b7248"/>
    <path d="M44 73 L86 108 M117 81 L154 61" stroke="#b5cf94" stroke-width="2" fill="none"/>
    <circle cx="89" cy="133" r="12" fill="#ad4231"/><circle cx="109" cy="120" r="12" fill="#c4533d"/>
    <circle cx="87" cy="129" r="3" fill="#efba9d"/><circle cx="107" cy="116" r="3" fill="#efba9d"/>
    </svg></section>''',unsafe_allow_html=True)

def photo_steps():
    st.markdown('''<ol class="cc-steps" aria-label="Cómo analizar una hoja">
    <li><strong>1. Escoge una hoja</strong><span>Una sola hoja de café. Incluye la zona con síntomas.</span></li>
    <li><strong>2. Toma una foto clara</strong><span>Luz natural, buen enfoque y sin cubrir la hoja.</span></li>
    <li><strong>3. Revisa la orientación</strong><span>Consulta el resultado y pide ayuda agrícola si hay dudas.</span></li>
    </ol>''',unsafe_allow_html=True)
