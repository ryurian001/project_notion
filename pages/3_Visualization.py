import streamlit as st
import os
import json
import pandas as pd
from datetime import datetime

LOG_DIR = "logs"

st.title("📊 Experiment Visualization")

# ----------------------------
# 로그 파일 목록
# ----------------------------
if not os.path.exists(LOG_DIR):
    st.error("logs 폴더가 존재하지 않습니다.")
    st.stop()

log_files = sorted(os.listdir(LOG_DIR), reverse=True)

if not log_files:
    st.warning("로그 파일이 없습니다.")
    st.stop()

selected_log = st.selectbox("📁 Select Log File", log_files)

log_path = os.path.join(LOG_DIR, selected_log)


# ----------------------------
# JSON 파싱 함수
# ----------------------------
def parse_log(path):
    hyperparams = {}
    metrics = []
    start_time = None
    end_time = None

    with open(path, "r") as f:
        for line in f:
            try:
                data = json.loads(line.strip())
            except:
                continue

            if data.get("type") == "event":
                if data.get("message") == "experiment_start":
                    start_time = datetime.fromisoformat(data["timestamp"])
                if data.get("message") == "experiment_end":
                    end_time = datetime.fromisoformat(data["timestamp"])

            if data.get("type") == "hyperparam":
                hyperparams[data["key"]] = data["value"]

            if data.get("type") == "metric":
                metrics.append(data)

    return hyperparams, metrics, start_time, end_time


# ----------------------------
# 로그 읽기
# ----------------------------
hyperparams, metrics, start_time, end_time = parse_log(log_path)


# ----------------------------
# Hyperparameter 표시
# ----------------------------
st.subheader("⚙️ Hyperparameters")

if hyperparams:
    st.json(hyperparams)
else:
    st.info("No hyperparameters found.")


# ----------------------------
# Metric 시각화
# ----------------------------
st.subheader("📈 Metrics")

if metrics:

    df = pd.DataFrame(metrics)

    # epoch 정렬
    if "epoch" in df.columns:
        df = df.sort_values("epoch")

    # Accuracy 그래프
    if "accuracy" in df.columns:
        st.markdown("### Accuracy (Epoch)")
        st.line_chart(df.set_index("epoch")["accuracy"])

    # Loss 그래프
    if "loss" in df.columns:
        st.markdown("### Loss (Epoch)")
        st.line_chart(df.set_index("epoch")["loss"])

    # 시간 기반 그래프
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["elapsed_sec"] = (df["timestamp"] - df["timestamp"].iloc[0]).dt.total_seconds()

        st.markdown("### Accuracy (Time)")
        st.line_chart(df.set_index("elapsed_sec")["accuracy"])

    # Best Accuracy
    if "accuracy" in df.columns:
        best_acc = df["accuracy"].max()
        best_epoch = df.loc[df["accuracy"].idxmax()]["epoch"]

        st.success(f"🏆 Best Accuracy: {best_acc:.4f} (Epoch {int(best_epoch)})")

else:
    st.warning("No metric data found.")


# ----------------------------
# 학습 시간 계산
# ----------------------------
st.subheader("⏱ Training Time")

if start_time and end_time:
    duration = (end_time - start_time).total_seconds()
    st.write(f"Total Training Time: {duration:.2f} seconds")
else:
    st.info("Training time information not available.")