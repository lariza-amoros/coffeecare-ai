import uuid
from urllib.parse import urlsplit

import httpx
import pandas as pd
import streamlit as st
from supabase import create_client

from coffeecare.admin_panel import STATUS, admin_records, csv_report, review_status
from coffeecare.auth_ui import render_sign_in
from coffeecare.core import CLASSES, PHOTO_PARTS, UNCERTAIN, apply_review_rules, clean_image, observation_label
from coffeecare.evaluation import render_model_evidence
from coffeecare.inference import MODEL_PATH, load_model, predict
from coffeecare.ui import LABELS, model_scope, page_header, photo_steps, result_summary, show_leaf, welcome_panel

st.set_page_config(page_title="CoffeeCare AI", page_icon="🌿", layout="wide")

if "SUPABASE_URL" not in st.secrets or "SUPABASE_KEY" not in st.secrets:
    page_header()
    st.info("Configura Supabase en los secretos de la aplicación para iniciar sesión.")
    st.stop()
# Never cache a mutable authenticated client across users.
if "sb" not in st.session_state:
    st.session_state.sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
sb = st.session_state.sb

if not sb.auth.get_session():
    page_header()
    welcome_panel()
    _, login_area, _ = st.columns([1, 3, 1])
    with login_area:
        render_sign_in(sb)
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
page_header(signed_in=True)
title, account = st.columns([5, 2], vertical_alignment="center")
title.title("Panel de administración" if admin else "Mi cafetal")
if account.button("Cerrar sesión"):
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


def render_capture():
    st.subheader("Analizar una foto")
    selected_part = st.radio("¿Qué quieres analizar?", PHOTO_PARTS, index=None, horizontal=True)
    if selected_part is None:
        st.caption("Elige una parte del café para tomar o subir una foto.")
        return
    mode = st.segmented_control(
        "Cómo añadir una foto", ["Tomar foto", "Subir foto"], width="stretch", label_visibility="collapsed",
    )
    photo = None
    if mode == "Tomar foto":
        st.caption("Permite el acceso a la cámara cuando el navegador lo solicite.")
        photo = st.camera_input("Tomar foto")
    elif mode == "Subir foto":
        photo = st.file_uploader("Subir foto", type=["jpg", "jpeg", "png", "webp"])
    with st.expander("Cómo tomar una foto clara y qué puedes analizar"):
        photo_steps()
        model_scope()
    if photo is None:
        return
    notes = st.text_area("Observaciones del agricultor", max_chars=2000, placeholder="Ejemplo: manchas desde hace tres días, en varias hojas del mismo árbol.", help="Describe lo que observas. Evita incluir datos personales.")
    consent = st.checkbox("Autorizo almacenar esta foto para mi historial y revisión administrativa. No autoriza reutilizarla para entrenar.")
    if photo:
        try:
            raw = photo.getvalue()
            image, jpeg = clean_image(raw)
            show_leaf(jpeg)
        except Exception:
            st.error("No se puede procesar la imagen. Usa una foto válida de hasta 8 MB y 20 megapíxeles.")
            return
        path = MODEL_PATH
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
                result, review_reason = apply_review_rules(result, image, selected_part)
                key = str(uuid.uuid4())
                object_path = f"{user.id}/{key}.jpg"
                sb.storage.from_("coffee-photos").upload(object_path, jpeg, {"content-type": "image/jpeg", "upsert": "false"})
                try:
                    row = dict(result, id=key, user_id=user.id, photo_path=object_path, notes=notes)
                    sb.table("observations").insert(row).execute()
                except Exception:
                    sb.storage.from_("coffee-photos").remove([object_path])
                    raise
                result_summary(result, key[:6], review_reason)
                st.info("Registra la ubicación y evolución de los síntomas y consulta con un agrónomo. No apliques fertilizantes o plaguicidas basándote solo en esta foto.")
            except Exception:
                st.error("No se pudo analizar o guardar la foto. Revisa tu conexión e inténtalo otra vez.")


def display_date(value):
    return pd.to_datetime(value, utc=True).tz_convert("America/Puerto_Rico").strftime("%d/%m/%Y %H:%M")


def condition_name(record):
    label = observation_label(record)
    return LABELS.get(label, label)


def paginate(page, size, records):
    previous, position, following = st.columns([1, 2, 1])
    if previous.button("Anterior", disabled=page <= 1):
        st.session_state.history_page = page - 1
        st.rerun()
    position.caption(f"Página {page} · hasta {size} observaciones")
    if following.button("Siguiente", disabled=len(records) <= size):
        st.session_state.history_page = page + 1
        st.rerun()
    return records[:size]


def render_observation(row, reviews):
    observation_id = row["id"]
    st.subheader("Detalle de la observación")
    st.caption(f"Código de observación: {observation_id[:6]} · {display_date(row['created_at'])} · Puerto Rico")
    st.markdown(f"**{condition_name(row)}**")
    if not row["abstained"]:
        st.write(f"Confianza del modelo · {row['confidence']:.1%}")
    if st.toggle("Ver foto privada", key=f"photo_{observation_id}"):
        try:
            show_leaf(sb.storage.from_("coffee-photos").download(row["photo_path"]))
        except Exception:
            st.error("No se pudo cargar la foto privada.")
    if admin:
        with st.container(border=True):
            st.markdown("**Datos del caso**")
            st.write(f"Versión del modelo · {row.get('model_version') or 'No disponible'}")
            if row["abstained"] and row["label"] != UNCERTAIN:
                st.write(f"Predicción original, pendiente de revisión · {LABELS[row['label']]} ({row['confidence']:.1%})")
            st.write("Almacenamiento · Foto privada")
            st.caption("La app solicita consentimiento antes de guardar fotos. El registro no incluye un comprobante separado.")
    if row.get("notes"):
        st.text(row["notes"])
    st.subheader("Revisión agrícola")
    if not reviews:
        if row["abstained"]:
            st.warning("Pendiente de revisión")
        else:
            st.caption("Todavía no hay una revisión.")
    verdict_labels = {
        "confirmed": "Orientación confirmada",
        "corrected": "Resultado de la revisión" if row["abstained"] else "Orientación corregida",
        "uncertain": "Se necesita más información",
    }
    for review in reviews:
        with st.container(border=True):
            st.write(verdict_labels[review["verdict"]])
            st.caption(display_date(review["created_at"]))
            if review.get("corrected_label"):
                st.write(LABELS.get(review["corrected_label"], review["corrected_label"]))
            st.text(review["comment"])
    if admin:
        render_review_form(row)


def render_review_form(row):
    options = {"confirmed": "Confirmar orientación", "corrected": "Registrar una clasificación",
               "uncertain": "Pedir más información"}
    choices = ["uncertain", "corrected"] if row["abstained"] else list(options)
    with st.form(f"review_{row['id']}"):
        st.markdown("**Registrar revisión**")
        verdict = st.radio("Revisión", choices, format_func=options.__getitem__)
        corrected = st.selectbox("Clase de la revisión", CLASSES, index=None, format_func=LABELS.__getitem__)
        comment = st.text_area("Comentario de revisión", max_chars=2000)
        if not st.form_submit_button("Guardar revisión", type="primary"):
            return
        if not comment.strip():
            st.error("Añade un comentario.")
            return
        if verdict == "corrected" and corrected is None:
            st.error("Elige una clase para guardar la clasificación.")
            return
        sb.table("reviews").insert({
            "observation_id": row["id"], "reviewer_id": user.id, "verdict": verdict,
            "corrected_label": corrected if verdict == "corrected" else None, "comment": comment,
        }).execute()
        st.session_state.review_saved = True
        st.rerun()


def render_farmer_history():
    st.subheader("Tu historial")
    st.caption("Abre una observación para consultar su foto y su revisión.")
    size = 20
    page = st.session_state.get("history_page", 1)
    try:
        records = (sb.table("observations").select("*,reviews(id,created_at,verdict)")
                   .order("created_at", desc=True).order("id").range((page - 1) * size, page * size).execute().data)
        rows = paginate(page, size, records)
        if not rows:
            st.info("Todavía no hay fotos en tu historial. Analiza una hoja o un fruto para empezar.")
            return
        for row in rows:
            with st.container(border=True):
                st.markdown(f"**{condition_name(row)}**")
                st.caption(f"Código de observación: {row['id'][:6]} · {display_date(row['created_at'])}")
                state = review_status(row)
                if (state == "pending" and row["abstained"]) or state == "uncertain":
                    st.warning(STATUS[state])
                else:
                    st.write(STATUS[state])
                if st.button("Abrir observación", key=f"open_{row['id']}"):
                    st.session_state.selected_observation = row["id"]
                    st.rerun()
        frame = pd.DataFrame(rows).drop(columns=["probabilities", "photo_path", "reviews"], errors="ignore")
        frame["label"] = [observation_label(row) for row in rows]
        # Prevent spreadsheet formula execution in exported free text.
        frame = frame.map(lambda x: "'" + x if isinstance(x, str) and x[:1] in ("=", "+", "-", "@", "\t", "\r") else x)
        st.download_button("Reporte CSV de esta página", frame.to_csv(index=False).encode("utf-8-sig"),
                           "coffee-report.csv", "text/csv")
        selected = st.session_state.get("selected_observation")
        row = next((row for row in rows if row["id"] == selected), rows[0])
        reviews = sb.table("reviews").select("*").eq("observation_id", row["id"]).order("created_at").execute().data
        render_observation(row, reviews)
    except Exception:
        st.error("No se pudo cargar el historial. Revisa tu sesión e inténtalo otra vez.")


def render_scientific_review():
    st.subheader("Revisión científica")
    st.caption("Selecciona una observación para ver su evidencia y registrar una revisión.")
    if st.session_state.pop("review_saved", False):
        st.success("Revisión guardada. La predicción original se conserva.")
    try:
        records, valid = admin_records(sb, LABELS)
        if not valid:
            return []
        size = 20
        page = min(st.session_state.get("history_page", 1), max(1, (len(records) + size - 1) // size))
        st.session_state.history_page = page
        rows = paginate(page, size, records[(page - 1) * size:page * size + 1])
        if not rows:
            st.info("No hay observaciones para estos filtros.")
            return records
        queue, detail = st.columns([3, 2], gap="medium")
        with queue:
            st.markdown("**Observaciones**")
            table = pd.DataFrame([
                {"Código de observación": row["id"][:6], "Condición": condition_name(row),
                 "Estado": STATUS[review_status(row)], "Fecha": display_date(row["created_at"])}
                for row in rows
            ])
            event = st.dataframe(table, hide_index=True, width="stretch", on_select="rerun",
                                 selection_mode="single-row", key="queue_" + "_".join(row["id"] for row in rows))
        with detail:
            indices = event.selection.rows
            row = rows[indices[0]] if indices and indices[0] < len(rows) else rows[0]
            render_observation(row, sorted(row.get("reviews") or [], key=lambda review: review["created_at"]))
        return records
    except Exception:
        st.error("No se pudo cargar o actualizar la revisión. Revisa tu sesión y los permisos.")
        return []


def render_data(records):
    st.subheader("Datos y almacenamiento")
    st.caption("Resumen de la bandeja con los filtros de Revisión científica.")
    observations, reviewed, versions = st.columns(3)
    observations.metric("Observaciones", len(records))
    reviewed.metric("Con revisión", sum(bool(row.get("reviews")) for row in records))
    versions.metric("Versiones del modelo", len({row["model_version"] for row in records if row.get("model_version")}))
    st.write("Supabase almacena las fotos en un depósito privado. El historial conserva la predicción original y cada revisión.")
    st.download_button("Descargar observaciones y revisiones CSV", csv_report(records),
                       "coffeecare-review.csv", "text/csv", disabled=not records)


if admin:
    review_tab, capture_tab, data_tab, model_tab = st.tabs(
        ["Revisión científica", "Analizar foto", "Datos", "Evaluación del modelo"],
    )
    with review_tab:
        filtered_records = render_scientific_review()
    with data_tab:
        render_data(filtered_records)
    with model_tab:
        render_model_evidence()
else:
    capture_tab, history_tab, guide_tab = st.tabs(["Analizar foto", "Historial y revisión", "Guía de campo"])
    with history_tab:
        render_farmer_history()
    with guide_tab:
        welcome_panel()
        model_scope()
        st.write("Si aparecen síntomas distintos, toma una foto separada de cada zona. Guarda el código "
                 "de observación para encontrar la foto cuando necesites consultar su revisión.")

with capture_tab:
    render_capture()
st.caption("Las predicciones orientan la revisión agrícola. El modelo puede equivocarse incluso con confianza alta.")
st.caption("Datos base: Jepkoech et al. (2021), JMuBEN/JMuBEN2, CC BY 4.0; distribución Project-AgML. Adaptación: nombres normalizados, auditoría y entrenamiento propios de CoffeeCare AI.")
