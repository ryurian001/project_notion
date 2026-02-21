"""
테스트용 WandB/TensorBoard/CSV 샘플 로그 생성 및 파서 검증 스크립트.

사용법 (project_notion conda 환경에서):
    python test_log_parsers.py
"""

import os
import json
import sys

# ── 1. 샘플 WandB 로그 디렉토리 생성 ──
print("=" * 50)
print("1. 샘플 WandB 로그 생성...")
wandb_dir = "test_logs/wandb/run-20260220_120000-abc123/files"
os.makedirs(wandb_dir, exist_ok=True)

# wandb-summary.json
summary_data = {
    "loss": 0.05,
    "accuracy": 0.95,
    "epoch": 10,
    "f1_score": 0.93,
    "_wandb": {},
    "_runtime": 120,
    "_step": 100,
    "_timestamp": 1234567890,
}
with open(f"{wandb_dir}/wandb-summary.json", "w") as f:
    json.dump(summary_data, f, indent=2)

# wandb-metadata.json
metadata = {
    "codePath": "train.py",
    "python": "3.10.12",
    "host": "gpu-server-01",
    "gpu": "NVIDIA RTX 4090",
    "gpuCount": 1,
}
with open(f"{wandb_dir}/wandb-metadata.json", "w") as f:
    json.dump(metadata, f, indent=2)

# wandb-history.jsonl
history_lines = [
    {"loss": 0.8, "accuracy": 0.5, "_step": 0},
    {"loss": 0.3, "accuracy": 0.8, "_step": 50},
    {"loss": 0.05, "accuracy": 0.95, "_step": 100},
]
with open(f"{wandb_dir}/wandb-history.jsonl", "w") as f:
    for line in history_lines:
        f.write(json.dumps(line) + "\n")

# config.yaml
try:
    import yaml
    config_data = {
        "lr": {"value": 0.001},
        "batch_size": {"value": 32},
        "epochs": {"value": 10},
        "optimizer": {"value": "Adam"},
        "weight_decay": {"value": 0.0001},
        "model": {"value": {"name": "ResNet18", "pretrained": True}},
        "_wandb": {"value": {"t": "test"}},
    }
    with open(f"{wandb_dir}/config.yaml", "w") as f:
        yaml.dump(config_data, f)
    print("  ✅ WandB config.yaml + wandb-summary.json + metadata + history 생성 완료")
except ImportError:
    print("  ⚠️ pyyaml 미설치 — config.yaml 생략 (summary만 테스트)")

# ── 2. 샘플 TensorBoard 로그 생성 ──
print("\n2. 샘플 TensorBoard 로그 생성...")
try:
    from torch.utils.tensorboard import SummaryWriter
    tb_dir = "test_logs/tb_logs"
    writer = SummaryWriter(tb_dir)
    for i in range(10):
        writer.add_scalar("train/loss", 1.0 - i * 0.1, i)
        writer.add_scalar("train/accuracy", i * 0.1, i)
        writer.add_scalar("val/loss", 1.1 - i * 0.1, i)
        writer.add_scalar("val/accuracy", i * 0.09, i)
    writer.close()
    print(f"  ✅ TensorBoard 이벤트 파일 생성 완료 ({tb_dir})")
except ImportError:
    print("  ⚠️ torch.utils.tensorboard 미설치 — tensorboard 테스트 생략")
    print("  💡 tensorboard 없이도 tbparse로 파싱은 가능합니다 (이미 생성된 파일로)")

# ── 3. 샘플 CSV 로그 생성 ──
print("\n3. 샘플 CSV 로그 생성...")
csv_dir = "test_logs/csv_logs"
os.makedirs(csv_dir, exist_ok=True)
csv_path = f"{csv_dir}/training_log.csv"
with open(csv_path, "w") as f:
    f.write("epoch,train_loss,val_loss,train_acc,val_acc,lr\n")
    for i in range(10):
        f.write(f"{i+1},{1.0-i*0.09:.4f},{1.1-i*0.08:.4f},{i*0.09:.4f},{i*0.08:.4f},0.001\n")
print(f"  ✅ CSV 학습 로그 생성 완료 ({csv_path})")

# ── 4. 파서 테스트 ──
print("\n" + "=" * 50)
print("4. 파서 테스트")
print("=" * 50)

try:
    from core.log_parsers import (
        parse_wandb_run, parse_tensorboard_log, parse_csv_log,
        detect_log_type, parse_log, _flatten_config
    )

    # Flat config 테스트
    print("\n--- Config Flatten 테스트 ---")
    nested = {"lr": {"value": 0.001}, "model": {"hidden": 256, "layers": 3}}
    flat = _flatten_config(nested)
    print(f"  입력: {nested}")
    print(f"  출력: {flat}")
    assert "lr" in flat and flat["lr"] == 0.001
    assert "model.hidden" in flat
    print("  ✅ 통과")

    # WandB 파서 테스트
    print("\n--- WandB 파서 ---")
    wandb_run_dir = "test_logs/wandb/run-20260220_120000-abc123"
    result = parse_wandb_run(wandb_run_dir)
    print(f"  Name:        {result['name']}")
    print(f"  Hyperparams: {result['hyperparams']}")
    print(f"  Metrics:     {result['metrics']}")
    print(f"  Metadata:    {result.get('metadata', {})}")
    assert result["metrics"].get("accuracy") == 0.95
    assert result["metrics"].get("loss") == 0.05
    print("  ✅ 통과")

    # WandB 프로젝트 디렉토리 자동 탐색 테스트
    print("\n--- WandB 프로젝트 디렉토리 자동 탐색 ---")
    detect_result = detect_log_type("test_logs/wandb")
    print(f"  test_logs/wandb → {detect_result} (expected: wandb)")
    assert detect_result == "wandb"
    result2 = parse_log("test_logs/wandb")
    print(f"  parse_log('test_logs/wandb') → metrics: {result2['metrics']}")
    print("  ✅ 통과")

    # Auto detect 테스트
    print(f"\n  Auto Detect: {detect_log_type(wandb_run_dir)} (expected: wandb)")

    # TensorBoard 파서 테스트
    tb_dir = "test_logs/tb_logs"
    if os.path.isdir(tb_dir):
        print("\n--- TensorBoard 파서 ---")
        result = parse_tensorboard_log(tb_dir)
        print(f"  Name:        {result['name']}")
        print(f"  Hyperparams: {result['hyperparams']}")
        print(f"  Metrics:     {result['metrics']}")
        # best 값 확인
        best_keys = [k for k in result["metrics"] if "_best" in k]
        print(f"  Best values: {best_keys}")
        print(f"\n  Auto Detect: {detect_log_type(tb_dir)} (expected: tensorboard)")
        print("  ✅ 통과")

    # CSV 파서 테스트
    print("\n--- CSV 파서 ---")
    result = parse_csv_log(csv_path)
    print(f"  Name:        {result['name']}")
    print(f"  Hyperparams: {result['hyperparams']}")
    print(f"  Metrics:     {result['metrics']}")
    assert len(result["metrics"]) > 0
    print(f"\n  Auto Detect (file): {detect_log_type(csv_path)} (expected: csv)")
    print(f"  Auto Detect (dir):  {detect_log_type(csv_dir)} (expected: csv)")
    print("  ✅ 통과")

    # CSV 디렉토리 자동 탐색 테스트
    print("\n--- CSV 디렉토리 자동 탐색 ---")
    result = parse_log(csv_dir)
    print(f"  parse_log('{csv_dir}') → metrics: {result['metrics']}")
    print("  ✅ 통과")

    # 통합 파서 테스트
    print("\n--- 통합 파서 (parse_log) ---")
    result = parse_log(wandb_run_dir)
    print(f"  WandB: {result['name']}, HP={len(result['hyperparams'])}, M={len(result['metrics'])}")
    result = parse_log(csv_path)
    print(f"  CSV:   {result['name']}, HP={len(result['hyperparams'])}, M={len(result['metrics'])}")

    print("\n✅ 모든 파서 테스트 통과!")

except Exception as e:
    print(f"❌ 파서 테스트 실패: {e}")
    import traceback
    traceback.print_exc()
