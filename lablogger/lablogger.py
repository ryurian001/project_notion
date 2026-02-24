import logging
import json
from datetime import datetime


class ExperimentLogger:

    def __init__(self):

        logging.basicConfig(
            level=logging.INFO,
            format="%(message)s"
        )

        self.log_event("experiment_start")


    # ----------------------------
    # 내부 JSON 기록 함수
    # ----------------------------
    def _log(self, data: dict):
        logging.info(json.dumps(data))


    # ----------------------------
    # 하이퍼파라미터 기록
    # ----------------------------
    def log_config(self, config: dict):

        for k, v in config.items():
            self._log({
                "type": "hyperparam",
                "key": k,
                "value": v
            })


    # ----------------------------
    # 메트릭 기록
    # ----------------------------
    def log_metric(self, **kwargs):

        data = {
            "type": "metric",
            "timestamp": datetime.now().isoformat()
        }

        data.update(kwargs)

        logging.info(json.dumps(data))


    # ----------------------------
    # 이벤트 기록
    # ----------------------------
    def log_event(self, message):

        self._log({
            "type": "event",
            "message": message,
            "timestamp": datetime.now().isoformat()
        })


    def end(self):
        self.log_event("experiment_end")
