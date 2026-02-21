"""
외부 로깅 라이브러리(WandB, TensorBoard, CSV)의 로그 파일을 파싱하는 모듈.

- parse_wandb_run(run_dir):      WandB run 디렉토리에서 config + summary 추출
- parse_tensorboard_log(log_dir): TensorBoard 이벤트 파일에서 스칼라 메트릭 추출
- parse_csv_log(csv_path):       CSV 학습 로그에서 하이퍼파라미터/메트릭 추출
- detect_log_type(path):         경로를 분석해 로그 타입 자동 판별
- parse_log(path, log_type):     통합 파서
"""

import csv
import json
import os
import glob
import re


# =====================================================================
# 공통 상수 & 헬퍼
# =====================================================================

# WandB 내부 키 (필터링 대상)
_WANDB_INTERNAL_KEYS = {
    "_wandb", "_runtime", "_timestamp", "_step",
    "_wandb_m", "_wandb_l", "_wandb_r",
}

# 하이퍼파라미터로 분류될 가능성이 높은 키 패턴
_HP_KEY_PATTERNS = {
    "lr", "learning_rate", "batch_size", "batch", "epochs", "num_epochs",
    "max_epochs", "optimizer", "weight_decay", "momentum", "dropout",
    "dropout_rate", "seed", "random_seed", "hidden_size", "hidden_dim",
    "num_layers", "num_heads", "embed_dim", "embedding_dim", "vocab_size",
    "max_len", "max_seq_len", "warmup_steps", "warmup", "scheduler",
    "lr_scheduler", "grad_clip", "gradient_clip", "num_workers",
    "model", "model_name", "architecture", "arch",
}

# 메트릭으로 분류될 가능성이 높은 키 패턴
_METRIC_KEY_PATTERNS = {
    "loss", "accuracy", "acc", "f1", "f1_score", "precision", "recall",
    "auc", "roc_auc", "mse", "rmse", "mae", "r2", "bleu", "rouge",
    "perplexity", "ppl", "top1", "top5", "iou", "dice", "map",
    "val_loss", "val_accuracy", "val_acc", "train_loss", "train_acc",
    "test_loss", "test_accuracy", "test_acc", "eval_loss", "eval_accuracy",
}

# 메트릭 중 best 값을 min으로 선택해야 하는 패턴
_MINIMIZE_PATTERNS = {"loss", "mse", "rmse", "mae", "perplexity", "ppl", "error"}
# 메트릭 중 best 값을 max로 선택해야 하는 패턴
_MAXIMIZE_PATTERNS = {"accuracy", "acc", "f1", "precision", "recall", "auc",
                      "bleu", "rouge", "iou", "dice", "map", "r2", "top1", "top5"}


def _is_wandb_internal(key: str) -> bool:
    """WandB 내부 메타데이터 키인지 확인"""
    return key.startswith("_") or key in _WANDB_INTERNAL_KEYS


def _flatten_config(d: dict, parent_key: str = "", sep: str = ".") -> dict:
    """
    중첩된 config dict를 flat하게 변환.

    예: {"model": {"lr": 0.001}} → {"model.lr": 0.001}
    WandB의 {key: {value: actual}} 형식도 자동 처리.
    """
    items = {}
    for k, v in d.items():
        if _is_wandb_internal(k):
            continue

        new_key = f"{parent_key}{sep}{k}" if parent_key else k

        # WandB config 형식: {"key": {"value": actual_val}}
        if isinstance(v, dict) and "value" in v and len(v) == 1:
            items[new_key] = v["value"]
        elif isinstance(v, dict) and "value" in v:
            # {"desc": ..., "value": actual} 같은 형식
            items[new_key] = v["value"]
        elif isinstance(v, dict):
            items.update(_flatten_config(v, new_key, sep))
        else:
            items[new_key] = v

    return items


def _classify_keys(data: dict) -> tuple[dict, dict]:
    """
    키-값 쌍을 하이퍼파라미터와 메트릭으로 자동 분류.

    Returns:
        (hyperparams, metrics) 튜플
    """
    hp = {}
    metrics = {}

    for key, val in data.items():
        key_lower = key.lower().replace("-", "_")

        # 숫자가 아니면 HP로 분류 (문자열 값은 설정값일 가능성 높음)
        if isinstance(val, str):
            hp[key] = val
            continue

        # 명시적 HP 패턴 매칭
        if any(p == key_lower or key_lower.endswith(f"_{p}") or key_lower.startswith(f"{p}_")
               for p in _HP_KEY_PATTERNS):
            hp[key] = val
            continue

        # 명시적 Metric 패턴 매칭
        if any(p in key_lower for p in _METRIC_KEY_PATTERNS):
            if isinstance(val, (int, float)):
                metrics[key] = val
                continue

        # 기본: 숫자값은 메트릭, 나머지는 HP
        if isinstance(val, (int, float)):
            # epoch, step 같은 건 HP로
            if key_lower in ("epoch", "step", "global_step", "total_steps"):
                hp[key] = val
            else:
                metrics[key] = val
        else:
            hp[key] = val

    return hp, metrics


def _should_minimize(tag: str) -> bool:
    """이 태그의 best 값이 min인지 판별"""
    tag_lower = tag.lower()
    return any(p in tag_lower for p in _MINIMIZE_PATTERNS)


def _should_maximize(tag: str) -> bool:
    """이 태그의 best 값이 max인지 판별"""
    tag_lower = tag.lower()
    return any(p in tag_lower for p in _MAXIMIZE_PATTERNS)


# =====================================================================
# WandB 파서
# =====================================================================

def _find_wandb_run_dir(path: str) -> str:
    """
    WandB 프로젝트 디렉토리에서 최신 run 디렉토리를 자동 탐색.

    사용자가 다음과 같은 경로를 입력할 수 있음:
    - wandb/                          → 내부에서 latest-run 또는 최신 run-* 찾기
    - wandb/run-20260220_120000-abc   → 그대로 반환
    - wandb/latest-run                → symlink resolve 후 반환
    """
    path = os.path.abspath(path)

    # 이미 run 디렉토리인지 확인 (files/ 하위에 wandb 파일이 있거나 직접 있으면)
    files_dir = os.path.join(path, "files")
    for check_dir in [files_dir, path]:
        if os.path.isdir(check_dir):
            if (os.path.isfile(os.path.join(check_dir, "wandb-summary.json")) or
                    os.path.isfile(os.path.join(check_dir, "config.yaml"))):
                return path

    # latest-run 심볼릭 링크 확인
    latest_run = os.path.join(path, "latest-run")
    if os.path.islink(latest_run) or os.path.isdir(latest_run):
        resolved = os.path.realpath(latest_run)
        if os.path.isdir(resolved):
            return resolved

    # run-* 패턴으로 최신 디렉토리 찾기
    run_dirs = sorted(glob.glob(os.path.join(path, "run-*")), reverse=True)
    for run_dir in run_dirs:
        if os.path.isdir(run_dir):
            return run_dir

    # 하위에 wandb/ 디렉토리가 있는지 확인
    wandb_subdir = os.path.join(path, "wandb")
    if os.path.isdir(wandb_subdir):
        return _find_wandb_run_dir(wandb_subdir)

    return path  # fallback


def _parse_wandb_metadata(files_dir: str) -> dict:
    """
    wandb-metadata.json에서 실행 환경 정보 추출.

    Returns:
        {"run_name": str, "program": str, "gpu": str, ...}
    """
    meta_path = os.path.join(files_dir, "wandb-metadata.json")
    info = {}

    if not os.path.isfile(meta_path):
        return info

    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        # run 이름
        if "codePath" in meta:
            info["program"] = meta["codePath"]
        if "gpu" in meta:
            info["gpu"] = meta["gpu"]
        if "gpuCount" in meta:
            info["gpu_count"] = meta["gpuCount"]
        if "python" in meta:
            info["python_version"] = meta["python"]
        if "host" in meta:
            info["host"] = meta["host"]

    except Exception:
        pass

    return info


def _parse_wandb_history(files_dir: str) -> dict:
    """
    wandb-history.jsonl에서 마지막 step의 메트릭 추출 (summary가 없을 때 fallback).

    Returns:
        메트릭 dict (숫자 값만)
    """
    history_path = os.path.join(files_dir, "wandb-history.jsonl")
    metrics = {}

    if not os.path.isfile(history_path):
        return metrics

    try:
        last_line = None
        with open(history_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    last_line = line

        if last_line:
            data = json.loads(last_line)
            for key, val in data.items():
                if _is_wandb_internal(key):
                    continue
                if isinstance(val, (int, float)):
                    metrics[key] = val

    except Exception:
        pass

    return metrics


def parse_wandb_run(run_dir: str) -> dict:
    """
    WandB run 디렉토리에서 하이퍼파라미터와 메트릭을 추출.

    지원하는 입력 경로:
    - wandb/run-YYYYMMDD_HHMMSS-<id>   → 직접 파싱
    - wandb/run-.../files/              → files/ 내부 파싱
    - wandb/latest-run                  → symlink resolve
    - wandb/                            → 최신 run 자동 탐색

    파싱 소스 (우선순위):
    1. config.yaml  → 하이퍼파라미터
    2. wandb-summary.json → 메트릭
    3. wandb-history.jsonl → summary 없을 때 fallback
    4. wandb-metadata.json → 실행 환경 정보

    Args:
        run_dir: WandB run 디렉토리 경로

    Returns:
        {"name": str, "hyperparams": dict, "metrics": dict, "metadata": dict}
    """
    # 프로젝트 디렉토리에서 run 디렉토리 자동 탐색
    run_dir = _find_wandb_run_dir(run_dir)
    run_dir = os.path.abspath(run_dir)

    # files/ 하위 디렉토리 탐색
    files_dir = os.path.join(run_dir, "files")
    if not os.path.isdir(files_dir):
        files_dir = run_dir

    result = {
        "name": os.path.basename(run_dir),
        "hyperparams": {},
        "metrics": {},
        "metadata": {},
    }

    # ── config.yaml → 하이퍼파라미터 ──
    config_path = os.path.join(files_dir, "config.yaml")
    if os.path.isfile(config_path):
        try:
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                raw_config = yaml.safe_load(f) or {}

            result["hyperparams"] = _flatten_config(raw_config)
        except ImportError:
            print("⚠️ config.yaml 파싱을 위해 pyyaml이 필요합니다: pip install pyyaml")
        except Exception as e:
            print(f"⚠️ WandB config.yaml 파싱 오류: {e}")

    # ── wandb-summary.json → 메트릭 ──
    summary_path = os.path.join(files_dir, "wandb-summary.json")
    has_summary = False
    if os.path.isfile(summary_path):
        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                raw_summary = json.load(f)

            for key, val in raw_summary.items():
                if _is_wandb_internal(key):
                    continue
                if isinstance(val, (int, float)):
                    result["metrics"][key] = val
            has_summary = True
        except Exception as e:
            print(f"⚠️ WandB summary 파싱 오류: {e}")

    # ── wandb-history.jsonl → summary가 없을 때 fallback ──
    if not has_summary or not result["metrics"]:
        history_metrics = _parse_wandb_history(files_dir)
        if history_metrics:
            # summary에 이미 있는 키는 덮어쓰지 않음
            for k, v in history_metrics.items():
                if k not in result["metrics"]:
                    result["metrics"][k] = v

    # ── wandb-metadata.json → 실행 환경 정보 ──
    result["metadata"] = _parse_wandb_metadata(files_dir)

    # run 이름 결정
    if "wandb_run_name" in result["hyperparams"]:
        result["name"] = str(result["hyperparams"].pop("wandb_run_name"))
    elif "run_name" in result["hyperparams"]:
        result["name"] = str(result["hyperparams"].pop("run_name"))

    # 파싱 실패 시 상세 에러 정보
    if not result["hyperparams"] and not result["metrics"]:
        existing = [f for f in os.listdir(files_dir)] if os.path.isdir(files_dir) else []
        raise ValueError(
            f"WandB run 디렉토리에서 파싱할 파일을 찾을 수 없습니다.\n"
            f"  경로: {files_dir}\n"
            f"  발견된 파일: {existing}\n"
            f"  필요한 파일: config.yaml, wandb-summary.json, 또는 wandb-history.jsonl"
        )

    return result


# =====================================================================
# TensorBoard 파서
# =====================================================================

def parse_tensorboard_log(log_dir: str) -> dict:
    """
    TensorBoard 이벤트 파일에서 스칼라 메트릭을 추출.

    tbparse 라이브러리를 사용합니다.
    하위 디렉토리(train/, val/ 등)도 자동으로 탐색합니다.

    각 메트릭에 대해:
    - last 값 (마지막 step)
    - best 값 (loss류 → min, accuracy류 → max)

    Args:
        log_dir: TensorBoard 로그 디렉토리 경로

    Returns:
        {"name": str, "hyperparams": dict, "metrics": dict}
    """
    try:
        from tbparse import SummaryReader
    except ImportError:
        raise ImportError(
            "TensorBoard 로그 파싱을 위해 tbparse가 필요합니다.\n"
            "설치: pip install tbparse"
        )

    log_dir = os.path.abspath(log_dir)

    result = {
        "name": os.path.basename(log_dir),
        "hyperparams": {},
        "metrics": {},
    }

    reader = SummaryReader(log_dir)

    # ── 스칼라 메트릭 ──
    scalars_df = reader.scalars
    if scalars_df is not None and not scalars_df.empty:
        for tag in scalars_df["tag"].unique():
            tag_data = scalars_df[scalars_df["tag"] == tag]
            values = tag_data["value"].values

            last_value = float(values[-1])

            # 태그 이름 정리: "/" → "_", 공백 → "_"
            clean_tag = re.sub(r"[/\s]+", "_", tag).strip("_")

            # last 값 저장
            result["metrics"][clean_tag] = round(last_value, 6)

            # best 값도 추가 (의미 있는 차이가 있을 때만)
            if len(values) > 1:
                if _should_minimize(clean_tag):
                    best_val = float(min(values))
                    if abs(best_val - last_value) > 1e-8:
                        result["metrics"][f"{clean_tag}_best"] = round(best_val, 6)
                elif _should_maximize(clean_tag):
                    best_val = float(max(values))
                    if abs(best_val - last_value) > 1e-8:
                        result["metrics"][f"{clean_tag}_best"] = round(best_val, 6)

    # ── hparams 추출 (있는 경우) ──
    try:
        hparams_df = reader.hparams
        if hparams_df is not None and not hparams_df.empty:
            for col in hparams_df.columns:
                val = hparams_df[col].iloc[0]
                if val != val:  # NaN check
                    continue
                result["hyperparams"][col] = val
    except Exception:
        pass

    # 파싱 결과 검증
    if not result["metrics"]:
        tfevents = glob.glob(os.path.join(log_dir, "**", "*.tfevents.*"), recursive=True)
        if not tfevents:
            raise ValueError(
                f"TensorBoard 이벤트 파일을 찾을 수 없습니다.\n"
                f"  경로: {log_dir}\n"
                f"  events.out.tfevents.* 파일이 있는 디렉토리를 지정해주세요."
            )

    return result


# =====================================================================
# CSV 로그 파서
# =====================================================================

def parse_csv_log(csv_path: str) -> dict:
    """
    CSV 형태의 학습 로그에서 하이퍼파라미터와 메트릭을 추출.

    지원하는 형태:
    - 일반 CSV: epoch, loss, accuracy, ... (마지막 row가 최종 메트릭)
    - 디렉토리 입력 시 내부 *.csv 자동 탐색

    Args:
        csv_path: CSV 파일 경로 또는 CSV가 있는 디렉토리 경로

    Returns:
        {"name": str, "hyperparams": dict, "metrics": dict}
    """
    csv_path = os.path.abspath(csv_path)

    # 디렉토리면 내부 CSV 탐색
    if os.path.isdir(csv_path):
        csv_files = glob.glob(os.path.join(csv_path, "*.csv"))
        if not csv_files:
            csv_files = glob.glob(os.path.join(csv_path, "**", "*.csv"), recursive=True)
        if not csv_files:
            raise ValueError(
                f"CSV 파일을 찾을 수 없습니다.\n"
                f"  경로: {csv_path}\n"
                f"  *.csv 파일이 있는 경로를 지정해주세요."
            )
        # 가장 최근 수정된 CSV 선택
        csv_path = max(csv_files, key=os.path.getmtime)

    if not os.path.isfile(csv_path):
        raise ValueError(f"CSV 파일을 찾을 수 없습니다: {csv_path}")

    result = {
        "name": os.path.splitext(os.path.basename(csv_path))[0],
        "hyperparams": {},
        "metrics": {},
    }

    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            # CSV 구분자 자동 감지
            sample = f.read(4096)
            f.seek(0)

            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel  # default comma-separated

            reader = csv.DictReader(f, dialect=dialect)
            rows = list(reader)

        if not rows:
            raise ValueError(f"CSV 파일이 비어 있습니다: {csv_path}")

        # 마지막 row에서 메트릭 추출
        last_row = rows[-1]

        for key, val_str in last_row.items():
            if not key or not val_str:
                continue

            key = key.strip()
            val_str = val_str.strip()

            # 숫자 변환 시도
            try:
                val = float(val_str)
                # 정수면 int로
                if val == int(val) and "." not in val_str:
                    val = int(val)
            except (ValueError, OverflowError):
                val = val_str

            result["metrics"][key] = val

        # HP vs Metric 자동 분류
        hp, metrics = _classify_keys(result["metrics"])
        result["hyperparams"] = hp
        result["metrics"] = metrics

        # 전체 row에서 best 값 추출
        if len(rows) > 1:
            for key in list(result["metrics"].keys()):
                try:
                    all_vals = [float(row.get(key, "nan")) for row in rows]
                    all_vals = [v for v in all_vals if v == v]  # NaN 제거
                except (ValueError, TypeError):
                    continue

                if not all_vals:
                    continue

                last_val = result["metrics"][key]
                if isinstance(last_val, (int, float)):
                    if _should_minimize(key):
                        best = min(all_vals)
                        if abs(best - last_val) > 1e-8:
                            result["metrics"][f"{key}_best"] = round(best, 6)
                    elif _should_maximize(key):
                        best = max(all_vals)
                        if abs(best - last_val) > 1e-8:
                            result["metrics"][f"{key}_best"] = round(best, 6)

    except csv.Error as e:
        raise ValueError(f"CSV 파싱 오류: {e}\n  파일: {csv_path}")

    return result


# =====================================================================
# 로그 타입 감지
# =====================================================================

def detect_log_type(path: str) -> str | None:
    """
    경로를 분석하여 로그 타입을 자동 판별.

    Args:
        path: 로그 디렉토리 또는 파일 경로

    Returns:
        "wandb", "tensorboard", "csv", 또는 None (판별 불가)
    """
    path = os.path.abspath(path)

    if not os.path.exists(path):
        return None

    # 단일 CSV 파일
    if os.path.isfile(path) and path.lower().endswith(".csv"):
        return "csv"

    if os.path.isdir(path):
        # WandB 판별: wandb-summary.json 또는 config.yaml 존재
        files_dir = os.path.join(path, "files")
        search_dirs = [files_dir, path] if os.path.isdir(files_dir) else [path]

        for d in search_dirs:
            if (os.path.isfile(os.path.join(d, "wandb-summary.json")) or
                    os.path.isfile(os.path.join(d, "config.yaml")) or
                    os.path.isfile(os.path.join(d, "wandb-history.jsonl"))):
                return "wandb"

        # WandB 프로젝트 디렉토리 (run-* 패턴 또는 latest-run)
        if (os.path.exists(os.path.join(path, "latest-run")) or
                glob.glob(os.path.join(path, "run-*"))):
            return "wandb"

        # TensorBoard 판별: tfevents 파일 존재
        tfevents = glob.glob(os.path.join(path, "**", "*.tfevents.*"), recursive=True)
        if not tfevents:
            tfevents = glob.glob(os.path.join(path, "*.tfevents.*"))
        if tfevents:
            return "tensorboard"

        # CSV 판별: 디렉토리 내 CSV 파일 존재
        csv_files = glob.glob(os.path.join(path, "*.csv"))
        if csv_files:
            return "csv"

    return None


# =====================================================================
# 통합 파서
# =====================================================================

def parse_log(path: str, log_type: str | None = None) -> dict:
    """
    로그 타입에 맞는 파서를 실행하여 결과를 반환.

    Args:
        path: 로그 디렉토리/파일 경로
        log_type: "wandb", "tensorboard", "csv", 또는 None (자동 감지)

    Returns:
        {"name": str, "hyperparams": dict, "metrics": dict}

    Raises:
        ValueError: 로그 타입을 판별할 수 없을 때
    """
    if log_type is None or log_type == "auto":
        log_type = detect_log_type(path)

    if log_type == "wandb":
        return parse_wandb_run(path)
    elif log_type == "tensorboard":
        return parse_tensorboard_log(path)
    elif log_type == "csv":
        return parse_csv_log(path)
    else:
        # 상세 에러 메시지
        path = os.path.abspath(path)
        if not os.path.exists(path):
            raise ValueError(f"경로를 찾을 수 없습니다: {path}")

        contents = os.listdir(path) if os.path.isdir(path) else []
        raise ValueError(
            f"로그 타입을 판별할 수 없습니다: {path}\n"
            f"  발견된 파일/폴더: {contents[:10]}{'...' if len(contents) > 10 else ''}\n\n"
            f"지원하는 로그 형식:\n"
            f"  • WandB:       wandb/run-YYYYMMDD-<id>/ (config.yaml + wandb-summary.json)\n"
            f"  • TensorBoard: runs/exp1/ (events.out.tfevents.* 파일)\n"
            f"  • CSV:         training_log.csv (epoch, loss, accuracy, ...)"
        )
