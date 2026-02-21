"""
WandB로 실제 학습 로깅 후 파서 테스트.

test_file.py의 학습 로직을 WandB로 로깅한 뒤,
생성된 실제 wandb 로그 파일로 core/log_parsers.py 파서를 검증합니다.

사용법:
    python test_wandb_real.py
"""

import torch
import torch.nn as nn
import torch.optim as optim
import torchvision
from torchvision import datasets, transforms
from torch.utils.data import DataLoader, random_split
import random
import os
import sys
import glob
import json

# ── 설정 ──
WANDB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_logs")
os.makedirs(WANDB_DIR, exist_ok=True)

def set_seed(seed=777):
    random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

set_seed()

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Device: {device}")

# ── 하이퍼파라미터 ──
config = {
    "batch_size": 128,
    "epochs": 2,
    "lr": 0.001,
    "optimizer": "Adam",
    "weight_decay": 1e-4,
    "model": "ResNet18",
    "dataset": "CIFAR10",
    "seed": 777,
}

# =====================================================
# 1단계: WandB로 학습 & 로깅
# =====================================================
print("=" * 60)
print("1단계: WandB로 실제 학습 & 로깅")
print("=" * 60)

import wandb

# offline 모드로 실행 (WandB 서버 연결 불필요)
os.environ["WANDB_MODE"] = "offline"
os.environ["WANDB_DIR"] = WANDB_DIR
os.environ["WANDB_SILENT"] = "true"

run = wandb.init(
    project="parser-test",
    name="resnet18_cifar10_test",
    config=config,
    dir=WANDB_DIR,
)

print(f"  WandB run dir: {run.dir}")
print(f"  WandB run id:  {run.id}")

# ── 데이터셋 ──
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2470, 0.2435, 0.2616)),
])
train_ds = datasets.CIFAR10(root="./data", train=True, download=True, transform=transform)
test_ds = datasets.CIFAR10(root="./data", train=False, download=True, transform=transform)

train_size = int(0.8 * len(train_ds))
val_size = len(train_ds) - train_size
train_ds, val_ds = random_split(train_ds, [train_size, val_size])

train_loader = DataLoader(train_ds, batch_size=config["batch_size"], shuffle=True, num_workers=2)
val_loader = DataLoader(val_ds, batch_size=config["batch_size"], shuffle=False, num_workers=2)
test_loader = DataLoader(test_ds, batch_size=config["batch_size"], shuffle=False, num_workers=2)

# ── 모델 ──
model = torchvision.models.resnet18(weights=torchvision.models.ResNet18_Weights.DEFAULT)
model.fc = nn.Linear(model.fc.in_features, 10)
model = model.to(device)

criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.parameters(), lr=config["lr"], weight_decay=config["weight_decay"])

# ── 학습 ──
for epoch in range(config["epochs"]):
    model.train()
    train_loss, train_correct, train_total = 0.0, 0, 0

    for images, labels in train_loader:
        images, labels = images.to(device), labels.to(device)
        outputs = model(images)
        loss = criterion(outputs, labels)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        train_loss += loss.item() * images.size(0)
        _, predicted = torch.max(outputs.data, 1)
        train_total += labels.size(0)
        train_correct += (predicted == labels).sum().item()

    avg_train_loss = train_loss / train_total
    train_acc = train_correct / train_total

    # 검증
    model.eval()
    val_loss, val_correct, val_total = 0.0, 0, 0
    with torch.no_grad():
        for images, labels in val_loader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            loss = criterion(outputs, labels)
            val_loss += loss.item() * images.size(0)
            _, predicted = torch.max(outputs.data, 1)
            val_total += labels.size(0)
            val_correct += (predicted == labels).sum().item()

    avg_val_loss = val_loss / val_total
    val_acc = val_correct / val_total

    # WandB 로깅
    wandb.log({
        "epoch": epoch + 1,
        "train/loss": avg_train_loss,
        "train/accuracy": train_acc,
        "val/loss": avg_val_loss,
        "val/accuracy": val_acc,
    })

    print(f"  Epoch {epoch+1}/{config['epochs']}: "
          f"Train Loss={avg_train_loss:.4f}, Train Acc={train_acc:.4f}, "
          f"Val Loss={avg_val_loss:.4f}, Val Acc={val_acc:.4f}")

# ── 테스트 ──
model.eval()
test_loss, test_correct, test_total = 0.0, 0, 0
with torch.no_grad():
    for images, labels in test_loader:
        images, labels = images.to(device), labels.to(device)
        outputs = model(images)
        loss = criterion(outputs, labels)
        test_loss += loss.item() * images.size(0)
        _, predicted = torch.max(outputs.data, 1)
        test_total += labels.size(0)
        test_correct += (predicted == labels).sum().item()

test_acc = test_correct / test_total
avg_test_loss = test_loss / test_total

wandb.log({
    "test/accuracy": test_acc,
    "test/loss": avg_test_loss,
})

# summary에 최종 결과 기록
wandb.summary["best_val_accuracy"] = val_acc
wandb.summary["final_test_accuracy"] = test_acc
wandb.summary["final_test_loss"] = avg_test_loss

print(f"\n  Test Accuracy: {test_acc:.4f}, Test Loss: {avg_test_loss:.4f}")

# wandb run 경로 저장 (파서 테스트에 필요)
wandb_run_dir = run.dir  # .../files 경로
wandb_run_parent = os.path.dirname(wandb_run_dir)  # run-xxx 경로
print(f"  WandB run parent dir: {wandb_run_parent}")

# ── offline 모드: files/ 디렉토리에 json/yaml 수동 저장 ──
import yaml

files_dir = wandb_run_dir  # run.dir 은 이미 .../files 경로
os.makedirs(files_dir, exist_ok=True)

# 1) config.yaml — wandb 내부 형식({key: {value: v}})으로 저장
config_data = {}
for k, v in dict(wandb.config).items():
    config_data[k] = {"value": v}
with open(os.path.join(files_dir, "config.yaml"), "w") as f:
    yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
print(f"  ✅ config.yaml 저장됨")

# 2) wandb-summary.json
summary_data = {}
for k, v in dict(wandb.summary).items():
    if not k.startswith("_"):
        summary_data[k] = v
with open(os.path.join(files_dir, "wandb-summary.json"), "w") as f:
    json.dump(summary_data, f, indent=2, ensure_ascii=False)
print(f"  ✅ wandb-summary.json 저장됨")

# 3) wandb-metadata.json
import platform
metadata = {
    "python": platform.python_version(),
    "host": platform.node(),
    "os": platform.system(),
    "program": os.path.basename(__file__),
    "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "N/A",
    "gpuCount": torch.cuda.device_count() if torch.cuda.is_available() else 0,
}
with open(os.path.join(files_dir, "wandb-metadata.json"), "w") as f:
    json.dump(metadata, f, indent=2, ensure_ascii=False)
print(f"  ✅ wandb-metadata.json 저장됨")

wandb.finish()
print("\n  ✅ WandB 로깅 완료!")

# =====================================================
# 2단계: 실제 WandB 로그 파일 확인
# =====================================================
print("\n" + "=" * 60)
print("2단계: 생성된 WandB 로그 파일 확인")
print("=" * 60)

# wandb run 디렉토리: 1단계에서 저장한 경로 직접 사용
wandb_base = os.path.join(WANDB_DIR, "wandb")
real_run_dir = wandb_run_parent
print(f"  Run 디렉토리: {real_run_dir}")

files_dir = os.path.join(real_run_dir, "files")
if os.path.isdir(files_dir):
    print(f"  Files 디렉토리 내용:")
    for f in sorted(os.listdir(files_dir)):
        fpath = os.path.join(files_dir, f)
        size = os.path.getsize(fpath) if os.path.isfile(fpath) else "dir"
        print(f"    {f} ({size} bytes)")

# 주요 파일 내용 출력
import json
for fname in ["wandb-summary.json", "config.yaml", "wandb-metadata.json"]:
    fpath = os.path.join(files_dir, fname)
    if os.path.isfile(fpath):
        print(f"\n  === {fname} ===")
        with open(fpath, "r") as f:
            content = f.read()
        # JSON 파일이면 예쁘게 출력
        if fname.endswith(".json"):
            try:
                data = json.loads(content)
                print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])
            except:
                print(content[:1000])
        else:
            print(content[:1000])

# =====================================================
# 3단계: 파서로 실제 WandB 로그 파싱 테스트
# =====================================================
print("\n" + "=" * 60)
print("3단계: 파서 테스트 — 실제 WandB 로그 사용")
print("=" * 60)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.log_parsers import parse_wandb_run, parse_log, detect_log_type

# 직접 run 디렉토리 파싱
print("\n--- parse_wandb_run (직접 run 경로) ---")
result = parse_wandb_run(real_run_dir)
print(f"  Name:        {result['name']}")
print(f"  Hyperparams: {result['hyperparams']}")
print(f"  Metrics:     {result['metrics']}")
print(f"  Metadata:    {result.get('metadata', {})}")

# auto detect
print(f"\n--- detect_log_type ---")
print(f"  run dir:  {detect_log_type(real_run_dir)}")
print(f"  wandb/:   {detect_log_type(wandb_base)}")

# 통합 파서 (프로젝트 디렉토리)
print(f"\n--- parse_log (프로젝트 디렉토리 자동 탐색) ---")
result2 = parse_log(wandb_base)
print(f"  Name:        {result2['name']}")
print(f"  HP count:    {len(result2['hyperparams'])}")
print(f"  Metric count:{len(result2['metrics'])}")

# 검증
assert len(result["hyperparams"]) > 0, "하이퍼파라미터가 비어있습니다!"
assert len(result["metrics"]) > 0, "메트릭이 비어있습니다!"
assert "accuracy" in str(result["metrics"]).lower() or "loss" in str(result["metrics"]).lower(), \
    "주요 메트릭(accuracy/loss)을 찾을 수 없습니다!"

print("\n✅ 실제 WandB 로그 파싱 테스트 통과!")
