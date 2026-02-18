import json

def parse_log(path):

    hyperparams = {}
    latest_metrics = {}

    with open(path, "r") as f:
        for line in f:

            # 🔥 JSON 시작 위치 찾기
            json_start = line.find("{")

            if json_start == -1:
                continue

            json_part = line[json_start:].strip()

            try:
                data = json.loads(json_part)
            except:
                continue

            if data.get("type") == "hyperparam":
                hyperparams[data["key"]] = data["value"]

            if data.get("type") == "metric":
                latest_metrics = data

    result = {}
    result.update(hyperparams)

    if latest_metrics:
        latest_metrics.pop("type", None)
        result.update(latest_metrics)

    return result