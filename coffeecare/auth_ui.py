"""Streamlit sign-in and Farmer registration."""

import logging

import streamlit as st

LOGGER = logging.getLogger(__name__)


def render_sign_in(client):
    login, signup = st.tabs(["Ingresar", "Crear cuenta de caficultor"])
    with login, st.form("login"):
        access = st.radio("Ingresar como", ("Caficultor", "Administrator"), horizontal=True)
        email = st.text_input("Correo")
        password = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Ingresar", type="primary", width="stretch"):
            try:
                response = client.auth.sign_in_with_password({"email": email.strip(), "password": password})
            except Exception:
                st.error("No se pudo ingresar. Verifica tus datos y la confirmación del correo.")
            else:
                admin = response.user is not None and response.user.app_metadata.get("role") == "admin"
                if response.user is not None and response.session is not None and admin == (access == "Administrator"):
                    st.rerun()
                # Discard the per-browser client even if revoking its session fails.
                try:
                    client.auth.sign_out({"scope": "local"})
                except Exception:
                    LOGGER.warning("Could not revoke a rejected sign-in session")
                finally:
                    st.session_state.pop("sb", None)
                st.error("El acceso seleccionado no corresponde a tu cuenta. Elige Caficultor o Administrator según tu cuenta.")
    with signup, st.form("signup"):
        email = st.text_input("Correo nuevo")
        password = st.text_input("Contraseña nueva", type="password")
        if st.form_submit_button("Crear cuenta", width="stretch"):
            try:
                client.auth.sign_up({"email": email.strip(), "password": password})
                st.success("Revisa tu correo para confirmar la cuenta antes de ingresar.")
            except Exception:
                st.error("No se pudo crear la cuenta. Intenta más tarde.")
