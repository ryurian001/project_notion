# core/grid_search.py

import itertools
import numpy as np


def generate_range(min_val, max_val, step):
    """min, max, step으로 값 리스트 생성"""
    # max_val + step * 0.5 로 인해 max_val을 초과하는 값이 나올 수 있음
    values = np.arange(min_val, max_val + step * 0.5, step).tolist()
    # 부동소수점 정리
    values = [round(v, 10) for v in values]

    result = []
    for v in values:
        if v > max_val:
            if max_val not in result:
                result.append(max_val)
        else:
            if v not in result:
                result.append(v)

    return result


def generate_grid(params_config):
    """
    파라미터 설정으로 Grid Search 조합 생성.

    params_config 형태:
    {
        "lr": {"mode": "range", "min": 0.001, "max": 0.01, "step": 0.003},
        "batch_size": {"mode": "single", "value": 32},
        "epochs": {"mode": "single", "value": 5}
    }

    Returns: list of dicts (각 조합)
    """
    param_names = []
    param_values = []

    for name, config in params_config.items():
        param_names.append(name)

        if config["mode"] == "range":
            values = generate_range(config["min"], config["max"], config["step"])
            param_values.append(values)
        else:  # single
            param_values.append([config["value"]])

    combinations = list(itertools.product(*param_values))

    result = []
    for combo in combinations:
        param_dict = {}
        for name, val in zip(param_names, combo):
            param_dict[name] = val
        result.append(param_dict)

    return result
