# experiments/train_lora.py

import logging
import argparse
import time
import random


# -----------------------------
# 공통: 하이퍼파라미터 기록 함수
# -----------------------------
def log_hyperparams(config):
    for k, v in config.items():
        logging.info(f"HP_{k}={v}")


# -----------------------------
# LoRA 실험
# -----------------------------
def train(config):

    logging.info("===== LORA EXPERIMENT START =====")

    # 🔥 하이퍼파라미터 자동 기록
    log_hyperparams(config)

    epochs = config["epochs"]

    for epoch in range(epochs):

        acc = random.uniform(0.7, 0.95)
        loss = random.uniform(0.05, 0.3)

        logging.info(
            f"EPOCH={epoch} ACC={acc:.4f} LOSS={loss:.4f}"
        )

        time.sleep(0.3)

    logging.info("===== LORA EXPERIMENT END =====")


# -----------------------------
# argparse
# -----------------------------
if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    # 공통 파라미터
    parser.add_argument("--lr", type=float, default=0.0002)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--epochs", type=int, default=5)

    # LoRA 전용
    parser.add_argument("--lora_q", type=str, default="True")
    parser.add_argument("--lora_v", type=str, default="True")
    parser.add_argument("--lora_rank", type=int, default=8)
    parser.add_argument("--lora_alpha", type=int, default=16)
    parser.add_argument("--lora_dropout", type=float, default=0.1)

    args = parser.parse_args()

    config = vars(args)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(message)s"
    )

    train(config)