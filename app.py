import io
import uuid
from pathlib import Path
import pandas as pd
import streamlit as st
from supabase import create_client
from core import CLASSES, clean_image
from inference import load_model, predict
from ui import page_header, photo_steps, LABELS, show_leaf

st.set_page_config(page_title="CoffeeCare AI", page_icon="🌿", layout="centered")
page_header()
st.warning("Prototipo experimental: distingue roya, Cercospora y hojas sin síntomas de esas clases. Una foto no confirma el diagnóstico y el modelo puede equivocarse incluso con puntuación alta. Otras enfermedades requieren revisión.")

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
    user = sb.auth.get_user().user  # validate/refresh through SDK, never trust UI role selection
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

capture, history, roadmap = st.tabs(["Analizar foto", "Historial y revisión", "Próximos módulos"])
with capture:
    photo_steps()
    st.subheader("Revisa una hoja de tu cafetal")
    st.caption("Puedes subir una foto o usar la cámara. Si es posible, fotografía también el envés.")
    mode = st.radio("Origen", ["Subir foto", "Cámara"], horizontal=True)
    photo = st.file_uploader("Foto", type=["jpg", "jpeg", "png", "webp"]) if mode == "Subir foto" else st.camera_input("Tomar foto")
    notes = st.text_area("Observaciones del agricultor", max_chars=2000)
    consent = st.checkbox("Autorizo almacenar esta foto para mi historial y revisión administrativa. No autoriza reutilizarla para entrenar.")
    if photo:
        try:
            image, jpeg = clean_image(photo.getvalue())
            show_leaf(jpeg)
        except Exception:
            st.error("No se puede procesar la imagen. Usa una foto válida de hasta 8 MB y 20 megapíxeles.")
            st.stop()
        path = Path(st.secrets.get("MODEL_PATH", "model/model.pt"))
        if not path.exists():
            st.info("Modelo entrenado pendiente. La aplicación no genera predicciones simuladas.")
        elif st.button("Analizar y guardar", disabled=not consent,type="primary",use_container_width=True):
            try:
                model, meta = model_resource(str(path), path.stat().st_mtime_ns)
                if meta.get("experimental", True):
                    st.warning("Modelo experimental: independencia de las hojas no verificada. Resultado solo para investigación y revisión.")
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
                if result["abstained"]:
                    st.warning("Resultado no concluyente. Solicita revisión y toma otra foto.")
                else:
                    st.success(f"Orientación: {LABELS[result['label']]}")
                st.write(f"Puntuación del modelo: {result['confidence']:.1%}. No equivale a probabilidad de diagnóstico correcto.")
                st.json(result["probabilities"])
                st.info("Registra la ubicación y evolución de los síntomas y consulta con un agrónomo. No apliques fertilizantes o plaguicidas basándote solo en esta foto.")
            except Exception:
                st.error("No se completó el análisis o guardado. Verifica la conexión, el modelo y la configuración de Supabase.")
with history:
    try:
        # RLS enforces ownership; fetch one extra row to detect the next page.
        size = 20
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
            st.info('Todavía no hay fotos en tu historial. Analiza una hoja para guardar tu primera observación.')
        else:
            st.caption('Fechas en hora de Puerto Rico. Los resultados son orientativos.')
            for record in rows:
                date = pd.to_datetime(record['created_at'],utc=True).tz_convert('America/Puerto_Rico').strftime('%d/%m/%Y %H:%M')
                with st.container(border=True):
                    st.markdown(f"**{LABELS.get(record['label'],record['label'])}**")
                    st.caption(date)
                    st.write(f"Puntuación del modelo: {record['confidence']:.1%}")
                    st.write('Necesita revisión' if record['abstained'] else 'Orientación disponible')
                    if record.get('notes'): st.write(record['notes'])
                    if st.button('Abrir observación',key='open_'+record['id']):
                        st.session_state.selected_observation = record['id']
                        st.rerun()
            frame = pd.DataFrame(rows).drop(columns=["probabilities", "photo_path"], errors="ignore")
            # Prevent spreadsheet formula execution in exported free text.
            frame = frame.map(lambda x: "'"+x if isinstance(x,str) and x[:1] in ("=","+","-","@","\t","\r") else x)
            st.download_button("Reporte CSV de esta página", frame.to_csv(index=False).encode("utf-8-sig"), "coffee-report.csv", "text/csv")
            selected = st.session_state.get('selected_observation')
            if selected not in {r['id'] for r in rows}: selected = rows[0]['id']
            row = next(r for r in rows if r['id']==selected)
            st.subheader('Detalle de la observación')
            detail_date = pd.to_datetime(row['created_at'],utc=True).tz_convert('America/Puerto_Rico').strftime('%d/%m/%Y %H:%M')
            st.caption(f"{detail_date} · {LABELS.get(row['label'],row['label'])} · Folio {selected[:6]}")
            if st.button("Ver foto privada"):
                photo_bytes = sb.storage.from_("coffee-photos").download(row["photo_path"])
                show_leaf(photo_bytes)
            reviews = sb.table("reviews").select("*").eq("observation_id",selected).order("created_at").execute().data
            st.subheader('Revisión agrícola')
            if not reviews: st.caption('Esta observación todavía no tiene una revisión administrativa.')
            for review in reviews:
                with st.container(border=True):
                    st.write({'confirmed':'Orientación confirmada','corrected':'Orientación corregida','uncertain':'Se necesita más información'}[review['verdict']])
                    if review.get('corrected_label'): st.write(LABELS.get(review['corrected_label'],review['corrected_label']))
                    st.write(review['comment'])
            if admin:
                with st.form("review"):
                    verdict = st.radio("Revisión", ["confirmed", "corrected", "uncertain"],format_func=lambda value:{'confirmed':'Confirmar orientación','corrected':'Corregir orientación','uncertain':'Pedir más información'}[value])
                    corrected = st.radio("Orientación corregida (solo si corriges)", CLASSES,format_func=lambda value:LABELS[value])
                    comment = st.text_area("Comentario de revisión", max_chars=2000)
                    if st.form_submit_button("Guardar revisión"):
                        if not comment.strip():
                            st.error("Añade un comentario.")
                        else:
                            sb.table("reviews").insert({"observation_id":selected,"reviewer_id":user.id,
                                "verdict":verdict,"corrected_label":corrected if verdict=="corrected" else None,"comment":comment}).execute()
                            st.success("Revisión guardada. La predicción original se conserva.")
    except Exception:
        st.error("No se pudo cargar o actualizar el historial. Revisa tu sesión y los permisos del proyecto.")
with roadmap:
    st.write("Provisionales: análisis de suelo y nutrición, fertilización, poda, renovación y cosecha selectiva.")
    st.write("Estos módulos aún no emiten recomendaciones. Requerirán datos adicionales, unidades verificadas y validación agronómica local.")
st.caption("Datos base: Jepkoech et al. (2021), JMuBEN/JMuBEN2, CC BY 4.0; distribución Project-AgML. Adaptación: nombres normalizados, auditoría y entrenamiento propios de CoffeeCare AI.")
