import streamlit as st
from core.runner import run_experiment
import os
import time
import threading

st.title("🟦 Experiment Runner")

# ----------------------
# Session State 초기화
# ----------------------
if "exp_process" not in st.session_state:
    st.session_state.exp_process = None

if "exp_log_path" not in st.session_state:
    st.session_state.exp_log_path = None

if "exp_output_lines" not in st.session_state:
    st.session_state.exp_output_lines = []

if "exp_running" not in st.session_state:
    st.session_state.exp_running = False

if "exp_log_file" not in st.session_state:
    st.session_state.exp_log_file = None

# ----------------------
# 실험 파일 선택
# ----------------------
workspace = st.session_state.get("workspace", ".")
exp_dir = os.path.join(workspace, "experiments")

exp_files = []
if os.path.exists(exp_dir):
    exp_files = [f for f in os.listdir(exp_dir) if f.endswith(".py") and f != "__init__.py"]

exp_options = exp_files + ["직접 입력 (Custom)"]

# 이전에 선택된 값이 exp_files에 없으면 Custom으로 취급
previous_selected = st.session_state.get("selected_exp")

if previous_selected and previous_selected.startswith("experiments/"):
    prev_filename = previous_selected.replace("experiments/", "", 1)
else:
    prev_filename = previous_selected

is_custom_prev = prev_filename not in exp_files if prev_filename else True

if is_custom_prev and previous_selected:
    default_idx = len(exp_options) - 1 # "직접 입력 (Custom)"
else:
    try:
        default_idx = exp_files.index(prev_filename) if prev_filename in exp_files else 0
    except ValueError:
        default_idx = 0

selected_option = st.selectbox("📂 Select Experiment", exp_options, index=default_idx)

if selected_option == "직접 입력 (Custom)":
    st.session_state.selected_exp = st.text_input("📝 실험 스크립트 경로 (workspace 기준 상대 경로)", value=previous_selected if is_custom_prev and previous_selected else "experiments/my_script.py")
else:
    st.session_state.selected_exp = f"experiments/{selected_option}"

if "target_log_dir" not in st.session_state:
    st.session_state.target_log_dir = "logs"

log_dir = st.text_input("📁 Log Directory", value=st.session_state.target_log_dir)
# Update session_state if changed manually without using the key parameter to avoid Streamlit rerun loops
if log_dir != st.session_state.target_log_dir:
    st.session_state.target_log_dir = log_dir

# ----------------------
# 백그라운드 출력 수집 스레드
# ----------------------
def collect_output(process, log_file, output_lines):
    """프로세스 stdout을 라인별로 수집하여 리스트에 추가"""
    try:
        for line in iter(process.stdout.readline, ""):
            if line:
                output_lines.append(line.rstrip("\n"))
                log_file.write(line)
                log_file.flush()
        process.stdout.close()
    except:
        pass
    finally:
        log_file.close()


# ----------------------
# 실험 시작
# ----------------------
col1, col2 = st.columns([1, 1])

with col1:
    start_clicked = st.button("🚀 Start Experiment", disabled=st.session_state.exp_running)

with col2:
    stop_clicked = st.button("⛔ Stop Experiment", disabled=not st.session_state.exp_running)

if start_clicked and not st.session_state.exp_running:
    if st.session_state.selected_exp:
        st.session_state.exp_output_lines = []

        workspace = st.session_state.get("workspace", ".")
        process, log_path, log_file = run_experiment(
            script_path=st.session_state.selected_exp,
            log_dir=log_dir,
            workspace=workspace
        )

        st.session_state.exp_process = process
        st.session_state.exp_log_path = log_path
        st.session_state.exp_log_file = log_file
        st.session_state.exp_running = True

        # 백그라운드 스레드로 출력 수집
        t = threading.Thread(
            target=collect_output,
            args=(process, log_file, st.session_state.exp_output_lines),
            daemon=True
        )
        t.start()
        st.rerun()

if stop_clicked and st.session_state.exp_running:
    if st.session_state.exp_process:
        st.session_state.exp_process.terminate()
    st.session_state.exp_running = False
    st.warning("⛔ 실험이 중단되었습니다.")
    st.session_state.exp_process = None


# ----------------------
# 상태 표시 + 터미널 출력
# ----------------------
if st.session_state.exp_running:
    process = st.session_state.exp_process

    if process and process.poll() is None:
        st.warning("🟡 Experiment Running...")
    else:
        st.success("🟢 Experiment Finished!")
        st.write(f"📄 Log saved at: `{st.session_state.exp_log_path}`")
        st.session_state.exp_running = False
        st.session_state.exp_process = None

# 터미널 출력 영역
st.subheader("📟 Terminal Output")

terminal_placeholder = st.empty()

if st.session_state.exp_output_lines:
    terminal_text = "\n".join(st.session_state.exp_output_lines[-200:])  # 최근 200줄
    terminal_placeholder.code(terminal_text, language="text")
else:
    terminal_placeholder.code("(대기 중...)", language="text")

# 자동 새로고침 (실행 중일 때)
if st.session_state.exp_running:
    time.sleep(1)
    st.rerun()