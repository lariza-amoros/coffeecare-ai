"""Run an isolated EfficientNet-B0 candidate against the deployed model A."""
import argparse
import ast
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile


SOURCE_HASH = "61bbe86bf6e853b6169d00630bb426b0001c368f04207af45f1c3eb260130e71"
LOADER_HASH = "a932c24bc4612a17ebaa564c97fadfff4f034674d04b16e2877b9b2df2321ce1"
FOCAL_HASH = "6e7d4cc05c8fa8b4e7d742ea3d144053b0a96b36b590c7d62b282ecf2caac0db"
BASELINE_HASH = "866458b381678945a5a6698a8d33410fbe7d8758c87ac07a7a733f2423c6cfba"
MANIFEST_HASH = "a5f24534e5a1491b2c266d78a8210bd65f1e04ca17e7adfd4a15801da2041dc9"
HEAD_EPOCHS = 4


def verified_file(path, expected):
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError(f"El SHA-256 de {path.name} no coincide con la versión auditada.")
    return path


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError(f"La receta no coincide en {old!r}.")
    return source.replace(old, new, 1)


def build_model(num_classes, pretrained=True):
    from torch import nn
    from torchvision import models

    weights = models.EfficientNet_B0_Weights.DEFAULT if pretrained else None
    model = models.efficientnet_b0(weights=weights)
    inputs = model.classifier[-1].in_features
    model.classifier = nn.Sequential(nn.Dropout(0.2), nn.Linear(inputs, num_classes))
    return model


def configure_trainable(model, fine_tuning):
    model.features.requires_grad_(False)
    if fine_tuning:
        model.features[-2:].requires_grad_(True)


def set_training_mode(model, fine_tuning):
    model.train()
    # Frozen blocks must keep their BatchNorm statistics.
    model.features.eval()
    if fine_tuning:
        for block in model.features[-2:]:
            block.train()


def make_trainer(source, project, scratch, baseline_path, launcher_dir):
    source = replace_once(source, "PROJECT=Path('/content/drive/MyDrive/CoffeeCare AI');AUDIT=PROJECT/'reinforcement_v1'",
                          f"PROJECT=Path({str(project)!r});AUDIT=Path({str(scratch / 'audit')!r})")
    source = replace_once(source, "DATA=Path('/content/coffeecare_reinforced/data');BASE=PROJECT/'runs/eight-class-20261106-001943'",
                          f"DATA=Path({str(scratch / 'data')!r})")
    source = replace_once(source, "shutil.copyfile(BASE/'model.pt',baseline_path)",
                          f"shutil.copyfile({str(baseline_path)!r},baseline_path)")
    source = replace_once(source, "assert baseline['architecture']=='mobilenet_v3_small'",
                          "assert baseline['architecture']=='mobilenet_v3_small'\n"
                          f"assert baseline['manifest_sha256']=={MANIFEST_HASH!r}\n"
                          f"assert hashlib.sha256(frame.to_csv(index=False,lineterminator='\\n').encode()).hexdigest()=={MANIFEST_HASH!r}")
    source = replace_once(source, "reinforced-val-%Y%m%d-%H%M%S", "efficientnet-b0-%Y%m%d-%H%M%S")
    source = replace_once(source, "(run/'environment.json').write_bytes((AUDIT/'environment.json').read_bytes())",
                          """(run/'environment.json').write_text(json.dumps({
    'torch': torch.__version__, 'cuda': torch.version.cuda,
    'device': torch.cuda.get_device_name(), 'seed': 42,
}, indent=2))""")
    start = source.index("net=model(True)\n")
    end = source.index("training_rows=", start)
    source = source[:start] + f"""import sys
sys.path.insert(0, {str(project)!r})
sys.path.insert(0, {str(launcher_dir)!r})
from coffeecare_ab import FocalLoss
from run_efficientnet_b0 import HEAD_EPOCHS, build_model, configure_trainable, set_training_mode
net=build_model(len(CLASSES)).cuda()
configure_trainable(net, False)
optimizer=torch.optim.AdamW(net.classifier.parameters(),lr=1e-3,weight_decay=1e-4)
counts=frame[frame.split=='train'].label.value_counts()
assert set(counts.index)==set(CLASSES)
loss_fn=FocalLoss(gamma=2.0,alpha=None)
""" + source[end:]
    source = replace_once(source, "'loss':'CrossEntropyLoss'", "'loss':'FocalLoss(gamma=2, alpha=None)'")
    source = replace_once(source, "CrossEntropyLoss sin pesos.", "Focal Loss gamma=2 sin pesos.")
    source = replace_once(source, "    net.train();total=0;seen=0", """    fine_tuning=epoch>=HEAD_EPOCHS
    if epoch==HEAD_EPOCHS:
        net.load_state_dict(torch.load(state_path,map_location='cuda',weights_only=True))
        configure_trainable(net, True)
        optimizer=torch.optim.AdamW([
            {'params':net.features[-2:].parameters(),'lr':1e-5},
            {'params':net.classifier.parameters(),'lr':1e-4},
        ],weight_decay=1e-4)
        scheduler=torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer,mode='max',patience=2,factor=.5)
        patience=0
    set_training_mode(net, fine_tuning)
    total=0;seen=0""")
    source = replace_once(source, "'epoch':epoch+1,'train_loss':total/seen",
                          "'epoch':epoch+1,'phase':'fine_tuning' if fine_tuning else 'head','train_loss':total/seen")
    source = replace_once(source, "    if patience>=5:break", "    if fine_tuning and patience>=5:break")
    source = replace_once(source, "checkpoint=dict(baseline,state_dict={k:v.cpu() for k,v in net.state_dict().items()},temperature=1.0,",
                          """checkpoint=dict(architecture='efficientnet_b0', classes=CLASSES, mean=mean, std=std,
                input_size=224, resize_mode='stretch', interpolation='bilinear',
                imagenet_weights='IMAGENET1K_V1', experiment='efficientnet-b0-focal',
                loss_name='FocalLoss', focal_gamma=2.0, focal_alpha=None, head_epochs=HEAD_EPOCHS,
                state_dict={k:v.cpu() for k,v in net.state_dict().items()},temperature=1.0,""")
    ast.parse(source)
    return source


def main():
    import torch

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path("/content/drive/MyDrive/CoffeeCare AI"))
    parser.add_argument("--baseline", type=Path, required=True, help="Checkpoint A calibrado de GitHub.")
    args = parser.parse_args()
    if not torch.cuda.is_available():
        parser.error("Selecciona un entorno GPU en Colab para entrenar.")
    project = args.project.resolve()
    baseline = verified_file(args.baseline.resolve(), BASELINE_HASH)
    recipe = verified_file(project / "reinforce_train.py", SOURCE_HASH)
    loader = verified_file(project / "load_verified_reinforcement.py", LOADER_HASH)
    verified_file(project / "coffeecare_ab.py", FOCAL_HASH)

    with tempfile.TemporaryDirectory(prefix="coffeecare-b0-") as temporary:
        scratch = Path(temporary)
        loader_source = replace_once(loader.read_text(encoding="utf-8"),
                                     "PROJECT=Path('/content/drive/MyDrive/CoffeeCare AI')",
                                     f"PROJECT=Path({str(project)!r})")
        loader_source = replace_once(loader_source,
                                     "ROOT=Path('/content/coffeecare_reinforced');ROOT.mkdir(exist_ok=True)",
                                     f"ROOT=Path({str(scratch)!r});ROOT.mkdir(exist_ok=True)")
        loader_source = replace_once(loader_source,
                                     "AUDIT=PROJECT/'reinforcement_v1';AUDIT.mkdir(exist_ok=True)",
                                     "AUDIT=ROOT/'audit';AUDIT.mkdir(exist_ok=True)")
        isolated_loader = scratch / "load_audited_data.py"
        isolated_loader.write_text(loader_source, encoding="utf-8")
        trainer = scratch / "train_efficientnet_b0.py"
        trainer.write_text(make_trainer(recipe.read_text(encoding="utf-8"), project, scratch,
                                        baseline, Path(__file__).resolve().parent), encoding="utf-8")
        for script in (isolated_loader, trainer):
            subprocess.run([sys.executable, "-u", str(script)], cwd=project, check=True)


if __name__ == "__main__":
    main()
