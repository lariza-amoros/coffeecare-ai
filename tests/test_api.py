"""Exercise the HTTP contract with a simulated Supabase Auth endpoint."""
import os
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import httpx
from fastapi.testclient import TestClient

from api import app
from coffeecare.core import MAX_UPLOAD_BYTES


class PredictionApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def auth_response(request):
            assert request.url.path == "/auth/v1/user"
            assert request.headers["apikey"] == "test-publishable-key"
            if request.headers.get("Authorization") == "Bearer fixture-session":
                return httpx.Response(200, json={"id": "fixture-user"})
            return httpx.Response(401)

        async_client = httpx.AsyncClient
        cls.enterClassContext(patch.dict(os.environ, {
            "SUPABASE_URL": "https://test.example",
            "SUPABASE_KEY": "test-publishable-key",
        }))
        cls.enterClassContext(patch(
            "api.httpx.AsyncClient",
            side_effect=lambda **kwargs: async_client(
                transport=httpx.MockTransport(auth_response), **kwargs,
            ),
        ))
        cls.client = cls.enterClassContext(TestClient(app))
        cls.headers = {"Authorization": "Bearer fixture-session", "Content-Type": "image/jpeg"}

    def test_health_and_docs(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["model_version"].startswith("a-final-"))
        contract = self.client.get("/openapi.json").json()["paths"]["/predict"]["post"]
        self.assertIn("security", contract)
        self.assertIn("image/jpeg", contract["requestBody"]["content"])

    def test_rejects_missing_and_invalid_session(self):
        self.assertEqual(self.client.post("/predict").status_code, 401)
        self.assertEqual(self.client.post(
            "/predict", headers={"Authorization": "Bearer expired-session"},
        ).status_code, 401)

    def test_rejects_invalid_type_image_and_size(self):
        headers = dict(self.headers, **{"Content-Type": "text/plain"})
        self.assertEqual(self.client.post("/predict", headers=headers).status_code, 415)
        self.assertEqual(self.client.post(
            "/predict", headers=self.headers, content=b"not an image",
        ).status_code, 422)
        self.assertEqual(self.client.post(
            "/predict", headers=self.headers, content=b"x" * (MAX_UPLOAD_BYTES + 1),
        ).status_code, 413)

    def test_real_model_returns_accepted_and_uncertain(self):
        archive = os.environ.get("COFFEECARE_VALIDATION_ZIP")
        if not archive:
            self.skipTest("Set COFFEECARE_VALIDATION_ZIP to the audited CoffeeCare dataset ZIP.")
        with ZipFile(Path(archive)) as photos:
            for path, expected in (("images/02886.jpg", "Fruit_Borer"),
                                   ("images/00294.jpg", "Uncertain")):
                with self.subTest(path=path):
                    response = self.client.post(
                        "/predict", headers=self.headers, content=photos.read(path),
                    )
                    self.assertEqual(response.status_code, 200, response.text)
                    result = response.json()
                    self.assertEqual(result["label"], expected)
                    self.assertEqual(result["abstained"], expected == "Uncertain")
                    if result["abstained"]:
                        self.assertEqual(result["probabilities"], {})
                    else:
                        self.assertEqual(len(result["probabilities"]), 8)


if __name__ == "__main__":
    unittest.main()
