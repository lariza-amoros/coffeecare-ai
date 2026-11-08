"""Shared input contract. No credentials or network at import time."""
import io
from PIL import Image, ImageOps

CLASSES = ["Healthy", "Rust", "Cercospora", "Phoma", "Miner",
           "Fruit_Healthy", "Fruit_Borer", "Fruit_Damaged"]
UNCERTAIN = "Uncertain"


def observation_label(record):
    """Hide the unaccepted class in older saved observations, too."""
    return UNCERTAIN if record["abstained"] else record["label"]
SOURCE_LABELS = {"Healthy": "Healthy", "Leaf_rust": "Rust", "Rust": "Rust",
                 "Cerscospora": "Cercospora", "Cercospora": "Cercospora",
                 "Phoma": "Phoma", "Miner": "Miner"}
MEAN = [0.485, 0.456, 0.406]
STD = [0.229, 0.224, 0.225]
Image.MAX_IMAGE_PIXELS = 20_000_000
MAX_UPLOAD_BYTES = 8 * 1024 * 1024

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
