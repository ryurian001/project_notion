import subprocess
import datetime
import os

def run_experiment(script_path, log_dir, extra_args=None):

    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(log_dir, f"run_{timestamp}.log")

    cmd = ["python", script_path]

    if extra_args:
        for k, v in extra_args.items():
            cmd += [f"--{k}", str(v)]

    with open(log_path, "w") as f:
        process = subprocess.Popen(cmd, stdout=f, stderr=f)

    return process, log_path