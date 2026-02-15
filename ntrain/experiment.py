"""
ntrain.Experiment — 하이퍼파라미터와 메트릭을 표준화된 방식으로 정의하고 저장.

사용법:
    from ntrain import Experiment

    exp = Experiment(
        name="ResNet18_CIFAR10",
        batch_size=128,
        epochs=10,
        lr=0.001,
        optimizer="Adam",
        weight_decay=1e-4,   # 커스텀 하이퍼파라미터도 자유롭게
    )

    # 학습 후 메트릭 기록
    exp.log_metrics(accuracy=95.2, loss=0.045)

    # JSON 저장
    exp.save()
"""

import json
import os
from datetime import datetime


class Experiment:
    """학습 실험의 하이퍼파라미터와 메트릭을 관리하는 클래스."""

    # 필수 하이퍼파라미터 (GUI 기본 필드와 매핑)
    REQUIRED_PARAMS = {"batch_size", "epochs", "lr", "optimizer"}

    def __init__(self, name: str, batch_size: int, epochs: int, lr: float, optimizer: str, **kwargs):
        """
        Args:
            name: 실험 이름 (예: "ResNet18_CIFAR10_v1")
            batch_size: 배치 크기
            epochs: 에폭 수
            lr: 학습률
            optimizer: 옵티마이저 이름 (예: "Adam", "SGD")
            **kwargs: 추가 하이퍼파라미터 (dropout, weight_decay 등)
        """
        self.name = name
        self.hyperparams = {
            "batch_size": batch_size,
            "epochs": epochs,
            "lr": lr,
            "optimizer": optimizer,
        }
        self.hyperparams.update(kwargs)
        self.metrics = {}
        self._save_path = None

    def log_metrics(self, **metrics):
        """
        학습 결과 메트릭을 기록.

        Args:
            **metrics: accuracy=95.2, loss=0.045, f1_score=0.93 등
        """
        self.metrics.update(metrics)

    def to_dict(self) -> dict:
        """전체 실험 데이터를 딕셔너리로 반환."""
        return {
            "name": self.name,
            "hyperparams": self.hyperparams,
            "metrics": self.metrics,
            "timestamp": datetime.now().isoformat(),
        }

    def save(self, path: str = None):
        """
        실험 데이터를 JSON 파일로 저장.

        Args:
            path: 저장 경로 (기본: 현재 디렉토리의 experiment_result.json)
        """
        if path is None:
            path = "experiment_result.json"

        self._save_path = path
        data = self.to_dict()

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"📦 Experiment saved to {os.path.abspath(path)}")

    def __repr__(self):
        params = ", ".join(f"{k}={v}" for k, v in self.hyperparams.items())
        return f"Experiment(name='{self.name}', {params})"
