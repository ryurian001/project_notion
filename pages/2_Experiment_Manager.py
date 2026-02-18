import streamlit as st
import os
from core.log_parser import parse_log
from core.runner import run_experiment
from core.notion_logger import auto_log

st.title("🟩 Experiment Manager")

log_dir = st.text_input("Log Directory", value="logs")

if not os.path.exists(log_dir):
    st.warning("Log directory not found")
    st.stop()

logs = sorted(
    [f for f in os.listdir(log_dir) if f.endswith(".log")],
    reverse=True
)

if not logs:
    st.info("No logs found")
    st.stop()

selected_log = st.selectbox("Select Log", logs)

# 로그에서 자동 추출
data = parse_log(os.path.join(log_dir, selected_log))

st.subheader("Extracted Hyperparameters")

edited_data = {}

for k, v in data.items():
    new_val = st.text_input(k, str(v))
    try:
        new_val = float(new_val)
    except:
        pass
    edited_data[k] = new_val


# 🔥 다시 RUN
if st.button("🔁 Re-run with Modified Params"):

    script_name = "train_lora.py" if "lora" in selected_log.lower() else "train_kd.py"

    log_path = run_experiment(
        script_path=f"experiments/{script_name}",
        log_dir=log_dir,
        extra_args=edited_data
    )[1]

    st.success(f"New run created: {log_path}")


# 🔥 Notion 기록
if st.button("📤 Log to Notion"):
    auto_log(selected_log.replace(".log", ""), edited_data)
    st.success("Logged to Notion")