import subprocess
import datetime
import os
import sys

def run_experiment(script_path, log_dir, extra_args=None):

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    logs_path = os.path.join(project_root, log_dir)
    os.makedirs(logs_path, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(logs_path, f"run_{timestamp}.log")

    full_script_path = os.path.join(project_root, script_path)

    cmd = [
        sys.executable,
        "-m",
        script_path.replace("/", ".").replace("\\", ".").replace(".py", "")
    ]

    if extra_args:
        for k, v in extra_args.items():
            cmd += [f"--{k}", str(v)]

    log_file = open(log_path, "w")

    process = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=log_file,
        cwd=project_root
    )

    return process, log_path