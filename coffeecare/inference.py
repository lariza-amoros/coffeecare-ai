import math
from pathlib import Path
import torch
from torchvision import models, transforms
from .core import CLASSES, UNCERTAIN

MODEL_PATH = Path(__file__).resolve().parent.parent / "model" / "model_a_calibrated.pt"


def transform(metadata):
    return transforms.Compose([transforms.Resize((224, 224)), transforms.ToTensor(),
                               transforms.Normalize(metadata["mean"], metadata["std"])])

def load_model(path):
    checkpoint = torch.load(Path(path), map_location="cpu", weights_only=True)
    if checkpoint["classes"] != CLASSES:
        raise ValueError("El orden de clases del modelo no es compatible.")
    if (checkpoint.get("architecture") != "mobilenet_v3_small"
            or checkpoint.get("calibrated") is not True
            or not 0 < checkpoint["threshold"] < 1
            or not math.isfinite(checkpoint["temperature"])
            or checkpoint["temperature"] <= 0):
        raise ValueError("Se necesita el modelo calibrado de CoffeeCare.")
    model = models.mobilenet_v3_small(weights=None)
    model.classifier[3] = torch.nn.Linear(model.classifier[3].in_features, len(CLASSES))
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    return model, checkpoint

def predict(model, metadata, image):
    with torch.inference_mode():
        logits = model(transform(metadata)(image).unsqueeze(0))
        probs = torch.softmax(logits.double() / metadata["temperature"], dim=1)[0]
        if not torch.isfinite(probs).all():
            raise ValueError("El modelo no produjo una puntuación válida.")
    index = int(probs.argmax())
    confidence = float(probs[index])
    abstained = confidence < metadata["threshold"]
    return {"label": UNCERTAIN if abstained else CLASSES[index], "confidence": confidence,
            "probabilities": {} if abstained else {c: float(p) for c, p in zip(CLASSES, probs)},
            "abstained": abstained,
            "model_version": metadata["version"]}
