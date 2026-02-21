import subprocess
import datetime
import os
import sys


def run_experiment(script_path, log_dir, extra_args=None):
    """
    실험 실행. stdout/stderr를 PIPE로 캡처하여 실시간 읽기 가능.
    동시에 로그 파일에도 기록.
    Returns: (process, log_path, log_file)
    """
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    logs_path = os.path.join(project_root, log_dir)
    os.makedirs(logs_path, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(logs_path, f"run_{timestamp}.log")

    cmd = [
        sys.executable, "-u",  # -u: unbuffered output
        "-m",
        script_path.replace("/", ".").replace("\\", ".").replace(".py", "")
    ]

    if extra_args:
        for k, v in extra_args.items():
            # 정수형 float (16.0 등) → int 변환하여 argparse 호환
            if isinstance(v, float) and v == int(v):
                v = int(v)
            cmd += [f"--{k}", str(v)]

    log_file = open(log_path, "w")

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=project_root,
        bufsize=1,
        universal_newlines=True
    )

    return process, log_path, log_file