from pathlib import Path
import torch
from torchvision import models, transforms
from core import CLASSES, MEAN, STD

def transform():
    return transforms.Compose([transforms.Resize((224, 224)), transforms.ToTensor(),
                               transforms.Normalize(MEAN, STD)])

def load_model(path):
    checkpoint = torch.load(Path(path), map_location="cpu", weights_only=True)
    if checkpoint["classes"] != CLASSES:
        raise ValueError("El orden de clases del modelo no es compatible.")
    model = models.mobilenet_v3_small(weights=None)
    model.classifier[3] = torch.nn.Linear(model.classifier[3].in_features, len(CLASSES))
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    return model, checkpoint

def predict(model, metadata, image):
    with torch.inference_mode():
        logits = model(transform()(image).unsqueeze(0))
        probs = torch.softmax(logits / metadata["temperature"], dim=1)[0]
    index = int(probs.argmax())
    confidence = float(probs[index])
    return {"label": CLASSES[index], "confidence": confidence,
            "probabilities": {c: float(p) for c, p in zip(CLASSES, probs)},
            "abstained": confidence < metadata["threshold"],
            "model_version": metadata["version"]}
