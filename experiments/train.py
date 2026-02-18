# experiments/train_kd.py

import logging
import argparse
import time
import random


def log_hyperparams(config):
    for k, v in config.items():
        logging.info(f"HP_{k}={v}")


def train(config):

    logging.info("===== KD EXPERIMENT START =====")

    log_hyperparams(config)

    epochs = config["epochs"]

    for epoch in range(epochs):

        acc = random.uniform(0.75, 0.93)
        loss = random.uniform(0.03, 0.2)

        logging.info(
            f"EPOCH={epoch} ACC={acc:.4f} LOSS={loss:.4f}"
        )

        time.sleep(0.3)

    logging.info("===== KD EXPERIMENT END =====")


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    # 공통
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=5)

    # KD 전용
    parser.add_argument("--teacher_model", type=str, default="ResNet50")
    parser.add_argument("--temperature", type=float, default=4.0)
    parser.add_argument("--alpha", type=float, default=0.7)
    parser.add_argument("--distill_loss", type=str, default="KL")

    args = parser.parse_args()

    config = vars(args)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(message)s"
    )

    train(config)