"""Shared input contract. No credentials or network at import time."""
import io
import numpy as np
from PIL import Image, ImageOps

CLASSES = ["Healthy", "Rust", "Cercospora", "Phoma", "Miner",
           "Fruit_Healthy", "Fruit_Borer", "Fruit_Damaged"]
UNCERTAIN = "Uncertain"
Image.MAX_IMAGE_PIXELS = 20_000_000
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
PHOTO_PARTS = ("Hoja", "Fruto")


def apply_review_rules(result, image, selected_part):
    """Route part conflicts and uncertain leaf conditions to review."""
    if selected_part not in PHOTO_PARTS:
        raise ValueError("Selecciona Hoja o Fruto.")
    if result["abstained"]:
        return result, None

    label = result["label"]
    predicted_part = "Fruto" if label.startswith("Fruit_") else "Hoja"
    if selected_part != predicted_part:
        return dict(result, abstained=True), "part_conflict"

    if label == "Cercospora":
        return dict(result, abstained=True), "cercospora_review"

    if label == "Miner" and result["probabilities"].get("Rust", 0) >= 0.075:
        hsv = np.asarray(image.resize((256, 256), Image.Resampling.BILINEAR).convert("HSV"))
        hue, saturation, value = hsv.transpose(2, 0, 1)
        orange = (hue >= 8) & (hue <= 28) & (saturation >= 125) & (value >= 115)
        if orange.mean() >= 0.02:
            return dict(result, abstained=True), "leaf_color"

    return result, None


def observation_label(record):
    """Hide the unaccepted class in older saved observations, too."""
    return UNCERTAIN if record["abstained"] else record["label"]


def clean_image(raw):
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValueError("La foto supera 8 MB.")
    with Image.open(io.BytesIO(raw)) as im:
        if im.format not in {"JPEG", "PNG", "WEBP"}:
            raise ValueError("Usa JPEG, PNG o WebP.")
        if min(im.size) < 74:
            raise ValueError("La foto es demasiado pequeña.")
        if im.width * im.height > 20_000_000:
            raise ValueError("La resolución supera el límite.")
        out = ImageOps.exif_transpose(im).convert("RGB")
        out.thumbnail((1600, 1600))
        buf = io.BytesIO()
        out.save(buf, format="JPEG", quality=90)  # removes EXIF/GPS
        return out, buf.getvalue()
