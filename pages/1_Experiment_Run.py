import streamlit as st
from core.runner import run_experiment
import os
import time

st.title("🟦 Experiment Runner")

if "process" not in st.session_state:
    st.session_state.process = None

if "log_path" not in st.session_state:
    st.session_state.log_path = None


exp_files = os.listdir("experiments")
selected_exp = st.selectbox("Select Experiment", exp_files)

log_dir = st.text_input("Log Directory", value="logs")


# ----------------------
# 실험 시작
# ----------------------
if st.button("🚀 Start Experiment"):

    process, log_path = run_experiment(
        script_path=f"experiments/{selected_exp}",
        log_dir=log_dir
    )

    st.session_state.process = process
    st.session_state.log_path = log_path


# ----------------------
# 상태 자동 체크
# ----------------------
if st.session_state.process:

    status = st.session_state.process.poll()

    if status is None:
        st.warning("🟡 Experiment Running...")

        # 🔥 자동 새로고침
        time.sleep(2)
        st.rerun()

    else:
        st.success("🟢 Experiment Finished")
        st.write(f"Log saved at: {st.session_state.log_path}")

        # 프로세스 초기화
        st.session_state.process = None
if st.session_state.process and st.session_state.process.poll() is None:

    if st.button("⛔ Stop Experiment"):
        st.session_state.process.terminate()
        st.warning("Experiment Stopped")
        st.session_state.process = None