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
# workspace가 설정되어 있지 않으면 기본값 "."
workspace = st.session_state.get("workspace", ".")
exp_dir = os.path.join(workspace, "experiments")

if os.path.exists(exp_dir):
    exp_files = [f for f in os.listdir(exp_dir) if f.endswith(".py") and f != "__init__.py"]
else:
    exp_files = []

if "selected_exp" not in st.session_state:
    st.session_state.selected_exp = exp_files[0] if exp_files else None

try:
    if exp_files:
        default_idx = exp_files.index(st.session_state.selected_exp) if st.session_state.selected_exp in exp_files else 0
    else:
        default_idx = 0
except ValueError:
    default_idx = 0

selected_exp = st.selectbox("📂 Select Experiment", exp_files if exp_files else ["(experiments 폴더 없음)"], index=default_idx)
if selected_exp != "(experiments 폴더 없음)":
    st.session_state.selected_exp = selected_exp

log_dir = st.text_input("📁 Log Directory", value="logs")


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
    if selected_exp and selected_exp != "(experiments 폴더 없음)":
        st.session_state.exp_output_lines = []

        workspace = st.session_state.get("workspace", ".")
        process, log_path, log_file = run_experiment(
            script_path=f"experiments/{selected_exp}",
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