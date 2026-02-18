from core.lablogger import ExperimentLogger
import argparse
import time
import random


def train(config):

    logger = ExperimentLogger()

    logger.log_event("KD EXPERIMENT START")
    logger.log_config(config)

    for epoch in range(config["epochs"]):

        acc = random.uniform(0.75, 0.93)
        loss = random.uniform(0.03, 0.2)

        # 🔥 여기 중요
        logger.log_metric(
            epoch=epoch,
            accuracy=round(acc, 4),
            loss=round(loss, 4)
        )

        time.sleep(0.3)

    logger.end()


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--teacher_model", type=str, default="ResNet50")
    parser.add_argument("--temperature", type=float, default=4.0)
    parser.add_argument("--alpha", type=float, default=0.7)
    parser.add_argument("--distill_loss", type=str, default="KL")

    args = parser.parse_args()

    train(vars(args))