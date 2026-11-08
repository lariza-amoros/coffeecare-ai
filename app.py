import io
import uuid
from pathlib import Path
from urllib.parse import urlsplit
import httpx
import pandas as pd
import streamlit as st
from supabase import create_client
from core import CLASSES, clean_image, observation_label
from inference import load_model, predict
from admin_panel import admin_records, review_status, STATUS
from ui import page_header, photo_steps, LABELS, show_leaf, model_scope, result_summary

st.set_page_config(page_title="CoffeeCare AI", page_icon="🌿", layout="centered")
page_header()
st.warning("Prototipo de orientación para hojas y frutos de café. El modelo puede equivocarse incluso con confianza alta. Consulta al personal agrícola antes de tomar decisiones.")

if "SUPABASE_URL" not in st.secrets or "SUPABASE_KEY" not in st.secrets:
    st.info("Configura Supabase en los secretos de la aplicación para iniciar sesión.")
    st.stop()
# Never cache a mutable authenticated client across users.
if "sb" not in st.session_state:
    st.session_state.sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
sb = st.session_state.sb

if not sb.auth.get_session():
    login, signup = st.tabs(["Ingresar", "Crear cuenta Farmer"])
    with login, st.form("login"):
        email = st.text_input("Correo")
        password = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Ingresar",type="primary",use_container_width=True):
            try:
                sb.auth.sign_in_with_password({"email": email, "password": password})
                st.rerun()
            except Exception:
                st.error("No se pudo ingresar. Verifica tus datos y la confirmación del correo.")
    with signup, st.form("signup"):
        email_new = st.text_input("Correo nuevo")
        pass_new = st.text_input("Contraseña nueva", type="password")
        if st.form_submit_button("Crear cuenta",use_container_width=True):
            try:
                sb.auth.sign_up({"email": email_new, "password": pass_new})
                st.success("Revisa tu correo para confirmar la cuenta antes de ingresar.")
            except Exception:
                st.error("No se pudo crear la cuenta. Intenta más tarde.")
    st.stop()
try:
    user = sb.auth.get_user().user  # validate with Auth; never trust a UI role selection
    session = sb.auth.get_session()
    if session.user.app_metadata.get("role") != user.app_metadata.get("role"):
        # Authorization claims stay stale until a new JWT is issued.
        sb.auth.refresh_session()
        st.rerun()
except Exception:
    st.session_state.clear()
    st.error("La sesión expiró. Vuelve a cargar la página e ingresa.")
    st.stop()
admin = user.app_metadata.get("role") == "admin"
st.caption("Panel de administración" if admin else "Mi cafetal · Agricultor")
if st.button("Cerrar sesión"):
    sb.auth.sign_out()
    st.session_state.clear()
    st.rerun()

@st.cache_resource
def model_resource(path, mtime):
    return load_model(path)


def predict_remotely(api_url, token, raw):
    endpoint = urlsplit(api_url)
    loopback = endpoint.hostname in {"localhost", "127.0.0.1", "::1"}
    if (not endpoint.hostname or endpoint.username or endpoint.password
            or endpoint.query or endpoint.fragment
            or (endpoint.scheme != "https" and not (loopback and endpoint.scheme == "http"))):
        raise ValueError("Configura una URL HTTPS para el servicio de predicción.")
    response = httpx.post(
        api_url.rstrip("/") + "/predict", content=raw,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
        timeout=httpx.Timeout(90.0, connect=5.0, write=20.0, pool=5.0),
        follow_redirects=False,
    )
    response.raise_for_status()
    return response.json()


capture, history, roadmap = st.tabs(["Analizar foto", "Historial y revisión", "Próximos módulos"])
with capture:
    model_scope()
    photo_steps()
    st.subheader("Revisa una hoja o un fruto de tu cafetal")
    st.caption("Puedes subir una foto o usar la cámara. Para hojas, también puedes fotografiar el envés.")
    mode = st.radio("Origen", ["Subir foto", "Cámara"], horizontal=True)
    photo = st.file_uploader("Foto", type=["jpg", "jpeg", "png", "webp"]) if mode == "Subir foto" else st.camera_input("Tomar foto")
    notes = st.text_area("Observaciones del agricultor", max_chars=2000, placeholder="Ejemplo: manchas desde hace tres días, en varias hojas del mismo árbol.", help="Describe lo que observas. Evita incluir datos personales.")
    consent = st.checkbox("Autorizo almacenar esta foto para mi historial y revisión administrativa. No autoriza reutilizarla para entrenar.")
    if photo:
        try:
            raw = photo.getvalue()
            image, jpeg = clean_image(raw)
            show_leaf(jpeg)
        except Exception:
            st.error("No se puede procesar la imagen. Usa una foto válida de hasta 8 MB y 20 megapíxeles.")
            st.stop()
        path = Path(__file__).with_name("model_a_calibrated.pt")
        api_url = st.secrets.get("PREDICTION_API_URL", "").strip()
        if not api_url and not path.exists():
            st.info("Modelo entrenado pendiente. La aplicación no genera predicciones simuladas.")
        elif st.button("Analizar y guardar", disabled=not consent,type="primary",use_container_width=True):
            try:
                if api_url:
                    with st.spinner("Analizando la foto. El primer análisis puede tardar un poco."):
                        result = predict_remotely(api_url, session.access_token, raw)
                else:
                    model, meta = model_resource(str(path), path.stat().st_mtime_ns)
                    result = predict(model, meta, image)
                key = str(uuid.uuid4())
                object_path = f"{user.id}/{key}.jpg"
                sb.storage.from_("coffee-photos").upload(object_path, jpeg, {"content-type": "image/jpeg", "upsert": "false"})
                try:
                    row = dict(result, id=key, user_id=user.id, photo_path=object_path, notes=notes)
                    sb.table("observations").insert(row).execute()
                except Exception:
                    sb.storage.from_("coffee-photos").remove([object_path])
                    raise
                result_summary(result)
                st.info("Registra la ubicación y evolución de los síntomas y consulta con un agrónomo. No apliques fertilizantes o plaguicidas basándote solo en esta foto.")
            except Exception:
                st.error("No se completó el análisis o guardado. Verifica la conexión, el modelo y la configuración de Supabase.")
with history:
    st.subheader("Tu historial" if not admin else "Observaciones y revisiones")
    st.caption("Abre una observación para ver su foto y los comentarios de revisión.")
    if st.session_state.pop("review_saved",False): st.success("Revisión guardada. La predicción original se conserva.")
    try:
        size = 20
        if admin:
            admin_rows, valid = admin_records(sb,LABELS)
            if not valid: admin_rows=[]
            max_page=max(1,(len(admin_rows)+size-1)//size)
            st.session_state.history_page=min(st.session_state.get("history_page",1),max_page)
            page=st.session_state.history_page
            records=admin_rows[(page-1)*size:page*size+1]
        else:
            page = st.session_state.get("history_page", 1)
            records = sb.table("observations").select("*").order("created_at", desc=True).range((page-1)*size, page*size).execute().data
        rows = records[:size]
        previous, position, following = st.columns([1,2,1])
        if previous.button("Anterior", disabled=page<=1):
            st.session_state.history_page = page-1
            st.rerun()
        position.caption(f"Página {page} · hasta {size} observaciones")
        if following.button("Siguiente", disabled=len(records)<=size):
            st.session_state.history_page = page+1
            st.rerun()
        if not rows:
            st.info('No hay observaciones que coincidan con estos filtros.' if admin else 'Todavía no hay fotos en tu historial. Analiza una hoja para guardar tu primera observación.')
        else:
            st.caption('Fechas en hora de Puerto Rico. Los resultados son orientativos.')
            for record in rows:
                date = pd.to_datetime(record['created_at'],utc=True).tz_convert('America/Puerto_Rico').strftime('%d/%m/%Y %H:%M')
                with st.container(border=True):
                    label = observation_label(record)
                    st.markdown(f"**{LABELS.get(label,label)}**")
                    st.caption(date)
                    if admin:
                        st.caption(f"Agricultor: {record['user_id']} · Folio: {record['id']}")
                        st.write('Estado: ' + STATUS[review_status(record)])
                    st.write(f"Puntuación del modelo: {record['confidence']:.1%}")
                    if not record['abstained']:
                        st.write('Orientación disponible')
                    if record.get('notes'): st.write(record['notes'])
                    if st.button('Abrir observación',key='open_'+record['id']):
                        st.session_state.selected_observation = record['id']
                        st.rerun()
            frame = pd.DataFrame(rows).drop(columns=["probabilities", "photo_path"], errors="ignore")
            frame["label"] = [observation_label(record) for record in rows]
            # Prevent spreadsheet formula execution in exported free text.
            frame = frame.map(lambda x: "'"+x if isinstance(x,str) and x[:1] in ("=","+","-","@","\t","\r") else x)
            st.download_button("Reporte CSV de esta página", frame.to_csv(index=False).encode("utf-8-sig"), "coffee-report.csv", "text/csv")
            selected = st.session_state.get('selected_observation')
            if selected not in {r['id'] for r in rows}: selected = rows[0]['id']
            row = next(r for r in rows if r['id']==selected)
            st.subheader('Detalle de la observación')
            detail_date = pd.to_datetime(row['created_at'],utc=True).tz_convert('America/Puerto_Rico').strftime('%d/%m/%Y %H:%M')
            label = observation_label(row)
            st.caption(f"{detail_date} · {LABELS.get(label,label)} · Folio {selected[:6]}")
            if st.button("Ver foto privada"):
                photo_bytes = sb.storage.from_("coffee-photos").download(row["photo_path"])
                show_leaf(photo_bytes)
            reviews = sb.table("reviews").select("*").eq("observation_id",selected).order("created_at").execute().data
            st.subheader('Revisión agrícola')
            if not reviews:
                st.caption('Pendiente de revisión' if row['abstained'] else 'Todavía no hay una revisión.')
            for review in reviews:
                with st.container(border=True):
                    verdict_labels = {'confirmed':'Orientación confirmada',
                                      'corrected':'Resultado de la revisión' if row['abstained'] else 'Orientación corregida',
                                      'uncertain':'Se necesita más información'}
                    st.write(verdict_labels[review['verdict']])
                    if review.get('corrected_label'): st.write(LABELS.get(review['corrected_label'],review['corrected_label']))
                    st.write(review['comment'])
            if admin:
                with st.form("review"):
                    choices = ["corrected", "uncertain"] if row["abstained"] else ["confirmed", "corrected", "uncertain"]
                    verdict = st.radio("Revisión", choices, index=choices.index("uncertain") if row["abstained"] else 0,
                                       format_func=lambda value:{'confirmed':'Confirmar orientación','corrected':'Registrar una clasificación','uncertain':'Pedir más información'}[value])
                    corrected = st.selectbox("Clase de la revisión (si registras una clasificación)",
                                             CLASSES, index=None, format_func=lambda value:LABELS[value])
                    comment = st.text_area("Comentario de revisión", max_chars=2000)
                    if st.form_submit_button("Guardar revisión"):
                        if not comment.strip():
                            st.error("Añade un comentario.")
                        elif verdict == "corrected" and corrected is None:
                            st.error("Elige una clase para guardar la clasificación.")
                        else:
                            sb.table("reviews").insert({"observation_id":selected,"reviewer_id":user.id,
                                "verdict":verdict,"corrected_label":corrected if verdict=="corrected" else None,"comment":comment}).execute()
                            st.session_state.review_saved = True
                            st.rerun()
    except Exception:
        st.error("No se pudo cargar o actualizar el historial. Revisa tu sesión y los permisos del proyecto.")
with roadmap:
    st.write("Provisionales: análisis de suelo y nutrición, fertilización, poda, renovación y cosecha selectiva.")
    st.write("Estos módulos aún no emiten recomendaciones. Requerirán datos adicionales, unidades verificadas y validación agronómica local.")
st.caption("Datos base: Jepkoech et al. (2021), JMuBEN/JMuBEN2, CC BY 4.0; distribución Project-AgML. Adaptación: nombres normalizados, auditoría y entrenamiento propios de CoffeeCare AI.")
