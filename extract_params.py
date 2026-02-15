"""
학습 코드에서 하이퍼파라미터와 메트릭을 자동 추출하는 모듈.

- extract_hyperparams(filepath): Python AST로 코드에서 하이퍼파라미터 추출
- extract_metrics(stdout_text): 학습 출력에서 메트릭 정규식 추출
"""

import ast
import re


# -------------------------
# 🔹 추출 대상 변수명 목록
# -------------------------
KNOWN_HYPERPARAMS = {
    "batch_size", "lr", "learning_rate", "num_epochs", "epochs",
    "weight_decay", "momentum", "dropout", "dropout_rate",
    "seed", "num_workers", "max_lr", "min_lr",
}

KNOWN_OPTIMIZERS = {
    "SGD", "Adam", "AdamW", "RMSprop", "Adagrad", "Adadelta", "Adamax", "ASGD",
}


def _eval_node(node):
    """AST 노드에서 Python 리터럴 값을 추출"""
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        pass

    # 음수 (UnaryOp: -0.001 등)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        val = _eval_node(node.operand)
        if val is not None:
            return -val

    return None


def extract_hyperparams(filepath: str) -> dict:
    """
    Python 학습 코드에서 하이퍼파라미터를 AST 파싱으로 추출.

    추출 대상:
    1. 알려진 변수명 할당 (batch_size = 128, num_epochs = 10)
    2. optim.XXX(...) 호출에서 optimizer 이름 + lr, weight_decay 등 키워드 인자

    Returns:
        dict: {"batch_size": 128, "lr": 0.001, "optimizer": "Adam", ...}
    """
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)
    params = {}

    for node in ast.walk(tree):

        # (1) 변수 할당: batch_size = 128
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.lower() in KNOWN_HYPERPARAMS:
                    val = _eval_node(node.value)
                    if val is not None:
                        params[target.id] = val

        # (2) optim.Adam(model.parameters(), lr=0.001, weight_decay=1e-4)
        if isinstance(node, ast.Call):
            func = node.func

            # optim.Adam 형태
            is_optim_call = False
            optimizer_name = None

            if isinstance(func, ast.Attribute):
                # optim.Adam
                if isinstance(func.value, ast.Name) and func.value.id in ("optim", "torch_optim"):
                    if func.attr in KNOWN_OPTIMIZERS:
                        is_optim_call = True
                        optimizer_name = func.attr
                # torch.optim.Adam
                elif isinstance(func.value, ast.Attribute):
                    if func.attr in KNOWN_OPTIMIZERS:
                        is_optim_call = True
                        optimizer_name = func.attr

            if is_optim_call:
                params["optimizer"] = optimizer_name

                # 키워드 인자 추출 (lr, weight_decay 등)
                for kw in node.keywords:
                    if kw.arg and kw.arg.lower() in KNOWN_HYPERPARAMS:
                        val = _eval_node(kw.value)
                        if val is not None:
                            params[kw.arg] = val

    return params


def extract_metrics(stdout_text: str) -> dict:
    """
    학습 스크립트의 stdout 출력에서 메트릭을 정규식으로 추출.

    지원하는 패턴:
    - "Test Accuracy: XX.XX%"
    - "Test Loss: X.XXXX"
    - 마지막 Epoch 행에서 Train/Val Loss, Acc

    Returns:
        dict: {"test_accuracy": 95.23, "test_loss": 0.045, ...}
    """
    metrics = {}

    # Test Accuracy: XX.XX%
    m = re.search(r"Test Accuracy:\s*([\d.]+)%", stdout_text)
    if m:
        metrics["test_accuracy"] = float(m.group(1))

    # Test Loss: X.XXXX
    m = re.search(r"Test Loss:\s*([\d.]+)", stdout_text)
    if m:
        metrics["test_loss"] = float(m.group(1))

    # 마지막 Epoch 행: "Epoch N: Train Loss: X.XXXX, Train Acc: XX.XX%, Val Loss: X.XXXX, Val Acc: XX.XX%"
    epoch_lines = re.findall(
        r"Epoch\s+\d+.*?Train Loss:\s*([\d.]+).*?Train Acc:\s*([\d.]+)%.*?Val Loss:\s*([\d.]+).*?Val Acc:\s*([\d.]+)%",
        stdout_text
    )
    if epoch_lines:
        last = epoch_lines[-1]
        metrics["final_train_loss"] = float(last[0])
        metrics["final_train_acc"] = float(last[1])
        metrics["final_val_loss"] = float(last[2])
        metrics["final_val_acc"] = float(last[3])

    return metrics


# -------------------------
# 🔹 테스트용 실행
# -------------------------
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python extract_params.py <script.py>")
        sys.exit(1)

    filepath = sys.argv[1]
    print("=== Hyperparameters ===")
    hp = extract_hyperparams(filepath)
    for k, v in hp.items():
        print(f"  {k}: {v}")

    print("\n(Run the script to extract metrics from stdout)")
