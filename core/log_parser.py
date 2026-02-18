# core/log_parser.py

def parse_log(path):

    data = {}
    metrics = {}

    with open(path, "r") as f:
        lines = f.readlines()

    for line in lines:

        if "HP_" in line:
            part = line.split("HP_")[1].strip()
            key, value = part.split("=")

            try:
                value = float(value)
            except:
                pass

            data[key] = value

        if "ACC=" in line:
            parts = line.strip().split()
            for p in parts:
                if "ACC=" in p:
                    metrics["accuracy"] = float(p.split("=")[1])
                if "LOSS=" in p:
                    metrics["loss"] = float(p.split("=")[1])

    data.update(metrics)

    return data