"""
외부 로깅 라이브러리(WandB, TensorBoard)의 로그 파일을 파싱하는 모듈.

- parse_wandb_run(run_dir): WandB run 디렉토리에서 config + summary 추출
- parse_tensorboard_log(log_dir): TensorBoard 이벤트 파일에서 스칼라 메트릭 추출
- detect_log_type(path): 경로를 분석해 로그 타입 자동 판별
"""

import json
import os
import glob


# WandB 내부 키 (필터링 대상)
_WANDB_INTERNAL_KEYS = {
    "_wandb", "_runtime", "_timestamp", "_step",
    "_wandb_m", "_wandb_l", "_wandb_r",
}


def _is_wandb_internal(key: str) -> bool:
    """WandB 내부 메타데이터 키인지 확인"""
    return key.startswith("_") or key in _WANDB_INTERNAL_KEYS


def parse_wandb_run(run_dir: str) -> dict:
    """
    WandB run 디렉토리에서 하이퍼파라미터와 메트릭을 추출.

    지원하는 디렉토리 구조:
    - wandb/run-YYYYMMDD_HHMMSS-<id>/files/
        - config.yaml → 하이퍼파라미터
        - wandb-summary.json → 최종 메트릭

    Args:
        run_dir: WandB run 디렉토리 경로
                 (예: ./wandb/run-20260220_120000-abc123 또는
                      ./wandb/latest-run)

    Returns:
        {"name": str, "hyperparams": dict, "metrics": dict}
    """
    run_dir = os.path.abspath(run_dir)

    # files/ 하위 디렉토리 탐색
    files_dir = os.path.join(run_dir, "files")
    if not os.path.isdir(files_dir):
        files_dir = run_dir  # files/ 없으면 run_dir 자체에서 탐색

    result = {
        "name": os.path.basename(run_dir),
        "hyperparams": {},
        "metrics": {},
    }

    # ── config.yaml → 하이퍼파라미터 ──
    config_path = os.path.join(files_dir, "config.yaml")
    if os.path.isfile(config_path):
        try:
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                raw_config = yaml.safe_load(f) or {}

            for key, val in raw_config.items():
                if _is_wandb_internal(key):
                    continue
                # WandB config는 {"key": {"value": actual_val}} 형식
                if isinstance(val, dict) and "value" in val:
                    result["hyperparams"][key] = val["value"]
                else:
                    result["hyperparams"][key] = val
        except Exception as e:
            print(f"⚠️ WandB config.yaml 파싱 오류: {e}")

    # ── wandb-summary.json → 메트릭 ──
    summary_path = os.path.join(files_dir, "wandb-summary.json")
    if os.path.isfile(summary_path):
        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                raw_summary = json.load(f)

            for key, val in raw_summary.items():
                if _is_wandb_internal(key):
                    continue
                # 숫자 값만 메트릭으로 취급
                if isinstance(val, (int, float)):
                    result["metrics"][key] = val
        except Exception as e:
            print(f"⚠️ WandB summary 파싱 오류: {e}")

    # run 이름: config에 wandb_run_name이 있으면 사용
    if "wandb_run_name" in result["hyperparams"]:
        result["name"] = result["hyperparams"].pop("wandb_run_name")

    return result


def parse_tensorboard_log(log_dir: str) -> dict:
    """
    TensorBoard 이벤트 파일에서 스칼라 메트릭을 추출.

    tbparse 라이브러리를 사용하여 tfevents 파일을 파싱합니다.

    Args:
        log_dir: TensorBoard 로그 디렉토리 경로
                 (예: ./runs/exp1 또는 ./tb_logs)

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

    # ── 스칼라 메트릭 (마지막 step 값 사용) ──
    scalars_df = reader.scalars
    if scalars_df is not None and not scalars_df.empty:
        # 각 태그의 마지막 step 값을 메트릭으로 추출
        for tag in scalars_df["tag"].unique():
            tag_data = scalars_df[scalars_df["tag"] == tag]
            last_value = tag_data.iloc[-1]["value"]

            # 태그 이름 정리 (/ → _)
            clean_tag = tag.replace("/", "_")
            result["metrics"][clean_tag] = float(last_value)

    # ── hparams 추출 (있는 경우) ──
    try:
        hparams_df = reader.hparams
        if hparams_df is not None and not hparams_df.empty:
            # hparams DataFrame의 각 컬럼을 하이퍼파라미터로
            for col in hparams_df.columns:
                val = hparams_df[col].iloc[0]
                # NaN 체크
                if val != val:  # NaN check
                    continue
                result["hyperparams"][col] = val
    except Exception:
        pass  # hparams가 없을 수 있음

    return result


def detect_log_type(path: str) -> str | None:
    """
    경로를 분석하여 로그 타입을 자동 판별.

    Args:
        path: 로그 디렉토리 또는 파일 경로

    Returns:
        "wandb", "tensorboard", 또는 None (판별 불가)
    """
    path = os.path.abspath(path)

    if not os.path.exists(path):
        return None

    # WandB 판별: wandb-summary.json 또는 config.yaml 존재
    if os.path.isdir(path):
        files_dir = os.path.join(path, "files")
        search_dirs = [files_dir, path] if os.path.isdir(files_dir) else [path]

        for d in search_dirs:
            if (os.path.isfile(os.path.join(d, "wandb-summary.json")) or
                    os.path.isfile(os.path.join(d, "config.yaml"))):
                return "wandb"

        # TensorBoard 판별: tfevents 파일 존재
        tfevents = glob.glob(os.path.join(path, "**", "*.tfevents.*"), recursive=True)
        if not tfevents:
            tfevents = glob.glob(os.path.join(path, "*.tfevents.*"))
        if tfevents:
            return "tensorboard"

    return None


# ── 통합 파서 ──
def parse_log(path: str, log_type: str | None = None) -> dict:
    """
    로그 타입에 맞는 파서를 실행하여 결과를 반환.

    Args:
        path: 로그 디렉토리 경로
        log_type: "wandb", "tensorboard", 또는 None (자동 감지)

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
    else:
        raise ValueError(
            f"로그 타입을 판별할 수 없습니다: {path}\n"
            "WandB run 디렉토리 또는 TensorBoard 로그 디렉토리를 지정해주세요."
        )
