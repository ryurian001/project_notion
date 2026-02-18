import streamlit as st
from core.runner import run_experiment
from core.experiment_state import ExperimentState
import os

st.title("🟦 Experiment Runner")

if "state" not in st.session_state:
    st.session_state.state = ExperimentState.IDLE

# 실험 파일 선택
exp_files = os.listdir("experiments")
selected_exp = st.selectbox("Select Experiment", exp_files)

# 로그 단위 설정
log_dir = st.text_input("Log Directory", value="logs")

if st.button("🚀 Start Experiment"):

    st.session_state.state = ExperimentState.RUNNING

    process, log_path = run_experiment(
        script_path=f"experiments/{selected_exp}",
        log_dir=log_dir
    )

    st.session_state.process = process
    st.session_state.log_path = log_path

# 상태 표시
if st.session_state.state == ExperimentState.RUNNING:
    st.warning("🟡 Experiment Running...")

    if st.button("⏹ Mark as Finished"):
        st.session_state.state = ExperimentState.FINISHED

if st.session_state.state == ExperimentState.FINISHED:
    st.success("🟢 Experiment Finished")
