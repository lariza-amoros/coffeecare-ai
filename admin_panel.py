"""Administrative queue; reads use the current user's RLS-protected client."""
import csv
import io
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
import streamlit as st

STATUS = {"pending":"Sin revisar", "confirmed":"Confirmada", "corrected":"Corregida", "uncertain":"Más información"}

def latest_review(row):
    reviews = row.get("reviews") or []
    return max(reviews, key=lambda r:(r["created_at"],int(r["id"]))) if reviews else None

def review_status(row):
    last = latest_review(row)
    return last["verdict"] if last else "pending"

def csv_report(rows):
    fields = ["folio","agricultor_id","fecha_utc","clase_original","puntuacion","modelo","observaciones","revision_id","revisor_id","fecha_revision_utc","veredicto","clase_corregida","comentario"]
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out,fieldnames=fields); writer.writeheader()
    for row in rows:
        # Keep every review, including the original chronology; one row if unreviewed.
        for r in sorted(row.get("reviews") or [{}],key=lambda r:(r.get("created_at",""),r.get("id",0))):
            values = dict(zip(fields,[row["id"],row["user_id"],row["created_at"],row["label"],row["confidence"],row["model_version"],row.get("notes",""),r.get("id",""),r.get("reviewer_id",""),r.get("created_at",""),r.get("verdict","pending"),r.get("corrected_label") or "",r.get("comment","")]))
            writer.writerow({k:("'"+v if isinstance(v,str) and v.lstrip()[:1] in ("=","+","-","@") else v) for k,v in values.items()})
    return out.getvalue().encode("utf-8-sig")

def admin_records(sb, labels):
    st.caption("Busca agricultores por su identificador del historial; no se exponen sus credenciales.")
    with st.form("admin_filters"):
        search = st.text_input("Buscar por folio, ID del agricultor o notas",max_chars=200)
        condition = st.radio("Condición",["all",*labels],format_func=lambda v:"Todas" if v=="all" else labels[v],horizontal=True)
        state = st.radio("Bandeja",["all","pending","reviewed","uncertain"],format_func=lambda v:{"all":"Todas","pending":"Sin revisar","reviewed":"Con revisión","uncertain":"Más información"}[v],horizontal=True)
        start = st.text_input("Desde (AAAA-MM-DD)",placeholder="2026-11-01")
        end = st.text_input("Hasta (AAAA-MM-DD)",placeholder="2026-11-30")
        st.caption("Fechas inclusivas en hora de Puerto Rico. Déjalas vacías para todo el periodo.")
        st.form_submit_button("Aplicar filtros",type="primary")
    try:
        begin = date.fromisoformat(start.strip()) if start.strip() else None
        finish = date.fromisoformat(end.strip()) if end.strip() else None
        if begin and finish and begin>finish: raise ValueError()
    except ValueError:
        st.error("Usa fechas válidas AAAA-MM-DD y un inicio anterior o igual al final.")
        return [],False
    signature=(search,condition,state,start,end)
    if st.session_state.get("admin_filter_signature") != signature:
        st.session_state.admin_filter_signature=signature
        st.session_state.history_page=1
    st.button("Actualizar observaciones")
    records=[]
    # Bounded prototype workload. Never label a truncated count as a global total.
    for offset in range(0,5001,500):
        query=sb.table("observations").select("*,reviews(id,reviewer_id,created_at,verdict,corrected_label,comment)").order("created_at",desc=True).order("id")
        if condition!="all": query=query.eq("label",condition)
        if begin: query=query.gte("created_at",datetime.combine(begin,time.min,ZoneInfo("America/Puerto_Rico")).astimezone(timezone.utc).isoformat())
        if finish: query=query.lt("created_at",datetime.combine(finish+timedelta(days=1),time.min,ZoneInfo("America/Puerto_Rico")).astimezone(timezone.utc).isoformat())
        batch=query.range(offset,min(offset+499,5000)).execute().data
        records.extend(batch)
        if len(batch)<500: break
    truncated=len(records)>5000
    records=records[:5000]
    if truncated: st.warning("Vista limitada a las 5.000 observaciones más recientes del periodo y condición. Reduce las fechas; resúmenes y reporte solo incluyen esta vista.")
    term=search.strip().casefold()
    if term: records=[r for r in records if term in " ".join(str(r.get(k,"")) for k in ("id","user_id","notes")).casefold()]
    pending=sum(review_status(r)=="pending" for r in records)
    st.markdown("#### Resumen del periodo, condición y búsqueda")
    a,b,c=st.columns(3)
    a.metric("Observaciones",len(records)); b.metric("Sin revisar",pending); c.metric("Con revisión",len(records)-pending)
    counts=Counter(r["label"] for r in records)
    st.caption(" · ".join(f"{labels.get(k,k)}: {v}" for k,v in sorted(counts.items())) or "Sin observaciones")
    if state=="pending": records=[r for r in records if review_status(r)=="pending"]
    elif state=="reviewed": records=[r for r in records if review_status(r)!="pending"]
    elif state=="uncertain": records=[r for r in records if review_status(r)=="uncertain"]
    st.caption(f"Bandeja: {len(records)} observaciones. El estado se toma de la revisión más reciente.")
    st.download_button("Descargar observaciones y revisiones CSV",csv_report(records),"coffeecare-admin.csv","text/csv",disabled=not records)
    return records,True
