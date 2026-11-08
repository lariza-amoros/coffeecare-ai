"""HTTP prediction service for CoffeeCare AI."""
import os
from contextlib import asynccontextmanager
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from PIL import Image
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from coffeecare.core import MAX_UPLOAD_BYTES, clean_image
from coffeecare.inference import MODEL_PATH, load_model, predict

IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp", "application/octet-stream")
bearer = HTTPBearer(auto_error=False)


class Prediction(BaseModel):
    label: str
    confidence: float
    probabilities: dict[str, float]
    abstained: bool
    model_version: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    auth_url = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_KEY"]
    if not auth_url.startswith("https://") or not key.strip():
        raise ValueError("Configura la URL HTTPS y la clave publicable de Supabase.")
    app.state.model = load_model(MODEL_PATH)
    async with httpx.AsyncClient(
        base_url=auth_url, headers={"apikey": key}, timeout=5, follow_redirects=False,
    ) as auth:
        app.state.auth = auth
        yield


app = FastAPI(title="CoffeeCare AI", version="1.0.0", lifespan=lifespan)


@app.get("/health")
def health(request: Request):
    return {"status": "ok", "model_version": request.app.state.model[1]["version"]}


@app.post(
    "/predict",
    response_model=Prediction,
    openapi_extra={"requestBody": {
        "required": True,
        "content": {mime: {"schema": {"type": "string", "format": "binary"}}
                    for mime in IMAGE_TYPES},
    }},
)
async def predict_photo(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
):
    unauthorized = HTTPException(401, "Inicia sesión para analizar la foto.",
                                 headers={"WWW-Authenticate": "Bearer"})
    if credentials is None:
        raise unauthorized
    try:
        user = await request.app.state.auth.get(
            "/auth/v1/user", headers={"Authorization": f"Bearer {credentials.credentials}"},
        )
    except httpx.RequestError:
        raise HTTPException(503, "La verificación de sesión no está disponible.") from None
    if user.status_code in (401, 403):
        raise unauthorized
    if not user.is_success:
        raise HTTPException(503, "La verificación de sesión no está disponible.")
    try:
        user_id = user.json().get("id")
    except (ValueError, AttributeError):
        raise HTTPException(503, "La verificación de sesión no está disponible.") from None
    if not user_id:
        raise unauthorized

    if request.headers.get("content-type", "").partition(";")[0].lower() not in IMAGE_TYPES:
        raise HTTPException(415, "Envía una imagen JPEG, PNG o WebP.")
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "La foto supera 8 MB.")
        raw.extend(chunk)
    try:
        image, _ = await run_in_threadpool(clean_image, raw)
    except (OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(422, "La imagen está dañada o fuera de los límites permitidos.") from None
    model, metadata = request.app.state.model
    return await run_in_threadpool(predict, model, metadata, image)
