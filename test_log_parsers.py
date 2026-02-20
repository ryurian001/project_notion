"""
테스트용 WandB/TensorBoard 샘플 로그 생성 및 파서 검증 스크립트.

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

# config.yaml
try:
    import yaml
    config_data = {
        "lr": {"value": 0.001},
        "batch_size": {"value": 32},
        "epochs": {"value": 10},
        "optimizer": {"value": "Adam"},
        "weight_decay": {"value": 0.0001},
        "_wandb": {"value": {"t": "test"}},
    }
    with open(f"{wandb_dir}/config.yaml", "w") as f:
        yaml.dump(config_data, f)
    print("  ✅ WandB config.yaml + wandb-summary.json 생성 완료")
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

# ── 3. 파서 테스트 ──
print("\n" + "=" * 50)
print("3. 파서 테스트")
print("=" * 50)

try:
    from core.log_parsers import parse_wandb_run, parse_tensorboard_log, detect_log_type, parse_log

    # WandB 파서 테스트
    print("\n--- WandB 파서 ---")
    wandb_run_dir = "test_logs/wandb/run-20260220_120000-abc123"
    result = parse_wandb_run(wandb_run_dir)
    print(f"  Name:        {result['name']}")
    print(f"  Hyperparams: {result['hyperparams']}")
    print(f"  Metrics:     {result['metrics']}")

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
        print(f"\n  Auto Detect: {detect_log_type(tb_dir)} (expected: tensorboard)")

    # 통합 파서 테스트
    print("\n--- 통합 파서 (parse_log) ---")
    result = parse_log(wandb_run_dir)
    print(f"  WandB: {result}")

    print("\n✅ 모든 파서 테스트 통과!")

except Exception as e:
    print(f"❌ 파서 테스트 실패: {e}")
    import traceback
    traceback.print_exc()
