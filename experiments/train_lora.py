import argparse
import time
import random
from core.lablogger import ExperimentLogger


def train(config):

    logger = ExperimentLogger()

    # 🔥 통일된 방식
    logger.log_config(config)

    for epoch in range(config["epochs"]):

        acc = random.uniform(0.8, 0.95)
        loss = random.uniform(0.05, 0.2)

        logger.log_metric(
            epoch=epoch,
            accuracy=round(acc, 4),
            loss=round(loss, 4)
        )

        time.sleep(0.3)

    logger.end()


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument("--lr", type=float, default=0.0002)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--lora_rank", type=int, default=8)

    args = parser.parse_args()

    train(vars(args))