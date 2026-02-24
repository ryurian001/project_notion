import subprocess
import datetime
import os
import sys


def run_experiment(script_path, log_dir, workspace=".", extra_args=None):
    """
    실험 실행. stdout/stderr를 PIPE로 캡처하여 실시간 읽기 가능.
    동시에 로그 파일에도 기록.
    Returns: (process, log_path, log_file)
    """
    project_root = os.path.abspath(workspace)

    logs_path = os.path.join(project_root, log_dir)
    os.makedirs(logs_path, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(logs_path, f"run_{timestamp}.log")

    if script_path.endswith(".py") or "/" in script_path.replace("\\", "/"):
        cmd = [sys.executable, "-u", script_path]
    else:
        cmd = [
            sys.executable, "-u",  # -u: unbuffered output
            "-m",
            script_path
        ]

    if extra_args:
        for k, v in extra_args.items():
            # 정수형 float (16.0 등) → int 변환하여 argparse 호환
            if isinstance(v, float) and v == int(v):
                v = int(v)
            cmd += [f"--{k}", str(v)]

    log_file = open(log_path, "w")

    env = os.environ.copy()
    script_dir = os.path.abspath(os.path.join(project_root, os.path.dirname(script_path)))
    # Add project_root and script_dir to PYTHONPATH so root/sibling imports work
    new_pythonpath = f"{project_root}:{script_dir}"
    env["PYTHONPATH"] = f'{new_pythonpath}:{env.get("PYTHONPATH", "")}' if env.get("PYTHONPATH") else new_pythonpath

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=project_root,
        env=env,
        bufsize=1,
        universal_newlines=True
    )

    return process, log_path, log_file