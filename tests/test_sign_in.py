"""Exercise the sign-in form with simulated Supabase accounts."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from streamlit.testing.v1 import AppTest


class SignInTest(unittest.TestCase):
    def submit(self, actual_role, selected_role):
        user = SimpleNamespace(app_metadata={"role": actual_role} if actual_role else {})
        client = Mock()
        client.auth.sign_in_with_password.return_value = SimpleNamespace(user=user, session=object())
        client.auth.get_session.side_effect = lambda: (
            None if not client.auth.sign_in_with_password.called or client.auth.sign_out.called
            else SimpleNamespace(user=user)
        )
        app = AppTest.from_string(
            "import streamlit as st\n"
            "from coffeecare.auth_ui import render_sign_in\n"
            "client = st.session_state.get('sb')\n"
            "if client is None:\n"
            "    st.text('Session discarded')\n"
            "elif session := client.auth.get_session():\n"
            "    st.text('Administrator' if session.user.app_metadata.get('role') == 'admin' else 'Caficultor')\n"
            "else:\n"
            "    render_sign_in(client)\n"
        )
        app.session_state["sb"] = client
        app.run()
        self.assertEqual(app.radio[0].options, ["Caficultor", "Administrator"])
        app.radio[0].set_value(selected_role)
        app.text_input[0].set_value("farmer@example.test")
        app.text_input[1].set_value("fixture-password")
        app.button[0].click().run()
        self.assertFalse(app.exception)
        return app, client

    def test_matching_roles_enter(self):
        for account_role, selected_role in ((None, "Caficultor"), ("admin", "Administrator")):
            with self.subTest(role=selected_role):
                app, client = self.submit(account_role, selected_role)
                self.assertEqual(app.text[0].value, selected_role)
                client.auth.sign_out.assert_not_called()

    def test_mismatched_roles_are_rejected(self):
        for account_role, selected_role in ((None, "Administrator"), ("admin", "Caficultor")):
            with self.subTest(role=selected_role):
                app, client = self.submit(account_role, selected_role)
                self.assertIn("no corresponde", app.error[0].value)
                self.assertNotIn("sb", app.session_state)
                client.auth.sign_out.assert_called_once_with({"scope": "local"})
